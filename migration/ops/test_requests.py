#!/usr/bin/env python3
"""Offline durable-claim regression: no POST before persistence and no automatic ambiguous replay."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Requests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.repo = self.tmp / "checkout"
        self.repo.mkdir()
        self.pending = self.repo / "migration/requests"
        self.pending.mkdir(parents=True)
        self.origin = self.tmp / "origin.git"
        self.run_count = 0
        self.checkout_count = 0
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main", str(self.origin)], check=True)
        self.git("init", "-q", "--initial-branch=main")
        self.configure()
        self.git("remote", "add", "origin", str(self.origin))
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text("""#!/usr/bin/env python3
import hashlib, json, os, signal, subprocess, sys
origin = os.environ['OFFLINE_ORIGIN']
def remote(*args):
    return subprocess.run(['git', '--git-dir', origin, *args], capture_output=True, text=True, check=True).stdout
workflow = sys.argv[3]
claims = []
for name in remote('ls-tree', '-r', '--name-only', 'main').splitlines():
    if name.startswith('migration/requests/inflight/') and name.endswith('.json'):
        record = json.loads(remote('show', 'main:' + name))
        meta = record.get('_dispatch', {})
        if record.get('workflow') == workflow and meta.get('dispatcher_run_id') == os.environ['GITHUB_RUN_ID']:
            original = subprocess.run(['git', '--git-dir', origin, 'show',
                meta['base_commit'] + ':' + meta['original_path']], capture_output=True, check=True).stdout
            assert hashlib.sha256(original).hexdigest() == meta['request_sha256'], 'CLAIM_HASH_MISMATCH'
            assert {k: v for k, v in record.items() if k != '_dispatch'} == json.loads(original), 'CLAIM_INPUT_CHANGED'
            assert meta['state'] == 'claimed', 'CLAIM_NOT_INFLIGHT'
            assert meta['original_path'] not in remote('ls-tree', '-r', '--name-only', 'main').splitlines(), 'PENDING_REMAINED'
            claims.append(name)
assert len(claims) == 1, 'NO_UNIQUE_DURABLE_CLAIM_BEFORE_POST'
with open(os.environ['DISPATCH_LOG'], 'a') as stream:
    stream.write(json.dumps({'args': sys.argv[1:], 'claim': claims[0], 'durable_before_post': True}) + '\\n')
# A server accepted the request, but the client received no acknowledgement.
if workflow == 'fail.yml':
    sys.exit(42)
# Simulate the dispatcher process dying after the accepted POST, before any acknowledgement is persisted.
if workflow == 'crash.yml':
    os.kill(os.getppid(), signal.SIGKILL)
    sys.exit(42)
sys.exit(0)
""")
        gh.chmod(0o755)
        # The only remote is a local bare repository; gh is a stub, never a provider call.
        self.env = {"PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "DISPATCH_LOG": str(self.tmp / "dispatch.jsonl"), "OFFLINE_ORIGIN": str(self.origin),
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

    def configure(self):
        self.git("config", "user.name", "Offline test")
        self.git("config", "user.email", "offline@example.invalid")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, check=True)

    def remote(self, *args):
        return subprocess.run(["git", "--git-dir", str(self.origin), *args],
                              capture_output=True, text=True, check=True).stdout

    def remote_files(self):
        return self.remote("ls-tree", "-r", "--name-only", "main").splitlines()

    def records(self, state):
        return {name: json.loads(self.remote("show", "main:" + name)) for name in self.remote_files()
                if name.startswith(f"migration/requests/{state}/") and name.endswith(".json")}

    def calls(self):
        path = self.tmp / "dispatch.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def request(self, name, workflow, **inputs):
        self.pending.mkdir(parents=True, exist_ok=True)
        (self.pending / name).write_text(json.dumps({"workflow": workflow, "inputs": inputs}))

    def publish_requests(self):
        self.git("add", "migration/requests")
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=self.repo, capture_output=True)
        if staged.returncode:
            self.git("commit", "-qm", "Pending requests")
        self.git("push", "-q", "-u", "origin", "main")
        return self.git("rev-parse", "HEAD").stdout.strip()

    def run_workflow(self, prepare=True):
        if prepare:
            self.publish_requests()
        self.run_count += 1
        workflow = (ROOT / ".github/workflows/requests.yml").read_text()
        script = textwrap.dedent(workflow.split("        run: |\n", 1)[1])
        env = dict(self.env, GITHUB_RUN_ID=str(123456 + self.run_count), GITHUB_RUN_ATTEMPT="1")
        return subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
                              cwd=self.repo, env=env, capture_output=True, text=True, timeout=30)

    def fresh_checkout(self, commit=None):
        self.checkout_count += 1
        self.repo = self.tmp / f"checkout-{self.checkout_count}"
        subprocess.run(["git", "clone", "-q", "--branch", "main", str(self.origin), str(self.repo)], check=True)
        self.pending = self.repo / "migration/requests"
        self.configure()
        if commit:
            self.git("checkout", "-q", "--detach", commit)

    def reject_commit_prefix(self, prefix):
        hook = self.origin / "hooks/pre-receive"
        hook.write_text("""#!/usr/bin/env python3
import subprocess, sys
for line in sys.stdin:
    old, new, ref = line.split()
    message = subprocess.run(['git', 'log', '-1', '--format=%%s', new], capture_output=True, text=True, check=True).stdout
    if message.startswith(%r):
        sys.exit(1)
""" % prefix)
        hook.chmod(0o755)
        return hook

    def test_e165_claim_precedes_post_and_ambiguous_dispatch_never_replays_on_a_later_push(self):
        # Both orders: a response failure cannot discard another request's independent acknowledgement.
        for good_name, bad_name in (("a-good.json", "z-bad.json"), ("z-good.json", "a-bad.json")):
            self.request(good_name, "good.yml", plan="one plan")
            self.request(bad_name, "fail.yml", plan="uncertain plan")
            original = (self.pending / bad_name).read_bytes()
            result = self.run_workflow()
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((self.pending / bad_name).exists())
            self.assertFalse((self.pending / good_name).exists())
            uncertain = [r for r in self.records("inflight").values()
                         if r["_dispatch"]["original_path"].endswith("/" + bad_name)]
            self.assertEqual(len(uncertain), 1)
            self.assertEqual(uncertain[0]["_dispatch"]["request_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(uncertain[0]["_dispatch"]["state"], "claimed")
            done = [r for r in self.records("done").values()
                    if r["_dispatch"]["original_path"].endswith("/" + good_name)]
            self.assertEqual(len(done), 1)
            self.assertEqual(done[0]["_dispatch"]["state"], "acknowledged")
        self.assertEqual(sum(c["args"][2] == "fail.yml" for c in self.calls()), 2)
        self.fresh_checkout()
        self.request("later.json", "good.yml")
        result = self.run_workflow()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sum(c["args"][2] == "fail.yml" for c in self.calls()), 2)
        self.assertTrue(all(c["durable_before_post"] for c in self.calls()))

    def test_invalid_or_previously_claimed_input_is_not_dispatched(self):
        self.request("good.json", "good.yml")
        self.request("invalid.json", "requests.yml")
        self.request("claimed.json", "fail.yml")
        claimed = self.pending / "claimed.json"
        record = json.loads(claimed.read_text())
        record["_dispatch"] = {"state": "claimed"}
        claimed.write_text(json.dumps(record))
        result = self.run_workflow()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.pending / "invalid.json").exists())
        self.assertTrue(claimed.exists())
        self.assertEqual([c["args"][2] for c in self.calls()], ["good.yml"])
        self.assertEqual(len(self.records("done")), 1)
        self.assertEqual(self.records("inflight"), {})

    def test_failed_claim_persistence_prevents_any_post(self):
        self.request("one.json", "good.yml")
        self.publish_requests()
        self.reject_commit_prefix("Claim workflow request ")
        result = self.run_workflow(prepare=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REQUEST_CLAIM_NOT_CONFIRMED", result.stdout)
        self.assertEqual(self.calls(), [])
        self.assertIn("migration/requests/one.json", self.remote_files())
        self.assertEqual(self.records("inflight"), {})
        self.assertEqual(self.records("done"), {})

    def test_failed_ack_push_keeps_remote_claim_and_does_not_replay_in_a_new_checkout(self):
        self.request("one.json", "good.yml")
        self.publish_requests()
        hook = self.reject_commit_prefix("Acknowledge workflow request ")
        result = self.run_workflow(prepare=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REQUEST_ACK_NOT_CONFIRMED", result.stdout)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len(self.records("inflight")), 1)
        self.assertEqual(self.records("done"), {})
        hook.unlink()
        self.fresh_checkout()
        self.request("independent.json", "good.yml")
        result = self.run_workflow()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(len(self.records("inflight")), 1)
        self.assertEqual(len(self.records("done")), 1)

    def test_crash_after_post_keeps_remote_claim_and_does_not_replay(self):
        self.request("crash.json", "crash.yml")
        first = self.run_workflow()
        self.assertNotEqual(first.returncode, 0)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len(self.records("inflight")), 1)
        self.assertEqual(self.records("done"), {})
        self.fresh_checkout()
        self.request("independent.json", "good.yml")
        second = self.run_workflow()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual([c["args"][2] for c in self.calls()], ["crash.yml", "good.yml"])

    def test_stale_queued_checkout_refreshes_main_before_discovery(self):
        self.request("one.json", "good.yml")
        old_event_commit = self.publish_requests()
        result = self.run_workflow(prepare=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.fresh_checkout(commit=old_event_commit)
        self.assertTrue((self.pending / "one.json").exists())  # the queued push snapshot is stale
        result = self.run_workflow(prepare=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse((self.pending / "one.json").exists())
        self.assertIn("ref: main", (ROOT / ".github/workflows/requests.yml").read_text())

    def test_symlink_request_is_not_followed_or_modified(self):
        outside = self.tmp / "outside-request.json"
        original = json.dumps({"workflow": "good.yml", "inputs": {}}).encode()
        outside.write_bytes(original)
        link = self.pending / "link.json"
        link.symlink_to(outside)
        result = self.run_workflow()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REQUEST_NOT_REGULAR", result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(outside.read_bytes(), original)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.records("inflight"), {})

    def test_shell_metacharacters_are_literal_and_claimed_inputs_are_unchanged(self):
        text = "value with spaces; $(touch escaped-dollar); " + chr(96) + "touch escaped-backtick" + chr(96) + " ' \"\nline two *"
        self.request("literal.json", "good.yml", plan=text)
        result = self.run_workflow()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("plan=" + text, self.calls()[0]["args"])
        self.assertFalse((self.repo / "escaped-dollar").exists())
        self.assertFalse((self.repo / "escaped-backtick").exists())
        done = next(iter(self.records("done").values()))
        self.assertEqual(done["inputs"]["plan"], text)
        self.assertEqual(done["_dispatch"]["state"], "acknowledged")


if __name__ == "__main__":
    unittest.main()
