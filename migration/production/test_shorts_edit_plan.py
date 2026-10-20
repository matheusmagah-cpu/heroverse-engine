#!/usr/bin/env python3
"""Offline contract tests: frozen bytes, synthetic signals, no live pilot reads."""
from array import array
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shorts_edit_plan as ep  # noqa: E402
import shorts_select as selector  # noqa: E402

FIXTURE = HERE / "fixtures" / "shorts-pilot-005-20261020"
# Exact bytes at accepted merge fae9879, including its one terminating newline.
INPUTS_RAW = b'{"voice_asset": "pilot-005-voice-sha256-6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc.flac", "voice_sha256": "6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc", "figure_asset": "pilot-005-figure-sha256-b81f6f73e0915e853bdb68ce07c316770836a89bffd9c13950ab4d2ee97a06e6.png", "figure_sha256": "b81f6f73e0915e853bdb68ce07c316770836a89bffd9c13950ab4d2ee97a06e6", "render": "runner 39346016001"}\n'
# Independent frozen plan literal: tests never open a production plan path.
PLAN_RAW = r'''{
  "version": "shorts-editorial-plan-v2",
  "source_pilot": "pilot-005",
  "source_baseline_sha": "7fb9e9e1fad9396b80c029212f0a3144c1428d51",
  "source_sha256": {
    "script": "c0cf3d5fc0747b5f743d9d0189e9deb4326a124a9769a41d4341b14aa347359a",
    "timeline": "53496f5a82ed391422974e517b5b895059d0040db790c2044030f06bd06245c5",
    "inputs": "67e393596d74f77e64f5a9de143c99dbc4bc4cb2cb8e898b261900ae69623831"
  },
  "voice": {
    "asset": "pilot-005-voice-sha256-6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc.flac",
    "sha256": "6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc"
  },
  "music": {
    "asset": "original-rest-music.lossless.flac",
    "sha256": "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c"
  },
  "candidate": {
    "start": 459.86,
    "end": 499.672,
    "hook": "Lord, protect my relationships.",
    "title": "A Prayer for Peace in Your Relationships",
    "reference": null
  },
  "tail_seconds": 0.5,
  "transition": {
    "type": "fade",
    "seconds": 0.5
  },
  "scenes": [
    {
      "image_id": "bg-dawn-lake",
      "asset": "pilot-003-img-bg-dawn-lake-sha256-74d22480484ff2088b82de7d0dd83170be6171711aaeb198f96fc74f40d26018.png",
      "sha256": "74d22480484ff2088b82de7d0dd83170be6171711aaeb198f96fc74f40d26018",
      "nominal_start": 0.0,
      "nominal_end": 5.0,
      "motion_profile": "phrase_push_in_v1"
    },
    {
      "image_id": "bg-sheltered-valley",
      "asset": "pilot-005-img-bg-sheltered-valley-sha256-1d8055fd45c97ae66eead1c19f80dcaf1a9a28644761f31f41f34975bfe34d85.png",
      "sha256": "1d8055fd45c97ae66eead1c19f80dcaf1a9a28644761f31f41f34975bfe34d85",
      "nominal_start": 5.0,
      "nominal_end": 10.0,
      "motion_profile": "phrase_pan_right_v1"
    },
    {
      "image_id": "bg-sunlit-road",
      "asset": "pilot-005-img-bg-sunlit-road-sha256-79591089b067d1e73cc8cb5ad7c5ebcea6754a1b6eb4e1eff039de3d6abb7794.png",
      "sha256": "79591089b067d1e73cc8cb5ad7c5ebcea6754a1b6eb4e1eff039de3d6abb7794",
      "nominal_start": 10.0,
      "nominal_end": 15.0,
      "motion_profile": "phrase_push_in_v1"
    },
    {
      "image_id": "bg-fortress-dawn",
      "asset": "pilot-005-img-bg-fortress-dawn-sha256-8fe838ae8d71963474991719861e02aaf83651817031e4af59a73858ba043bba.png",
      "sha256": "8fe838ae8d71963474991719861e02aaf83651817031e4af59a73858ba043bba",
      "nominal_start": 15.0,
      "nominal_end": 20.0,
      "motion_profile": "phrase_pan_right_v1"
    },
    {
      "image_id": "bg-sunrise-field",
      "asset": "pilot-003-img-bg-sunrise-field-sha256-8083ef5de4d2e1bf8b078a4f8ac0af71cc9992a68c9663528149fe8255aed1e0.png",
      "sha256": "8083ef5de4d2e1bf8b078a4f8ac0af71cc9992a68c9663528149fe8255aed1e0",
      "nominal_start": 20.0,
      "nominal_end": 25.0,
      "motion_profile": "phrase_push_in_v1"
    },
    {
      "image_id": "bg-misty-valley",
      "asset": "pilot-003-img-bg-misty-valley-sha256-a7e0c31b6a3cd366971a604e648ec0728c1227b45ae71dcfaac0a03679f6acdc.png",
      "sha256": "a7e0c31b6a3cd366971a604e648ec0728c1227b45ae71dcfaac0a03679f6acdc",
      "nominal_start": 25.0,
      "nominal_end": 30.0,
      "motion_profile": "phrase_pan_right_v1"
    },
    {
      "image_id": "bg-mountain-sunrise",
      "asset": "pilot-003-img-bg-mountain-sunrise-sha256-886b55ab2de854099a05358f2a8059cd5ad8b42d1a7af482c40e2dde1b84c6c5.png",
      "sha256": "886b55ab2de854099a05358f2a8059cd5ad8b42d1a7af482c40e2dde1b84c6c5",
      "nominal_start": 30.0,
      "nominal_end": 35.0,
      "motion_profile": "phrase_push_in_v1"
    },
    {
      "image_id": "bg-tower-hill",
      "asset": "pilot-005-img-bg-tower-hill-sha256-0a2619e6dbddc3966d31850f2ab74e2e92738d2787ac0dcdd23ad44b7c92f961.png",
      "sha256": "0a2619e6dbddc3966d31850f2ab74e2e92738d2787ac0dcdd23ad44b7c92f961",
      "nominal_start": 35.0,
      "nominal_end": 40.312,
      "motion_profile": "phrase_pan_right_v1"
    }
  ],
  "publish": false,
  "rhythm_exception": {
    "id": "pilot-005-20261020-eight-scenes-r3",
    "target_slot": "2026-10-20T20:00:00Z",
    "scene_count": 8,
    "nominal_seconds": [
      4.0,
      6.0
    ],
    "visible_seconds": [
      4.0,
      6.0
    ]
  },
  "hook_animation": {
    "profile": "cinematic_hook_v1",
    "start_seconds": 0.0,
    "end_seconds": 3.0,
    "caption_policy": "single_track_no_duplicate"
  }
}
'''
NEW_REVIEW_RAW = r'''{
 "version": "shorts-produce-v2-r8",
 "source_pilot": "pilot-005",
 "selection_rubric_model": null,
 "rejected_r8": [],
 "shorts": [
  {
   "file": "short-00.mp4",
   "sha256": "3588afa8468882e7f528d204f41bbb72a8b1b27b4f21b841ab634b20ebbf0dd7",
   "seconds": 40.31,
   "source_start": 459.86,
   "source_end": 499.672,
   "segments": [
    "prayer-relationships",
    "prayer-words"
   ],
   "hook": "Lord, protect my relationships.",
   "hook_shown": true,
   "title": "A Prayer for Peace in Your Relationships",
   "reference": null,
   "scenes": [
    "bg-home-sunrise",
    "bg-garden"
   ],
   "parallax": false,
   "figure": false,
   "selection": {
    "final_score": null,
    "measured_score": null,
    "features": null,
    "rubric": null
   },
   "text": "Lord, protect my relationships. Guard marriages from coldness and from anything that would divide them. Protect friendships from gossip and misunderstanding. Where there is tension, bring honest conversations and quick forgiveness. Let love win in every home today. Father, set a guard over my mouth today. Protect me from words I would regret: harsh words, careless words, words spoken in anger. Let what I say build people up. Let my words carry your peace into every room I enter.",
   "render_plan": {
    "expected_frame_count": 1209,
    "fps": 30,
    "scene_frame_spans": [
     {
      "image_id": "bg-home-sunrise",
      "start_frame": 0,
      "end_frame": 672,
      "nominal_start_frame": 0,
      "nominal_end_frame": 665
     },
     {
      "image_id": "bg-garden",
      "start_frame": 657,
      "end_frame": 1209,
      "nominal_start_frame": 665,
      "nominal_end_frame": 1209
     }
    ]
   },
   "source_image_info": {
    "bg-home-sunrise": {
     "source_width": 2048,
     "source_height": 2048,
     "scaled_width": 1920,
     "scaled_height": 1920,
     "crop_width": 1080,
     "crop_height": 1920,
     "crop_x": 420.0,
     "crop_y": 0.0,
     "native_portrait_width": 1152.0,
     "native_portrait_height": 2048
    },
    "bg-garden": {
     "source_width": 1344,
     "source_height": 768,
     "scaled_width": 3360,
     "scaled_height": 1920,
     "crop_width": 1080,
     "crop_height": 1920,
     "crop_x": 1140.0,
     "crop_y": 0.0,
     "native_portrait_width": 432.0,
     "native_portrait_height": 768
    }
   },
   "publish": false,
   "media_checks": {
    "version": "shorts-media-checks-v1",
    "output_sha256": "3588afa8468882e7f528d204f41bbb72a8b1b27b4f21b841ab634b20ebbf0dd7",
    "source_voice_sha256": "6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc",
    "source_music_sha256": "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c",
    "source_image_sha256": {
     "bg-home-sunrise": "5ebdbb61901120845c3872f15cdca23d2ff0baac58ae0284f6f52effffd848c6",
     "bg-garden": "5172945b7bc917143eb1e0d62ed1f66d90b943a9956ddd20b84c73b679dfea04"
    },
    "measured_at": "2026-10-20T17:36:36.888040+00:00",
    "acoustic": {
     "pcm_sample_rate": 48000,
     "window_samples": 480,
     "active_threshold_dbfs": -40.0,
     "leading_inactive_seconds": 0.14,
     "trailing_inactive_seconds": 0.212,
     "first_active_sample": 6720,
     "last_active_sample": 1900800,
     "narration_samples": 1910976,
     "status": "PASS"
    },
    "video": {
     "decoded_frame_count": 1209,
     "fps": 30.0,
     "seconds": 40.312,
     "expected_frame_count": 1209,
     "black_intervals": [],
     "scene_frame_spans": [
      {
       "image_id": "bg-home-sunrise",
       "start_frame": 0,
       "end_frame": 672,
       "nominal_start_frame": 0,
       "nominal_end_frame": 665
      },
      {
       "image_id": "bg-garden",
       "start_frame": 657,
       "end_frame": 1209,
       "nominal_start_frame": 665,
       "nominal_end_frame": 1209
      }
     ],
     "status": "PASS"
    },
    "status": "PASS"
   },
   "media_checks_reason": null,
   "qa_output_sha256": "3588afa8468882e7f528d204f41bbb72a8b1b27b4f21b841ab634b20ebbf0dd7",
   "qa": {
    "file": "/home/runner/work/_temp/work/shorts/short-00.mp4",
    "seconds": 40.31,
    "lufs": -14.9,
    "true_peak_dbtp": -2.3,
    "checks": {
     "decode_clean": true,
     "one_h264_1080x1920": true,
     "fps_30": true,
     "one_aac_stereo_48k": true,
     "duration": true,
     "loudness": true,
     "true_peak": true
    },
    "status": "PASS"
   },
   "review": {
    "hook_in_first_2s": 7.5,
    "captions_readable_and_synced": 8.5,
    "text_clear_of_shorts_ui": 9.0,
    "picture_quality": 7.5,
    "edit_rhythm": 5.5,
    "audio_clarity": 8.5,
    "stands_alone": 9.0,
    "ending_and_loop": 6.5,
    "policy_safe": 10.0,
    "overall": 7.3,
    "issues": [
     "00:00 - Redundant text: static hook text at the top clashes with animated caption in the center displaying the exact same words.",
     "00:00-00:21 - Pacing is visually static; staying on a single AI illustration for over 20 seconds causes visual fatigue on Shorts.",
     "00:39 - Background audio and voice cut out abruptly at the loop point without a smooth transition."
    ],
    "strongest_moment": "00:21 - The shift in visual theme and prayer topic to guarding words spoken over a tranquil garden path.",
    "model": "gemini-3.8-flash",
    "status": "FAIL",
    "output_sha256": "3588afa8468882e7f528d204f41bbb72a8b1b27b4f21b841ab634b20ebbf0dd7"
   },
   "release_status": "REVIEW_FAIL"
  }
 ],
 "edit_plan": {
  "version": "shorts-editorial-plan-v1",
  "source_pilot": "pilot-005",
  "source_baseline_sha": "7fb9e9e1fad9396b80c029212f0a3144c1428d51",
  "source_sha256": {
   "script": "c0cf3d5fc0747b5f743d9d0189e9deb4326a124a9769a41d4341b14aa347359a",
   "timeline": "53496f5a82ed391422974e517b5b895059d0040db790c2044030f06bd06245c5",
   "inputs": "67e393596d74f77e64f5a9de143c99dbc4bc4cb2cb8e898b261900ae69623831"
  },
  "voice": {
   "asset": "pilot-005-voice-sha256-6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc.flac",
   "sha256": "6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc"
  },
  "music": {
   "asset": "original-rest-music.lossless.flac",
   "sha256": "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c"
  },
  "candidate": {
   "start": 459.86,
   "end": 499.672,
   "hook": "Lord, protect my relationships.",
   "title": "A Prayer for Peace in Your Relationships",
   "reference": null
  },
  "tail_seconds": 0.5,
  "transition": {
   "type": "fade",
   "seconds": 0.5,
   "center_seconds": 22.153
  },
  "scenes": [
   {
    "image_id": "bg-home-sunrise",
    "asset": "pilot-005-img-bg-home-sunrise-sha256-5ebdbb61901120845c3872f15cdca23d2ff0baac58ae0284f6f52effffd848c6.png",
    "sha256": "5ebdbb61901120845c3872f15cdca23d2ff0baac58ae0284f6f52effffd848c6",
    "nominal_start": 0.0,
    "nominal_end": 22.153,
    "motion_profile": "phrase_push_in_v1"
   },
   {
    "image_id": "bg-garden",
    "asset": "pilot-002-img-bg-garden-sha256-5172945b7bc917143eb1e0d62ed1f66d90b943a9956ddd20b84c73b679dfea04.png",
    "sha256": "5172945b7bc917143eb1e0d62ed1f66d90b943a9956ddd20b84c73b679dfea04",
    "nominal_start": 22.153,
    "nominal_end": 40.312,
    "motion_profile": "phrase_pan_right_v1"
   }
  ],
  "publish": false
 },
 "publish": false,
 "release_status": "REVIEW_FAIL",
 "review_rubric": {
  "items": [
   "hook_in_first_2s",
   "captions_readable_and_synced",
   "text_clear_of_shorts_ui",
   "picture_quality",
   "edit_rhythm",
   "audio_clarity",
   "stands_alone",
   "ending_and_loop",
   "policy_safe"
  ],
  "pass_item": 7,
  "pass_overall": 8
 },
 "finalization": {
  "status": "COMPLETE",
  "output_sha256": "3588afa8468882e7f528d204f41bbb72a8b1b27b4f21b841ab634b20ebbf0dd7",
  "finalized_at": "2026-10-20T17:38:44.399454+00:00",
  "target_slot": "2026-10-20T20:00:00Z"
 }
}
'''
OUTPUT_SHA = hashlib.sha256(b"synthetic output only").hexdigest()
NOW = "2026-10-20T19:14:59Z"


def plan():
    return json.loads(PLAN_RAW)


def sources():
    script_raw = (FIXTURE / "script.json").read_bytes()
    timeline_raw = (FIXTURE / "out" / "timeline.json").read_bytes()
    return json.loads(timeline_raw), json.loads(script_raw), json.loads(INPUTS_RAW), {
        "script": hashlib.sha256(script_raw).hexdigest(), "timeline": hashlib.sha256(timeline_raw).hexdigest(),
        "inputs": hashlib.sha256(INPUTS_RAW).hexdigest()}


def media():
    p = plan()
    frames = ep.frame_plan(p)
    return {"version": "shorts-media-checks-v1", "output_sha256": OUTPUT_SHA,
            "source_voice_sha256": p["voice"]["sha256"], "source_music_sha256": p["music"]["sha256"],
            "source_image_sha256": {s["image_id"]: s["sha256"] for s in p["scenes"]},
            "measured_at": "2026-10-20T19:13:00+00:00",
            "acoustic": {"pcm_sample_rate": 48000, "window_samples": 480, "active_threshold_dbfs": -40.0,
                         "leading_inactive_seconds": 0.01, "trailing_inactive_seconds": 0.002,
                         "first_active_sample": 480, "last_active_sample": 1910880, "narration_samples": 1910976,
                         "status": "PASS"},
            "video": {"decoded_frame_count": 1209, "fps": 30.0, "seconds": 40.312,
                      "expected_frame_count": 1209, "black_intervals": [],
                      "scene_frame_spans": frames["scene_frame_spans"], "status": "PASS"}, "status": "PASS"}


def history():
    return {"source_baseline_sha": "7fb9e9e1fad9396b80c029212f0a3144c1428d51",
            "source_sha256": "3e1357fb31d87c5e1b3f6e90fdf86c461b1232a996511a586dce2643e5a58b98",
            "historical_records": json.loads((FIXTURE / "shorts" / "shorts.json").read_bytes()), "new_reviews": [json.loads(NEW_REVIEW_RAW)]}


def spec():
    p = plan()
    rec = {"file": "short-00.mp4", "sha256": OUTPUT_SHA, "seconds": 40.31,
           "source_start": 459.860, "source_end": 499.672, "hook": p["candidate"]["hook"], "hook_shown": True, "hook_mode": "caption_only",
           "title": p["candidate"]["title"], "reference": None,
           "scenes": [s["image_id"] for s in p["scenes"]], "figure": False, "parallax": False,
           "render_plan": ep.frame_plan(p), "publish": True, "media_checks": media(), "qa_output_sha256": OUTPUT_SHA,
           "qa": {"file": "/synthetic/short-00.mp4", "seconds": 40.31, "lufs": -14.0, "true_peak_dbtp": -2.0,
                  "checks": {k: True for k in ep.QA_CHECKS}, "status": "PASS"},
           "review": {**{k: 7 for k in ep.RUBRIC}, "overall": 8, "issues": [], "strongest_moment": "Synthetic fixture",
                      "model": "gemini-3.8-flash", "status": "PASS", "output_sha256": OUTPUT_SHA}}
    return {"source_pilot": "pilot-005", "edit_plan": p, "shorts": [rec],
            "review_rubric": {"items": list(ep.RUBRIC), "pass_item": 7, "pass_overall": 8}}


def finish(s, now=NOW, sha=OUTPUT_SHA):
    return ep.finalize_manifest(s, actual_output_sha256=sha, now_utc=now, target_slot=ep.TARGET_SLOT)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.timeline, self.script, self.inputs, self.hashes = sources()

    def prepare(self, p=None):
        return ep.validate_plan(plan() if p is None else p, self.timeline, self.script, self.inputs, raw_sha256=self.hashes)

    def test_exact_frozen_raw_hashes(self):
        self.assertEqual(hashlib.sha256(INPUTS_RAW).hexdigest(), "67e393596d74f77e64f5a9de143c99dbc4bc4cb2cb8e898b261900ae69623831")
        self.assertEqual(self.hashes, plan()["source_sha256"])

    def test_v7_plan_and_real_rejected_manifest_literals_have_pinned_hashes(self):
        self.assertEqual(hashlib.sha256(PLAN_RAW.encode()).hexdigest(),
                         "d725f27cd86f16447123ae5b68384a42eff6057838cc7a7e0011a4ee11fb4d2c")
        self.assertEqual(hashlib.sha256(NEW_REVIEW_RAW.encode()).hexdigest(),
                         "556251e9ad6c6fce4661face3d5c3355621135cb4d700ffd256bab9332131273")
        canonical = json.dumps(json.loads(NEW_REVIEW_RAW), sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(),
                         "0d80d5291959b8d718b184f894687caf63862b70bd27fe24461a766cecb6d654")

    def test_owner_exception_cannot_be_copied_or_expanded(self):
        cases = []
        p = plan()
        p["source_pilot"] = "pilot-006"
        cases.append(p)
        for count in (7, 9):
            p = plan()
            p["scenes"] = p["scenes"][:7] if count == 7 else p["scenes"] + [deepcopy(p["scenes"][-1])]
            p["rhythm_exception"]["scene_count"] = count
            cases.append(p)
        for key, value in (("target_slot", "2026-10-21T20:00:00Z"), ("scene_count", True),
                           ("nominal_seconds", [3, 6]), ("visible_seconds", [4, 7]), ("id", "generic-r3-bypass")):
            p = plan()
            p["rhythm_exception"][key] = value
            cases.append(p)
        p = plan()
        p["scenes"][0], p["scenes"][1] = p["scenes"][1], p["scenes"][0]
        cases.append(p)
        p = plan()
        del p["rhythm_exception"]
        cases.append(p)
        for key, value in (("profile", "arbitrary-expression"), ("end_seconds", 4),
                           ("start_seconds", True), ("caption_policy", "overlay")):
            p = plan()
            p["hook_animation"][key] = value
            cases.append(p)
        # The rejected v1 may be archived but is no executable fallback.
        cases.append(json.loads(NEW_REVIEW_RAW)["edit_plan"])
        with patch.object(ep.subprocess, "run", side_effect=AssertionError("no render")) as run, \
                patch.object(selector, "rubric", side_effect=AssertionError("no provider")) as provider:
            for p in cases:
                with self.subTest(version=p.get("version"), policy=p.get("rhythm_exception")), self.assertRaises(ValueError):
                    self.prepare(p)
        self.assertEqual(run.call_count, 0)
        self.assertEqual(provider.call_count, 0)

    def test_real_plan_one_reconstructed_candidate_no_provider(self):
        with patch.object(selector, "rubric", side_effect=AssertionError("provider forbidden")), \
                patch.object(ep.subprocess, "run", side_effect=AssertionError("subprocess forbidden")):
            result = self.prepare()
        self.assertEqual(result["selection_mode"], "EDITORIAL_PLAN")
        self.assertIsNone(result["rubric_model"])
        self.assertEqual(len(result["chosen"]), 1)
        self.assertEqual(len(result["edit_plan"]["scenes"]), 8)
        self.assertEqual([s["image_id"] for s in result["edit_plan"]["scenes"]],
                         ["bg-dawn-lake", "bg-sheltered-valley", "bg-sunlit-road", "bg-fortress-dawn",
                          "bg-sunrise-field", "bg-misty-valley", "bg-mountain-sunrise", "bg-tower-hill"])
        self.assertNotIn("bg-home-sunrise", [s["image_id"] for s in result["edit_plan"]["scenes"]])
        m = result["chosen"][0]
        self.assertEqual(len(m["sentences"]), 10)
        self.assertEqual(m["sentences"], self.timeline["sentences"][106:116])
        self.assertEqual(m["text"], " ".join(s["text"] for s in self.timeline["sentences"][106:116]))
        self.assertEqual((m["start"], m["end"]), (459.860, 499.672))
        self.assertAlmostEqual(m["end"] - m["start"] + result["edit_plan"]["tail_seconds"], 40.312)
        self.assertIsNone(m["reference"])
        self.assertEqual(m["hook"], m["sentences"][0]["text"])
        for field in ("rubric", "measured_score", "final_score"):
            self.assertNotIn(field, m)

    def test_adapter_uses_shared_validator(self):
        with patch.object(ep, "validate_candidate", wraps=selector.validate_candidate) as shared:
            self.prepare()
        shared.assert_called_once()

    def test_reconstructed_source_must_pass_phase_one(self):
        self.timeline["sentences"][106]["end"] = 463
        with self.assertRaisesRegex(ValueError, "SOURCE_CANDIDATE_REJECTED"):
            self.prepare()

    def test_forged_sentence_text_is_not_an_accepted_plan_field(self):
        p = plan()
        p["candidate"].update(sentences=[{"text": "Forged", "start": 0}], final_score=999)
        with self.assertRaises(ValueError):
            self.prepare(p)

    def test_every_closed_schema_value_is_bound(self):
        mutations = [
            (("source_pilot",), "pilot-006"), (("source_baseline_sha",), "0" * 40),
            (("candidate", "start"), 1404.681), (("candidate", "end"), 1440.736),
            (("candidate", "hook"), "Another hook"), (("candidate", "title"), "Other title"),
            (("candidate", "reference"), "Psalm 23:1"), (("tail_seconds",), True),
            (("tail_seconds",), float("nan")), (("transition", "seconds"), float("inf")),
            (("transition", "seconds"), 0.4), (("voice", "sha256"), "a" * 64),
            (("music", "asset"), "../music.flac"), (("scenes", 0, "asset"), "../image.png"),
            (("scenes", 1, "image_id"), "bg-home-sunrise"), (("scenes", 1, "motion_profile"), "expression=evil"),
            (("scenes", 0, "sha256"), "not-a-hash"), (("scenes", 0, "nominal_start"), False),
            (("publish",), 0), (("publish",), True)]
        for keys, value in mutations:
            with self.subTest(keys=keys, value=value):
                p, node = plan(), None
                node = p
                for k in keys[:-1]:
                    node = node[k]
                node[keys[-1]] = value
                with self.assertRaises(ValueError):
                    self.prepare(p)
        for keys in [(), ("voice",), ("source_sha256",), ("candidate",), ("transition",), ("scenes", 0)]:
            p, node = plan(), None
            node = p
            for k in keys:
                node = node[k]
            node["unexpected"] = 1
            with self.assertRaises(ValueError):
                self.prepare(p)
        p = plan()
        del p["music"]
        with self.assertRaises(ValueError):
            self.prepare(p)

    def test_changed_inputs_mapping_and_pilot_rejected(self):
        self.inputs["voice_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "VOICE_INPUT_MISMATCH"):
            self.prepare()
        self.inputs = json.loads(INPUTS_RAW)
        self.script["pilot_id"] = "pilot-006"
        with self.assertRaisesRegex(ValueError, "SOURCE_PILOT_MISMATCH"):
            self.prepare()

    def test_main_exact_raw_hash_not_reserialized_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plan.json").write_text(PLAN_RAW)
            (root / "timeline.json").write_bytes((FIXTURE / "out" / "timeline.json").read_bytes())
            (root / "script.json").write_bytes((FIXTURE / "script.json").read_bytes())
            (root / "inputs.json").write_bytes(INPUTS_RAW)
            args = [root / n for n in ("plan.json", "timeline.json", "script.json", "inputs.json", "out.json")]
            with patch.object(ep.subprocess, "run", side_effect=AssertionError("pure only")):
                self.assertEqual(len(ep.main(*args)["chosen"]), 1)
                for name in ("timeline.json", "script.json", "inputs.json"):
                    p = root / name
                    original = p.read_bytes()
                    p.write_bytes(original + b"\n")
                    with self.assertRaisesRegex(ValueError, "INPUT_SHA256_MISMATCH"):
                        ep.main(*args)
                    p.write_bytes(original)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            for raw in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e309}'):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    ep.read_json(path)

    def test_frame_plan_exact_overlap_and_nominal_spans(self):
        p = ep.frame_plan(plan())
        self.assertEqual(p["expected_frame_count"], 1209)
        self.assertEqual(p["fps"], 30)
        spans = p["scene_frame_spans"]
        self.assertEqual(len(spans), 8)
        self.assertEqual([(s["start_frame"], s["end_frame"]) for s in spans],
                         [(0, 158), (143, 308), (293, 458), (443, 608), (593, 758), (743, 908), (893, 1058), (1043, 1209)])
        nominal = [s["nominal_end_frame"] - s["nominal_start_frame"] for s in spans]
        inputs = [s["end_frame"] - s["start_frame"] for s in spans]
        self.assertEqual(nominal, [150] * 7 + [159])
        self.assertEqual(inputs, [158] + [165] * 6 + [166])
        self.assertEqual(sum(inputs) - 7 * 15, 1209)
        self.assertEqual(sum(nominal), 1209)
        for i in range(7):
            self.assertEqual(spans[i]["end_frame"] - spans[i + 1]["start_frame"], 15)
        for i in range(6):
            self.assertLess(spans[i]["end_frame"], spans[i + 2]["start_frame"])


class AcousticTests(unittest.TestCase):
    def pcm(self, lead, active, tail, amplitude=1000):
        a = array("h", [0] * lead + [amplitude] * active + [0] * tail)
        if sys.byteorder != "little":
            a.byteswap()
        return a.tobytes()

    def test_exact_threshold_and_window_clock(self):
        r = ep.acoustic_measurements(self.pcm(14400, 4800, 14400))
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["first_active_sample"], 14400)
        self.assertEqual(r["last_active_sample"], 19200)
        self.assertEqual(r["leading_inactive_seconds"], 0.3)
        self.assertEqual(r["trailing_inactive_seconds"], 0.3)
        self.assertEqual(ep.acoustic_measurements(self.pcm(14880, 4800, 0))["status"], "FAIL")
        self.assertEqual(ep.acoustic_measurements(self.pcm(0, 4800, 14880))["status"], "FAIL")

    def test_all_silent_below_threshold_and_partial_window(self):
        for amplitude in (0, 327):
            r = ep.acoustic_measurements(self.pcm(0, 480, 0, amplitude))
            self.assertEqual(r["status"], "FAIL")
            self.assertIsNone(r["first_active_sample"])
        r = ep.acoustic_measurements(self.pcm(0, 481, 0, 328))
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["last_active_sample"], 481)
        for bad in (b"", b"a", "pcm"):
            with self.assertRaises(ValueError):
                ep.acoustic_measurements(bad)


class FinalizeTests(unittest.TestCase):
    def assertBlocked(self, s, code=None, sha=OUTPUT_SHA):
        result = finish(s, sha=sha)
        self.assertEqual(result["finalization"]["status"], "ERROR")
        self.assertFalse(any(r.get("publish") for r in result.get("shorts", []) if isinstance(r, dict)))
        if code:
            self.assertEqual(result["release_status"], code)
        return result

    def test_complete_synthetic_evidence_eligible_without_provider(self):
        original = spec()
        with patch.object(ep.subprocess, "run", side_effect=AssertionError("pure only")), \
                patch.object(selector, "rubric", side_effect=AssertionError("provider forbidden")):
            result = finish(original)
        self.assertEqual(result["finalization"]["status"], "COMPLETE")
        self.assertEqual(result["release_status"], "READY_FOR_TARGET_SLOT")
        self.assertEqual(sum(r["publish"] for r in result["shorts"]), 1)
        self.assertNotIn("finalization", original)
        self.assertEqual(result["shorts"][0]["qa"], original["shorts"][0]["qa"])
        self.assertEqual(result["shorts"][0]["review"], original["shorts"][0]["review"])

    def test_deadline_is_exact_and_never_rolls_target_slot(self):
        self.assertTrue(finish(spec(), "2026-10-20T19:30:00Z")["shorts"][0]["publish"])
        self.assertTrue(finish(spec(), "2026-10-20T19:15:01Z")["shorts"][0]["publish"])
        r = finish(spec(), "2026-10-20T19:30:01Z")
        self.assertFalse(r["shorts"][0]["publish"])
        self.assertEqual(r["release_status"], "TARGET_SLOT_LEAD_MISSED")
        self.assertEqual(r["finalization"]["target_slot"], "2026-10-20T20:00:00Z")
        self.assertEqual(r["finalization"]["status"], "COMPLETE")

    def test_extended_operational_margin_still_requires_real_review(self):
        missing = spec()
        del missing["shorts"][0]["review"]
        result = finish(missing, "2026-10-20T19:20:00Z")
        self.assertFalse(result["shorts"][0]["publish"])
        self.assertNotEqual(result["release_status"], "READY_FOR_TARGET_SLOT")
        self.assertEqual(result["finalization"]["target_slot"], "2026-10-20T20:00:00Z")

    def test_invalid_clocks_and_slots_reject(self):
        for now in ("2026-10-20T19:14:59", datetime(2026, 10, 20, 19), None, "not a date", "2026-10-20T20:14:59+01:00"):
            with self.subTest(now=now), self.assertRaises(ValueError):
                finish(spec(), now)
        with self.assertRaises(ValueError):
            ep.finalize_manifest(spec(), actual_output_sha256=OUTPUT_SHA, now_utc=NOW, target_slot="2026-10-21T20:00:00Z")
        self.assertTrue(finish(spec(), datetime(2026, 10, 20, 19, 14, 59, tzinfo=timezone.utc))["shorts"][0]["publish"])

    def test_missing_stale_hash_and_wrong_source_evidence(self):
        for key in list(media()):
            s = spec()
            del s["shorts"][0]["media_checks"][key]
            self.assertBlocked(s, "MEDIA_CHECKS_SCHEMA")
        s = spec()
        del s["shorts"][0]["media_checks"]
        self.assertBlocked(s, "MEDIA_CHECKS_SCHEMA")
        for key in ("output_sha256", "source_voice_sha256", "source_music_sha256"):
            s = spec()
            s["shorts"][0]["media_checks"][key] = "a" * 64
            self.assertBlocked(s)
        s = spec()
        s["shorts"][0]["media_checks"]["source_image_sha256"]["bg-sheltered-valley"] = "a" * 64
        self.assertBlocked(s, "MEDIA_SOURCE_HASH_MISMATCH")
        for date in ("2026-10-19T19:13:00Z", "2026-10-20T19:15:00Z", "2026-10-20T19:13:00"):
            s = spec()
            s["shorts"][0]["media_checks"]["measured_at"] = date
            self.assertBlocked(s)
        self.assertBlocked(spec(), "OUTPUT_SHA256_MISMATCH", sha="b" * 64)

    def test_false_pass_bad_acoustics_recomputed(self):
        mutations = {"leading_inactive_seconds": 0.301, "trailing_inactive_seconds": 0.301,
                     "first_active_sample": 14880, "last_active_sample": 1000, "narration_samples": 1910975,
                     "pcm_sample_rate": True, "window_samples": 481, "active_threshold_dbfs": -60,
                     "status": "FAIL"}
        for key, value in mutations.items():
            with self.subTest(key=key):
                s = spec()
                s["shorts"][0]["media_checks"]["acoustic"][key] = value
                self.assertBlocked(s)
        s = spec()
        a = s["shorts"][0]["media_checks"]["acoustic"]
        a.update(first_active_sample=14880, leading_inactive_seconds=0.31)
        self.assertBlocked(s, "ACOUSTIC_ONSET_OR_ENDING_FAIL")

    def test_false_pass_bad_video_recomputed(self):
        for key, value in {"decoded_frame_count": 1207, "fps": 29.97, "seconds": 40.4,
                           "expected_frame_count": True, "status": "FAIL", "black_intervals": [
                               {"start": 0, "end": 1 / 30, "duration": 1 / 30}]}.items():
            with self.subTest(key=key):
                s = spec()
                s["shorts"][0]["media_checks"]["video"][key] = value
                self.assertBlocked(s)
        for key in ("start_frame", "end_frame", "nominal_start_frame", "nominal_end_frame"):
            s = spec()
            s["shorts"][0]["media_checks"]["video"]["scene_frame_spans"][1][key] -= 10
            self.assertBlocked(s)
        for count in (1208, 1210):
            s = spec()
            s["shorts"][0]["media_checks"]["video"]["decoded_frame_count"] = count
            self.assertTrue(finish(s)["shorts"][0]["publish"])

    def test_scoped_scene_evidence_119_or_181_frames_and_missing_scene_fail(self):
        for count in (119, 181):
            for ending, start in (("nominal_end_frame", "nominal_start_frame"), ("end_frame", "start_frame")):
                for i in range(8):
                    with self.subTest(count=count, ending=ending, scene=i):
                        s = spec()
                        scene = s["shorts"][0]["media_checks"]["video"]["scene_frame_spans"][i]
                        scene[ending] = scene[start] + count
                        self.assertBlocked(s)
        for count in (7, 9):
            s = spec()
            spans = s["shorts"][0]["media_checks"]["video"]["scene_frame_spans"]
            if count == 7:
                spans.pop()
            else:
                spans.append(deepcopy(spans[-1]))
            self.assertBlocked(s)

    def test_caption_only_declaration_is_required_not_inferred_from_hook_flag(self):
        for value in (None, "overlay", True):
            s = spec()
            if value is None:
                del s["shorts"][0]["hook_mode"]
            else:
                s["shorts"][0]["hook_mode"] = value
            self.assertBlocked(s, "RECORD_HOOK_MODE_MISMATCH")

    def test_forged_qa_flags_missing_items_and_numbers(self):
        for key in ep.QA_CHECKS:
            s = spec()
            del s["shorts"][0]["qa"]["checks"][key]
            self.assertBlocked(s, "QA_CHECKS_SCHEMA")
        for key in ep.QA_CHECKS:
            s = spec()
            s["shorts"][0]["qa"]["checks"][key] = 1
            self.assertBlocked(s, "QA_CHECKS_SCHEMA")
        for key, value in (("lufs", -20), ("lufs", True), ("true_peak_dbtp", 0), ("seconds", 12)):
            s = spec()
            s["shorts"][0]["qa"][key] = value
            self.assertBlocked(s)
        s = spec()
        s["shorts"][0]["qa"]["checks"]["decode_clean"] = False
        self.assertBlocked(s, "QA_FALSE_STATUS")

    def test_qa_output_hash_missing_stale_or_forged_is_not_publishable(self):
        for value in (None, False, "a" * 64, "not a hash"):
            with self.subTest(value=value):
                s = spec()
                if value is None:
                    del s["shorts"][0]["qa_output_sha256"]
                else:
                    s["shorts"][0]["qa_output_sha256"] = value
                self.assertBlocked(s, "QA_OUTPUT_HASH_MISMATCH")
        s = spec()
        s["shorts"][0]["qa_output_sha256"] = "b" * 64
        s["shorts"][0]["review"]["output_sha256"] = "b" * 64
        self.assertBlocked(s, "QA_OUTPUT_HASH_MISMATCH")

    def test_review_recomputed_not_status_or_boolean(self):
        for item in (*ep.RUBRIC, "overall"):
            for value in (True, False, float("nan"), float("inf"), "8", -1, 11, 6):
                with self.subTest(item=item, value=value):
                    s = spec()
                    s["shorts"][0]["review"][item] = value
                    self.assertBlocked(s)
        s = spec()
        s["shorts"][0]["review"]["model"] = "gemini-other"
        self.assertBlocked(s, "UNDESIGNATED_REVIEW_MODEL")
        s = spec()
        del s["shorts"][0]["review"]["issues"]
        self.assertBlocked(s, "REVIEW_REPORT_MALFORMED")
        s = spec()
        s["review_rubric"]["pass_item"] = 6
        self.assertBlocked(s, "REVIEW_RUBRIC_MISMATCH")

    def test_review_hash_is_mandatory_for_pass_and_fail(self):
        for status in ("PASS", "FAIL"):
            for value in (None, False, "a" * 64, "not a hash"):
                with self.subTest(status=status, value=value):
                    s = spec()
                    r = s["shorts"][0]["review"]
                    if status == "FAIL":
                        r.update(status="FAIL", edit_rhythm=6)
                    if value is None:
                        del r["output_sha256"]
                    else:
                        r["output_sha256"] = value
                    self.assertBlocked(s, "REVIEW_OUTPUT_HASH_MISMATCH")

    def test_valid_editorial_fail_and_not_reviewed_preserved(self):
        s = spec()
        s["shorts"][0]["review"].update(edit_rhythm=6, status="FAIL")
        before = deepcopy(s["shorts"][0]["review"])
        result = finish(s)
        self.assertEqual(result["release_status"], "REVIEW_FAIL")
        self.assertEqual(result["finalization"]["status"], "COMPLETE")
        self.assertFalse(result["shorts"][0]["publish"])
        self.assertEqual(result["shorts"][0]["review"], before)
        for review in ({"status": "NOT_REVIEWED_NO_KEY"}, {"status": "NOT_REVIEWED_ProviderFailure", "output_sha256": OUTPUT_SHA,
                                                         "error_code": "UNKNOWN", "provider_diagnostic": {}}):
            s = spec()
            s["shorts"][0]["review"] = review
            result = finish(s)
            self.assertEqual(result["finalization"]["status"], "COMPLETE")
            self.assertEqual(result["release_status"], "REVIEW_NOT_REVIEWED")
            self.assertEqual(result["shorts"][0]["review"], review)

    def test_valid_qa_fail_preserved_without_review(self):
        s = spec()
        r = s["shorts"][0]
        r["qa"].update(status="FAIL", lufs=-20)
        r["qa"]["checks"]["loudness"] = False
        r["review"] = {"status": "NOT_REVIEWED_QA_FAIL"}
        result = finish(s)
        self.assertEqual(result["finalization"]["status"], "COMPLETE")
        self.assertEqual(result["release_status"], "QA_FAIL")
        self.assertFalse(result["shorts"][0]["publish"])

    def test_exactly_one_record_and_renderer_binding(self):
        for shorts in ([], [spec()["shorts"][0]] * 2, [None]):
            s = spec()
            s["shorts"] = shorts
            self.assertBlocked(s)
        for field, value in (("file", "../short-00.mp4"), ("source_start", 1404.681), ("hook_shown", False),
                             ("scenes", ["bg-garden"]), ("figure", True), ("render_plan", {})):
            s = spec()
            s["shorts"][0][field] = value
            self.assertBlocked(s)
        s = spec()
        s["shorts"][0]["previous_editorial_review"] = {"status": "FAIL"}
        self.assertBlocked(s, "PREVIOUS_FAILED_BYTES")
        s["shorts"][0]["previous_editorial_review"]["output_sha256"] = OUTPUT_SHA
        self.assertBlocked(s, "PREVIOUS_FAILED_BYTES")
        s["shorts"][0]["previous_editorial_review"]["output_sha256"] = "c" * 64
        self.assertTrue(finish(s)["shorts"][0]["publish"])


class MediaAndCliTests(unittest.TestCase):
    def setup_files(self, root):
        manifest = root / "shorts.json"
        manifest.write_text(json.dumps(spec()))
        mp4 = root / "short-00.mp4"
        mp4.write_bytes(b"synthetic output only")
        (root / "history.json").write_text(json.dumps(history()))
        return manifest, mp4

    def test_finalize_cli_hashes_actual_bytes_and_error_revokes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, mp4 = self.setup_files(root)
            # Wall-clock independent: patch only the real clock, never the guard/hash.
            class Clock(datetime):
                @classmethod
                def now(cls, tz):
                    return cls(2026, 10, 20, 19, 14, 59, tzinfo=tz)
            with patch.object(ep, "datetime", Clock), \
                    patch.object(ep, "finalize_manifest", wraps=ep.finalize_manifest) as guarded, \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(ep.cli(["--finalize", str(manifest), str(mp4)]), 0)
            self.assertTrue(json.loads(manifest.read_text())["shorts"][0]["publish"])
            self.assertEqual(guarded.call_args.kwargs["actual_output_sha256"], OUTPUT_SHA)
            manifest.write_text(json.dumps(spec()))
            mp4.write_bytes(b"changed actual output")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(ep.cli(["--finalize", str(manifest), str(mp4)]), 1)
            self.assertFalse(json.loads(manifest.read_text())["shorts"][0]["publish"])
            self.assertNotIn(str(root), output.getvalue())
            self.assertNotIn("changed actual output", output.getvalue())

    def test_any_finalize_exception_revokes_inherited_true(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, mp4 = self.setup_files(root)
            for failure in (OSError("secret path /private/key"), RuntimeError("secret provider body")):
                manifest.write_text(json.dumps(spec()))
                output = io.StringIO()
                with patch.object(ep, "hash_file", side_effect=failure), redirect_stdout(output):
                    self.assertEqual(ep.cli(["--finalize", str(manifest), str(mp4)]), 1)
                self.assertFalse(json.loads(manifest.read_text())["shorts"][0]["publish"])
                self.assertNotIn("secret", output.getvalue())
                self.assertNotIn(str(root), output.getvalue())

    def test_malformed_json_is_replaced_by_nonpublishable_tombstone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, mp4 = self.setup_files(root)
            for raw in ('{"shorts":[{"publish":true}],"x":NaN}',
                        '{"shorts":[{"publish":true}],"x":1,"x":2}',
                        '{"shorts":[{"publish":true}],"x":1e309}',
                        '{"shorts":[{"publish":true}],"secret":"never print me",'):
                manifest.write_text(raw)
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(ep.cli(["--finalize", str(manifest), str(mp4)]), 1)
                self.assertEqual(json.loads(manifest.read_text()),
                                 {"shorts": [], "publish": False, "release_status": "MALFORMED_EVIDENCE"})
                self.assertNotIn("never print me", output.getvalue())

    def test_invalid_cli_arity_also_revokes_identified_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self.setup_files(root)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ep.cli(["--finalize", str(manifest)]), 1)
            self.assertFalse(json.loads(manifest.read_text())["shorts"][0]["publish"])
            manifest.write_text(json.dumps(spec()))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ep.cli(["--check-media", str(root), str(root / "plan.json"), str(manifest)]), 1)
            self.assertFalse(json.loads(manifest.read_text())["shorts"][0]["publish"])

    def test_valid_review_failure_cli_preserves_reports_exit_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, mp4 = self.setup_files(root)
            original = spec()
            original["shorts"][0]["review"].update(status="FAIL", ending_and_loop=6)
            manifest.write_text(json.dumps(original))
            class Clock(datetime):
                @classmethod
                def now(cls, tz):
                    return cls(2026, 10, 20, 19, 14, 59, tzinfo=tz)
            with patch.object(ep, "datetime", Clock), redirect_stdout(io.StringIO()):
                self.assertEqual(ep.cli(["--finalize", str(manifest), str(mp4)]), 0)
            saved = json.loads(manifest.read_text())
            self.assertEqual(saved["release_status"], "REVIEW_FAIL")
            self.assertFalse(saved["shorts"][0]["publish"])
            self.assertEqual(saved["shorts"][0]["review"], original["shorts"][0]["review"])

    def test_check_media_wrong_file_hash_stops_before_subprocess(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self.setup_files(root)
            (root / "timeline.json").write_bytes((FIXTURE / "out" / "timeline.json").read_bytes())
            (root / "voice.flac").write_bytes(b"synthetic incorrect source")
            (root / "music.flac").write_bytes(b"synthetic incorrect music")
            for scene in plan()["scenes"]:
                (root / (scene["image_id"] + ".json")).write_text(json.dumps({"id": scene["image_id"], "sha256": scene["sha256"], "release_asset": scene["asset"]}))
                (root / (scene["image_id"] + ".png")).write_bytes(b"synthetic incorrect image")
            with patch.object(ep.subprocess, "run", side_effect=AssertionError("no decode before hash match")) as run:
                checks = ep.check_media(root, plan(), manifest, root / "voice.flac", root / "music.flac", root, root / "history.json")
            self.assertEqual(checks["status"], "FAIL")
            self.assertEqual(checks["output_sha256"], OUTPUT_SHA)
            self.assertEqual(checks["source_voice_sha256"], hashlib.sha256(b"synthetic incorrect source").hexdigest())
            self.assertEqual(run.call_count, 0)
            saved = json.loads(manifest.read_text())
            self.assertFalse(saved["shorts"][0]["publish"])
            self.assertEqual(saved["release_status"], "MEDIA_SOURCE_HASH_MISMATCH")

    def test_check_media_cli_sanitized_hash_bound_unpreserved_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self.setup_files(root)
            (root / "plan.json").write_text(PLAN_RAW)
            (root / "timeline.json").write_bytes(b"{}\n")
            output = io.StringIO()
            with redirect_stdout(output):
                result = ep.cli(["--check-media", str(root), str(root / "plan.json"), str(manifest),
                                 str(root / "voice.flac"), str(root / "music.flac"), str(root), str(root / "history.json")])
            self.assertEqual(result, 1)
            logged = json.loads(output.getvalue())
            self.assertEqual(logged["media_checks"]["output_sha256"], OUTPUT_SHA)
            self.assertEqual(logged["artifact_status"], "MP4_UNPRESERVED")
            self.assertEqual(logged["reason"], "INPUT_SHA256_MISMATCH")
            self.assertNotIn(str(root), output.getvalue())

    def test_pinned_history_contains_exactly_three_editorial_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            path.write_text(json.dumps(history()))
            before = path.read_bytes()
            hashes = ep.historical_failed_hashes(path)
            self.assertEqual(hashes, {
                "eb0646b09bd28a0623dcc32bdfe69aa3959111f522aff1f5797876f66caba74c",
                "19b9569e93d53d71e9d22026e4a0384414abcddf538bac1d3aa1b3c01273d8b7",
                "3588afa8468882e7f528d204f41bbb72a8b1b27b4f21b841ab634b20ebbf0dd7"})
            self.assertNotIn("cdb21f50a4aa431a2d662ebe409846816cee9a109da26bb2bbce3652df369d73", hashes)
            self.assertEqual(path.read_bytes(), before)

    def test_identical_historical_fail_stops_before_measurement_or_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, mp4 = self.setup_files(root)
            old = history()["historical_records"]["shorts"][0]["sha256"]
            latest = "3588afa8468882e7f528d204f41bbb72a8b1b27b4f21b841ab634b20ebbf0dd7"
            for failed in (old, latest):
                with self.subTest(failed=failed):
                    s = spec()
                    s["shorts"][0]["sha256"] = failed
                    manifest.write_text(json.dumps(s))
                    # No historic production media is downloaded. This digest spy
                    # tests the boundary after hashing the synthetic local MP4.
                    with patch.object(ep, "hash_file", return_value=failed) as hash_spy, \
                            patch.object(ep.subprocess, "run", side_effect=AssertionError("must stop before decoding")) as run, \
                            patch.object(selector, "rubric", side_effect=AssertionError("provider forbidden")) as provider:
                        measured = ep.check_media(root, plan(), manifest, root / "voice.flac", root / "music.flac", root,
                                                  root / "history.json")
                    hash_spy.assert_called_once_with(mp4)
                    self.assertEqual(run.call_count, 0)
                    self.assertEqual(provider.call_count, 0)
                    self.assertEqual(measured["output_sha256"], failed)
                    self.assertEqual(measured["status"], "FAIL")
                    saved = json.loads(manifest.read_text())
                    self.assertEqual(saved["release_status"], "HISTORICAL_EDITORIAL_FAIL_BYTES")
                    self.assertFalse(saved["shorts"][0]["publish"])

    def test_new_rejected_manifest_cannot_be_removed_replaced_or_relabelled(self):
        cases = []
        h = history()
        del h["new_reviews"]
        cases.append(h)
        cases.extend(dict(history(), new_reviews=value) for value in ([], {}, [None], [json.loads(NEW_REVIEW_RAW)] * 2))
        for key, value in (("sha256", "a" * 64), ("qa_output_sha256", "b" * 64), ("publish", True)):
            h = history()
            h["new_reviews"][0]["shorts"][0][key] = value
            cases.append(h)
        for key, value in (("status", "PASS"), ("output_sha256", "c" * 64), ("overall", 8.0)):
            h = history()
            h["new_reviews"][0]["shorts"][0]["review"][key] = value
            cases.append(h)
        h = history()
        h["new_reviews"][0]["shorts"][0]["media_checks"]["output_sha256"] = "d" * 64
        cases.append(h)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self.setup_files(root)
            for h in cases:
                manifest.write_text(json.dumps(spec()))
                (root / "history.json").write_text(json.dumps(h))
                with patch.object(ep.subprocess, "run", side_effect=AssertionError("no subprocess")) as run:
                    checks = ep.check_media(root, plan(), manifest, root / "voice.flac", root / "music.flac", root,
                                           root / "history.json")
                self.assertEqual(run.call_count, 0)
                self.assertEqual(checks["status"], "FAIL")
                saved = json.loads(manifest.read_text())
                self.assertFalse(saved["shorts"][0]["publish"])
                self.assertTrue(saved["release_status"].startswith("NEW_REVIEW_HISTORY_"))

    def test_missing_malformed_or_mismatched_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self.setup_files(root)
            path = root / "history.json"
            cases = [None, "not json", json.dumps({}), json.dumps(dict(history(), source_baseline_sha="a" * 40)),
                     json.dumps(dict(history(), source_sha256="a" * 64))]
            changed = history()
            changed["historical_records"]["shorts"][0]["review"]["status"] = "PASS"
            cases.append(json.dumps(changed))
            for raw in cases:
                with self.subTest(raw_type=type(raw).__name__):
                    manifest.write_text(json.dumps(spec()))
                    if raw is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_text(raw)
                    with patch.object(ep.subprocess, "run", side_effect=AssertionError("no subprocess")) as run:
                        checks = ep.check_media(root, plan(), manifest, root / "voice.flac", root / "music.flac", root, path)
                    self.assertEqual(checks["status"], "FAIL")
                    self.assertEqual(checks["output_sha256"], OUTPUT_SHA)
                    self.assertEqual(run.call_count, 0)
                    saved = json.loads(manifest.read_text())
                    self.assertFalse(saved["shorts"][0]["publish"])
                    self.assertTrue(saved["release_status"].startswith("HISTORICAL_ARCHIVE_"))

    def test_changed_pinned_fixture_raw_bytes_rejected_before_history_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self.setup_files(root)
            mutated = root / "fixture.json"
            mutated.write_bytes((FIXTURE / "shorts" / "shorts.json").read_bytes() + b"\n")
            with patch.object(ep, "HISTORY_FIXTURE", mutated), \
                    patch.object(ep.subprocess, "run", side_effect=AssertionError("no subprocess")):
                checks = ep.check_media(root, plan(), manifest, root / "voice.flac", root / "music.flac", root,
                                       root / "history.json")
            self.assertEqual(checks["status"], "FAIL")
            saved = json.loads(manifest.read_text())
            self.assertEqual(saved["release_status"], "HISTORICAL_FIXTURE_SHA256_MISMATCH")
            self.assertFalse(saved["shorts"][0]["publish"])

    def test_distinct_bytes_continue_to_existing_gates_not_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = self.setup_files(root)
            (root / "timeline.json").write_bytes(b"{}\n")
            self.assertNotIn(OUTPUT_SHA, ep.historical_failed_hashes(root / "history.json"))
            checks = ep.check_media(root, plan(), manifest, root / "voice.flac", root / "music.flac", root,
                                   root / "history.json")
            self.assertEqual(checks["output_sha256"], OUTPUT_SHA)
            self.assertEqual(checks["status"], "FAIL")
            saved = json.loads(manifest.read_text())
            self.assertEqual(saved["release_status"], "INPUT_SHA256_MISMATCH")
            self.assertFalse(saved["shorts"][0]["publish"])

    def test_video_measurement_synthetic_complete_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "synthetic.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "testsrc2=size=64x96:rate=30", "-frames:v", "1209", "-c:v", "libx264", "-preset", "ultrafast",
                            "-pix_fmt", "yuv420p", str(output)], check=True, capture_output=True)
            measured = ep.measure_video(output, plan(), ep.frame_plan(plan()))
            self.assertEqual(measured["status"], "PASS")
            self.assertEqual(measured["decoded_frame_count"], 1209)
            self.assertAlmostEqual(measured["seconds"], 40.3)
            self.assertEqual(measured["black_intervals"], [])

    def test_video_measurement_actual_black_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "synthetic.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "color=black:size=64x96:rate=30", "-frames:v", "1209", "-c:v", "libx264", "-preset", "ultrafast",
                            "-pix_fmt", "yuv420p", str(output)], check=True, capture_output=True)
            measured = ep.measure_video(output, plan(), ep.frame_plan(plan()))
            self.assertEqual(measured["status"], "FAIL")
            self.assertGreaterEqual(len(measured["black_intervals"]), 1)

    def test_single_black_frame_at_start_middle_and_eof_fails(self):
        # In particular d=1/30 alone has no final summary for a lone black EOF
        # frame. Its actual per-frame metadata must still close at frame 1209.
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "synthetic.mp4"
            for frame in (0, 600, 1208):
                with self.subTest(frame=frame):
                    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                                    "color=white:size=64x96:rate=30", "-vf",
                                    f"drawbox=color=black:t=fill:enable='eq(n,{frame})'", "-frames:v", "1209",
                                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(output)],
                                   check=True, capture_output=True)
                    measured = ep.measure_video(output, plan(), ep.frame_plan(plan()))
                    self.assertEqual(measured["status"], "FAIL")
                    self.assertEqual(len(measured["black_intervals"]), 1)
                    self.assertAlmostEqual(measured["black_intervals"][0]["duration"], 1 / 30, places=5)
                    self.assertAlmostEqual(measured["black_intervals"][0]["start"], frame / 30, places=5)

    def test_ffmpeg_6_1_six_significant_digit_metadata_uses_integer_frames(self):
        # FFmpeg 6.1 av_ts2timestr uses %.6g (upstream timestamp.h). These
        # source-backed log fixtures preserve exact frame counters/PTS and
        # intentionally reproduce its rounded times. No installed version or
        # test skip can hide the single-frame middle/EOF regressions.
        probe = subprocess.CompletedProcess([], 0, json.dumps({
            "streams": [{"nb_read_frames": "1209", "r_frame_rate": "30/1"}],
            "format": {"duration": "40.300000"}}).encode(), b"")
        for frame in (0, 600, 1208):
            with self.subTest(frame=frame):
                lines = [f"[Parsed_metadata_1 @ 0x1] frame:{frame} pts:{frame * 512} pts_time:{frame / 30:.6g}",
                         f"[Parsed_metadata_1 @ 0x1] lavfi.black_start={frame / 30:.6g}"]
                if frame < 1208:
                    lines.extend([f"[Parsed_metadata_1 @ 0x1] frame:{frame + 1} pts:{(frame + 1) * 512} pts_time:{(frame + 1) / 30:.6g}",
                                  f"[Parsed_metadata_1 @ 0x1] lavfi.black_end={(frame + 1) / 30:.6g}"])
                decoded = subprocess.CompletedProcess([], 0, b"", ("\n".join(lines) + "\n").encode())
                with patch.object(ep, "_run", side_effect=[probe, decoded]) as run:
                    measured = ep.measure_video("synthetic.mp4", plan(), ep.frame_plan(plan()))
                self.assertEqual(measured["status"], "FAIL")
                self.assertEqual(measured["black_intervals"], [
                    {"start": frame / 30, "end": (frame + 1) / 30, "duration": 1 / 30}])
                command = run.call_args_list[1].args[0]
                self.assertEqual(command[command.index("-vf") + 1],
                                 "blackdetect=d=0.03333333333333333:pix_th=0.02:pic_th=0.99,metadata=mode=print")

    def test_black_metadata_requires_consistent_integer_frame_identity(self):
        probe = subprocess.CompletedProcess([], 0, json.dumps({
            "streams": [{"nb_read_frames": "1209", "r_frame_rate": "30/1"}],
            "format": {"duration": "40.300000"}}).encode(), b"")
        logs = ["[Parsed_metadata_1 @ 0x1] lavfi.black_start=40.2667\n",
                "[Parsed_metadata_1 @ 0x1] frame:1208 pts:618496 pts_time:40.2667\n"
                "[Parsed_metadata_1 @ 0x1] lavfi.black_start=20\n",
                "[Parsed_metadata_1 @ 0x1] frame:1209 pts:619008 pts_time:40.3\n"
                "[Parsed_metadata_1 @ 0x1] lavfi.black_start=40.3\n"]
        for log in logs:
            decoded = subprocess.CompletedProcess([], 0, b"", log.encode())
            with patch.object(ep, "_run", side_effect=[probe, decoded]), \
                    self.assertRaisesRegex(ep.EvidenceError, "BLACKDETECT_PARSE_FAILED"):
                ep.measure_video("synthetic.mp4", plan(), ep.frame_plan(plan()))

    def test_media_probe_or_decode_failure_is_categorical(self):
        for reply in (subprocess.CompletedProcess([], 1, b"", b"secret path"),
                      subprocess.CompletedProcess([], 0, b"malformed", b"")):
            with patch.object(ep.subprocess, "run", return_value=reply), self.assertRaises(ep.EvidenceError) as raised:
                ep.measure_video("secret.mp4", plan(), ep.frame_plan(plan()))
            self.assertNotIn("secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
