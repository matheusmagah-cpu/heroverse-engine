#!/usr/bin/env python3
"""The hookify rules in .claude/ block what the owner forbids and nothing legitimate (owner, 2026-10-24):
APPROVAL.json by hand, the frozen QA v2/v3/v4 criteria, and fade/wipe between scenes of a vertical vidiq_compose.
The rules are evaluated here the way hookify does (every condition must match; a bare `pattern` is the command
for bash rules), so the test runs on every PR without the plugin installed."""
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
    if tool in ("Write", "Edit"):
        return {"new_text": inp.get("new_string", ""), "content": inp.get("content") or inp.get("new_string", ""),
                "file_path": inp.get("file_path", "")}.get(name)
    return None


def blocked(tool, inp):
    event = "bash" if tool == "Bash" else "file" if tool in ("Write", "Edit") else None
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
            ok = ok and v is not None and (re.search(c["pattern"], v) if c["operator"] == "regex_match"
                                           else v == c["pattern"] if c["operator"] == "equals" else False)
        if ok:
            return True
    return False


def compose(fmt, *kinds, overlay=None):
    scenes = [{"source": f"https://x/{i}.mp4", "duration": 4, "type": "video"} | ({"transitionIn": {"kind": k}} if k else {})
              for i, k in enumerate(kinds)]
    return {"format": fmt, "scenes": scenes} | ({"overlays": [overlay]} if overlay else {})


APPROVAL = "migration/production/pilot-011/" + "APPROVAL.json"
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
    ("mcp__vidIQ__vidiq_compose", compose("vertical", None, "fade")),
    ("mcp__vidIQ__vidiq_compose", compose("vertical", "wipe")),
]
ALLOW = [
    ("Edit", {"file_path": "migration/production/pilot-008/inspection/claude_review.json", "old_string": "a", "new_string": "b"}),
    ("Write", {"file_path": "migration/production/notes.md", "content": "APPROVAL.json is written by approve.yml"}),
    ("Bash", {"command": f"cat {APPROVAL} | python3 -m json.tool"}),
    ("Bash", {"command": f"git show HEAD:{APPROVAL}"}),
    ("Bash", {"command": f"git diff --stat > /tmp/d.txt; ls {APPROVAL}"}),
    ("Edit", {"file_path": "migration/production/qa_pilot.py", "old_string": "a", "new_string": "b"}),
    ("Edit", {"file_path": "migration/production/pilot-008/script.json", "old_string": "a", "new_string": "b"}),
    ("Bash", {"command": "cp migration/production/pilot-008/qa_criteria.json migration/production/pilot-015/"}),
    ("Bash", {"command": "sha256sum migration/production/qa_criteria_v3.json"}),
    ("mcp__vidIQ__vidiq_compose", compose("vertical", "cut", "dip_to_black", overlay={"kind": "text", "text": "fade"})),
    ("mcp__vidIQ__vidiq_compose", compose("landscape", "fade")),
]


class HookifyRules(unittest.TestCase):
    def test_the_three_owner_rules_exist_and_block(self):
        names = {parse(p)["name"] for p in RULES if parse(p).get("action") == "block"}
        for n in ("block-approval-json-by-hand", "block-approval-json-by-shell", "block-frozen-qa-criteria",
                  "block-frozen-qa-criteria-by-shell", "block-shorts-fade-wipe"):
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
                         ("migration/ops/link_session_guards.sh", "migration/ops/link_session_guards.sh")):
            self.assertTrue((ROOT / f).exists(), f)
            self.assertIn(named, md)

    def test_guards_link_into_a_parent_session_root(self):
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as root:
            subprocess.run(["bash", str(ROOT / "migration/ops/link_session_guards.sh"), root], check=True, capture_output=True)
            linked = {p.name for p in (Path(root) / ".claude").iterdir()}
            self.assertEqual({p.name for p in RULES} - linked, set())
            self.assertIn("settings.json", linked)


if __name__ == "__main__":
    unittest.main()
