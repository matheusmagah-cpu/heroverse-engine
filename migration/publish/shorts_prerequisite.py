#!/usr/bin/env python3
"""Read-only prerequisite: Shorts may spend quota only after their long qualifies."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import publication_binding as binding


def problems(pilot_dir):
    d = Path(pilot_dir)
    if (d.parents[1] / 'ops/PUBLICATION_HOLD').exists():
        return ['PUBLICATION_HOLD']
    try:
        docs = [json.loads((d / name).read_bytes()) for name in binding.FILES]
        review = json.loads((d / 'out/review.json').read_bytes())
        script_sha = hashlib.sha256((d / 'script.json').read_bytes()).hexdigest()
    except (OSError, ValueError):
        return ['LONG_EVIDENCE_UNREADABLE']
    errors = binding.check(*docs, review=review)
    qa, _, manifest, _ = docs
    if not isinstance(review, dict): errors.append('LONG_REVIEW_MISSING')
    if not isinstance(qa, dict) or qa.get('criteria_version') != 'pilot-qa-criteria-v3':
        errors.append('LONG_NOT_V3')
    if not isinstance(qa, dict) or qa.get('criteria_sha256') != binding.canonical_gate.FROZEN_CRITERIA_SHA256['pilot-qa-criteria-v3']:
        errors.append('LONG_CRITERIA_HASH_CHANGED')
    if not isinstance(manifest, dict) or manifest.get('script_sha256') != script_sha:
        errors.append('LONG_SCRIPT_CHANGED')
    return errors


def ready(pilot_dir):
    return not problems(pilot_dir)


def main(pilot_dir):
    errors = problems(pilot_dir)
    print(json.dumps({'status': 'FAIL' if errors else 'PASS', 'problems': errors}))
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
