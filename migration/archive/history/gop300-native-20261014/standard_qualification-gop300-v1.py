from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .qa_phase5 import _black_freeze_scan, _loudness, _probe


FFMPEG = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = shutil.which("ffprobe") or r"C:\ffmpeg\bin\ffprobe.exe"
V3 = Path("output/production/phase5/pilot-001/creative-v3")


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode:
        raise RuntimeError("\n".join(result.stderr.splitlines()[-80:]))
    return result


def read_audio_static_codec_controls(root: Path, package: Path, *, binding: dict[str, str],
                                     music_bindings: dict | None = None) -> dict[str, Any]:
    """Read an externally anchored completed control set, never caller PASS."""
    from .native_gop300_bridge import offered as _gop300_offered
    if _gop300_offered(binding):
        from .native_gop300_bridge import read_controls as _gop300_read
        return _gop300_read(root, package, binding=binding, music_bindings=music_bindings, expected_bridge_sha256='e293cfe48dd8cf0f7bebcbe99ea65239a1e37b369d9221a94f68344f5acd783b')
    from .phase6_visual_metrics import calibrate_error_limit
    from .phase6_render_contract import PALETTE_QP1_SEGMENT_RENDERER, segment_encoder_arguments
    from .procedural_infographics_phase5 import read_audio_static_source
    root, package = root.resolve(), package.resolve()
    if (not isinstance(binding, dict) or set(binding) != {'path','sha256'}
            or not re.fullmatch(r'sha256:[0-9a-f]{64}',binding.get('sha256',''))):
        raise PermissionError('Exact external codec control binding required')
    path=Path(binding['path']).resolve()
    if not path.is_relative_to(root/'output/runtime/gestor-central/maintenance-runs') or _sha256(path)!=binding['sha256']:
        raise PermissionError('Codec control anchor/root diverged')
    bundle=_read(path)
    if (bundle.get('status')!='COMPLETED_CODEC_CONTROLS_AUTHENTICATED_NOT_RELEASE'
            or bundle.get('authority')!={'application':False,'render_production':False,'publication':False}):
        raise PermissionError('Control set is not the unapproved observed codec scope')
    artifacts={}
    for item in bundle['artifacts']:
        target=Path(item['path']).resolve()
        if (target in artifacts or not target.is_relative_to(path.parent)
                or target.stat().st_size!=item['size_bytes'] or _sha256(target)!=item['sha256']):
            raise PermissionError('Codec control artifact diverged')
        artifacts[target]=item['sha256']
    def reopen(target):
        target=Path(target).resolve()
        if target not in artifacts:raise PermissionError('Required control artifact not authenticated')
        return _read(target)
    # Explicit byte-exact timing-only successor. Its reviewed diff changes only
    # active decode accounting, not decoded RGB, metrics, references or limits.
    # Historical bundles remain immutable; any other old/new pair is rejected.
    timing_successor = (
        'c3e1197cbd2187c85be6e649b2a4e4c73a03ab272b843a057174e2b30ed6f4b0',
        'ca54c3c277b8046afc784fcfdd3203b2d32220982cd7af834c8afa4a19062578',
    )
    # Reviewed music-observation-only extension of the timing successor.
    # All pre-existing measurement functions are AST-identical to ca54c3...;
    # only the separate, non-authorizing music CLI/reader was added. This
    # explicit pair preserves static control evidence, not musical approval
    # or approval of the complete new candidate. Unknown bytes fail closed.
    music_observation_successor = '3365c6e1f894dd691b3c8773b936accc78ea9fb4f593faeb6db1c3a481f59e15'
    reviewed_successors = {timing_successor} | {
        (historical, music_observation_successor) for historical in timing_successor
    }
    # Only new, separate music inference functions were added. Legacy visual,
    # spoken and short-signal functions are AST-identical to 3365c6... . This
    # preserves their controls, not musical quality or deployment approval.
    music_aesthetic_successor = '4b9a9c8fd5b65adceb723b4d4ee4a3cc98aee64ea6c9cc563cd1256273b0bf79'
    reviewed_successors |= {(historical,music_aesthetic_successor)
        for historical in (*timing_successor,music_observation_successor)}
    # Reviewed editorial-opening extension. Static decoding, RGB measurements,
    # technical predicates and spoken evaluation are AST-identical to 4b9a9... .
    # _asr adds opt-in word timings; music assessment adds an opt-in body start.
    # Neither changes static codec calibration. Preserve that scope only:
    # these exact pairs grant no speech/music quality or deployment authority.
    editorial_opening_successor = '684d06bb4af06418b873c58b4221ed9d4cf37991bb3a0d8837850b608e6e417e'
    reviewed_successors |= {(historical,editorial_opening_successor)
        for historical in (*timing_successor,music_observation_successor,music_aesthetic_successor)}
    # Reviewed long-form decode budget successor of 684d06... . The entire
    # module outside _decoded_static_frames is byte-identical after line-ending
    # normalization. Every RGB frame, metric, reference and calibration limit
    # remains mandatory; only bounded active decode time scales with media time.
    # Preserve immutable controls for these exact pairs, never arbitrary bytes.
    long_decode_successor = 'ae17d7a18b93f9ae150e87ae4b59a358190ef3f110fe439b6127eb0a1665ca21'
    reviewed_successors |= {(historical,long_decode_successor)
        for historical in (*timing_successor,music_observation_successor,
                           music_aesthetic_successor,editorial_opening_successor)}
    # Reviewed caption-boundary-only successor: observed zero-duration words
    # are retained in positive-duration cues. No pixel/codec metric, reference,
    # threshold, ASR model or decode behavior changes. Exact bytes only; this
    # preserves static codec calibration, not speech approval or deployment.
    caption_boundary_successor = '15a8cca7e501e21b76f72096128e37df4ed53e8a0eef1f9184569f774c2e4176'
    reviewed_successors |= {(historical,caption_boundary_successor)
        for historical in (*timing_successor,music_observation_successor,
                           music_aesthetic_successor,editorial_opening_successor,
                           long_decode_successor)}
    # Exact real-tail-context successor. Review against 15a8cca7... proves
    # measure_music_aesthetics is the only changed AST node. Static decoding,
    # RGB measures, controls and numeric limits are unchanged. This preserves
    # STATIC controls only; it grants no music/voice/release/deployment PASS.
    musical_tail_context_successor = 'ec10ea9a0acdb28f148928c864b4819d2abb2ca47cb75871cd3acc6ce6be265e'
    reviewed_successors |= {(historical,musical_tail_context_successor)
        for historical in (*timing_successor,music_observation_successor,
                           music_aesthetic_successor,editorial_opening_successor,
                           long_decode_successor,caption_boundary_successor)}
    frozen={row['path']:row for row in bundle['candidate']['files']}
    implementations = {}
    for name in ('hero_engine/phase6_visual_metrics.py','hero_engine/phase5_autonomous_quality.py',
                 'hero_engine/procedural_infographics_phase5.py','hero_engine/phase6_render_contract.py'):
        observed = _sha256(root/name)
        implementations[name] = observed
        historical = frozen.get(name, {}).get('sha256')
        if (historical != observed.removeprefix('sha256:') and not (
                name == 'hero_engine/phase5_autonomous_quality.py'
                and (historical, observed.removeprefix('sha256:')) in reviewed_successors)):
            raise PermissionError('Codec measurement implementation changed')
    result=reopen(path.parent/'control-result.json')
    if result.get('status')!='CONTROL_SEPARATION_PASSED':raise PermissionError('Control separation failed')
    if not package.is_relative_to(root/'output/production'):raise PermissionError('Static package escaped root')
    if music_bindings is None:
        plan=_read(package/'take_plan.json')
        assets=_read(package/'asset_manifest.json')['assets']
        if plan.get('render_profile')!=PALETTE_QP1_SEGMENT_RENDERER or len(assets)!=1:
            raise PermissionError('Static calibration codec/source domain differs')
    else:
        from .render_phase5 import _rest_render_inputs
        _, asset, music_inputs = _rest_render_inputs(root,package,music_bindings)
        assets=[asset]
    rights=_read(Path(assets[0]['rights_evidence_uri']))
    manifest=rights['composition_manifest']
    source=read_audio_static_source(root,Path(manifest['path']),expected_sha256=manifest['sha256'])
    layout=source['layout']
    if layout['style_bible']!=_read(package/'channel_style_bible.json'):
        raise PermissionError('Static calibration current Bible differs from reference')
    def domain(value):
        return {key:value[key] for key in ('font','palette','canvas')} | {
            'font_size':value['texts'][0]['font_size'],'text_color':value['texts'][0]['color']}
    layout_by_reference={}
    for target in artifacts:
        if target.name=='command.json':
            command=reopen(target)
            if 'layout' in command:
                layout_by_reference[command['reference_sha256']]=command['layout']
    selected=result['selected_controls']
    if len(selected)!=8:raise PermissionError('Incomplete independent codec controls')
    for row in selected:
        directory=Path(row['control_directory']).resolve()
        command=reopen(directory/'command.json')
        measurement=reopen(directory/'measurement.json')
        if (measurement!=row or row['observed_frames']!=30
                or reopen(directory/'process-result.json')['exit_code']!=0
                or artifacts.get(directory/'control.mp4')!='sha256:'+row['source_sha256']):
            raise PermissionError('Codec control observation incomplete')
        observed_layout=layout_by_reference.get(row['reference_sha256'])
        if not observed_layout or domain(observed_layout)!=domain(layout):
            raise PermissionError('Codec control font/palette/geometry domain differs')
        argv=command['argv']
        start=argv.index('-c:v')
        if argv[start:start+len(segment_encoder_arguments(PALETTE_QP1_SEGMENT_RENDERER))]!=segment_encoder_arguments(PALETTE_QP1_SEGMENT_RENDERER):
            raise PermissionError('Observed control encoder differs')
        if row['reference_sha256']==assets[0]['content_hash'].removeprefix('sha256:'):
            raise PermissionError('Target reference used for its own calibration')
    calibration={}
    for metric in ('text_error','colour_error'):
        groups={group:[{'source_sha256':row['source_sha256'],'value':row['measurements'][metric]}
                       for row in selected if row['group']==group]
                for group in ('positive','negative','holdout_positive','holdout_negative')}
        if [len(groups[group]) for group in groups]!=[3,2,1,2]:
            raise PermissionError('Control/holdout populations differ')
        calibration[metric]=calibrate_error_limit(candidate_hash=assets[0]['content_hash'].removeprefix('sha256:'),**groups)
        if calibration[metric]!=result['calibration'][metric] or calibration[metric]['status']!='CALIBRATED_NUMERIC_SCOPE':
            raise PermissionError('Control numeric result changed or unsupported')
    if (_sha256(path)!=binding['sha256']
            or any(_sha256(target)!=expected for target,expected in artifacts.items())
            or any(_sha256(root/name)!=expected for name,expected in implementations.items())
            or (music_bindings is not None and any(_sha256(target)!=expected
                for target,expected in music_inputs.items()))):
        raise PermissionError('Codec control changed before consumption')
    return {'status':'AUTHENTICATED_STATIC_CODEC_LIMITS','binding':dict(binding),
        'limits':{key:value['maximum_error'] for key,value in calibration.items()},
        'authenticated_inputs':[{'path':str(target),'sha256':expected} for target,expected in artifacts.items()]
            +[{'path':str(root/name),'sha256':expected} for name,expected in implementations.items()],
        'domain':domain(layout),'quality_authorized':False,'publication_authorized':False}


def _fps(value: str) -> float:
    numerator, denominator = value.split("/", 1)
    return float(numerator) / float(denominator)


def verify_audio_static_execution(root: Path, package: Path, media: Path, *, binding: dict[str,str]) -> dict[str,Any]:
    """Consume the producer's existing native execution observations, not a label."""
    from .native_gop300_bridge import offered as _gop300_offered
    if _gop300_offered(binding):
        from .native_gop300_bridge import read_execution as _gop300_execution
        return _gop300_execution(root, package, media, binding=binding, expected_bridge_sha256='e293cfe48dd8cf0f7bebcbe99ea65239a1e37b369d9221a94f68344f5acd783b')
    from .phase6_render_contract import PALETTE_QP1_SEGMENT_RENDERER, segment_encoder_arguments
    root,package,media=root.resolve(),package.resolve(),media.resolve()
    path=Path(binding['path']).resolve()
    if (path!=package/'resource-observation.json'
            or not re.fullmatch(r'sha256:[0-9a-f]{64}',binding.get('sha256',''))
            or _sha256(path)!=binding['sha256']):
        raise PermissionError('Exact native static execution anchor required')
    record=_read(path)
    if record.get('quality_approval') is not False:raise PermissionError('Execution record cannot grant quality')
    plan=_read(package/'take_plan.json')
    executions=[row['execution'] for row in record['observations'] if 'execution' in row]
    if not executions:raise PermissionError('No observed static encoder execution')
    def reopen(row, *, confined=True):
        target=Path(row['path']).resolve()
        if ((confined and not target.is_relative_to(root)) or target.stat().st_size!=row['size_bytes']
                or _sha256(target)!=row['sha256']):raise PermissionError('Observed execution file diverged')
        return target
    loops=[]
    for execution in executions:
        if (execution['version']!='phase6-observed-ffmpeg-execution-v1'
                or execution['status']!='COMPLETED' or execution['exit_code']!=0
                or execution['quality_approval'] is not False):
            raise PermissionError('Static execution incomplete')
        executable=reopen(execution['executable'],confined=False)
        argv=execution['argv']
        if Path(argv[0]).resolve()!=executable:raise PermissionError('Execution executable binding differs')
        inputs={reopen(row) for row in execution['inputs']}
        for index,value in enumerate(argv[:-1]):
            if value=='-i' and Path(argv[index+1]).resolve() not in inputs:
                raise PermissionError('Observed direct input missing')
        output=reopen(execution['output'])
        if Path(argv[-1]).resolve()!=output:raise PermissionError('Execution output differs')
        if '-loop' in argv:
            start=argv.index('-c:v')
            encoder=segment_encoder_arguments(PALETTE_QP1_SEGMENT_RENDERER)
            if argv[start:start+len(encoder)]!=encoder:raise PermissionError('Static encoder changed')
            loops.append(execution)
        elif '-c:v' in argv and argv[argv.index('-c:v')+1]!='copy':
            raise PermissionError('Static output received unqualified second video encoding')
    if len(loops)!=len(plan['takes']):raise PermissionError('Static segment execution coverage incomplete')
    source=Path(_read(package/'asset_manifest.json')['assets'][0]['uri']).resolve()
    filters='scale=1920:1080:force_original_aspect_ratio=decrease:out_color_matrix=bt709:out_range=tv,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709'
    from .render_phase5 import _frame_count_for_duration_ms
    for take,execution in zip(plan['takes'],loops):
        argv=execution['argv']
        if (Path(argv[argv.index('-i')+1]).resolve()!=source
                or argv[argv.index('-vf')+1]!=filters
                or argv[argv.index('-frames:v')+1]!=str(_frame_count_for_duration_ms(take['end_ms']-take['start_ms']))
                or Path(execution['output']['path']).name!=take['take_id']+'.mp4'):
            raise PermissionError('Static source/filter/frame domain differs')
    final=executions[-1]
    if (Path(final['output']['path']).resolve()!=media
            or final['argv'][final['argv'].index('-c:v')+1]!='copy'):
        raise PermissionError('Final static output execution is not the observed mux')
    if _sha256(path)!=binding['sha256']:raise PermissionError('Execution observation changed')
    return {'status':'OBSERVED_STATIC_QP1_EXECUTION_BOUND','binding':dict(binding),
            'observed_segments':len(loops),'media_sha256':_sha256(media),'quality_authorized':False,
            'authenticated_inputs':[row for execution in executions for row in
                [execution['executable'],*execution['inputs'],execution['output']]]}


def _frame_count(path: Path) -> int:
    result = _run([
        FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(path),
    ])
    return int(result.stdout.strip())


def _decoded_stream_hash(path: Path, stream: str) -> str:
    if stream == "video":
        command = [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(path),
            "-map", "0:v:0", "-an", "-f", "hash", "-hash", "sha256", "-",
        ]
    elif stream == "audio":
        command = [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(path),
            "-map", "0:a:0", "-vn", "-f", "hash", "-hash", "sha256", "-",
        ]
    else:
        raise ValueError(f"unsupported stream: {stream}")
    value = _run(command).stdout.strip()
    match = re.fullmatch(r"SHA256=([0-9a-fA-F]{64})", value)
    if not match:
        raise RuntimeError(f"unexpected FFmpeg hash output: {value}")
    return "sha256:" + match.group(1).lower()


def _ssim(reference: Path, candidate: Path) -> float:
    result = subprocess.run(
        [
            FFMPEG, "-hide_banner", "-nostats", "-i", str(reference), "-i", str(candidate),
            "-lavfi", "[0:v:0][1:v:0]ssim", "-an", "-f", "null", os.devnull,
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError("\n".join(result.stderr.splitlines()[-80:]))
    matches = re.findall(r"All:([0-9.]+)", result.stderr)
    if not matches:
        raise RuntimeError("FFmpeg SSIM result was not found")
    return float(matches[-1])


def _encode_standard(source: Path, destination: Path) -> float:
    destination.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    _run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-profile:v", "high",
        "-preset", "slow", "-b:v", "10M", "-minrate", "10M", "-maxrate", "10M",
        "-bufsize", "20M", "-x264-params", "nal-hrd=cbr:force-cfr=1", "-pix_fmt", "yuv420p",
        "-r", "30", "-g", "60", "-keyint_min", "30", "-sc_threshold", "0",
        "-c:a", "copy", "-movflags", "+faststart", str(destination),
    ])
    return round(time.perf_counter() - started, 6)


def _record(check: str, status: str, threshold: Any, observed: Any, evidence: list[str]) -> dict[str, Any]:
    return {
        "check": check,
        "status": status,
        "threshold": threshold,
        "observed": observed,
        "evidence_refs": evidence,
    }


def build_standard_qualification(
    root: Path,
    *,
    created_at: str | None = None,
    reuse_existing_encodes: bool = False,
    package_relative: Path | None = None,
    asr_receipt_binding: dict[str, str] | None = None,
    visual_controls_binding: dict[str, str] | None = None,
    render_execution_binding: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Qualify the explicitly selected format without borrowing legacy media.

    Default preserves the historical cinematic STANDARD report contract.
    The audio/static Pack returns the existing creative-quality-gate report
    contract, whose individual gates are authoritative (not a legacy replay).
    Its QP1 source and execution are evaluated directly; no extra lossy encode
    is justified, and no production/publication transition occurs here.
    """
    if package_relative is not None:
        root = root.resolve()
        offered = Path(package_relative)
        package = (root / offered).resolve()
        if (offered.is_absolute() or '..' in offered.parts
                or not package.is_relative_to(root / 'output/production')):
            raise PermissionError('Qualification package escaped the production root')
        plan = _read(package / 'take_plan.json')
        if plan.get('format_pack_id') != 'fp-narrated-reflection-static':
            raise PermissionError('Explicit package qualification supports only the audio/static Pack')
        if reuse_existing_encodes:
            raise PermissionError('Cinematic replay reuse cannot approve the audio/static Pack')
        if visual_controls_binding is None or render_execution_binding is None:
            raise PermissionError('Static qualification requires exact codec controls and observed execution')
        from .qa_phase5 import run_phase5_quality_gates
        report, _ = run_phase5_quality_gates(root, package_relative=offered,
            created_at=created_at, asr_receipt_binding=asr_receipt_binding,
            visual_controls_binding=visual_controls_binding,
            render_execution_binding=render_execution_binding)
        return report
    if any(value is not None for value in
           (asr_receipt_binding, visual_controls_binding, render_execution_binding)):
        raise PermissionError('Static bindings require an explicit current package')
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    v3 = root / V3
    directory = v3 / "standard-qualification"
    source_manifest = _read(v3 / "render_manifest.json")
    automatic_qa = _read(v3 / "qa" / "creative_quality_gate_report.json")
    remediation = _read(v3 / "qa" / "creative_revision_metrics.json")
    profile = _read(root / "config" / "production_quality_profiles" / "standard-v1.json")
    format_pack = _read(root / "config" / "format_packs" / "fp-broll-cinematic-narration-v1.json")
    integration = _read(root / "output" / "integrations" / "youtube" / "heroverse" / "operational-readiness.json")
    thumbnails = _read(v3 / "thumbnail" / "thumbnail_set_manifest.json")
    source = Path(source_manifest["output"]["path"])
    if not source.is_file() or _sha256(source) != source_manifest["output"]["content_hash"]:
        raise RuntimeError("canonical DRAFT render is absent or does not match its manifest")
    if remediation["automatic_status"] != "PASS":
        raise PermissionError("STANDARD qualification requires the automatic remediation contract to pass")

    candidate = directory / "after-you-pray-do-this-next.phase5-creative-v3-standard-candidate.mp4"
    replay = directory / "replay" / "after-you-pray-do-this-next.phase5-creative-v3-standard-candidate.replay.mp4"
    previous_report_path = directory / "standard_qualification_report.json"
    if reuse_existing_encodes:
        if not candidate.is_file() or not replay.is_file():
            raise FileNotFoundError("both existing STANDARD encodes are required for reassessment")
        previous = _read(previous_report_path) if previous_report_path.is_file() else {}
        candidate_seconds = float(previous.get("measurements", {}).get("candidate_encode_seconds", 0))
        replay_seconds = float(previous.get("measurements", {}).get("replay_encode_seconds", 0))
    else:
        candidate_seconds = _encode_standard(source, candidate)
        replay_seconds = _encode_standard(source, replay)

    candidate_probe = _probe(candidate)
    replay_probe = _probe(replay)
    video = next(item for item in candidate_probe["streams"] if item["codec_type"] == "video")
    audio = next(item for item in candidate_probe["streams"] if item["codec_type"] == "audio")
    duration_ms = round(float(candidate_probe["format"]["duration"]) * 1000)
    frame_count = _frame_count(candidate)
    candidate_hash = _sha256(candidate)
    replay_hash = _sha256(replay)
    candidate_video_hash = _decoded_stream_hash(candidate, "video")
    replay_video_hash = _decoded_stream_hash(replay, "video")
    candidate_audio_hash = _decoded_stream_hash(candidate, "audio")
    replay_audio_hash = _decoded_stream_hash(replay, "audio")
    ssim = _ssim(source, candidate)
    replay_ssim = _ssim(candidate, replay)
    loudness = _loudness(candidate)
    black_freeze = _black_freeze_scan(candidate)

    minimums = profile["technical_minimums"]
    bitrate_kbps = int(video.get("bit_rate") or candidate_probe["format"].get("bit_rate") or 0) / 1000
    target_lufs = float(minimums["loudness_lufs"]["target"])
    tolerance = float(minimums["loudness_lufs"]["tolerance"])
    technical_checks = [
        _record("resolution", "PASS" if int(video["width"]) == minimums["width"] and int(video["height"]) == minimums["height"] else "FAIL", [minimums["width"], minimums["height"]], [int(video["width"]), int(video["height"])], [str(candidate.resolve())]),
        _record("frame_rate", "PASS" if math.isclose(_fps(video["r_frame_rate"]), float(minimums["fps"]), abs_tol=0.01) else "FAIL", minimums["fps"], _fps(video["r_frame_rate"]), [str(candidate.resolve())]),
        _record("codecs", "PASS" if video["codec_name"] == minimums["video_codec"] and audio["codec_name"] == minimums["audio_codec"] else "FAIL", [minimums["video_codec"], minimums["audio_codec"]], [video["codec_name"], audio["codec_name"]], [str(candidate.resolve())]),
        _record("video_bitrate_kbps", "PASS" if bitrate_kbps >= minimums["minimum_bitrate_kbps"] else "FAIL", minimums["minimum_bitrate_kbps"], round(bitrate_kbps, 3), [str(candidate.resolve())]),
        _record("loudness_lufs", "PASS" if target_lufs - tolerance <= loudness["integrated_lufs"] <= target_lufs + tolerance else "FAIL", [target_lufs - tolerance, target_lufs + tolerance], loudness["integrated_lufs"], [str(candidate.resolve())]),
        _record("true_peak_dbtp", "PASS" if loudness["true_peak_dbtp"] <= float(minimums["true_peak_dbtp"]) else "FAIL", minimums["true_peak_dbtp"], loudness["true_peak_dbtp"], [str(candidate.resolve())]),
        _record("timeline", "PASS" if duration_ms == source_manifest["output"]["duration_ms"] and frame_count == source_manifest["measurements"]["expected_total_frames"] else "FAIL", {"duration_ms": source_manifest["output"]["duration_ms"], "frames": source_manifest["measurements"]["expected_total_frames"]}, {"duration_ms": duration_ms, "frames": frame_count}, [str(candidate.resolve()), "creative-v3/render_manifest.json"]),
        _record("black_and_freeze", "PASS" if black_freeze["black_event_count"] == 0 and black_freeze["freeze_event_count"] == 0 else "FAIL", {"black": 0, "freeze": 0}, black_freeze, [str(candidate.resolve())]),
        _record("visual_fidelity_ssim", "PASS" if ssim >= 0.98 else "FAIL", 0.98, ssim, [str(source.resolve()), str(candidate.resolve())]),
        _record("replay_timeline_and_size_equivalence", "PASS" if round(float(replay_probe["format"]["duration"]) * 1000) == duration_ms and _frame_count(replay) == frame_count and abs(replay.stat().st_size - candidate.stat().st_size) / candidate.stat().st_size <= 0.001 else "FAIL", {"duration_ms": duration_ms, "frames": frame_count, "maximum_size_variance": 0.001}, {"duration_ms": round(float(replay_probe["format"]["duration"]) * 1000), "frames": _frame_count(replay), "size_variance": round(abs(replay.stat().st_size - candidate.stat().st_size) / candidate.stat().st_size, 9)}, [str(candidate.resolve()), str(replay.resolve())]),
        _record("replay_content_equivalence", "PASS" if replay_ssim >= 0.995 and candidate_audio_hash == replay_audio_hash else "FAIL", {"minimum_video_ssim": 0.995, "audio_decoded_hash": candidate_audio_hash}, {"video_ssim": replay_ssim, "audio_decoded_hash": replay_audio_hash}, [str(candidate.resolve()), str(replay.resolve())]),
    ]
    automatic_profile_status = "PASS" if all(item["status"] == "PASS" for item in technical_checks) else "FAIL"

    unresolved = [
        _record("independent_human_full_render_review", "NEEDS_REVIEW", "PASS", automatic_qa["human_review"]["status"], ["creative-v3/human_review_checklist.md"]),
        _record("thumbnail_human_selection", "NEEDS_REVIEW", "selected A, B or C", thumbnails["selection_status"], ["creative-v3/thumbnail/human_selection_brief.md"]),
        _record("format_pack_production_capability", "BLOCKED", "PRODUCTION_READY or LIMITED", format_pack["capability_status"], ["config/format_packs/fp-broll-cinematic-narration-v1.json"]),
        _record("oauth_continuous_operation", "BLOCKED", True, integration["continuous_operation_ready"], ["output/integrations/youtube/heroverse/operational-readiness.json"]),
    ]
    report = {
        "schema_version": "1.0.0",
        "qualification_id": "standard-qualification-" + hashlib.sha256(f"{candidate_hash}|{timestamp}".encode()).hexdigest()[:20],
        "video_id": source_manifest["video_id"],
        "source_quality_profile": source_manifest["quality_profile"],
        "target_quality_profile": profile["profile"],
        "qualification_mode": True,
        "automatic_profile_status": automatic_profile_status,
        "overall_status": "BLOCKED_PENDING_HUMAN_AND_EXTERNAL_GATES" if automatic_profile_status == "PASS" else "FAIL",
        "production_approved": False,
        "publication_eligible": False,
        "profile_version": profile["version"],
        "pipeline_id": source_manifest["pipeline_id"],
        "pipeline_version": source_manifest["pipeline_version"],
        "format_pack_id": source_manifest["format_pack_id"],
        "format_pack_version": source_manifest["format_pack_version"],
        "source": {"path": str(source.resolve()), "content_hash": _sha256(source)},
        "candidate": {"path": str(candidate.resolve()), "content_hash": candidate_hash, "size_bytes": candidate.stat().st_size, "duration_ms": duration_ms, "frame_count": frame_count, "video_bitrate_kbps": round(bitrate_kbps, 3), "decoded_video_hash": candidate_video_hash, "decoded_audio_hash": candidate_audio_hash},
        "replay": {"path": str(replay.resolve()), "content_hash": replay_hash, "size_bytes": replay.stat().st_size, "decoded_video_hash": replay_video_hash, "decoded_audio_hash": replay_audio_hash, "container_exact_match": candidate_hash == replay_hash, "decoded_streams_exact_match": candidate_video_hash == replay_video_hash and candidate_audio_hash == replay_audio_hash, "perceptual_ssim": replay_ssim, "equivalence_pass": replay_ssim >= 0.995 and candidate_audio_hash == replay_audio_hash},
        "measurements": {"candidate_encode_seconds": candidate_seconds, "replay_encode_seconds": replay_seconds, "visual_fidelity_ssim": ssim, "replay_perceptual_ssim": replay_ssim, "loudness": loudness, "black_freeze": black_freeze, "external_cost_usd": 0},
        "technical_checks": technical_checks,
        "unresolved_gates": unresolved,
        "variance_observations": [{"type": "MULTITHREADED_H264_NON_BIT_EXACT", "status": "MEASURED", "container_exact_match": candidate_hash == replay_hash, "decoded_video_exact_match": candidate_video_hash == replay_video_hash, "decoded_audio_exact_match": candidate_audio_hash == replay_audio_hash, "assessment": "The independently encoded H.264 outputs are not byte/pixel exact. Reproducibility is accepted only as measured media equivalence: identical duration/frame count, decoded-audio hash equality, <=0.1% size variance and replay SSIM >=0.995. This does not claim bitwise determinism."}],
        "claim_boundary": "PASS means the measured automatic STANDARD media contract and the declared replay-equivalence tolerance passed. It does not claim bitwise H.264 determinism, satisfy independent human review, promote the FormatPack, make OAuth durable, authorize upload or predict audience performance.",
        "created_at": timestamp,
    }
    schema = _read(root / "schemas" / "standard_qualification_report.schema.json")
    Draft202012Validator(schema).validate(report)
    _write(directory / "standard_qualification_report.json", report)
    return report
