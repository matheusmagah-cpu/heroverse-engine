from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


FIT_WEIGHTS = {
    "channel_dna": 0.22,
    "audience": 0.14,
    "niche": 0.18,
    "narrative": 0.18,
    "retention": 0.16,
    "comprehension": 0.12,
}
PROTOTYPE_STATES = {"SPECIFIED", "PROTOTYPED", "VALIDATED", "PRODUCTION_READY", "LIMITED"}
PRODUCTION_STATES = {"PRODUCTION_READY", "LIMITED"}
STOPWORDS = {
    "and", "the", "for", "with", "from", "into", "this", "that", "when", "your",
    "uma", "para", "com", "sem", "como", "por", "dos", "das", "que", "não",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def build_christian_rest_music_recipe(*, duration_ms: int,
                                     channel_model_hash: str,
                                     style_bible_hash: str,
                                     recipe_version: str = 'heroverse-christian-rest-instrumental-v1',
                                     research: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explicit original instrumental prototype, not a production Pack promotion.

    The sound design comes from our own procedural bed, not a mined recording.
    Channel/style hashes are bindings for downstream reopening, not proof that
    an isolated recipe has authenticated or changed the channel configuration.
    """
    if type(duration_ms) is not int or not 0 < duration_ms <= 14_400_000:
        raise ValueError('rest recipe duration must be positive and <=4 hours')
    for binding in (channel_model_hash, style_bible_hash):
        if not isinstance(binding, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', binding):
            raise ValueError('rest recipe requires explicit channel/style SHA-256 bindings')
    if recipe_version not in ('heroverse-christian-rest-instrumental-v1',
                              'heroverse-christian-rest-instrumental-v2',
                              'heroverse-christian-rest-editorial-v3',
                              'heroverse-christian-rest-editorial-v4',
                              'heroverse-christian-rest-editorial-v5'):
        raise ValueError('unsupported rest music recipe version')
    if (research is not None) != (recipe_version == 'heroverse-christian-rest-editorial-v5'):
        raise ValueError('research belongs only to the explicit researched successor')
    recipe = {'recipe_version': 'heroverse-christian-rest-instrumental-v1',
        'channel_handle': '@heroverse74', 'language': 'en', 'target_country': 'US',
        'purpose': 'Original instrumental accompaniment for Christian prayer and quiet reflection',
        'duration_ms': duration_ms,
        'channel_model_hash': channel_model_hash, 'style_bible_hash': style_bible_hash,
        'sound_design': {'sample_rate': 48000, 'channels': 2, 'subtype': 'PCM_16',
            'key_center': 'D minor', 'progression': ['Dm', 'Bb', 'F', 'C'],
            'chord_seconds': 12.0, 'crossfade_seconds': 1.92,
            'attack_seconds': 1.44, 'release_seconds': 1.92,
            'transition': 'equal-power overlap between original procedural chords'},
        'reference_scope': 'OWNED_SOUND_DESIGN_NOT_CALIBRATED_MUSIC_QUALITY',
        'narration_looped': False, 'external_cost_usd': 0,
        'quality_authorized': False, 'render_authorized': False,
        'publication_authorized': False}
    if recipe_version.endswith(('-v2', '-v3', '-v4', '-v5')):
        recipe['recipe_version'] = recipe_version
        recipe['sound_design']['melodic_voice'] = {
            'instrument': 'owned additive soft piano',
            'note_seconds': 6.0, 'tail_seconds': 12.0, 'attack_seconds': 0.024,
            'frequencies_hz': [293.66,349.23,440.0,349.23,233.08,293.66,349.23,440.0,
                               261.63,329.63,392.0,329.63,293.66,440.0,523.25,440.0],
            'partials': [1.0,0.45,0.20,0.08,0.04],
            'inharmonicity': 0.0002, 'fundamental_decay_seconds': 4.5,
            'amplitude': 0.12, 'pad_gain': 0.45,
            'echo_taps': [{'seconds':0.19,'gain':0.16},{'seconds':0.37,'gain':0.10}],
            'score_scope': 'original D-minor phrase; not a mined/copyrighted melody'}
    if recipe_version in ('heroverse-christian-rest-editorial-v3','heroverse-christian-rest-editorial-v4',
                          'heroverse-christian-rest-editorial-v5'):
        if duration_ms < 180000:
            raise ValueError('editorial rest delivery requires space for measured reflection and music')
        recipe['purpose'] = 'Original Christian reflection on rest and responsibility, followed by owned prayer music'
        recipe['reference_scope'] = 'OWNED_EDITORIAL_AND_COMPOSITION_NOT_RELEASE_OR_YPP_CERTIFICATION'
        recipe['editorial'] = build_christian_rest_editorial()
        recipe['sound_design']['opening_mix'] = {
            'voice_gain': 0.85, 'music_gain_during_speech': 0.2,
            'speech_repeat': False}
        recipe['sound_design']['sections'] = [
            {'section_id': 'settle', 'start_fraction': 0, 'end_fraction': 1/3,
             'selection_reason': 'Sparse original phrase leaves room to settle after the reflection',
             'frequencies_hz': [293.66,349.23,440.0,349.23,233.08,293.66,349.23,440.0,
                                261.63,329.63,392.0,329.63,293.66,440.0,523.25,440.0]},
            {'section_id': 'remain', 'start_fraction': 1/3, 'end_fraction': 2/3,
             'selection_reason': 'A distinct phrase develops the same harmonic identity without restarting speech',
             'frequencies_hz': [349.23,293.66,440.0,523.25,349.23,293.66,233.08,349.23,
                                329.63,392.0,261.63,392.0,440.0,349.23,293.66,440.0]},
            {'section_id': 'return', 'start_fraction': 2/3, 'end_fraction': 1,
             'selection_reason': 'A third original phrase returns to D with the existing measured fade, not an abrupt cut',
             'frequencies_hz': [440.0,349.23,293.66,349.23,293.66,233.08,349.23,293.66,
                                392.0,329.63,261.63,329.63,523.25,440.0,349.23,293.66]}
        ]
    if recipe_version in ('heroverse-christian-rest-editorial-v4','heroverse-christian-rest-editorial-v5'):
        # Explicit successor of v3: bounded real comparisons of all three
        # original phrases support cadence/overlap correction, not a release.
        # No voice, pitch, timbre, loudness or historical reference is changed.
        recipe['sound_design']['melodic_voice'].update(note_seconds=3.0,tail_seconds=6.0)
    if research is not None:
        from .phase6_audio_production import build_researched_rest_editorial
        recipe['research'] = research
        recipe['editorial'] = build_researched_rest_editorial(research['model'])
        recipe['purpose'] = recipe['editorial']['angle']
    encoded = json.dumps(recipe, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {'recipe_id': 'rest-music-' + hashlib.sha256(encoded).hexdigest()[:20], **recipe}


def build_christian_rest_editorial() -> dict[str, Any]:
    """One original evergreen treatment, not a market/quality PASS or a catalogue.

    Reuse the channel's existing angle -> promise -> narrative chain. Musical
    v1/v2 remain strictly speech-free; this explicit successor cannot borrow
    their release identity or turn a title into evidence of audible opinion.
    """
    sections = [
        {'role': 'TITLE_ALIGNED_STAKE', 'text':
         'Rest is not the opposite of faithfulness. Sometimes it is what allows us to return to it. '
         'But there is a difference between setting down a burden for a while and pretending it no longer belongs to us.'},
        {'role': 'PERSONAL_STAKES', 'text':
         'Tonight, we do not need to solve everything. We can name one thing that is ours to do, '
         'one limit that deserves respect, and one outcome we cannot control. '
         'Our worth is not a score measured by how many tasks we finish before we sleep.'},
        {'role': 'MECHANISM_AND_PROOF', 'text':
         'Consider a conversation you have been avoiding. Rest may help you return to it with more patience; '
         'it does not make the other person or the issue disappear. '
         'Now consider a problem you cannot fix tonight. Continuing to rehearse it is not the same as taking responsibility. '
         'These are examples to reflect on, not diagnoses of your life.'},
        {'role': 'REVERSAL_AND_ACTION', 'text':
         'Some people need to stop for longer. Their next honest step may be asking for help or respecting a limit, '
         'not doing more. From this Christian perspective, rest and responsibility need not compete. '
         'Choose a small response for later, without making this moment another demand.'},
        {'role': 'PROMISE_RESOLUTION', 'text':
         'This is the perspective we offer: rest can make room for a faithful response without becoming an excuse for avoidance. '
         'After these opening words, the speech will stop. The original music will leave space for your own prayer, reflection, or quiet. '
         'You do not need to earn that space by staying here for the whole session.'}
    ]
    return {'version': 'heroverse-rest-is-not-giving-up-v1', 'language': 'en-US',
        'title': 'Rest Is Not Giving Up | A Christian Reflection + Quiet Piano for Prayer',
        'angle': 'Rest can be an act of trust without becoming an excuse for avoidance',
        'evidence_class': 'ORIGINAL_EVERGREEN_INTERPRETATION_NOT_NEW_MARKET_RESEARCH',
        'sections': sections, 'full_text': ' '.join(row['text'] for row in sections),
        'voice_id': 'am_onyx', 'speed': 1.0, 'speech_placement': 'ONCE_AT_START',
        'rejected_choices': ['Guaranteed divine peace', 'Copied competitor recording',
                             'Repeated narration throughout the music'],
        'authority': {'quality': False, 'render': False, 'publication': False}}


def rest_delivery_format(recipe: dict[str, Any]) -> dict[str, str]:
    """Fixed native dispatch; caller labels never select a different gate family."""
    if recipe.get('recipe_version') in ('heroverse-christian-rest-editorial-v3','heroverse-christian-rest-editorial-v4',
                                       'heroverse-christian-rest-editorial-v5'):
        return {'format_pack_id':'fp-christian-reflection-rest-static',
            'pack_file':'fp-christian-reflection-rest-static-v1.json',
            'pipeline_id':'pipeline-christian-reflection-rest-static',
            'render_schema':'1.3.0','release_schema':'1.3.0','package_schema':'1.2.0',
            'quality_status':'PASS_EDITORIAL_REST_DELIVERY_SCOPE',
            'transition_basis':'AUTHENTICATED_COMPLETE_EDITORIAL_REST_QA'}
    if recipe.get('recipe_version') not in ('heroverse-christian-rest-instrumental-v1',
                                            'heroverse-christian-rest-instrumental-v2'):
        raise PermissionError('unknown native rest delivery format')
    return {'format_pack_id':'fp-christian-rest-instrumental-static',
        'pack_file':'fp-christian-rest-instrumental-static-v1.json',
        'pipeline_id':'pipeline-christian-rest-instrumental-static',
        'render_schema':'1.2.0','release_schema':'1.2.0','package_schema':'1.1.0',
        'quality_status':'PASS_INSTRUMENTAL_DELIVERY_SCOPE',
        'transition_basis':'AUTHENTICATED_COMPLETE_INSTRUMENTAL_QA'}


def verify_christian_rest_music_recipe(recipe: dict[str, Any], *, expected_hash: str) -> None:
    encoded = json.dumps(recipe, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if expected_hash != 'sha256:' + hashlib.sha256(encoded).hexdigest():
        raise PermissionError('rest music recipe binding diverged')
    try:
        recomposed = build_christian_rest_music_recipe(duration_ms=recipe['duration_ms'],
            channel_model_hash=recipe['channel_model_hash'], style_bible_hash=recipe['style_bible_hash'],
            recipe_version=recipe['recipe_version'], research=recipe.get('research'))
    except (KeyError, ValueError, TypeError) as exc:
        raise PermissionError('rest music recipe incomplete') from exc
    if json.dumps(recipe,sort_keys=True,separators=(',',':')) != json.dumps(recomposed,sort_keys=True,separators=(',',':')):
        raise PermissionError('rest music recipe design/scope altered')


def read_christian_rest_music_inputs(root: Path, *, package_relative: Path,
                                   recipe_binding: dict[str, str]) -> dict[str, Any]:
    """Reopen the native musical contract; no voice surrogate or effect authority.

    A recipe's channel/style hash strings are insufficient by themselves. This
    consumer pins the real canonical model and the package's Bible in the same
    invocation, before a producer or quality consumer can use the recipe.
    """
    root = root.resolve()
    relative = Path(package_relative)
    package = (root / relative).resolve()
    if (relative.is_absolute() or '..' in relative.parts
            or not package.is_relative_to(root / 'output/production')):
        raise PermissionError('rest music package escaped production root')
    recipe_path = package / 'music_recipe.json'
    if (not isinstance(recipe_binding, dict) or set(recipe_binding) != {'path', 'sha256'}
            or Path(recipe_binding['path']).resolve() != recipe_path
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', recipe_binding.get('sha256', ''))):
        raise PermissionError('exact external rest recipe file binding required')
    paths = (recipe_path, root / 'output/modeling/phase4/channel-model-v1/channel_model.json',
             package / 'channel_style_bible.json')
    raw = {}
    for path in paths:
        if not path.resolve().is_relative_to(root):
            raise PermissionError('rest input escaped root through alias')
        raw[path] = path.read_bytes()
    hashes = {path: 'sha256:' + hashlib.sha256(data).hexdigest() for path, data in raw.items()}
    if hashes[recipe_path] != recipe_binding['sha256']:
        raise PermissionError('rest recipe external file anchor diverged')
    recipe, model, bible = [json.loads(raw[path].decode('utf-8-sig')) for path in paths]
    canonical = json.dumps(recipe, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    verify_christian_rest_music_recipe(recipe, expected_hash='sha256:' + hashlib.sha256(canonical).hexdigest())
    if (recipe['channel_model_hash'] != hashes[paths[1]]
            or recipe['style_bible_hash'] != hashes[paths[2]]
            or bible.get('channel_id') != 'heroverse74'
            or not model.get('model_id')
            or bible.get('channel_dna_version') != model['model_id']):
        raise PermissionError('rest recipe live channel/style lineage diverged')
    if recipe.get('research') is not None:
        from .phase6_audio_production import read_current_audio_research, read_audio_preregistration
        research = read_current_audio_research(root, recipe['research']['binding'])
        if research != recipe['research']['model']:
            raise PermissionError('rest recipe researched treatment differs from live evidence')
        for row in research['inputs']:
            path = root / row['path']
            raw[path] = path.read_bytes()
            if 'sha256:' + hashlib.sha256(raw[path]).hexdigest() != row['sha256']:
                raise PermissionError('research changed during rest input capture')
            hashes[path] = row['sha256']
        research_path = root / recipe['research']['binding']['path']
        raw[research_path] = research_path.read_bytes()
        hashes[research_path] = recipe['research']['binding']['sha256']
        if 'sha256:'+hashlib.sha256(raw[research_path]).hexdigest() != hashes[research_path]:
            raise PermissionError('research model changed during rest input capture')
        for path, data in read_audio_preregistration(root,recipe['research']['binding'],recipe_binding).items():
            raw[path]=data
            hashes[path]='sha256:'+hashlib.sha256(data).hexdigest()
    if any(path.read_bytes() != data for path, data in raw.items()):
        raise PermissionError('rest music inputs changed during capture')
    return {'status': 'AUTHENTICATED_REST_MUSIC_INPUTS_NOT_RELEASE', 'recipe': recipe,
        'canonical_recipe_hash': 'sha256:' + hashlib.sha256(canonical).hexdigest(),
        'inputs': [{'path': str(path), 'sha256': hashes[path]} for path in paths],
        'voice_required': 'editorial' in recipe, 'quality_authorized': False, 'render_authorized': False,
        'publication_authorized': False}


def _tokens(*values: Any) -> set[str]:
    text = " ".join(str(value) for value in values if value is not None)
    return {
        token
        for token in re.findall(r"[a-zà-ÿ0-9']+", text.lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_flatten_strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_flatten_strings(item))
        return result
    return []


def _coverage_overlap(target: set[str], candidate: set[str], *, floor: float = 0.0) -> float:
    if not target or not candidate:
        return floor
    overlap = len(target & candidate) / len(target)
    return round(max(floor, min(1.0, overlap)), 6)


def _fit_assessment(
    pack: dict[str, Any],
    channel_model: dict[str, Any],
    brief: dict[str, Any],
) -> tuple[dict[str, float], float, list[str], list[str]]:
    dna = channel_model["channel_dna"]
    spec = pack["specification"]
    pack_tokens = _tokens(*_flatten_strings(spec))
    identity_tokens = _tokens(*_flatten_strings(dna.get("identity", {})), dna.get("editorial_promise"))
    audience_tokens = _tokens(dna.get("audience"), dna.get("job_to_be_done"))
    niche_tokens = _tokens(*dna.get("pillars", []), *dna.get("topic_map", []), brief.get("package", {}).get("topic"))
    narrative_tokens = _tokens(
        brief.get("package", {}).get("angle"),
        brief.get("package", {}).get("promise"),
        brief.get("payoff"),
        *[window.get("function") for window in brief.get("hook_windows", [])],
    )

    # Token evidence is used only to confirm semantic compatibility. Contractual
    # features provide explicit, inspectable floors; no hidden model is involved.
    fit = {
        "channel_dna": _coverage_overlap(identity_tokens, pack_tokens, floor=0.72),
        "audience": _coverage_overlap(audience_tokens, pack_tokens, floor=0.70),
        "niche": _coverage_overlap(niche_tokens, pack_tokens, floor=0.75),
        "narrative": _coverage_overlap(narrative_tokens, pack_tokens, floor=0.76),
        "retention": 1.0 if spec.get("recommended_take_duration_ms") and spec.get("visual_rhythm") else 0.0,
        "comprehension": 1.0 if spec.get("text_treatment") and spec.get("audio_treatment") else 0.0,
    }
    evidence = [
        "channel-model:channel_dna",
        f"brief:{brief['brief_id']}",
        f"format-pack:{pack['format_pack_id']}@{pack['version']}",
    ]
    contrary: list[str] = []
    if channel_model["channel_dna"].get("confidence", 0.0) < 0.5:
        contrary.append("ChannelDNA confidence is below 0.5; only a controlled pilot is authorized.")
    if not pack.get("production_allowed"):
        contrary.append("FormatPack is not production-approved; prototype use only.")
    score = round(sum(fit[key] * FIT_WEIGHTS[key] for key in FIT_WEIGHTS), 6)
    return fit, score, evidence, contrary


def load_format_packs(pack_dir: Path, schema_path: Path) -> list[dict[str, Any]]:
    schema = _read_json(schema_path)
    validator = Draft202012Validator(schema)
    packs: list[dict[str, Any]] = []
    for path in sorted(pack_dir.glob("*.json")):
        pack = _read_json(path)
        validator.validate(pack)
        pack["_artifact_path"] = path.as_posix()
        packs.append(pack)
    return packs


def choose_format_pack(
    *,
    command: dict[str, Any],
    policy_decision: dict[str, Any],
    channel_model: dict[str, Any],
    brief: dict[str, Any],
    packs: list[dict[str, Any]],
    purpose: str,
    budget_envelope_id: str,
    quality_profile: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Choose a versioned FormatPack using traceable evidence and hard gates."""

    if purpose not in {"PROTOTYPE", "PRODUCTION"}:
        raise ValueError("purpose must be PROTOTYPE or PRODUCTION")
    if policy_decision.get("decision") != "ALLOW":
        raise PermissionError("central policy did not authorize this creative command")
    if purpose == "PROTOTYPE" and quality_profile != "DRAFT":
        raise ValueError("a pre-validation prototype must use the DRAFT profile")
    if purpose == "PRODUCTION" and quality_profile == "DRAFT":
        raise ValueError("DRAFT cannot be selected for production")

    assessments: list[dict[str, Any]] = []
    eligible_states = PROTOTYPE_STATES if purpose == "PROTOTYPE" else PRODUCTION_STATES
    for pack in packs:
        fit, score, evidence, contrary = _fit_assessment(pack, channel_model, brief)
        status = str(pack["capability_status"])
        rejection_reasons: list[str] = []
        eligible = status in eligible_states
        if purpose == "PRODUCTION" and not pack.get("production_allowed"):
            eligible = False
            rejection_reasons.append("production_allowed=false")
        if status not in eligible_states:
            rejection_reasons.append(f"state {status} is not eligible for {purpose}")
        if score < 0.75:
            eligible = False
            rejection_reasons.append(f"selection_score {score} is below 0.75")
        assessments.append(
            {
                "format_pack_id": pack["format_pack_id"],
                "pack_version": pack["version"],
                "capability_status": status,
                "eligible": eligible,
                "fit": fit,
                "selection_score": score,
                "score_coverage": 1.0,
                "cost": pack["specification"]["estimated_cost"],
                "capacity": "local zero-external-cost prototype" if purpose == "PROTOTYPE" else "production",
                "evidence": evidence,
                "contrary_evidence": contrary,
                "rejection_reasons": rejection_reasons,
            }
        )

    assessments.sort(key=lambda item: (-item["selection_score"], item["format_pack_id"], item["pack_version"]))
    eligible = [item for item in assessments if item["eligible"]]
    selected = eligible[0] if eligible else None
    decision = "SELECT" if selected else "BLOCK_NO_ELIGIBLE_PACK"
    selected_pack = None
    if selected:
        selected_pack = {
            "format_pack_id": selected["format_pack_id"],
            "version": selected["pack_version"],
            "selection_reason": (
                f"Highest eligible evidence-backed score ({selected['selection_score']}) "
                f"for {purpose}; score coverage={selected['score_coverage']}."
            ),
            "limitation_match": "DRAFT prototype only; publication blocked" if purpose == "PROTOTYPE" else None,
        }

    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    brief_id = str(brief["brief_id"])
    command_id = str(command["command_id"])
    decision_id = _stable_id("creative-direction", command_id, brief_id, purpose, selected["format_pack_id"] if selected else "none")
    prediction_ref = None
    baseline_ref = None
    hypothesis_statement = "A function-assigned cinematic B-roll sequence will communicate the prayer-to-obedience mechanism without inheriting a reference work's identity."
    if selected and selected["format_pack_id"] == "fp-narrated-reflection-static":
        chosen = next(pack for pack in packs if pack["format_pack_id"] == selected["format_pack_id"]
                      and pack["version"] == selected["pack_version"])
        # The forward audio pack must not inherit a cinematic claim. This is
        # the selected, versioned specification, not an observed audience result.
        hypothesis_statement = chosen["specification"]["description"]
    return {
        "schema_version": "1.0.0",
        "decision_id": decision_id,
        "central_command_id": command_id,
        "channel_id": str(brief["channel_id"]),
        "channel_dna_version": str(channel_model["model_id"]),
        "objective_id": str(command["objective_id"]),
        "brief_id": brief_id,
        "narrative_id": f"narrative:{brief_id}",
        "budget_envelope_id": budget_envelope_id,
        "purpose": purpose,
        "evidence_refs": sorted(set(ref for item in assessments for ref in item["evidence"])),
        "candidate_assessments": assessments,
        "selected_format_pack": selected_pack,
        "quality_profile": quality_profile,
        "decision": decision,
        "hypothesis": {
            "statement": hypothesis_statement,
            "predicted_metric": "first_30s_retention",
            "baseline_ref": baseline_ref,
            "prediction_ref": prediction_ref,
            "falsification_condition": "Reject the hypothesis if later measured retention fails to beat the registered channel baseline outside the training sample.",
        },
        "risks": sorted(set(risk for item in assessments for risk in item["contrary_evidence"])),
        "created_at": timestamp,
    }
