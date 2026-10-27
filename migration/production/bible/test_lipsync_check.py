#!/usr/bin/env python3
"""lipsync_check.py and syncnet.py: the sync gate (SyncNet, E120) calibrated on the labelled set of real speakers, the
still-mouth and face checks (no model needed for these cases)."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lipsync_check as lc
import syncnet as sn


class Measures(unittest.TestCase):
    def test_best_lag_finds_the_shift(self):
        a = np.sin(np.linspace(0, 20, 200)) + np.linspace(0, 1, 200)
        b = np.roll(a, 3)
        corr, lag = lc.best_lag(a, b, 6)
        self.assertGreater(corr, 0.95)
        self.assertEqual(lag, -3)

    def test_envelope_hops(self):
        self.assertEqual(len(lc.envelope(np.ones(16000, dtype=np.float32), 16000)), 25)


class Verdict(unittest.TestCase):
    GOOD_AUDIO = {"corr": 0.886, "lag_ms": 0}
    # the Pavo calibration clip (keeper-lipsync.mp4 with line-01.wav), measured 2026-10-27 with SyncNet
    GOOD_MOUTH = {"corr": 0.483, "lag_ms": 0, "speak_to_pause": 1.87, "face_frames": 0.89,
                  "sync": {"offset": -1, "conf": 8.43, "min_dist": 7.534, "windows": 177}}

    def test_calibration_clip_passes(self):
        self.assertEqual(lc.verdict(self.GOOD_AUDIO, self.GOOD_MOUTH), [])

    def test_the_same_clip_with_its_audio_400_ms_late_fails(self):
        # ffmpeg adelay=400 on the calibration clip (the episode.yml / shot-probe.yml self-check): offset -11
        flags = lc.verdict({"corr": 0.245, "lag_ms": 240},
                           dict(self.GOOD_MOUTH, sync={"offset": -11, "conf": 8.245, "min_dist": 7.81, "windows": 176}))
        self.assertEqual(flags, ["AUDIO_NOT_OUR_LINE", "AUDIO_OFFSET", "MOUTH_NOT_IN_SYNC"])

    def test_each_rule(self):
        self.assertIn("AUDIO_OFFSET", lc.verdict({"corr": 0.9, "lag_ms": 120}, self.GOOD_MOUTH))
        self.assertIn("FACE_NOT_FOUND", lc.verdict(self.GOOD_AUDIO, dict(self.GOOD_MOUTH, face_frames=0.5)))
        sync = self.GOOD_MOUTH["sync"]
        for bad in ({"offset": 3}, {"offset": -3}, {"conf": 2.69}):
            self.assertIn("MOUTH_NOT_IN_SYNC", lc.verdict(self.GOOD_AUDIO, dict(self.GOOD_MOUTH, sync=dict(sync, **bad))))
        for ok in ({"offset": 2}, {"offset": -2}, {"conf": 2.7}):
            self.assertEqual(lc.verdict(self.GOOD_AUDIO, dict(self.GOOD_MOUTH, sync=dict(sync, **ok))), [])
        # nothing measured (no face, too short) is never in sync
        self.assertIn("MOUTH_NOT_IN_SYNC", lc.verdict(self.GOOD_AUDIO, dict(self.GOOD_MOUTH, sync=None)))
        self.assertIn("MOUTH_NOT_IN_SYNC", lc.verdict(self.GOOD_AUDIO, {"face_frames": 1.0}))

    def test_the_lip_opening_correlation_no_longer_judges(self):
        # E119/E120: it could not separate real speech from shifted audio; reported, not a gate
        weak = dict(self.GOOD_MOUTH, corr=0.1, lag_ms=250, speak_to_pause=0.9)
        self.assertEqual(lc.verdict(self.GOOD_AUDIO, weak), [])

    def test_the_cli_takes_the_syncnet_weights_next_to_the_face_model(self):
        self.assertEqual(lc.syncnet_path("/tmp/x/face_landmarker.task"), Path("/tmp/x/syncnet_v2.model"))
        self.assertEqual(lc.syncnet_path("/tmp/x/face.task", "/w/s.model"), Path("/w/s.model"))
        with self.assertRaises(SystemExit) as e:
            lc.check("clip.mp4", "line.wav", "/nonexistent/face_landmarker.task")
        self.assertIn("SYNCNET_MODEL_MISSING", str(e.exception))


class GodShotFaces(unittest.TestCase):
    """God's voice-over shot shows no person: one face in any sampled frame flags the clip (calibration 2026-10-26:
    the Genesis 6 storm, sunbeams and tents clips 0 faces; the Keeper's clip 30/44)."""
    def test_any_face_flags_the_clip_and_an_empty_clip_is_not_a_pass(self):
        self.assertEqual(lc.face_verdict("storm.mp4", 40, 0, [])["flags"], [])
        r = lc.face_verdict("keeper.mp4", 44, 1, [12])
        self.assertEqual(r["flags"], ["GOD_SHOT_FACE"])
        self.assertEqual(r["face_frames"], [12])
        self.assertIn("NO_FRAMES", lc.face_verdict("empty.mp4", 0, 0, [])["flags"])

    def test_the_cli_has_a_faces_mode(self):
        text = Path(lc.__file__).read_text()
        self.assertIn('sys.argv[1] == "--faces"', text)
        self.assertGreaterEqual(lc.FACE_SAMPLE_EVERY, 1)


SERIES = Path(__file__).resolve().parents[2] / "evidence/pavo/20261026/keeper-vo/opening-series.json"
FPS = 24.0


def closed(seconds, level=0.002, noise=0.0004, seed=1):
    return level + np.random.default_rng(seed).normal(0, noise, int(seconds * FPS))


def talk(seconds, amplitude=0.11):
    return np.abs(np.sin(np.linspace(0, 1.5 * np.pi * seconds, int(seconds * FPS)))) * amplitude + 0.002


class StillMouth(unittest.TestCase):
    """Plan B (owner, 2026-10-26): a voice-over Keeper clip shows no talking mouth (MOUTH_TALKING: the fastest ~1 s of
    lip motion anywhere in the clip, or the old whole-clip rule) and a mouth confirmed closed after a settle window
    (MOUTH_NOT_CLOSED: the most open ~1 s after STILL_MOUTH_SETTLE_S). Calibrated on the 42 talking and 14 closed
    clips of 26/10, whose per-frame series are kept and replayed here."""

    def test_the_thresholds_sit_between_the_closed_and_the_talking_clips(self):
        # calibration.json: window motion talking >= 0.0091, closed <= 0.0043; open after the settle talking >= 0.0389,
        # closed <= 0.0046
        self.assertTrue(0.0043 * 1.3 < lc.STILL_MOUTH_WINDOW_MOTION_MAX < 0.0091 / 1.3)
        self.assertTrue(0.0046 * 2 < lc.STILL_MOUTH_CLOSED_MAX < 0.0389 / 2)
        self.assertEqual(lc.STILL_MOUTH_SETTLE_S, 2.5)          # clip 5 settles closed within ~2.5 s
        self.assertEqual(lc.STILL_MOUTH_WINDOW_S, 1.0)

    def test_every_recorded_talking_clip_is_flagged_every_closed_clip_with_a_face_passes(self):
        data = json.loads(SERIES.read_text())
        self.assertEqual((len(data["talking"]), len(data["closed"])), (42, 14))
        for name, s in data["talking"].items():
            o = np.array([np.nan if x is None else x for x in s["opening"]])
            self.assertIn("MOUTH_TALKING", lc.still_mouth_verdict(o, s["share"], s["fps"])["flags"], name)
        passed = []
        for name, s in data["closed"].items():
            o = np.array([np.nan if x is None else x for x in s["opening"]])
            r = lc.still_mouth_verdict(o, s["share"], s["fps"])
            self.assertNotIn("MOUTH_TALKING", r["flags"], name)
            if s["share"] >= lc.FACE_FRAMES_MIN:
                self.assertEqual(r["flags"], [], (name, r))
                passed.append(name)
        # clip 5 and the 6 build probes of genesis-07's own prompts (k-insight revised, k-question, k-close)
        self.assertEqual(len(passed), 7, passed)

    def test_a_talking_mouth_is_flagged_a_closed_one_passes(self):
        r = lc.still_mouth_verdict(closed(8), 0.95, FPS)
        self.assertEqual(r["flags"], [])
        self.assertLess(r["window_motion"], lc.STILL_MOUTH_WINDOW_MOTION_MAX)
        self.assertLess(r["closed_opening"], lc.STILL_MOUTH_CLOSED_MAX)
        self.assertEqual((r["face_frames"], r["frames"]), (0.95, 192))
        self.assertIn("MOUTH_TALKING", lc.still_mouth_verdict(talk(8), 0.95, FPS)["flags"])

    def test_two_and_a_half_seconds_of_talking_inside_twelve_is_not_averaged_away(self):
        o = np.concatenate([closed(5, noise=0.0002), talk(2.5), closed(4.5, noise=0.0002, seed=2)])
        r = lc.still_mouth_verdict(o, 1.0, FPS)
        self.assertLess(r["opening_motion"], lc.STILL_MOUTH_MOTION_MAX)   # the whole-clip mean would pass it
        self.assertIn("MOUTH_TALKING", r["flags"])

    def test_an_open_still_mouth_is_not_confirmed_closed(self):
        r = lc.still_mouth_verdict(closed(8, level=0.05), 1.0, FPS)
        self.assertNotIn("MOUTH_TALKING", r["flags"])
        self.assertEqual(r["flags"], ["MOUTH_NOT_CLOSED"])
        # open for 1.5 s at the end, after it had closed: refused too
        late = np.concatenate([closed(6), closed(1.5, level=0.05)])
        self.assertEqual(lc.still_mouth_verdict(late, 1.0, FPS)["flags"], ["MOUTH_NOT_CLOSED"])

    def test_the_mouth_may_settle_closed_within_the_settle_window_not_later(self):
        # clip 5 (conversation 373100393016087168): the talking reference's open mouth closes over ~2.5 s, then stays
        settle = np.concatenate([np.linspace(0.061, 0.002, int(2.4 * FPS)), closed(5.6)])
        self.assertEqual(lc.still_mouth_verdict(settle, 1.0, FPS)["flags"], [])
        slow = np.concatenate([np.linspace(0.061, 0.002, int(5 * FPS)), closed(3)])
        self.assertIn("MOUTH_NOT_CLOSED", lc.still_mouth_verdict(slow, 1.0, FPS)["flags"])

    def test_the_face_must_be_found_in_80_percent_of_frames_as_for_the_lips(self):
        self.assertEqual(lc.still_mouth_verdict(closed(5), 0.79, FPS)["flags"], ["FACE_NOT_FOUND"])
        self.assertEqual(lc.FACE_FRAMES_MIN, 0.8)
        empty = lc.still_mouth_verdict(np.array([np.nan] * 100), 0.0, FPS)
        self.assertIn("FACE_NOT_FOUND", empty["flags"])
        self.assertIn("MOUTH_NOT_CLOSED", empty["flags"])     # nothing measured is never a confirmed closed mouth
        self.assertIn("MOUTH_UNMEASURED", empty["flags"])
        self.assertIsNone(empty["opening_range"])
        self.assertIn("NO_FRAMES", lc.still_mouth_verdict(np.array([]), 0.0, FPS)["flags"])

    def test_frames_without_a_face_are_left_out_not_counted_as_closed(self):
        o = talk(8)
        o[40:80] = np.nan                                            # the face lost for a while: still talking
        r = lc.still_mouth_verdict(o, 0.8, FPS)
        self.assertIn("MOUTH_TALKING", r["flags"])
        self.assertEqual(r["frames"], 192)

    def test_the_cli_has_a_still_mouth_mode(self):
        self.assertIn('sys.argv[1] == "--still-mouth"', Path(lc.__file__).read_text())


CALIBRATION = Path(__file__).resolve().parents[2] / "evidence/lipsync-calibration/20261027/calibration.json"


def _replay(seg, env):
    """The first mouth gate (E119, no longer used: MOUTH_CORR_MIN, LAG_MAX_MS, SPEAK_TO_PAUSE_MIN) on a segment."""
    o = np.array([np.nan if v is None else v for v in seg["opening"]])
    corr, lag, ratio = lc.mouth_sync(o, seg["fps"], env)
    passed = corr >= lc.MOUTH_CORR_MIN and abs(lag) <= lc.LAG_MAX_MS and ratio >= lc.SPEAK_TO_PAUSE_MIN
    return ([] if passed else ["MOUTH_NOT_IN_SYNC"]), corr


def _env(seg, shift_s=0.0):
    k = int(round((seg["env_pad_s"] + shift_s) / lc.HOP_S))
    return np.array(seg["env"][k:k + int(round((seg["t1"] - seg["t0"]) / lc.HOP_S))])


class Calibration(unittest.TestCase):
    """E119: the mouth thresholds were set on one Pavo clip. Measured 2026-10-27 on a labelled set of real speakers
    (20 segments with full beards and moustaches over the lips, 14 clean-shaven; public-domain / CC sources, series
    only, evidence/lipsync-calibration/20261027): every negative (audio shifted 300-500 ms or another clip's audio)
    fails, and no real positive passes either, bearded or not (corr medians 0.28 bearded, 0.30 clean-shaven). The
    instrument does not under-read beards; it accepts only mouths at least as audio-coupled as the Pavo calibration,
    more than natural speech shows. Any change to the mouth gate must be replayed here."""

    def test_the_mouth_gate_is_measured_on_the_labelled_calibration_set(self):
        data = json.loads(CALIBRATION.read_text())
        segs = data["segments"]
        by_id = {s["id"]: s for s in segs}
        groups = {g: [s for s in segs if s["group"] == g] for g in ("beard", "clear")}
        self.assertGreaterEqual(len(groups["beard"]), 5)
        self.assertGreaterEqual(len(groups["clear"]), 3)
        self.assertGreaterEqual(len({s["clip"] for s in groups["beard"]}), 4)
        for s in segs:
            src = data["sources"][s["clip"]]
            self.assertTrue(src["licence"] and src["page"].startswith("https://commons.wikimedia.org/"), s["clip"])
        passed, corr = {"beard": 0, "clear": 0}, {"beard": [], "clear": []}
        for s in segs:
            flags, c = _replay(s, _env(s))
            self.assertAlmostEqual(c, s["measured"]["pos"]["corr"], places=3)     # the series reproduce the record
            passed[s["group"]] += flags == []
            corr[s["group"]].append(c)
            # negatives: never a pass, whatever the gate becomes
            for d in (-0.5, -0.3, 0.3, 0.5):
                self.assertNotEqual(_replay(s, _env(s, d))[0], [], (s["id"], d))
            self.assertNotEqual(_replay(s, _env(by_id[s["swap_with"]]))[0], [], (s["id"], "swap"))
        # no beard bias: the bearded positives pass at least as often and read about as high as the clean-shaven
        rate = {g: passed[g] / len(groups[g]) for g in groups}
        self.assertGreaterEqual(rate["beard"], rate["clear"], rate)
        self.assertLess(abs(np.median(corr["beard"]) - np.median(corr["clear"])), 0.1)
        # as measured 2026-10-27 with the first gate: no real speaker passes (recorded, not a target); E120 replaced it
        self.assertEqual(passed, {"beard": 0, "clear": 0})


SYNC_CAL = CALIBRATION.with_name("syncnet-calibration.json")
NEGATIVES = ("shift-500ms", "shift-300ms", "shift+300ms", "shift+500ms", "swap")
SHIFT_FRAMES = {"shift-500ms": -12.5, "shift-300ms": -7.5, "shift+300ms": 7.5, "shift+500ms": 12.5}


class SyncNetCalibration(unittest.TestCase):
    """E120: the instrument could not measure the property (E119); SyncNet can. On the same labelled set (series of
    distances per offset kept in syncnet-calibration.json), the gate passes no negative (audio shifted 300-500 ms or
    another speaker's) and passes 14/14 clean-shaven and 14/20 bearded positives (the 6 misses are the two sources whose
    own soundtrack is off by +3 and -5 frames on every segment), with a confidence margin of at least 1 on each side."""

    def test_the_sync_gate_separates_the_labelled_set_with_no_false_positive(self):
        data = json.loads(SYNC_CAL.read_text())
        cal = json.loads(CALIBRATION.read_text())
        group = {s["id"]: s["group"] for s in cal["segments"]}
        self.assertEqual(set(data["segments"]), set(group))
        passed, neg_in, pos_conf = {"beard": 0, "clear": 0}, [], []
        for sid, seg in data["segments"].items():
            for name in ("pos",) + NEGATIVES:
                m = seg[name]
                again = sn.measure_mean(m["mdist"])
                self.assertEqual(again["offset"], m["offset"], (sid, name))   # the series reproduce the record
                self.assertAlmostEqual(again["conf"], m["conf"], delta=0.002)
                fails = lc.sync_verdict(m)
                if name == "pos":
                    passed[group[sid]] += not fails
                    if not fails:
                        pos_conf.append(m["conf"])
                else:
                    self.assertTrue(fails, (sid, name, m["offset"], m["conf"]))   # zero false positives
                    if abs(m["offset"]) <= lc.SYNC_OFFSET_MAX:
                        neg_in.append(m["conf"])
        self.assertEqual(passed, {"beard": 14, "clear": 14})
        # margin: the threshold sits at least 1.0 from the closest negative and the weakest passing positive
        self.assertGreaterEqual(lc.SYNC_CONF_MIN - max(neg_in), 1.0)
        self.assertGreaterEqual(min(pos_conf) - lc.SYNC_CONF_MIN, 1.0)
        # no beard bias among the sources that are themselves in sync (c00, c06, c07)
        beard_ok = [s for s in data["segments"] if group[s] == "beard" and s[:3] in ("c00", "c06", "c07")]
        self.assertTrue(all(not lc.sync_verdict(data["segments"][s]["pos"]) for s in beard_ok))

    def test_the_offset_follows_the_applied_shift(self):
        data = json.loads(SYNC_CAL.read_text())["segments"]
        dev = [seg[n]["offset"] - seg["pos"]["offset"] - f for seg in data.values() for n, f in SHIFT_FRAMES.items()]
        self.assertGreaterEqual(sum(abs(d) <= 0.5 for d in dev), 133)


class _FakeTorch:
    """A legacy torch.save file written without torch: fake torch / torch._utils modules only while pickling."""
    def __init__(self):
        import types
        self.torch, self.utils = types.ModuleType("torch"), types.ModuleType("torch._utils")

        class FloatStorage:
            pass
        FloatStorage.__module__, FloatStorage.__qualname__ = "torch", "FloatStorage"
        self.torch.FloatStorage = FloatStorage

        def _rebuild_tensor_v2(*a):
            return a
        _rebuild_tensor_v2.__module__, _rebuild_tensor_v2.__qualname__ = "torch._utils", "_rebuild_tensor_v2"
        self.utils._rebuild_tensor_v2 = _rebuild_tensor_v2

    def save(self, tensors):
        import collections
        import io
        import pickle
        import struct
        saved = {k: sys.modules.get(k) for k in ("torch", "torch._utils")}
        sys.modules["torch"], sys.modules["torch._utils"] = self.torch, self.utils
        try:
            fake = self

            class T:
                def __init__(self, key, arr):
                    self.key, self.arr = key, arr

                def __reduce__(self):
                    return (fake.utils._rebuild_tensor_v2, (("storage", self.key), 0, self.arr.shape,
                                                            tuple(s // 4 for s in self.arr.strides), False,
                                                            collections.OrderedDict()))

            class P(pickle.Pickler):
                def persistent_id(self, obj):
                    if isinstance(obj, tuple) and len(obj) == 2 and obj[0] == "storage":
                        return ("storage", fake.torch.FloatStorage, obj[1], "cpu", tensors[obj[1]].size, None)
                    return None

            f = io.BytesIO()
            for v in (0x1950A86A20F9469CFC6C, 1001, {"protocol_version": 1001, "little_endian": True}):
                pickle.dump(v, f, protocol=2)
            P(f, protocol=2).dump(collections.OrderedDict((k, T(k, v)) for k, v in tensors.items()))
            pickle.dump(sorted(tensors), f, protocol=2)
            for k in sorted(tensors):
                f.write(struct.pack("<q", tensors[k].size) + tensors[k].astype("<f4").tobytes())
            return f.getvalue()
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v


class SyncNetUnits(unittest.TestCase):
    """syncnet.py pieces against plain definitions (the network itself needs the 54 MB weights: the workflows' self
    checks run it on the Pavo calibration clip and on the same clip with its audio 400 ms late)."""

    def test_the_weights_are_pinned_and_parsed_without_torch(self):
        tensors = {"a.weight": np.arange(6, dtype=np.float32).reshape(2, 3), "a.bias": np.ones(2, np.float32)}
        w = sn.parse(_FakeTorch().save(tensors))
        self.assertTrue(np.array_equal(w["a.weight"], tensors["a.weight"]))
        self.assertTrue(np.array_equal(w["a.bias"], tensors["a.bias"]))
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".model") as f:
            f.write(b"not the weights")
            f.flush()
            with self.assertRaises(SystemExit) as e:
                sn.load(f.name)
        self.assertIn("SYNCNET_MODEL_HASH_MISMATCH", str(e.exception))
        self.assertRegex(sn.SYNCNET_SHA256, r"^[0-9a-f]{64}$")

    def test_a_weights_file_cannot_run_code(self):
        import pickle
        evil = b"".join(pickle.dumps(v, protocol=2) for v in (1, 1001, {})) + b"cos\nsystem\n(S'true'\ntR."
        with self.assertRaises(pickle.UnpicklingError) as e:
            sn.parse(evil)
        self.assertIn("SYNCNET_MODEL_FORBIDDEN", str(e.exception))

    def test_conv_and_pool_match_their_definition(self):
        rng = np.random.default_rng(0)
        x, w, b = rng.normal(size=(2, 3, 9, 8)), rng.normal(size=(4, 3, 3, 2)), rng.normal(size=4)
        got = sn._conv(x, w, b, (2, 1), (1, 1))
        xp = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)))
        for i in range(got.shape[2]):
            for j in range(got.shape[3]):
                ref = np.tensordot(xp[:, :, 2 * i:2 * i + 3, j:j + 2], w, axes=([1, 2, 3], [1, 2, 3])) + b
                self.assertTrue(np.allclose(got[:, :, i, j], ref))
        p = sn._pool(x, (3, 3), (2, 2), (1, 1))
        xp = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)), constant_values=-np.inf)
        self.assertTrue(np.array_equal(p[:, :, 1, 2], xp[:, :, 2:5, 4:7].max(axis=(2, 3))))

    def test_the_first_conv3d_is_the_sum_of_its_time_slices(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=(7, 3, 11, 11)).astype(np.float32)
        w = rng.normal(size=(4, 3, 5, 3, 3)).astype(np.float32)
        b = rng.normal(size=4).astype(np.float32)
        got = sn.conv3d_first(x, w, b)
        self.assertEqual(got.shape, (3, 4, 5, 5))
        ref = sum(np.tensordot(x[1 + t, :, 4:7, 2:5], w[:, :, t], axes=([0, 1, 2], [1, 2, 3])) for t in range(5)) + b
        self.assertTrue(np.allclose(got[1, :, 2, 1], ref, atol=1e-4))

    def test_mfcc_frames_and_energy(self):
        x = np.random.default_rng(2).normal(0, 3000, 16000)
        m = sn.mfcc(x)
        self.assertEqual(m.shape, (1 + int(np.ceil((16000 - 400) / 160)), 13))
        pre = np.append(x[:1], x[1:] - 0.97 * x[:-1])
        self.assertAlmostEqual(m[0, 0], np.log((np.abs(np.fft.rfft(pre[:400], 512)) ** 2 / 512).sum()), places=6)

    def test_the_measure_finds_a_shift_and_a_wrong_voice(self):
        rng = np.random.default_rng(3)
        lip = rng.normal(size=(120, 16))
        aud = np.roll(lip, 4, axis=0) + rng.normal(0, 0.1, (120, 16))       # audio 4 windows late
        m = sn.measure(sn.distances(lip, aud))
        self.assertEqual(m["offset"], -4)
        self.assertGreater(m["conf"], 2)
        wrong = sn.measure(sn.distances(lip, rng.normal(size=(120, 16))))
        self.assertLess(wrong["conf"], m["conf"] / 4)
        self.assertEqual(sn.measure_mean(np.r_[np.ones(15) * 5, 1, np.ones(15) * 5]), {"offset": 0, "conf": 4.0,
                                                                                      "min_dist": 1.0})

    def test_the_face_box_is_filled_and_smoothed_and_no_face_is_none(self):
        boxes = np.array([[10, 10, 50, 70]] * 20, dtype=float)
        boxes[5] = np.nan
        track = sn.crop_boxes(boxes)
        self.assertTrue(np.allclose(track[5], [30, 30, 40]))               # size max(w, h) / 2, centre
        self.assertIsNone(sn.crop_boxes(np.full((5, 4), np.nan)))
        face = sn.crop(np.zeros((100, 100, 3), np.uint8), 30, 30, 40)
        self.assertEqual(face.shape, (224, 224, 3))


if __name__ == "__main__":
    unittest.main()
