#!/usr/bin/env python3
"""The hookify rules in .claude/ block what the owner forbids and nothing legitimate (owner, 2026-10-24):
APPROVAL.json by hand, the frozen QA v2/v3/v4 criteria, and fade/wipe between scenes of a vertical vidiq_compose.
The rules are evaluated here the way hookify does (every condition must match; a bare `pattern` is the command
for bash rules), so the test runs on every PR without the plugin installed. It also keeps the paid Runway connector and the vidIQ
write/generator tools denied in .claude/settings.json under both server names (connector and plugin)."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
RULES = sorted((ROOT / ".claude").glob("hookify.*.local.md"))


def parse(path):
    front = path.read_text().split("---", 2)[1]
    rule, conds = {}, []
    for line in front.splitlines():
        m = re.match(r"^(\s*)(- )?(\w+):\s*(.*)$", line)
        if not m:
            continue
        indent, item, key, value = m.groups()
        if not indent and not item:
            rule[key] = value
        elif item:
            conds.append({key: value})
        else:
            conds[-1][key] = value
    if not conds and rule.get("pattern"):
        field = {"bash": "command", "file": "new_text"}.get(rule["event"], "content")
        conds = [{"field": field, "operator": "regex_match", "pattern": rule["pattern"]}]
    rule["conditions"] = conds
    return rule


def field(tool, inp, name):
    if name in inp:
        return inp[name] if isinstance(inp[name], str) else str(inp[name])
    if tool == "Bash" and name == "command":
        return inp.get("command", "")
    if tool == "MultiEdit":
        joined = " ".join(e.get("new_string", "") for e in inp.get("edits", []))
        return {"new_text": joined, "content": joined, "file_path": inp.get("file_path", "")}.get(name)
    if tool in ("Write", "Edit"):
        return {"new_text": inp.get("new_string", ""), "content": inp.get("content") or inp.get("new_string", ""),
                "file_path": inp.get("file_path", "")}.get(name)
    return None


def blocked(tool, inp):
    event = "bash" if tool == "Bash" else "file" if tool in ("Write", "Edit", "MultiEdit") else None
    for rule in map(parse, RULES):
        if rule.get("enabled") != "true" or rule.get("action") != "block":
            continue
        if event and rule["event"] not in ("all", event):
            continue
        if rule.get("tool_matcher") and tool not in rule["tool_matcher"].split("|"):
            continue
        ok = bool(rule["conditions"])
        for c in rule["conditions"]:
            v = field(tool, inp, c["field"])
            ok = ok and v is not None and (re.search(c["pattern"], v, re.I) if c["operator"] == "regex_match"
                                           else v == c["pattern"] if c["operator"] == "equals" else False)
        if ok:
            return True
    return False


def compose(fmt, *kinds, overlay=None):
    scenes = [{"source": f"https://x/{i}.mp4", "duration": 4, "type": "video"} | ({"transitionIn": {"kind": k}} if k else {})
              for i, k in enumerate(kinds)]
    return {"format": fmt, "scenes": scenes} | ({"overlays": [overlay]} if overlay else {})


APPROVAL = "migration/production/pilot-011/" + "APPROVAL.json"
EB = "migration/production/bible/episode_build.py"
G7, G8 = "migration/production/bible/plans/genesis-07-short.json", "migration/production/bible/plans/genesis-08-short.json"
BLOCK = [
    ("Write", {"file_path": "/home/user/heroverse-engine/" + APPROVAL, "content": "{}"}),
    ("Edit", {"file_path": APPROVAL, "old_string": "a", "new_string": "b"}),
    ("Bash", {"command": f"echo '{{}}' > {APPROVAL}"}),
    ("Bash", {"command": f"sed -i 's/FAIL/PASS/' {APPROVAL}"}),
    ("Bash", {"command": f"python3 -c \"open('{APPROVAL}','w').write('x')\""}),
    ("Edit", {"file_path": "migration/production/qa_criteria_v3.json", "old_string": "a", "new_string": "b"}),
    ("Write", {"file_path": "migration/production/qa_criteria_v4.json", "content": "{}"}),
    ("Edit", {"file_path": "migration/production/pilot-008/qa_criteria.json", "old_string": "a", "new_string": "b"}),
    ("Bash", {"command": "sed -i 's/0.95/0.80/' migration/production/qa_criteria_v4.json"}),
    ("Bash", {"command": "echo x >> migration/production/pilot-013/qa_criteria.json"}),
    ("MultiEdit", {"file_path": APPROVAL, "edits": [{"old_string": "a", "new_string": "b"}]}),
    ("MultiEdit", {"file_path": "migration/production/qa_criteria_v4.json", "edits": [{"old_string": "a", "new_string": "b"}]}),
    ("Bash", {"command": f"cp /tmp/x.json {APPROVAL}"}),
    ("Bash", {"command": f"install -m 644 /tmp/x.json {APPROVAL} && ls"}),
    ("Bash", {"command": f"git checkout other-branch -- {APPROVAL}"}),
    ("Bash", {"command": "cp /tmp/loose.json migration/production/qa_criteria_v4.json"}),
    ("Bash", {"command": "git restore --source=HEAD~3 migration/production/qa_criteria_v3.json"}),
    ("Edit", {"file_path": "migration/production/qa_criteria_story_v1.json", "old_string": "a", "new_string": "b"}),
    ("Bash", {"command": "sed -i 's/0.4/0.2/' migration/production/qa_criteria_story_v1.json"}),
    ("mcp__vidIQ__vidiq_compose", compose("vertical", None, "fade")),
    ("mcp__vidIQ__vidiq_compose", compose("vertical", "wipe")),
    # E106: no episode build without a PASS preflight of that plan, chained in the same command
    ("Bash", {"command": "gh workflow run episode.yml -f plan=migration/production/bible/plans/genesis-08-short.json"}),
    ("Bash", {"command": "gh workflow run .github/workflows/episode.yml --ref main -f plan=x -f resume_run=123456"}),
    ("Bash", {"command": "gh api repos/o/r/actions/workflows/episode.yml/dispatches -f ref=main -f inputs[plan]=x"}),
    ("Bash", {"command": "python3 migration/production/bible/plan_check.py p.json --strict && gh workflow run episode -f plan=p"}),
    ("mcp__github__actions_run_trigger", {"method": "run_workflow", "owner": "o", "repo": "r", "workflow_id": "episode.yml",
                                          "ref": "main", "inputs": {"plan": "x"}}),
    # review of #422: only `verify-preflight P && gh workflow run episode.yml -f plan=P`, the same P, nothing else
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7}; gh workflow run episode.yml -f plan={G7}"}),
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7} || gh workflow run episode.yml -f plan={G7}"}),
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7} && gh workflow run episode.yml -f plan={G8}"}),
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7} && gh workflow run episode.yml -f plan={G7}; "
                         f"gh workflow run episode.yml -f plan={G8}"}),
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7} && gh workflow run episode.yml -f plan={G7}x"}),
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7} && "
                         "gh api repos/o/r/actions/workflows/episode.yml/dispatches -f ref=main"}),
    # regenerate only together with resume_run, after it, on the same allowed form
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7} && gh workflow run episode.yml --ref main "
                         f"-f plan={G7} -f regenerate=s-well"}),
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7} && gh workflow run episode.yml --ref main "
                         f"-f plan={G7} -f resume_run=1 -f regenerate=s-well; gh workflow run episode.yml -f plan={G8}"}),
    # E96/E106: cf-images takes pilot-NNN or characters, never a path
    ("Bash", {"command": "gh workflow run cf-images.yml -f pilot=migration/production/characters -f engine=flux"}),
    ("Bash", {"command": "gh workflow run cf-images.yml -f engine=flux -f pilot='production/pilot-015'"}),
    ("mcp__github__actions_run_trigger", {"method": "run_workflow", "owner": "o", "repo": "r", "workflow_id": "cf-images.yml",
                                          "ref": "main", "inputs": {"pilot": "migration/production/characters"}}),
    # Studio MCP (2026-10-27): the session cookies never pass through the shell
    ("Bash", {"command": "echo $YT_STUDIO_COOKIES"}),
    ("Bash", {"command": "printenv YT_STUDIO_COOKIES | head -c 20"}),
    ("Bash", {"command": "python3 -c \"import os; print(os.environ['YT_STUDIO_COOKIES'])\""}),
    ("Bash", {"command": "echo \"${YT_STUDIO_COOKIES:0:10}\""}),
    ("Bash", {"command": "env"}),
    ("Bash", {"command": "env | grep -i cookie"}),
    ("Bash", {"command": "cd /tmp && printenv > /tmp/e.txt"}),
    ("Bash", {"command": "cat /proc/self/environ"}),
]
ALLOW = [
    ("Bash", {"command": "YT_STUDIO_COOKIES= python3 -B migration/integrations/studio/test_stdio.py"}),
    ("Bash", {"command": "printenv PATH"}),
    ("Bash", {"command": "env -u FOO python3 x.py"}),
    ("Bash", {"command": "python3 -I -B migration/integrations/studio/test_client.py"}),
    ("Write", {"file_path": "migration/integrations/studio/README.md", "content": "set YT_STUDIO_COOKIES in settings"}),
    ("Edit", {"file_path": "migration/production/pilot-008/inspection/claude_review.json", "old_string": "a", "new_string": "b"}),
    ("Write", {"file_path": "migration/production/notes.md", "content": "APPROVAL.json is written by approve.yml"}),
    ("Bash", {"command": f"cat {APPROVAL} | python3 -m json.tool"}),
    ("Bash", {"command": f"git show HEAD:{APPROVAL}"}),
    ("Bash", {"command": f"git diff --stat > /tmp/d.txt; ls {APPROVAL}"}),
    ("Edit", {"file_path": "migration/production/qa_pilot.py", "old_string": "a", "new_string": "b"}),
    ("Edit", {"file_path": "migration/production/pilot-008/script.json", "old_string": "a", "new_string": "b"}),
    ("Bash", {"command": "cp migration/production/pilot-008/qa_criteria.json migration/production/pilot-015/"}),
    ("Bash", {"command": "sha256sum migration/production/qa_criteria_v3.json"}),
    ("Bash", {"command": f"cp {APPROVAL} /tmp/approval-copy.json"}),
    ("Bash", {"command": f"python3 x.py > /tmp/out.txt\ncat {APPROVAL}"}),
    ("Bash", {"command": "sed -i 's/a/b/' notes.md\nsha256sum migration/production/qa_criteria_v4.json"}),
    ("Bash", {"command": "cp migration/production/qa_criteria_v4.json /tmp/v4.json"}),
    ("Bash", {"command": "sha256sum migration/production/qa_criteria_story_v1.json"}),
    ("mcp__vidIQ__vidiq_compose", compose("vertical", "cut", "dip_to_black", overlay={"kind": "text", "text": "fade"})),
    ("mcp__vidIQ__vidiq_compose", compose("landscape", "fade")),
    ("Bash", {"command": "python3 -I -B migration/production/bible/episode_build.py verify-preflight "
                         "migration/production/bible/plans/genesis-08-short.json && gh workflow run episode.yml "
                         "-f plan=migration/production/bible/plans/genesis-08-short.json"}),
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7} && gh workflow run episode.yml --ref main "
                         f"-f plan={G7} -f resume_run=40297987571"}),
    ("Bash", {"command": f"python3 -I -B {EB} verify-preflight {G7} && gh workflow run episode.yml --ref main "
                         f"-f plan={G7} -f resume_run=40357197063 -f regenerate=s-well,s-scroll"}),
    ("Bash", {"command": f"python3 {EB} verify-preflight '{G7}' && gh workflow run episode.yml -f 'plan={G7}'"}),
    ("Bash", {"command": 'gh workflow run cf-images.yml -f pilot="characters" -f engine=flux'}),
    ("Bash", {"command": "gh workflow run cf-images.yml -f pilot='pilot-015' -f engine=sdxl"}),
    ("Bash", {"command": 'gh workflow run cf-images.yml -f "pilot=characters" -f engine=flux'}),
    ("Bash", {"command": "gh workflow run publish-episode.yml -f episode=genesis-07-short"}),
    ("Bash", {"command": "gh run list --workflow episode.yml --limit 3"}),
    ("Bash", {"command": "gh workflow run cf-images.yml -f pilot=characters -f engine=flux -f only=ch-noah-front"}),
    ("Bash", {"command": "gh workflow run cf-images.yml -f pilot=pilot-015 -f engine=sdxl"}),
    ("mcp__github__actions_run_trigger", {"method": "run_workflow", "owner": "o", "repo": "r", "workflow_id": "cf-images.yml",
                                          "ref": "main", "inputs": {"pilot": "characters", "engine": "flux"}}),
    ("mcp__github__actions_run_trigger", {"method": "run_workflow", "owner": "o", "repo": "r", "workflow_id": "heartbeat.yml",
                                          "ref": "main"}),
]


VIDIQ_DENIED = ("vidiq_update_video", "vidiq_update_video_thumbnail", "vidiq_video_upload", "vidiq_reply_to_comment",
                "vidiq_generate_comment_replies", "vidiq_comment_reply_permission", "vidiq_instagram_publish_reel",
                "vidiq_connect_youtube_channel", "vidiq_authorize_with_youtube", "vidiq_update_competitors",
                "vidiq_generate_video", "vidiq_generate_clips", "vidiq_generate_broll", "vidiq_generate_music",
                "vidiq_voiceover_generate", "vidiq_edit_media", "vidiq_motion_graphics", "vidiq_compose")


class HookifyRules(unittest.TestCase):
    def test_the_three_owner_rules_exist_and_block(self):
        names = {parse(p)["name"] for p in RULES if parse(p).get("action") == "block"}
        for n in ("block-approval-json-by-hand", "block-approval-json-by-shell", "block-frozen-qa-criteria",
                  "block-frozen-qa-criteria-by-shell", "block-shorts-fade-wipe", "require-episode-preflight",
                  "require-episode-preflight-mcp", "block-cf-images-bad-pilot", "block-cf-images-bad-pilot-mcp"):
            self.assertIn(n, names)

    def test_forbidden_actions_are_blocked(self):
        for tool, inp in BLOCK:
            self.assertTrue(blocked(tool, inp), (tool, inp))

    def test_legitimate_actions_pass(self):
        for tool, inp in ALLOW:
            self.assertFalse(blocked(tool, inp), (tool, inp))


class PluginSetup(unittest.TestCase):
    def test_project_files_named_in_claude_md_exist(self):
        md = (ROOT / "CLAUDE.md").read_text()
        for f, named in ((".claude/claude-security-guidance.md", ".claude/claude-security-guidance.md"),
                         ("docs/audits/categories.md", "docs/audits/"), ("docs/audits/sweep-registry.md", "docs/audits/"),
                         ("migration/production/bible/brand-profile.md", "migration/production/bible/brand-profile.md"),
                         ("migration/ops/link_session_guards.sh", "migration/ops/link_session_guards.sh"),
                         ("migration/strategy/VIDIQ.md", "migration/strategy/VIDIQ.md")):
            self.assertTrue((ROOT / f).exists(), f)
            self.assertIn(named, md)

    def test_guards_link_into_a_parent_session_root(self):
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as root:
            subprocess.run(["bash", str(ROOT / "migration/ops/link_session_guards.sh"), root], check=True, capture_output=True)
            linked = {p.name for p in (Path(root) / ".claude").iterdir()}
            self.assertEqual({p.name for p in RULES} - linked, set())
            self.assertNotIn("settings.json", linked)

    def test_paid_and_write_tools_stay_denied_under_every_server_name(self):
        import json
        perms = json.loads((ROOT / ".claude/settings.json").read_text())["permissions"]
        self.assertIn("mcp__Runway", perms["deny"])
        self.assertFalse([a for a in perms["allow"] if "Runway" in a])
        for tool in VIDIQ_DENIED:
            for server in ("mcp__vidIQ__", "mcp__plugin_vidiq_vidiq__"):
                self.assertIn(server + tool, perms["deny"])


if __name__ == "__main__":
    unittest.main()
