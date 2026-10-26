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
