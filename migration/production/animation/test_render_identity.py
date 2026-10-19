import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_identity as ri  # noqa: E402

CRITERIA = HERE / "qa_criteria_animation_v1.json"
SAMPLE = {"script_sha256": "a" * 64, "scenes_sha256": "b" * 64, "voice_wav_sha256": "c" * 64, "music_sha256": "d" * 64,
          "srt_sha256": {"master.srt": "e" * 64, "short1.srt": "f" * 64}, "bundle_sha256": {"scene_base.py": "1" * 64},
          "blender_version": "4.3.2", "engine": "BLENDER_EEVEE_NEXT", "samples": 16, "fps": 24,
          "resolution": "1920x1080", "criteria_sha256": "2" * 64}


def changed(value):
    if isinstance(value, dict):
        out = dict(value)
        out[next(iter(out))] = "0" * 64
        return out
    if isinstance(value, int):
        return value + 1
    return value + "x"


class RenderId(unittest.TestCase):
    def test_canonical_sha256(self):
        expected = hashlib.sha256(json.dumps(SAMPLE, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(ri.render_id(SAMPLE), expected)
        self.assertEqual(ri.render_id(dict(reversed(list(SAMPLE.items())))), expected)

    def test_any_field_change_gives_a_new_id(self):
        base = ri.render_id(SAMPLE)
        seen = {base}
        for key in SAMPLE:
            fields = copy.deepcopy(SAMPLE)
            fields[key] = changed(fields[key])
            new = ri.render_id(fields)
            self.assertNotIn(new, seen, key)
            seen.add(new)
        fields = copy.deepcopy(SAMPLE)
        del fields["samples"]
        self.assertNotEqual(ri.render_id(fields), base)

    def test_sample_covers_every_criteria_field(self):
        self.assertEqual(sorted(ri.field_names(json.loads(CRITERIA.read_text()))), sorted(SAMPLE))


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.d = Path(self.tmp.name)
        for name in ("script.json", "scenes.json", "voice.wav", "music.flac", "master.srt", "short1.srt"):
            (d / name).write_text(name)
        (d / "bundle").mkdir()
        (d / "bundle" / "scene_base.py").write_text("a")
        (d / "bundle" / "story.json").write_text("{}")

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, **over):
        d = self.d
        pairs = {"script_sha256": d / "script.json", "scenes_sha256": d / "scenes.json", "voice_wav_sha256": d / "voice.wav",
                 "music_sha256": d / "music.flac", "bundle_sha256": d / "bundle", "blender_version": "4.3.2",
                 "engine": "BLENDER_EEVEE_NEXT", "samples": "16", "fps": "24", "resolution": "1920x1080"}
        pairs.update(over)
        out = [f"{k}={v}" for k, v in pairs.items() if v is not None]
        return out + [f"srt_sha256={d / 'master.srt'}", f"srt_sha256={d / 'short1.srt'}"]

    def test_fields_from_files_and_scalars(self):
        f = ri.build_fields(CRITERIA, self.args())
        self.assertEqual(f["criteria_sha256"], ri.sha256_file(CRITERIA))
        self.assertEqual(f["script_sha256"], hashlib.sha256(b"script.json").hexdigest())
        self.assertEqual(sorted(f["bundle_sha256"]), ["scene_base.py", "story.json"])
        self.assertEqual(sorted(f["srt_sha256"]), ["master.srt", "short1.srt"])
        self.assertEqual((f["samples"], f["fps"], f["blender_version"], f["resolution"]), (16, 24, "4.3.2", "1920x1080"))

    def test_bundle_file_change_changes_id(self):
        before = ri.render_id(ri.build_fields(CRITERIA, self.args()))
        (self.d / "bundle" / "story.json").write_text('{"x": 1}')
        self.assertNotEqual(ri.render_id(ri.build_fields(CRITERIA, self.args())), before)

    def test_scalar_change_changes_id(self):
        before = ri.render_id(ri.build_fields(CRITERIA, self.args()))
        self.assertNotEqual(ri.render_id(ri.build_fields(CRITERIA, self.args(samples="32"))), before)

    def test_missing_and_unknown_fields_exit_1(self):
        run = [sys.executable, "-I", "-B", str(HERE / "render_identity.py"), str(CRITERIA)]
        ok = subprocess.run(run + self.args(), capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        data = json.loads(ok.stdout)
        self.assertEqual(data["render_id"], ri.render_id(data["fields"]))
        missing = subprocess.run(run + self.args(engine=None), capture_output=True, text=True)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("MISSING_FIELD engine", missing.stdout)
        unknown = subprocess.run(run + self.args() + ["colour=red"], capture_output=True, text=True)
        self.assertEqual(unknown.returncode, 1)
        self.assertIn("UNKNOWN_FIELD colour", unknown.stdout)


if __name__ == "__main__":
    unittest.main()
