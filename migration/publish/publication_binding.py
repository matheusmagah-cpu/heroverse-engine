#!/usr/bin/env python3
"""Fail-closed revalidation of recorded publication evidence; no side effects.
Usage: publication_binding.py PILOT_DIR
This does not compute a new approval or loosen the prepublication rubric.
"""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepublish_gate as canonical_gate

FILES = ('out/qa.json', 'inspection/APPROVAL.json', 'out/manifest.json', 'out/gate.json')


def check(qa, approval, manifest, gate, review=None):
    documents = {'QA': qa, 'APPROVAL': approval, 'MANIFEST': manifest, 'GATE': gate}
    problems = [name + '_NOT_OBJECT' for name, doc in documents.items() if not isinstance(doc, dict)]
    if problems:
        return problems
    if qa.get('status') != 'PASS': problems.append('QA_NOT_PASS')
    if approval.get('approved') is not True: problems.append('NOT_APPROVED')
    hashes = [doc.get('output_sha256') for doc in documents.values()]
    if any(not isinstance(h, str) or not re.fullmatch('[0-9a-f]{64}', h) for h in hashes):
        problems.append('INVALID_OUTPUT_SHA256')
    elif len(set(hashes)) != 1:
        problems.append('EVIDENCE_NOT_FOR_THIS_FILE')
    # reviewer text is deliberately irrelevant: every approval must carry the gate.
    if gate.get('version') != 'prepublish-gate-v1': problems.append('GATE_SCHEMA_INVALID')
    if gate.get('decision') != 'PASS': problems.append('GATE_NOT_PASS')
    if gate.get('eligible_for_automatic_publication') is not True: problems.append('GATE_NOT_ELIGIBLE')
    version = qa.get('criteria_version')
    if version not in canonical_gate.FROZEN_CRITERIA_SHA256:
        problems.append('QA_CRITERIA_VERSION_UNKNOWN')
    compilation = version in canonical_gate.DEFECT_TRACKS   # E251/E259: their own dimensions, no score rows
    if compilation:
        required = {name: {('qa', key) for key in keys} for name, keys in canonical_gate.DEFECT_TRACKS[version][1].items()}
        required['defect_review'] = {('review', key) for key in canonical_gate.COMPILATION_REVIEW_ITEMS}
        required['format'] = {('format', 'story_long')}
        required['binding'] = {('binding', key) for key in ('manifest', 'qa_for_this_file', 'qa_criteria_frozen', 'review_for_this_file')}
        required.update({'full_file_scan': set(), 'preflight': {('preflight', 'preflight')}})
    else:
        mapping = (canonical_gate.dimensions_story_v3(version) if version in canonical_gate.STORY_VERSIONS
                   else canonical_gate.DIMENSIONS_BY_VERSION.get(version, canonical_gate.DIMENSIONS))
        required = {name: {(kind, key) for kind, keys in spec.items() for key in keys}
                    for name, spec in mapping.items()}
        required['content_and_policy'].add(('review', 'overall'))
        required.update({'binding': {('binding', key) for key in ('manifest', 'qa_for_this_file', 'qa_criteria_frozen', 'review_for_this_file')},
                         'scorecard': {('score', key) for key in canonical_gate.score_hard_keys(version)},
                         'full_file_scan': set(), 'preflight': {('preflight', 'preflight')}})
    if version in canonical_gate.STORY_VERSIONS and not compilation:
        story = 'story_qa_' + version.rsplit('-', 1)[-1]
        required[story] = {(story, key) for key in canonical_gate.story_v3_rows(version)}
        required['format'] = {('format', 'story_long')}
    if version in canonical_gate.STANDARD_VERSIONS and not compilation: required.update({'structure': set(), 'authenticity': set()})
    if review is not None:
        if not isinstance(review, dict) or review.get('status') != 'PASS' or review.get('output_sha256') != hashes[0]:
            problems.append('REVIEW_NOT_PASS_FOR_THIS_FILE')
    dimensions, items = gate.get('dimensions'), gate.get('items')
    if not isinstance(dimensions, dict) or not dimensions:
        problems.append('GATE_DIMENSIONS_MISSING')
    else:
        if not set(required) <= set(dimensions): problems.append('GATE_CANONICAL_DIMENSIONS_MISSING')
        if any(state != 'PASS' for state in dimensions.values()): problems.append('GATE_DIMENSION_NOT_PASS')
    if not isinstance(items, dict) or not items:
        problems.append('GATE_ITEMS_MISSING')
    else:
        if isinstance(dimensions, dict) and set(items) != set(dimensions):
            problems.append('GATE_DIMENSION_ITEMS_MISMATCH')
        for name, rows in sorted(items.items()):
            if not isinstance(rows, list) or not rows:
                problems.append('GATE_ITEMS_EMPTY:' + name)
            elif any(not isinstance(row, dict) or row.get('state') != 'PASS' for row in rows):
                problems.append('GATE_ITEM_NOT_PASS:' + name)
            else:
                identities = {(r.get('source'), r.get('item')) for r in rows if isinstance(r.get('source'), str) and isinstance(r.get('item'), str)}
                if not required.get(name, set()) <= identities: problems.append('GATE_CANONICAL_ITEMS_MISSING:' + name)
    return problems


def main(pilot_dir):
    d = Path(pilot_dir)
    try:
        docs = [json.loads((d / name).read_bytes()) for name in FILES]
        review_path = d / 'out/review.json'
        review = json.loads(review_path.read_bytes()) if review_path.exists() else None
        if review_path.exists() and not isinstance(review, dict): raise ValueError('review must be object')
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'FAIL', 'problems': ['EVIDENCE_UNREADABLE:' + type(exc).__name__]}))
        return 1
    problems = check(*docs, review=review)
    if isinstance(docs[0], dict) and docs[0].get('criteria_version') == canonical_gate.COMPILATION:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'production/bible'))
        import compilation_long
        try:
            compilation_long.verify(d)
        except (OSError, ValueError, KeyError, TypeError, SystemExit):
            problems.append('COMPILATION_HANDOFF_INVALID')
    elif isinstance(docs[0], dict) and docs[0].get('criteria_version') == canonical_gate.BUZZY_LONG:   # E259
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'production/bible'))
        import buzzy_long
        try:
            buzzy_long.verify(d)
        except (OSError, ValueError, KeyError, TypeError, SystemExit):
            problems.append('BUZZY_LONG_HANDOFF_INVALID')
    elif isinstance(docs[0], dict) and docs[0].get('criteria_version') in canonical_gate.STORY_VERSIONS:
        # Recheck the plan/script/package/timeline/thumbnail identity at upload as well as at qualification.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'production/bible'))
        import long_handoff
        try:
            long_handoff.verify(d)
        except (OSError, ValueError, KeyError, TypeError, SystemExit):
            problems.append('LONG_HANDOFF_INVALID')
    # owner, 2026-10-26: prayer longs stopped. publish.yml runs this before any upload or resume, so a prayer pilot
    # is refused here even when an older approval and a PASS gate exist for it
    if not canonical_gate.story_long(d):
        problems.append('NOT_STORY_LONG')
    print(json.dumps({'status': 'FAIL' if problems else 'PASS', 'problems': problems,
                      'output_sha256': docs[0].get('output_sha256') if isinstance(docs[0], dict) else None}))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
