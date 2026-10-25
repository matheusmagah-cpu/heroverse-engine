#!/usr/bin/env python3
"""Offline: the full render waits for a preview of the current script reviewed at the owner's floor."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preview_gate as pg  # noqa: E402
import render_queue as rq  # noqa: E402
from test_render_queue import NOW, pilot  # noqa: E402

rq.HOLD = Path(tempfile.gettempdir()) / "no-such-hold-file"
rq.RENDER_HOLD = Path(tempfile.gettempdir()) / "no-such-render-hold-file"


class Fixed(rq.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


def queue(root, mode, hours="48"):
    out = io.StringIO()
    with patch.object(rq, "datetime", Fixed), contextlib.redirect_stdout(out):
        rq.main(root, str(Path(root) / "ledger.json"), mode, hours)
    return out.getvalue().split()


def review(d, overall, sha=None):
    (d / "inspection" / "preview_review.json").write_text(json.dumps({"script_sha256": sha or pg.script_sha(d),
                                                                     "overall": overall}))


class Gate(unittest.TestCase):
    def test_render_queue_runs_isolated_like_the_heartbeat_and_runner(self):
        # E73: heartbeat.yml and the runner call "python3 -I -B render_queue.py"; -I leaves the script's directory off
        # sys.path, so a sibling import that worked in these tests broke every scheduled render and preview
        import subprocess
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "ledger.json").write_text("{}")
            for mode in ("preview", "preview-review", "render", "review", "reassign"):
                r = subprocess.run([sys.executable, "-I", "-B", str(Path(rq.__file__)), t, str(Path(t) / "ledger.json"), mode, "72"],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_cut_keeps_the_opening_a_scripture_and_every_clip(self):
        script = {"pilot_id": "pilot-008", "footage": ["a", "b", "c"],
                  "segments": [{"id": "hook"}, {"id": "roadmap"}, {"id": "invitation"}, {"id": "prayer"},
                               {"id": "psalm", "reference": "Psalm 23:1"}, {"id": "close"}]}
        out = pg.cut(script)
        self.assertEqual([s["id"] for s in out["segments"]], ["hook", "roadmap", "invitation", "prayer", "psalm"])
        self.assertEqual(out["footage"], ["a", "b", "c"])  # the footage sheet shows every clip of the full video

    def test_full_render_waits_for_a_preview_at_the_floor(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "ledger.json").write_text("{}")
            pilot(t, "pilot-008", "2026-10-19T00:00:00Z", previewed=False)
            d = Path(t) / "pilot-008"
            self.assertEqual(queue(t, "render"), [])            # never rendered blind
            self.assertEqual(queue(t, "preview", "72"), ["pilot-008"])
            self.assertEqual(pg.main(["gate", str(d)]), 1)
            pg.main(["record", str(d), "run 1"])
            self.assertEqual(queue(t, "preview", "72"), [])     # one preview per script, not a loop
            self.assertEqual(queue(t, "preview-review"), ["pilot-008", pg.script_sha(d)])
            review(d, 9.2)                                      # 008 v2's footage would stop here (E71)
            self.assertEqual(queue(t, "render"), [])
            self.assertEqual(queue(t, "preview-review"), [])
            self.assertEqual(pg.main(["gate", str(d)]), 1)
            review(d, 9.5)
            self.assertEqual(queue(t, "render"), ["pilot-008"])
            self.assertEqual(pg.main(["gate", str(d)]), 0)

    def test_footage_rejected_in_the_library_stops_preview_and_render(self):
        # E78: pilot-009's preview showed 7 clips the library had REJECTED (a railed boardwalk, a concrete weir, a
        # village); pilot-014's did too. The queue never read the library, so stale footage reached a preview.
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "ledger.json").write_text("{}")
            lib = Path(t) / "footage" / "library"
            lib.mkdir(parents=True)
            (lib / "clip-ok.json").write_text(json.dumps({"vetting": "APPROVED"}))
            (lib / "clip-bad.json").write_text(json.dumps({"vetting": "REJECTED"}))
            pilot(t, "pilot-009", "2026-10-19T00:00:00Z", previewed=False)
            pilot(t, "pilot-014", "2026-10-19T10:00:00Z")      # preview already at 9.5
            for p in ("pilot-009", "pilot-014"):
                d = Path(t) / p
                s = json.loads((d / "script.json").read_text())
                (d / "script.json").write_text(json.dumps(dict(s, footage=["clip-ok", "clip-bad", "clip-gone"])))
            review(Path(t) / "pilot-014", 9.5)
            self.assertEqual(queue(t, "preview", "72"), [])
            self.assertEqual(queue(t, "render"), [])
            self.assertEqual(queue(t, "reassign"), ["pilot-009", "clip-bad,clip-gone", "pilot-014", "clip-bad,clip-gone"])
            for p in ("pilot-009", "pilot-014"):
                d = Path(t) / p
                s = json.loads((d / "script.json").read_text())
                (d / "script.json").write_text(json.dumps(dict(s, footage=["clip-ok"])))
            review(Path(t) / "pilot-014", 9.5)
            self.assertEqual(queue(t, "preview", "72"), ["pilot-009"])
            self.assertEqual(queue(t, "render"), ["pilot-014"])
            self.assertEqual(queue(t, "reassign"), [])

    def test_a_changed_script_needs_a_new_preview(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "ledger.json").write_text("{}")
            pilot(t, "pilot-008", "2026-10-19T00:00:00Z")
            d = Path(t) / "pilot-008"
            self.assertTrue(pg.approved(d))
            (d / "script.json").write_text((d / "script.json").read_text() + "\n")  # e.g. footage reassigned
            self.assertFalse(pg.approved(d))
            self.assertEqual(queue(t, "render"), [])
            self.assertEqual(queue(t, "preview", "72"), ["pilot-008"])


if __name__ == "__main__":
    unittest.main()
