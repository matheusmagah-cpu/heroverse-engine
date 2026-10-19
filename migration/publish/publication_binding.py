#!/usr/bin/env python3
"""Fail-closed revalidation of recorded publication evidence; no side effects.
Usage: publication_binding.py PILOT_DIR
This does not compute a new approval or loosen the prepublication rubric.
"""
import json
from pathlib import Path
import re
import sys

FILES = ('out/qa.json', 'inspection/APPROVAL.json', 'out/manifest.json', 'out/gate.json')


def check(qa, approval, manifest, gate):
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
    dimensions, items = gate.get('dimensions'), gate.get('items')
    if not isinstance(dimensions, dict) or not dimensions:
        problems.append('GATE_DIMENSIONS_MISSING')
    elif any(state != 'PASS' for state in dimensions.values()):
        problems.append('GATE_DIMENSION_NOT_PASS')
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
    return problems


def main(pilot_dir):
    d = Path(pilot_dir)
    try:
        docs = [json.loads((d / name).read_bytes()) for name in FILES]
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'FAIL', 'problems': ['EVIDENCE_UNREADABLE:' + type(exc).__name__]}))
        return 1
    problems = check(*docs)
    print(json.dumps({'status': 'FAIL' if problems else 'PASS', 'problems': problems,
                      'output_sha256': docs[0].get('output_sha256') if isinstance(docs[0], dict) else None}))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
