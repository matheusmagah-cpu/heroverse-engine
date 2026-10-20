#!/usr/bin/env python3
"""E31: production tests use frozen fixtures, not mutable live pilot inputs.

Static path analysis follows repository roots and aliases. Temporary fixture roots
are not repository roots. Constructing a live path is rejected conservatively,
including paths passed to helpers rather than only direct read_text calls.
"""
import ast
from pathlib import Path, PurePosixPath
import re
import unittest

HERE = Path(__file__).resolve().parent
ALLOWLIST = frozenset({"test_long_review.py", "test_script_check.py", "test_still_render.py"})
LIVE = re.compile(r"(?:^|/)pilot-(?:\d{3}|\*|\[|\{)")


def live_paths(source):
    tree = ast.parse(source)
    values = {"__file__": "@repo/test.py"}
    path_names = {"Path"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "pathlib":
            path_names.update(a.asname or a.name for a in node.names if a.name == "Path")

    def value(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.JoinedStr):
            return "".join(x.value if isinstance(x, ast.Constant) else (value(x.value) or "{dynamic}") for x in node.values)
        if isinstance(node, ast.Attribute) and node.attr == "parent":
            v = value(node.value)
            return v.rsplit("/", 1)[0] if v and "/" in v else v
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "parents":
            v = value(node.value.value)
            return "@repo" if v and v.startswith("@repo") else None
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
            left, right = value(node.left), value(node.right)
            if left is not None and right is not None:
                return left + ("/" if isinstance(node.op, ast.Div) else "") + right
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in path_names | {"str", "open", "load"} and node.args:
                parts = [value(x) for x in node.args] if node.func.id in path_names else [value(node.args[0])]
                if all(x is not None for x in parts):
                    return "/".join(parts)
            if isinstance(node.func, ast.Attribute):
                base = value(node.func.value)
                if node.func.attr in ("resolve", "absolute"):
                    return base
                if node.func.attr in ("joinpath", "glob", "rglob") and base is not None:
                    parts = [value(x) for x in node.args]
                    if all(x is not None for x in parts):
                        return "/".join([base] + parts)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "join":
                parts = [value(x) for x in node.args]
                if parts and all(x is not None for x in parts):
                    return "/".join(parts)
        return None

    # Resolve aliases without depending on source assignment order.
    for _ in range(len(list(ast.walk(tree)))):
        old = dict(values)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                v = value(node.value)
                if v is not None:
                    for target in targets:
                        if isinstance(target, ast.Name):
                            values[target.id] = v
        if values == old:
            break
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.BinOp, ast.Call)):
            continue
        v = value(node)
        v = str(PurePosixPath(v.replace("\\", "/"))) if v else v
        if v and LIVE.search(v):
            # Absolute/repository paths and bare relative live paths are unsafe;
            # known temporary paths never resolve to @repo or these prefixes.
            if v.startswith(("@repo", "migration/production/", "pilot-")) or "/migration/production/pilot-" in v:
                found.add((getattr(node, "lineno", 0), v))
    return sorted(found)


class NoLivePilotData(unittest.TestCase):
    def test_no_live_pilot_data(self):
        violations = []
        for p in sorted(HERE.rglob("test_*.py")):
            if p.parent == HERE and p.name in ALLOWLIST:
                continue
            violations.extend((str(p.relative_to(HERE)), line, path)
                              for line, path in live_paths(p.read_text()))
        self.assertEqual(violations, [], "Use frozen fixtures instead of live pilot directories")

    def test_exact_legacy_allowlist(self):
        self.assertEqual(ALLOWLIST, {"test_long_review.py", "test_script_check.py", "test_still_render.py"})
        self.assertNotIn("test_shorts_produce.py", ALLOWLIST)

    def test_detects_live_reads_and_aliases(self):
        cases = [
            'HERE = Path(__file__).resolve().parent\nx = (HERE / "pilot-006/script.json").read_text()',
            'HERE = Path(__file__).parent\nPILOT = HERE / "pilot-006"\nload(PILOT / "out/timeline.json")',
            'ROOT = Path(__file__).resolve().parents[2]\np = ROOT.joinpath("migration", "production", "pilot-007")\nopen(p / "script.json")',
            'open(Path("migration/production/pilot-006/script.json"))',
            'open(Path("pilot-006/script.json"))',
            'from pathlib import Path as P\nHERE = P(__file__).parent\nP(HERE, "pilot-006", "script.json").read_text()',
            'HERE = Path(__file__).parent\nopen(f"{HERE}/pilot-006/script.json")',
            'open("migration/production/pilot-006/script.json").read()',
            'HERE = Path(__file__).parent\nx = Path(HERE, "pilot-006", "script.json").read_text()',
            'Path("./migration/production/pilot-006/script.json").read_text()',
            'HERE = Path(__file__).parent\nfor p in HERE.glob("pilot-*"): load(p)',
            'HERE = Path(__file__).parent\np = HERE / f"pilot-{number:03d}"\nload(p)',
            'HERE = Path(__file__).parent\np = os.path.join(HERE, "pilot-006", "script.json")\nopen(p)',
        ]
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(live_paths(source))

    def test_frozen_and_temporary_inputs_are_allowed(self):
        for source in [
            'HERE = Path(__file__).parent\nPILOT = HERE / "fixtures" / "shorts-pilot-006"\nload(PILOT / "script.json")',
            'with TemporaryDirectory() as temp:\n p = Path(temp) / "pilot-006"\n load(p / "script.json")',
            'expected = "pilot-006"\nself.assertEqual(result, expected)',
            'Path("/tmp/fixtures/pilot-006/script.json").read_text()',
            '# HERE / "pilot-006" is a comment, not a read\nx = 1',
        ]:
            with self.subTest(source=source):
                self.assertEqual(live_paths(source), [])


if __name__ == "__main__":
    unittest.main()
