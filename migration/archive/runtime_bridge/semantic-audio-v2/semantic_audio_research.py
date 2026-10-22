"""Evidence-bound semantic successor. No acquisition, generation or effect authority."""
from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from jsonschema import Draft202012Validator

VERSION = 'heroverse-semantic-audio-research-v2'

def sha(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
def text(value):
    if not isinstance(value, str) or not value.strip():
        raise PermissionError('SEMANTIC_NONEMPTY_TEXT_REQUIRED')
    return value

def reopen(root, binding, captured):
    if not isinstance(binding, dict) or set(binding) != {'path', 'sha256'}:
        raise PermissionError('SEMANTIC_EXACT_BINDING_REQUIRED')
    relative = Path(binding['path'])
    path = (root / relative).resolve()
    if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(root / 'output/market'):
        raise PermissionError('SEMANTIC_EVIDENCE_ESCAPED_MARKET')
    raw = path.read_bytes()
    if sha(raw) != binding['sha256']:
        raise PermissionError('SEMANTIC_EVIDENCE_HASH_CHANGED')
    captured[path] = raw
    return raw

def verify_editorial(model):
    draft = model['editorial_draft']
    if (draft.get('authorship') != 'ORIGINAL_HEROVERSE'
            or draft.get('language') != 'en-US' or draft.get('speech_placement') != 'ONCE_AT_START'):
        raise PermissionError('SEMANTIC_ORIGINAL_COMPATIBLE_DRAFT_REQUIRED')
    text(draft.get('title')); text(draft.get('angle'))
    sections = draft.get('sections', [])
    if not 3 <= len(sections) <= 12:
        raise PermissionError('SEMANTIC_COMPLETE_NARRATIVE_REQUIRED')
    subtopics = set(model['subtopics'])
    covered = set()
    known = set(model['structure_refs'])
    for section in sections:
        for key in ('role', 'text', 'retention_function', 'original_contribution'):
            text(section.get(key))
        refs = section.get('mechanism_refs', [])
        topics = section.get('subtopics', [])
        if not refs or not set(refs) <= known or not topics or not set(topics) <= subtopics:
            raise PermissionError('SEMANTIC_SECTION_LINEAGE_REQUIRED')
        covered.update(topics)
    if covered != subtopics:
        raise PermissionError('SEMANTIC_SUBTOPIC_NOT_APPLIED')
    # Mechanical plagiarism screen only; passing does not prove originality/rights.
    words = lambda s: re.findall(r"[a-z]+", s.lower())
    grams = lambda w: {tuple(w[i:i+12]) for i in range(max(0,len(w)-11))}
    original = grams(words(' '.join(s['text'] for s in sections)))
    for source in model['source_transcripts']:
        if original & grams(words(source)):
            raise PermissionError('SEMANTIC_VERBATIM_SOURCE_REUSE')
    if model['baseline'].get('editorial_angle') == draft['angle']:
        raise PermissionError('SEMANTIC_NO_NEW_SUBSTANTIVE_ANGLE')
    from .creative_direction import build_christian_rest_editorial
    result = build_christian_rest_editorial()
    result.update(version='heroverse-semantic-rest-editorial-v2', title=draft['title'], angle=draft['angle'],
        research_model_id=model['model_id'], evidence_class='ORIGINAL_DRAFT_WITH_REOPENED_SEMANTIC_MECHANISMS',
        sections=sections, full_text=' '.join(s['text'] for s in sections))
    return result

def build_semantic_audio_research(root, source, *, baseline, semantic_binding):
    from .phase6_production import CHANNEL_ID
    from .observatory.format_cohorts import compile_format_cohorts
    root = Path(root).resolve(); source = Path(source).resolve(); captured = {}
    if not source.is_relative_to(root / 'output/market'):
        raise PermissionError('SEMANTIC_SOURCE_ESCAPED_MARKET')
    raw = source.read_bytes(); captured[source] = raw; bundle = json.loads(raw)
    observed = datetime.fromisoformat(bundle['captured_at'].replace('Z','+00:00'))
    now = datetime.now(timezone.utc)
    if observed.tzinfo is None or not 0 <= (now-observed).total_seconds() <= 86400:
        raise PermissionError('SEMANTIC_FRESH_SNAPSHOT_REQUIRED')
    config_path = root / 'config/current_audio_research.json'
    config_raw = config_path.read_bytes(); captured[config_path] = config_raw
    config = json.loads(config_raw); ids = {r['channel_id'] for r in config['references']}
    if config.get('channel_id') != CHANNEL_ID or config.get('media_downloaded') is not False or len(ids) != 3:
        raise PermissionError('SEMANTIC_REFERENCE_IDENTITY_CHANGED')
    for row in bundle['snapshots']:
        if row['channel_id'] not in ids or row['payload'].get('channel_id_public') != row['channel_id']:
            raise PermissionError('SEMANTIC_PUBLIC_IDENTITY_CHANGED')
    envelope = json.loads(reopen(root, semantic_binding, captured))
    if envelope.get('version') != 'heroverse-semantic-handoff-v1' or envelope.get('channel_id') != CHANNEL_ID:
        raise PermissionError('SEMANTIC_HANDOFF_IDENTITY_REQUIRED')
    if envelope.get('snapshot_binding') != {'path': source.relative_to(root).as_posix(), 'sha256': sha(raw)}:
        raise PermissionError('SEMANTIC_CURRENT_SNAPSHOT_LINK_REQUIRED')
    topic = text(envelope.get('topic'))
    if topic == baseline.get('topic'):
        raise PermissionError('SEMANTIC_NO_NEW_TOPIC')
    subtopics = envelope.get('subtopics', [])
    if not subtopics or len(set(subtopics)) != len(subtopics):
        raise PermissionError('SEMANTIC_DISTINCT_SUBTOPICS_REQUIRED')
    for value in subtopics: text(value)
    cohorts = compile_format_cohorts(source)
    eligible = {}
    for group in cohorts['groups']:
        if (group['population_scope'] == 'MARKET' and group['content_format'] == 'LONG'
                and group['age_band'] in ('0_7D','8_30D') and group['status'] == 'SUFFICIENT'):
            for member in group['members']:
                eligible[member['snapshot_id']] = (member, group)
    schema_path = root / 'schemas/video_mining.schema.json'
    schema_raw = schema_path.read_bytes(); captured[schema_path] = schema_raw
    validator = Draft202012Validator(json.loads(schema_raw))
    snapshots = {r['snapshot_id']: r for r in bundle['snapshots']}
    evidence_rows = []; known = []; transcripts = []; seen = set(); winners = set(); kinds = set(); age_bands = set()
    input_bindings = [{'path':source.relative_to(root).as_posix(),'sha256':sha(raw)},
        {'path':'config/current_audio_research.json','sha256':sha(config_raw)},semantic_binding,
        {'path':'schemas/video_mining.schema.json','sha256':sha(schema_raw)}]
    for record in envelope.get('records', []):
        sid = record['snapshot_id']
        if sid in seen or sid not in eligible: raise PermissionError('SEMANTIC_CURRENT_COHORT_REQUIRED')
        seen.add(sid); member, group = eligible[sid]; snap = snapshots[sid]
        mining_raw = reopen(root, record['mining_binding'], captured); mining = json.loads(mining_raw)
        validator.validate(mining)
        if (mining['source']['video_id'] != snap['entity_id'] or mining['source']['channel_id'] != snap['channel_id']
                or mining['source'].get('language') not in ('en','en-US')
                or mining['quality']['manual_review_status'] != 'APPROVED'
                or mining['quality']['evidence_resolvable'] is not True):
            raise PermissionError('SEMANTIC_REVIEWED_MATCHING_AV_REQUIRED')
        published = datetime.fromisoformat(mining['source']['published_at'].replace('Z','+00:00'))
        if (published.tzinfo is None or published.timestamp() != snap['payload'].get('timestamp')
                or mining['source']['duration_ms'] != snap['payload'].get('duration_seconds',0)*1000):
            raise PermissionError('SEMANTIC_CURRENT_SOURCE_CLOCK_REQUIRED')
        # Resolve referenced lightweight artifacts against their actual pinned bytes.
        artifacts = record.get('artifact_bindings', {})
        evidences = {}
        def index_evidence(value):
            if isinstance(value, dict):
                if 'evidence_id' in value:
                    key = value['evidence_id']
                    if key in evidences and evidences[key] != value:
                        raise PermissionError('SEMANTIC_AMBIGUOUS_EVIDENCE_ID')
                    evidences[key] = value
                for child in value.values(): index_evidence(child)
            elif isinstance(value, list):
                for child in value: index_evidence(child)
        index_evidence(mining)
        def resolve(refs):
            if not refs: raise PermissionError('SEMANTIC_EVIDENCE_REFS_REQUIRED')
            for ref in refs:
                if ref not in evidences: raise PermissionError('SEMANTIC_UNRESOLVED_EVIDENCE')
                artifact = evidences[ref]['artifact']
                if artifact not in artifacts: raise PermissionError('SEMANTIC_ARTIFACT_PIN_REQUIRED')
                reopen(root, artifacts[artifact], captured)
        analysis = mining['content_analysis']
        for name in ('topic','angle','thesis'):
            claim = analysis[name]
            if claim['class'] in ('UNKNOWN','PRIVATE'): raise PermissionError('SEMANTIC_KNOWN_CLAIM_REQUIRED')
            resolve(claim['evidence_refs'])
        assignments = record.get('subtopic_evidence', {})
        if set(assignments) != set(subtopics): raise PermissionError('SEMANTIC_SUBTOPIC_EVIDENCE_REQUIRED')
        for refs in assignments.values(): resolve(refs)
        mined_information = {item for segment in mining['narrative_segments'] for item in segment['information']}
        if not set(subtopics) <= mined_information:
            raise PermissionError('SEMANTIC_SUBTOPICS_ABSENT_FROM_MINING')
        chosen = record.get('segment_ids', [])
        segments = {s['segment_id']:s for s in mining['narrative_segments']}
        if not chosen or len(set(chosen)) != len(chosen): raise PermissionError('SEMANTIC_STRUCTURE_REQUIRED')
        for segment_id in chosen:
            if segment_id not in segments: raise PermissionError('SEMANTIC_SEGMENT_MISSING')
            segment = segments[segment_id]
            if not 0 <= segment['start_ms'] < segment['end_ms'] <= mining['source']['duration_ms']:
                raise PermissionError('SEMANTIC_SEGMENT_CLOCK_INVALID')
            refs = [e['evidence_id'] for e in segment['evidence']]
            # Segment-local evidence may share IDs with content evidence; all must resolve.
            for e in segment['evidence']: evidences[e['evidence_id']] = e
            resolve(refs)
            known.append(sid + ':' + segment_id)
        transcript_binding = record['transcript_binding']
        reviewed = mining['transcript']['reviewed_artifact']
        if not reviewed or artifacts.get(reviewed) != transcript_binding:
            raise PermissionError('SEMANTIC_REVIEWED_TRANSCRIPT_LINK_REQUIRED')
        transcript_raw = reopen(root, transcript_binding, captured)
        transcripts.append(transcript_raw.decode('utf-8-sig'))
        input_bindings.extend([record['mining_binding'],transcript_binding,*artifacts.values()])
        evidence_rows.append({'snapshot_id':sid,'topic_claim':analysis['topic'], 'angle_claim':analysis['angle'],
            'subtopic_evidence':assignments,'segments':[segments[s] for s in chosen], 'cohort_member':member})
        kinds.add(member['kind']); age_bands.add(group['age_band'])
        if member['kind'] == 'WINNER': winners.add(group['channel_id'])
    if len(winners) < 3 or not {'WINNER','MEDIAN','WEAK'} <= kinds or len(age_bands) != 1:
        raise PermissionError('SEMANTIC_WINNERS_AND_COUNTEREVIDENCE_REQUIRED')
    result = {'version':VERSION,'channel_id':CHANNEL_ID,'language':'en-US','topic':topic,'subtopics':subtopics,
        'baseline':baseline,'cohorts':cohorts,'supporting_channels':sorted(winners),'inputs':input_bindings,
        'semantic_binding':semantic_binding,'evidence_rows':evidence_rows,'structure_refs':known,
        'source_transcripts':transcripts,'editorial_draft':envelope['editorial_draft'],
        'evidence_class':'REVIEWED_AV_SEMANTIC_HYPOTHESIS_NOT_CAUSAL_OR_CTR',
        'limitations':['No public competitor CTR, RPM or audience forecast inferred.',
            'Pinned review labels are provenance, not a new human review or media rights approval.',
            'Structural originality screen is necessary but insufficient for quality or YPP.'],
        'authority':{'quality':False,'render':False,'publication':False}}
    result['model_id'] = 'semantic-audio-' + hashlib.sha256(canonical(result)).hexdigest()[:20]
    verify_editorial(result)
    if any(path.read_bytes() != data for path,data in captured.items()):
        raise PermissionError('SEMANTIC_INPUT_CHANGED_DURING_CAPTURE')
    return result


def handoff_source(root, binding):
    root = Path(root).resolve(); captured = {}
    envelope = json.loads(reopen(root,binding,captured))
    snapshot = envelope['snapshot_binding']
    reopen(root,snapshot,captured)
    return (root/snapshot['path']).resolve()
