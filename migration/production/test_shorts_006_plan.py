#!/usr/bin/env python3
"""Offline synthetic contracts, not media qualification or production evidence."""
from contextlib import contextmanager, ExitStack, redirect_stdout
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
import shorts_006_plan as ep

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
PLAN_HASH = "95624da1b4e4e4b256faee29fb37c8bc78fdb5c9747a3be86c69d9ec0e319905"
HISTORY_HASH = "4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677"
OUTPUT_BYTES = b"synthetic corrected file, not a video or a qualification"
OUTPUT_HASH = hashlib.sha256(OUTPUT_BYTES).hexdigest()


def sources():
    # Fully local synthetic timeline. Only contract-required endpoints and hook
    # match the pinned candidate; interior wording is deliberately synthetic.
    sentences = [{"segment": "earlier", "text": "Earlier synthetic sentence.", "start": i * 3., "end": i * 3. + 1.}
                 for i in range(191)]
    bounds = [(813.728, 815.669), (815.849, 817.791), (819.171, 821.155),
              (821.335, 824.343), (824.523, 826.443), (826.623, 831.081),
              (831.261, 834.525), (834.705, 836.135), (837.515, 846.389),
              (846.569, 850.559), (850.739, 852.915), (853.095, 854.417)]
    for i, (start, end) in enumerate(bounds):
        sentences.append({"segment": "sleep-relax-1" if i < 2 else "sleep-relax-2" if i < 8 else "sleep-relax-3",
                          "text": "Let your face soften." if i == 0 else f"Synthetic complete sentence {i}.",
                          "start": start, "end": end})
    sentences.append({"segment": "following", "text": "Following synthetic sentence.", "start": 855.797, "end": 858.0})
    script = {"pilot_id": "pilot-006", "segments": [{"id": ident, "reference": None}
              for ident in dict.fromkeys(s["segment"] for s in sentences)],
              "backgrounds": ["bg-still-water-night", "bg-healing-garden"]}
    return {"timeline": {"sentences": sentences}, "script": script,
            "inputs": {"voice_asset": ep.EXPECTED_PLAN["voice"]["asset"], "voice_sha256": ep.EXPECTED_PLAN["voice"]["sha256"]}}


def media_fixture(plan, docs):
    return {"version": "shorts-006-media-checks-v1", "plan_sha256": ep.PLAN_SHA256, "history_sha256": ep.HISTORY_SHA256,
        "source_sha256": deepcopy(plan["source_sha256"]), "output_sha256": OUTPUT_HASH,
        "source_voice_sha256": plan["voice"]["sha256"], "source_music_sha256": plan["music"]["sha256"],
        "source_image_sha256": {s["image_id"]: s["sha256"] for s in plan["scenes"]},
        "source_durations": {"voice_seconds": 1529.993333, "music_seconds": 10800., "voice_sample_rate": 24000, "voice_channels": 1},
        "measured_at": "2026-10-21T11:00:00+00:00", "status": "PASS",
        "acoustic": {"pcm_sample_rate": 48000, "window_samples": 480, "active_threshold_dbfs": -40.,
            "leading_inactive_seconds": .13, "trailing_inactive_seconds": .29, "first_active_sample": 6240,
            "last_active_sample": 1939200, "narration_samples": 1953120, "status": "PASS"},
        "video": {"decoded_frame_count": 1260, "fps": 30., "seconds": 42., "width": 1080, "height": 1920,
            "video_codec": "h264", "audio_codec": "aac", "audio_sample_rate": 48000, "audio_channels": 2,
            "decoded_audio_samples": 2016256, "presentation_audio_samples": 2016000,
            "first_pts": 0., "last_pts": 1259 / 30, "pts_uniform": True,
            "audio_packets": {"packet_count": 1970, "first_pts_samples": -1024, "skip_samples": 1024,
                "last_pts_samples": 2015232, "last_duration_samples": 768, "packet_clock_continuous": True, "codec_frame_samples": 1024},
            "black_intervals": [], "render_plan": ep.frame_plan(plan), "status": "PASS"},
        "editorial_metadata": ep._editorial_metadata(plan, docs)}


def manifest_fixture(plan, docs, media, media_hash):
    moment = ep.validate_plan(plan, docs["timeline"], docs["script"], docs["inputs"],
                              raw_sha256={k: plan["source_sha256"][k] for k in ("timeline", "script", "inputs")})["chosen"][0]
    qa = {"file": "short-00.mp4", "seconds": 42., "lufs": -14., "true_peak_dbtp": -2.,
          "checks": {k: True for k in ep.QA_CHECKS}, "status": "PASS"}
    review = {k: 9. for k in ep.RUBRIC}
    review.update(status="PASS", model="gemini-3.8-flash", overall=9., issues=[], strongest_moment="synthetic", output_sha256=OUTPUT_HASH)
    record = {"file": "short-00.mp4", "sha256": OUTPUT_HASH, "seconds": 42., "source_start": 813.728, "source_end": 854.417,
        "hook": "Let your face soften.", "title": "Rest in God's Care", "reference": None,
        "hook_mode": "caption_only", "hook_shown": True, "scenes": [s["image_id"] for s in plan["scenes"]],
        "figure": False, "parallax": False, "render_plan": ep.frame_plan(plan), "text": moment["text"], "segments": moment["segments"],
        "qa_output_sha256": OUTPUT_HASH, "qa": qa, "review": review, "media_checks": deepcopy(media), "media_checks_sha256": media_hash,
        "publish": False, "selection": {"final_score": None}}
    return {"source_pilot": "pilot-006", "edit_plan": deepcopy(plan), "shorts": [record],
            "review_rubric": {"items": list(ep.RUBRIC), "pass_item": 7, "pass_overall": 8}}


def _synthetic_long(pilot, script_hash):
    """Pass real long structural validators using explicitly synthetic evidence."""
    gate_module = ep.shorts_prerequisite.binding.canonical_gate
    identities = {name: {(kind, key) for kind, keys in spec.items() for key in keys}
                  for name, spec in gate_module.DIMENSIONS_V3.items()}
    identities["content_and_policy"].add(("review", "overall"))
    identities.update({"binding": {("binding", k) for k in ("manifest", "qa_for_this_file", "qa_criteria_frozen", "review_for_this_file")},
        "scorecard": {("score", k) for k in gate_module.SCORE_HARD}, "full_file_scan": {("scan", "synthetic")},
        "preflight": {("preflight", "preflight")}, "structure": {("structure", "synthetic")}, "authenticity": {("authenticity", "synthetic")}})
    gate = {"version": "prepublish-gate-v1", "decision": "PASS", "eligible_for_automatic_publication": True,
        "output_sha256": "a" * 64, "dimensions": {k: "PASS" for k in identities},
        "items": {k: [{"source": source, "item": item, "state": "PASS"} for source, item in sorted(values)] for k, values in identities.items()}}
    docs = {"out/manifest.json": {"output_sha256": "a" * 64, "script_sha256": script_hash},
        "out/review.json": {"status": "PASS", "output_sha256": "a" * 64},
        "out/qa.json": {"status": "PASS", "output_sha256": "a" * 64, "criteria_version": "pilot-qa-criteria-v3",
                        "criteria_sha256": gate_module.FROZEN_CRITERIA_SHA256["pilot-qa-criteria-v3"]},
        "out/gate.json": gate, "inspection/APPROVAL.json": {"approved": True, "output_sha256": "a" * 64}}
    for name, doc in docs.items():
        (pilot / name).parent.mkdir(parents=True, exist_ok=True)
        ep.atomic_json(pilot / name, doc)


@contextmanager
def synthetic_environment(root, *, media_sources=False):
    """Integration fixture: actual files and actual binding, only code pins replaced.

    Patches are confined to in-process tests. No production file is read as a
    positive expected answer, and the fake MP4 is never passed to a reviewer.
    """
    pilot = Path(root) / "production/pilot-006"
    (pilot / "shorts").mkdir(parents=True)
    (pilot / "out").mkdir()
    docs = sources()
    paths = {"script": "script.json", "timeline": "out/timeline.json", "inputs": "shorts/inputs.json", "images": "images.json"}
    docs["images"] = {"synthetic": True}
    for key, relative in paths.items():
        ep.atomic_json(pilot / relative, docs[key])
    _synthetic_long(pilot, ep.hash_file(pilot / "script.json"))
    paths.update(long_manifest="out/manifest.json", long_review="out/review.json")
    plan = deepcopy(ep.EXPECTED_PLAN)
    if media_sources:
        assets = Path(root) / "assets"
        assets.mkdir()
        for name in ("voice", "music"):
            path = assets / (name + ".flac")
            path.write_bytes(("synthetic " + name).encode())
            plan[name]["sha256"] = ep.hash_file(path)
        docs["inputs"]["voice_sha256"] = plan["voice"]["sha256"]
        ep.atomic_json(pilot / "shorts/inputs.json", docs["inputs"])
        for scene in plan["scenes"]:
            image = assets / (scene["image_id"] + ".png")
            image.write_bytes(("synthetic " + scene["image_id"]).encode())
            scene["sha256"] = ep.hash_file(image)
            ep.atomic_json(image.with_suffix(".json"), {"id": scene["image_id"], "release_asset": scene["asset"],
                "sha256": scene["sha256"], "models": {"synthetic": {"license": "test only"}}})
    plan["source_sha256"] = {key: ep.hash_file(pilot / relative) for key, relative in paths.items()}
    history = {"source_pilot": "pilot-006", "shorts": [
        {"file": f"short-{i:02d}.mp4", "sha256": ep.REJECTED_SHA256 if i == 0 else str(i) * 64,
         "review": {"status": "FAIL" if i == 0 else "NOT_REVIEWED_ProviderFailure"}, "publish": False} for i in range(3)]}
    history_path = pilot / "shorts/correction-history.json"
    ep.atomic_json(history_path, history)
    history_hash = ep.hash_file(history_path)
    plan["history"]["sha256"] = history_hash
    plan_path = pilot / "shorts/correction-plan.json"
    ep.atomic_json(plan_path, plan)
    plan_hash = ep.hash_file(plan_path)
    with ExitStack() as stack:
        for name, value in (("CANONICAL_PILOT", pilot), ("EXPECTED_PLAN", plan), ("PLAN_SHA256", plan_hash), ("HISTORY_SHA256", history_hash)):
            stack.enter_context(patch.object(ep, name, value))
        docs = ep._sources(pilot)
        media = media_fixture(plan, docs)
        ep.atomic_json(pilot / "shorts" / ep.MEDIA_FILE, media)
        media_hash = ep.hash_file(pilot / "shorts" / ep.MEDIA_FILE)
        spec = manifest_fixture(plan, docs, media, media_hash)
        spec = ep.finalize_manifest(spec, actual_output_sha256=OUTPUT_HASH, now_utc=NOW,
            media_checks=media, media_sha256=media_hash, contract=ep._contract())
        ep.atomic_json(pilot / "shorts/shorts.json", spec)
        (pilot / "shorts/short-00.mp4").write_bytes(OUTPUT_BYTES)
        yield {"pilot": pilot, "spec": spec, "plan": plan, "docs": docs, "media": media,
               "media_hash": media_hash, "plan_hash": plan_hash, "history_hash": history_hash}


class PlanTests(unittest.TestCase):
    def test_literal_plan_digest_and_arithmetic(self):
        raw = (json.dumps(ep.EXPECTED_PLAN, ensure_ascii=False, indent=2) + "\n").encode()
        self.assertEqual(len(raw), 3489)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PLAN_HASH)
        self.assertEqual(ep.PLAN_SHA256, PLAN_HASH)
        self.assertEqual(ep.HISTORY_SHA256, HISTORY_HASH)
        p = ep.EXPECTED_PLAN
        self.assertAlmostEqual(p["candidate"]["end"] - p["candidate"]["start"], 40.689)
        self.assertAlmostEqual(p["audio"]["source_end"] - p["audio"]["source_start"], 40.690)
        self.assertEqual(p["audio"]["resampled_source_samples"] + p["audio"]["padding_samples"], 2016000)
        self.assertEqual(ep.frame_plan(p)["expected_frame_count"], 1260)
        self.assertEqual([(s["start_frame"], s["end_frame"]) for s in ep.frame_plan(p)["scene_frame_spans"]], [(0, 637), (622, 1260)])

    def test_closed_recursive_schema(self):
        for path, value in [(('fps',), True), (('fps',), float('nan')), (('audio', 'source_end'), 854.417),
                            (('candidate', 'hook'), 'Let your face soften. He will not.'), (('scenes', 0, 'atmosphere', 'envelope'), .5),
                            (('source_pilot',), 'pilot-005'), (('tail_seconds',), 1.13)]:
            p = deepcopy(ep.EXPECTED_PLAN); obj = p
            for key in path[:-1]: obj = obj[key]
            obj[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ep.EvidenceError): ep.validate_plan_schema(p)
        p = deepcopy(ep.EXPECTED_PLAN); p['audio']['extra'] = 1
        with self.assertRaises(ep.EvidenceError): ep.validate_plan_schema(p)

    def test_old_plan_and_opening_profile_rejected(self):
        old = deepcopy(ep.EXPECTED_PLAN)
        old['candidate'].update(start=1311.607, end=1346.297,
                                hook='You can let go.', title='His Peace Stands Watch Over You',
                                reference='Philippians 4:6-7 (KJV)')
        old['audio'].update(source_start=1311.607, source_end=1346.477,
                            source_samples=836880, resampled_source_samples=1673760,
                            padding_samples=54240, output_samples=1728000,
                            fade_start=34.87, fade_seconds=1.13)
        old.update(tail_seconds=1.13, narrative_tail_seconds=1.31, output_seconds=36.0)
        old['music']['source_start'] = 2511.607
        old['scenes'][0]['nominal_end'] = 18.0
        old['scenes'][0]['atmosphere'].pop('opening_profile')
        old['scenes'][1].update(nominal_start=18.0, nominal_end=36.0)
        raw = (json.dumps(old, ensure_ascii=False, indent=2) + '\n').encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '1c52034ce611b8a30c9d92ce22e9b6ce8f7cbff14b803a44ff8e7d1eb4991c57')
        with self.assertRaisesRegex(ep.EvidenceError, 'INVALID_CORRECTION_PLAN'):
            ep.validate_plan_schema(old)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'old-plan.json'; path.write_bytes(raw)
            with self.assertRaisesRegex(ep.EvidenceError, 'PLAN_RAW_SHA256_MISMATCH'):
                ep._plan_file(path)
        for change in ('missing', 'wrong', 'second_scene'):
            p = deepcopy(ep.EXPECTED_PLAN)
            if change == 'missing': p['scenes'][0]['atmosphere'].pop('opening_profile')
            elif change == 'wrong': p['scenes'][0]['atmosphere']['opening_profile'] = 'unapproved'
            else: p['scenes'][1]['atmosphere']['opening_profile'] = 'source_atmosphere_hook_v1'
            with self.subTest(change=change), self.assertRaises(ep.EvidenceError):
                ep.validate_plan_schema(p)

    def test_frozen_acoustic_point_three_boundary(self):
        p = ep.EXPECTED_PLAN
        acoustic = media_fixture(p, sources())['acoustic']
        for side in ('leading', 'trailing'):
            for seconds, passes in ((.3, True), (.31, False)):
                a = deepcopy(acoustic)
                a[side + '_inactive_seconds'] = seconds
                if side == 'leading': a['first_active_sample'] = round(seconds * 48000)
                else: a['last_active_sample'] = a['narration_samples'] - round(seconds * 48000)
                # Last active sample must align with the unchanged 10ms RMS bins.
                if side == 'trailing':
                    a['last_active_sample'] = (a['last_active_sample'] // 480) * 480
                    a['trailing_inactive_seconds'] = (a['narration_samples'] - a['last_active_sample']) / 48000
                with self.subTest(side=side, seconds=seconds):
                    if passes: ep._validate_acoustic(a, p)
                    else:
                        with self.assertRaisesRegex(ep.EvidenceError, 'ACOUSTIC_ONSET_OR_ENDING_FAIL'):
                            ep._validate_acoustic(a, p)

    def test_unpreserved_failed_output_never_qualifies(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            spec = deepcopy(f['spec']); spec['shorts'][0]['sha256'] = ep.UNPRESERVED_FAIL_SHA256
            with self.assertRaisesRegex(ep.EvidenceError, 'OUTPUT_SHA256_MISMATCH'):
                ep._bind_record(spec, f['plan'], spec['shorts'][0], ep.UNPRESERVED_FAIL_SHA256, sources())

    def test_selection_reconstructs_twelve_sentences(self):
        docs = sources(); p = deepcopy(ep.EXPECTED_PLAN)
        result = ep.validate_plan(p, docs['timeline'], docs['script'], docs['inputs'],
                                 raw_sha256={k: p['source_sha256'][k] for k in ('timeline', 'script', 'inputs')})
        chosen = result['chosen'][0]
        self.assertEqual(len(result['chosen']), 1); self.assertEqual(len(chosen['sentences']), 12)
        self.assertEqual(chosen['sentences'][-1]['end'], 854.417)
        self.assertNotIn('Following synthetic sentence.', chosen['text'])
        self.assertIsNone(chosen['reference'])
        self.assertAlmostEqual(chosen['sentences'][0]['end'] - chosen['start'], 1.941)
        for change in ('first', 'next', 'reference', 'hash'):
            d = deepcopy(docs); hashes = {k: p['source_sha256'][k] for k in ('timeline', 'script', 'inputs')}
            if change == 'first': d['timeline']['sentences'][191]['text'] = 'Different.'
            elif change == 'next': d['timeline']['sentences'][203]['start'] = 854.5
            elif change == 'reference': d['script']['segments'][2]['reference'] = 'Wrong'
            else: hashes['script'] = '0' * 64
            with self.subTest(change=change), self.assertRaises(ep.EvidenceError):
                ep.validate_plan(p, d['timeline'], d['script'], d['inputs'], raw_sha256=hashes)

    def test_duplicate_and_nonfinite_json_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'input.json'
            for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}'):
                p.write_text(raw)
                with self.assertRaises(ValueError): ep.read_json(p)

    def test_preflight_single_attempt_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            pilot = f['pilot']; manifest = pilot / 'shorts/shorts.json'; history = pilot / 'shorts/correction-history.json'; plan = pilot / 'shorts/correction-plan.json'
            manifest.write_bytes(history.read_bytes())
            self.assertEqual(ep.preflight(pilot, plan, history), f['plan'])
            for raw in [b'{bad', *[(json.dumps({'review': {'status': status}}) + '\n').encode() for status in ('PASS', 'FAIL', 'NOT_REVIEWED_ProviderFailure')]]:
                manifest.write_bytes(raw)
                with self.assertRaisesRegex(ep.EvidenceError, 'CANONICAL_ATTEMPT_ALREADY_CHANGED'): ep.preflight(pilot, plan, history)
            manifest.write_bytes(history.read_bytes())
            alias = Path(tmp) / 'alias'; alias.symlink_to(pilot, target_is_directory=True)
            with self.assertRaisesRegex(ep.EvidenceError, 'UNSAFE_PATH'): ep.preflight(alias, plan, history)
            with self.assertRaisesRegex(ep.EvidenceError, 'UNSAFE_PATH'): ep.preflight(pilot / '..' / 'pilot-006', plan, history)
            original = plan.read_bytes(); plan.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ep.EvidenceError, 'PLAN_RAW'): ep.preflight(pilot, plan, history)
            plan.write_bytes(original); (pilot / 'script.json').write_text('{}')
            with self.assertRaisesRegex(ep.EvidenceError, 'SOURCE_PIN'): ep.preflight(pilot, plan, history)

    def test_bound_nine_pass_and_nested_forgeries(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            def bind(spec): return ep.binding(spec, plan_sha256=f['plan_hash'], history_sha256=f['history_hash'])
            self.assertEqual(bind(f['spec'])['output_sha256'], OUTPUT_HASH)
            self.assertEqual(f['spec']['finalization']['status'], 'COMPLETE')
            self.assertEqual(f['spec']['release_status'], 'READY')
            mutations = [lambda s: s['shorts'][0]['qa'].update(status='FAIL'),
                lambda s: s['shorts'][0]['review'].update(overall=8.99),
                lambda s: s['shorts'][0]['media_checks']['video'].update(decoded_frame_count=1259),
                lambda s: s['shorts'][0].update(media_checks_sha256='0'*64),
                lambda s: s['finalization'].update(kind='wrong'), lambda s: s.update(review_recovery={}),
                lambda s: s['finalization'].update(owner_exception={}), lambda s: s['edit_plan'].update(source_pilot='pilot-005'),
                lambda s: s['shorts'].append(deepcopy(s['shorts'][0])), lambda s: s['shorts'][0].update(sha256=ep.REJECTED_SHA256),
                lambda s: s['shorts'][0].update(text='changed'), lambda s: s['finalization'].update(extra='no'),
                lambda s: s['shorts'][0]['review'].update(output_sha256='b'*64)]
            for mutate in mutations:
                spec = deepcopy(f['spec']); mutate(spec)
                with self.subTest(spec=spec.get('finalization')), self.assertRaises((ValueError, KeyError, TypeError)): bind(spec)
            media_path = f['pilot'] / 'shorts' / ep.MEDIA_FILE
            media_path.write_bytes(media_path.read_bytes() + b'\n')
            with self.assertRaisesRegex(ep.EvidenceError, 'MEDIA_FILE_BINDING'): bind(f['spec'])

    def test_legitimate_negatives_complete_not_publishable(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            for kind in ('qa', 'review', 'floor', 'provider', 'no_key', 'late'):
                spec = deepcopy(f['spec']); rec = spec['shorts'][0]; now = NOW
                if kind == 'qa':
                    rec['qa']['checks']['decode_clean'] = False; rec['qa']['status'] = 'FAIL'; rec['review'] = {'status': 'NOT_REVIEWED_QA_FAIL'}
                elif kind == 'review': rec['review']['edit_rhythm'] = 6.5; rec['review']['status'] = 'FAIL'
                elif kind == 'floor': rec['review']['overall'] = 8.99
                elif kind == 'provider': rec['review'] = {'status': 'NOT_REVIEWED_ProviderFailure', 'output_sha256': OUTPUT_HASH}
                elif kind == 'no_key': rec['review'] = {'status': 'NOT_REVIEWED_NO_KEY'}
                else: now = datetime(2026, 10, 21, 13, 15, 1, tzinfo=timezone.utc)
                original = deepcopy(rec.get('review'))
                result = ep.finalize_manifest(spec, actual_output_sha256=OUTPUT_HASH, now_utc=now,
                    media_checks=f['media'], media_sha256=f['media_hash'], contract=ep._contract())
                with self.subTest(kind=kind):
                    self.assertEqual(result['finalization']['status'], 'COMPLETE', result['release_status'])
                    self.assertFalse(result['shorts'][0]['publish']); self.assertNotEqual(result['release_status'], 'READY')
                    self.assertEqual(result['shorts'][0]['review'], original)

    def test_deadline_inclusive(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            result = ep.finalize_manifest(f['spec'], actual_output_sha256=OUTPUT_HASH,
                now_utc='2026-10-21T13:15:00Z', media_checks=f['media'], media_sha256=f['media_hash'], contract=ep._contract())
            self.assertEqual(result['release_status'], 'READY')

    def test_integrity_errors_and_file_cli_exit_semantics(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            path = f['pilot'] / 'shorts/shorts.json'; mp4 = path.parent / 'short-00.mp4'
            for kind in ('pass', 'qa', 'review', 'floor', 'provider', 'missing_review', 'wrong_hash', 'changed_bytes', 'second'):
                spec = deepcopy(f['spec']); mp4.write_bytes(OUTPUT_BYTES); rec = spec['shorts'][0]
                if kind == 'qa': rec['qa']['checks']['decode_clean'] = False; rec['qa']['status'] = 'FAIL'
                elif kind == 'review': rec['review']['overall'] = 7.; rec['review']['status'] = 'FAIL'
                elif kind == 'floor': rec['review']['overall'] = 8.99
                elif kind == 'provider': rec['review'] = {'status': 'NOT_REVIEWED_ProviderFailure'}
                elif kind == 'missing_review': rec.pop('review')
                elif kind == 'wrong_hash': rec['qa_output_sha256'] = 'b' * 64
                elif kind == 'changed_bytes': mp4.write_bytes(b'changed')
                elif kind == 'second': spec['shorts'].append(deepcopy(rec))
                ep.atomic_json(path, spec)
                with patch.object(ep, 'datetime') as clock, redirect_stdout(io.StringIO()):
                    clock.now.return_value = NOW
                    code = ep.cli(['--finalize', str(path), str(mp4)])
                result, _ = ep.read_json(path)
                expected = 0 if kind in ('pass', 'qa', 'review', 'floor', 'provider') else 1
                with self.subTest(kind=kind):
                    self.assertEqual(code, expected, result)
                    self.assertEqual(result['finalization']['status'], 'COMPLETE' if expected == 0 else 'ERROR')
                    self.assertEqual(result['shorts'][0]['publish'], kind == 'pass')

    def test_acoustic_extraction_uses_segment_not_narrative_end(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            acoustic = deepcopy(f['media']['acoustic'])
            ep._validate_acoustic(acoustic, f['plan'])
            for count in (1939200, 2016000, True):
                acoustic['narration_samples'] = count
                with self.assertRaises(ep.EvidenceError): ep._validate_acoustic(acoustic, f['plan'])
            intervals = f['media']['editorial_metadata']['caption_source_intervals']
            self.assertEqual(intervals[-1]['end'], 40.689)
            self.assertLess(max(s['end'] for s in intervals), f['plan']['audio']['fade_start'])

    def test_pcm_padding_requires_packet_clock_evidence(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            for samples in (2016000, 2016256):
                v = deepcopy(f['media']['video']); v['decoded_audio_samples'] = samples
                ep._validate_video(v, f['plan'])
            for key, value in [('decoded_audio_samples', 2016257), ('presentation_audio_samples', 2016256), ('pts_uniform', False),
                               ('last_pts', 42), ('black_intervals', [{'start_frame':1259, 'end_frame':1260}])]:
                v = deepcopy(f['media']['video']); v[key] = value
                with self.subTest(key=key), self.assertRaises(ep.EvidenceError): ep._validate_video(v, f['plan'])
            v = deepcopy(f['media']['video']); v['audio_packets']['last_duration_samples'] = 1024
            with self.assertRaises(ep.EvidenceError): ep._validate_video(v, f['plan'])

    def test_check_media_preflight_blocks_changed_canonical_before_measurement(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            pilot = f['pilot']; work = Path(tmp) / 'work'; work.mkdir()
            path = work / 'shorts.json'; ep.atomic_json(path, f['spec'])
            with patch.object(ep, '_run') as measure, patch.object(ep, 'source_durations') as durations:
                result = ep.check_media(pilot / 'out', pilot / 'shorts/correction-plan.json', path,
                    Path(tmp) / 'voice.flac', Path(tmp) / 'music.flac', Path(tmp), pilot / 'shorts/correction-history.json')
            self.assertEqual(result['status'], 'FAIL'); measure.assert_not_called(); durations.assert_not_called()
            result_spec, _ = ep.read_json(path)
            self.assertEqual(result_spec['release_status'], 'CANONICAL_ATTEMPT_ALREADY_CHANGED')
            self.assertFalse(result_spec['shorts'][0]['publish'])
            self.assertEqual(result_spec['shorts'][0]['media_checks'], ep.read_json(work / ep.MEDIA_FILE)[0])

    def test_check_media_synthetic_primitive_measurements_bind_exact_file(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp, media_sources=True) as f:
            pilot = f['pilot']; canonical = pilot / 'shorts/shorts.json'
            canonical.write_bytes((pilot / 'shorts/correction-history.json').read_bytes())
            work = Path(tmp) / 'work'; work.mkdir(); path = work / 'shorts.json'
            ep.atomic_json(path, f['spec']); (work / 'short-00.mp4').write_bytes(OUTPUT_BYTES)
            assets = Path(tmp) / 'assets'
            pcm = b'\x00\x00' * 6240 + b'\xff\x7f' * (1939200 - 6240) + b'\x00\x00' * 13920
            result = subprocess.CompletedProcess([], 0, stdout=pcm, stderr=b'')
            with patch.object(ep, '_run', return_value=result) as run, \
                 patch.object(ep, 'source_durations', return_value=f['media']['source_durations']), \
                 patch.object(ep, 'measure_video', return_value=f['media']['video']):
                measured = ep.check_media(pilot / 'out', pilot / 'shorts/correction-plan.json', path,
                    assets / 'voice.flac', assets / 'music.flac', assets, pilot / 'shorts/correction-history.json')
            self.assertEqual(measured['status'], 'PASS', ep.read_json(path)[0].get('release_status'))
            self.assertEqual(measured['acoustic']['narration_samples'], 1953120)
            command = run.call_args.args[0]
            self.assertEqual(command[command.index('-t') + 1], '40.690')
            recorded, _ = ep.read_json(path); sidecar, digest = ep.read_json(work / ep.MEDIA_FILE)
            self.assertEqual(recorded['shorts'][0]['media_checks'], sidecar)
            self.assertEqual(recorded['shorts'][0]['media_checks_sha256'], digest)
            self.assertFalse(recorded['shorts'][0]['publish'])

    def test_check_media_integrity_negatives_before_measurement(self):
        for kind in ('missing_history', 'bad_plan', 'source_changed', 'old_fail', 'changed_output', 'symlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp, media_sources=True) as f:
                pilot = f['pilot']; canonical = pilot / 'shorts/shorts.json'; history = pilot / 'shorts/correction-history.json'
                canonical.write_bytes(history.read_bytes())
                work = Path(tmp) / 'work'; work.mkdir(); path = work / 'shorts.json'; spec = deepcopy(f['spec'])
                output = work / 'short-00.mp4'; output.write_bytes(OUTPUT_BYTES)
                assets = Path(tmp) / 'assets'; plan = pilot / 'shorts/correction-plan.json'
                if kind == 'missing_history': history.unlink()
                elif kind == 'bad_plan': plan.write_bytes(plan.read_bytes() + b'\n')
                elif kind == 'source_changed': (assets / 'voice.flac').write_bytes(b'changed')
                elif kind == 'old_fail': spec['shorts'][0]['sha256'] = ep.REJECTED_SHA256
                elif kind == 'changed_output': output.write_bytes(b'changed output')
                else:
                    output.unlink(); output.symlink_to(pilot / 'shorts/short-00.mp4')
                ep.atomic_json(path, spec)
                with patch.object(ep, '_run') as run:
                    result = ep.check_media(pilot / 'out', plan, path, assets / 'voice.flac', assets / 'music.flac', assets, history)
                self.assertEqual(result['status'], 'FAIL'); run.assert_not_called()
                self.assertFalse(ep.read_json(path)[0]['shorts'][0]['publish'])

    def test_source_duration_requires_full_extraction_and_bed(self):
        with tempfile.TemporaryDirectory() as tmp:
            voice = Path(tmp) / 'voice.flac'; music = Path(tmp) / 'music.flac'
            voice.touch(); music.touch()
            def info(seconds, rate=24000, channels=1):
                return {'streams':[{'codec_type':'audio', 'sample_rate': str(rate), 'channels':channels}], 'format':{'duration':str(seconds)}}
            for vs, ms, rate in [(854.418, 2055.728, 24000), (854.417, 10800, 24000), (1530, 2055.727, 24000), (1530, 10800, 48000)]:
                with patch.object(ep, '_probe', side_effect=[info(vs, rate), info(ms)]):
                    if (vs, ms, rate) == (854.418, 2055.728, 24000):
                        self.assertEqual(ep.source_durations(voice, music, ep.EXPECTED_PLAN)['voice_sample_rate'], 24000)
                    else:
                        with self.assertRaises(ep.EvidenceError): ep.source_durations(voice, music, ep.EXPECTED_PLAN)

    def test_audio_packet_evidence_discontinuous_or_extra_content(self):
        packets = [{'pts':(i-1)*1024, 'duration':768 if i ==1969 else 1024} for i in range(1970)]
        packets[0]['side_data_list'] = [{'side_data_type':'Skip Samples', 'skip_samples':1024, 'discard_padding':0}]
        for kind in ('good', 'extra_content', 'discontinuity', 'missing_skip'):
            copy = deepcopy(packets)
            if kind == 'extra_content': copy[-1]['duration'] = 1024
            elif kind == 'discontinuity': copy[800]['pts'] += 1
            elif kind == 'missing_skip': copy[0].pop('side_data_list')
            response = subprocess.CompletedProcess([], 0, stdout=json.dumps({'packets':copy}).encode(), stderr=b'')
            with patch.object(ep, '_run', return_value=response):
                if kind == 'good': self.assertEqual(ep._audio_packets('synthetic.mp4', {'time_base':'1/48000'})['last_duration_samples'], 768)
                else:
                    with self.assertRaises(ep.EvidenceError): ep._audio_packets('synthetic.mp4', {'time_base':'1/48000'})

    def test_finalization_rejects_nested_authority_and_unreadable_media(self):
        with tempfile.TemporaryDirectory() as tmp, synthetic_environment(tmp) as f:
            spec = deepcopy(f['spec']); spec['finalization']['owner_exception'] = {}
            result = ep.finalize_manifest(spec, actual_output_sha256=OUTPUT_HASH, now_utc=NOW,
                media_checks=f['media'], media_sha256=f['media_hash'], contract=ep._contract())
            self.assertEqual(result['release_status'], 'MIXED_AUTHORITY')
            path = f['pilot'] / 'shorts/shorts.json'; output = path.parent / 'short-00.mp4'
            output.unlink()
            with patch.object(ep, 'datetime') as clock, redirect_stdout(io.StringIO()):
                clock.now.return_value = NOW
                self.assertEqual(ep.cli(['--finalize', str(path), str(output)]), 1)
            result, _ = ep.read_json(path)
            self.assertEqual(result['finalization']['status'], 'ERROR'); self.assertFalse(result['shorts'][0]['publish'])
            path.write_bytes(b'{broken')
            with patch.object(ep, 'datetime') as clock, redirect_stdout(io.StringIO()):
                clock.now.return_value = NOW
                self.assertEqual(ep.cli(['--finalize', str(path), str(output)]), 1)
            self.assertEqual(ep.read_json(path)[0]['finalization']['status'], 'ERROR')

    def test_real_synthetic_aac_clock_and_final_black_frame(self):
        # Tiny local fixtures: this is not production, and not editorial evidence.
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / 'synthetic.m4a'
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'lavfi',
                '-i', 'sine=frequency=440:sample_rate=48000:duration=42', '-ac', '2', '-threads', '1',
                '-c:a', 'aac', '-b:a', '160k', '-t', '42', str(audio)], check=True, capture_output=True)
            stream = ep._probe(audio)['streams'][0]
            self.assertEqual(stream['duration_ts'], 2016000)
            packets = ep._audio_packets(audio, stream)
            self.assertEqual(packets['last_duration_samples'], 768)
            pcm = ep._run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(audio), '-f', 's16le', '-acodec', 'pcm_s16le', 'pipe:1'])
            self.assertIn(len(pcm.stdout) // 4, (2016000, 2016256))
            video = Path(tmp) / 'last-black.mkv'
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-filter_complex_threads', '1',
                '-f', 'lavfi', '-i', 'color=white:s=64x64:r=30:d=0.0333333333',
                '-f', 'lavfi', '-i', 'color=black:s=64x64:r=30:d=0.0333333333',
                '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-an',
                '-frames:v', '2', '-threads', '1', '-c:v', 'ffv1', str(video)], check=True, capture_output=True)
            self.assertEqual(ep._black_intervals(video, 2), [{'start_frame': 1, 'end_frame': 2}])

    def test_no_005_validators_or_provider_import(self):
        import ast
        tree = ast.parse(Path(ep.__file__).read_text())
        imported = [alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module == 'shorts_edit_plan' for alias in node.names]
        self.assertFalse(set(imported) & {'measure_video', '_validate_video', '_validate_acoustic', 'validate_media_checks', 'validate_plan_schema', 'frame_plan'})
        self.assertNotIn('shorts_review', sys.modules)


if __name__ == '__main__':
    unittest.main()
