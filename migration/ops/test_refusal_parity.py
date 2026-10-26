#!/usr/bin/env python3
"""Refusal parity (owner, 2026-10-26: "analyze deeply and meticulously so we never have this rework again"; E106).

Rework is a check that passes at a cheap early stage (a plan, a script, a dispatch) and a refusal at an expensive
later one (Pavo generations, an hour-long build, a render, a review, an upload) whose cause could have been known
earlier. Every refusal code the later stages can raise is listed in ops/refusal_registry.json with its class:

  A  predicted before the expensive work by the same function or constant the later stage uses (`early`: where)
  B  predictable early but checked only later: a rework hole (`early`: the cheap check that would catch it, `open`:
     why it is not closed yet). The goal is none.
  C  knowable only after a generation, a voice or a render (`probe`: the cheapest earlier probe that measures it)
  D  external or transient (outage, quota, credential, a state not reached yet) (`resume`: the wait or resume path
     that needs no new work)
  I  an engine invariant that no plan or input can break (`guard`: the test or workflow step that keeps it)
  N  not a refusal (an environment variable, a log line, a state word) (`why`)

This test parses the codes in the later stages (LATER) and fails when a code is in no class, when an entry lacks the
field its class needs, when an `early` / `guard` names a file that does not hold its needle, or when the registry
keeps a code no later stage raises any more. So a new build-time refusal cannot be added without saying how the
early stage predicts it, or why it cannot.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "migration" / "ops" / "refusal_registry.json"
# the later, expensive stages (the early ones are plan_check.py, script_check.py, long_plan_check.py and preflight)
LATER = [
    "migration/production/bible/episode_build.py", "migration/production/bible/short_engine.py",
    "migration/production/bible/lipsync_check.py", "migration/production/bible/clip_check.py",
    "migration/production/render_queue.py", "migration/production/qa_pilot.py", "migration/production/still_render.py",
    "migration/production/preview_gate.py", "migration/production/pilot_render.py", "migration/production/long_review.py",
    "migration/production/footage/assign.py", "migration/production/imagegen/cf_images.py",
    "migration/production/characters/characters.py",
    "migration/publish/prepublish_gate.py", "migration/publish/publication_binding.py",
    "migration/publish/tiktok_publish.py", "migration/publish/arc_links.py", "migration/publish/publish_episode.py",
    "migration/publish/publish_video.py", "migration/publish/captions.py",
    "migration/integrations/pavo/client.py", "migration/integrations/pavo/video.py",
    "migration/integrations/pavo/images.py", "migration/integrations/pavo/audio.py",
    ".github/workflows/episode.yml", ".github/workflows/cf-images.yml", ".github/workflows/publish-episode.yml",
    ".github/workflows/pavo-footage.yml", ".github/workflows/footage.yml", ".github/workflows/approve.yml",
    ".github/workflows/publish.yml", ".github/workflows/shorts.yml", ".github/workflows/publish-shorts.yml",
    ".github/workflows/tiktok.yml", ".github/workflows/agnes-clip.yml",
]
# any later build added beside the Short's (a long build, a new engine) is scanned without being listed
LATER_GLOBS = ["migration/production/bible/*_build.py", "migration/production/bible/*_engine.py"]
CODE = r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+"
QUOTED = re.compile(r"""(?:\bf|\b)?["'](%s)\b""" % CODE)
ECHOED = re.compile(r"""\becho\s+(%s)\b""" % CODE)
CLASSES = {"A": "early", "B": "early", "C": "probe", "D": "resume", "I": "guard", "N": "why"}


def later_files():
    files = [ROOT / f for f in LATER]
    for pattern in LATER_GLOBS:
        files += [p for p in sorted(ROOT.glob(pattern)) if p not in files and not p.name.startswith("test_")]
    return files


def codes_in(path):
    """Refusal-shaped codes in a later stage: string literals that start with an UPPER_SNAKE word, and bare
    `echo CODE` in workflow steps."""
    text = Path(path).read_text()
    found = set(QUOTED.findall(text))
    if path.suffix == ".yml":
        found |= set(ECHOED.findall(text))
    return found


def inventory():
    out = {}
    for path in later_files():
        for code in codes_in(path):
            out.setdefault(code, []).append(str(path.relative_to(ROOT)))
    return out


def registry():
    return json.loads(REGISTRY.read_text())["codes"]


REVIEW_CLASSES = ("plan", "preflight", "build_gate", "render_qa", "open", "review_only")


def review():
    return json.loads(REGISTRY.read_text())["review"]


def rubric_items():
    """The items of ops/CLAUDE_REVIEW.md's rubric (the line after '## Rubric'), plus overall."""
    text = (ROOT / "migration" / "ops" / "CLAUDE_REVIEW.md").read_text()
    body = text.split("## Rubric", 1)[1].split("\n", 1)[1].strip()
    line = body.split(";")[0]
    return [x.strip() for x in line.split(",") if x.strip()] + ["overall"]


def built_items():
    """The numbered items of PROMPT_GUIDE.md's "Built for 9.5" section (the Bible Short's own standard)."""
    text = (ROOT / "migration" / "production" / "bible" / "PROMPT_GUIDE.md").read_text()
    section = text.split("## Built for 9.5", 1)[1].split("\n## ", 1)[0]
    return [m for m in re.findall(r"^(\d+)\. ", section, re.M)]


def story_v3_rows():
    """Every row of the acted long's frozen QA: section.key for technical, speech, rights and grammar."""
    qa = json.loads((ROOT / "migration" / "production" / "qa_criteria_story_v3.json").read_text())
    return sorted(f"{s}.{k}" for s in ("technical", "speech", "rights", "grammar") for k in qa[s])


def needle_holds(ref):
    """`path::needle`: the file exists and holds the needle (the early check or guard is real, not a wish)."""
    if "::" not in ref:
        return False
    path, needle = ref.split("::", 1)
    target = ROOT / path
    return target.is_file() and needle in target.read_text()


class RefusalParity(unittest.TestCase):
    def test_every_later_refusal_is_classified(self):
        known = registry()
        missing = {c: w for c, w in inventory().items() if c not in known}
        self.assertEqual(missing, {}, "classify each new later-stage code in ops/refusal_registry.json (A/B/C/D/I/N): "
                                      "how the early stage predicts it, or why it cannot")

    def test_each_class_names_what_it_needs(self):
        for code, entry in registry().items():
            cls = entry.get("class")
            self.assertIn(cls, CLASSES, code)
            self.assertTrue(entry.get(CLASSES[cls]), f"{code}: class {cls} needs `{CLASSES[cls]}`")
            if cls == "B":
                self.assertTrue(entry.get("open"), f"{code}: a B hole states why it is still open")

    def test_early_checks_and_guards_exist(self):
        for code, entry in registry().items():
            for field in ("early", "guard"):
                if entry.get("class") in ("A", "I") and field == CLASSES[entry["class"]]:
                    refs = entry[field] if isinstance(entry[field], list) else [entry[field]]
                    for ref in refs:
                        self.assertTrue(needle_holds(ref), f"{code}: {field} {ref!r} is not in that file")

    def test_the_registry_holds_no_code_that_is_gone(self):
        found = inventory()
        self.assertEqual(sorted(c for c in registry() if c not in found), [])

    # ---- the review (owner, 2026-10-26: "Production has to come out at 9.5 already; the review only confirms") ----
    def test_every_rubric_item_has_its_earlier_check_for_the_short_and_the_long(self):
        mapped = review()["rubric"]
        self.assertEqual(len(rubric_items()), 9)   # the eight scored items and overall: the parser reads them all
        for item in rubric_items():
            self.assertIn(item, mapped, f"rubric item {item} (ops/CLAUDE_REVIEW.md) has no mapping")
            for fmt in ("short", "long"):
                self.assertIn(fmt, mapped[item], f"rubric item {item}: no {fmt} mapping")
        self.assertEqual(sorted(set(mapped) - set(rubric_items())), [], "a mapped item the rubric no longer has")

    def test_every_built_for_9_5_item_and_story_v3_row_is_mapped(self):
        r = review()
        self.assertEqual(sorted(r["short_built_for_9_5"], key=int), built_items())
        self.assertEqual(sorted(r["story_qa_v3"]), story_v3_rows())

    def test_each_review_mapping_names_a_real_check_or_its_reason(self):
        r = review()
        entries = [(f"rubric {k}/{f}", e) for k, v in r["rubric"].items() for f, e in v.items()]
        entries += [(f"built {k}", e) for k, e in r["short_built_for_9_5"].items()]
        entries += [(f"v3 {k}", e) for k, e in r["story_qa_v3"].items()]
        for name, e in entries:
            self.assertIn(e["class"], REVIEW_CLASSES, name)
            if e["class"] in ("review_only", "open"):
                self.assertTrue(e.get("reason"), f"{name}: {e['class']} needs its reason")
            else:
                self.assertTrue(e["checks"], f"{name}: {e['class']} needs its checks")
            for ref in e["checks"]:
                self.assertTrue(needle_holds(ref), f"{name}: check {ref!r} is not in that file")

    def test_the_parser_sees_a_new_build_refusal(self):
        # the antidote of E106: a refusal added to a later stage is found here, so it cannot skip the registry
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "x.py")
            p.write_text('raise SystemExit(f"NEW_BUILD_REFUSAL {shot}")\nproblems.append("OTHER_ONE x")\n')
            self.assertEqual(codes_in(p), {"NEW_BUILD_REFUSAL", "OTHER_ONE"})
            y = Path(d, "x.yml")
            y.write_text('run: |\n  test -n "$X" || { echo X_MISSING; exit 1; }\n  echo "Y_REFUSED"\n')
            self.assertEqual(codes_in(y), {"X_MISSING", "Y_REFUSED"})


if __name__ == "__main__":
    unittest.main()
