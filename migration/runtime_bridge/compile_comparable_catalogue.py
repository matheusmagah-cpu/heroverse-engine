import hashlib
import copy
import importlib.util
import json
from pathlib import Path
import sys
from market_comparability import select

native=Path(sys.argv[1]).resolve(); source=Path(sys.argv[2]).resolve(); out=Path(sys.argv[3]).resolve()
out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(native))
module_path=native/'hero_engine/observatory/format_cohorts.py'
spec=importlib.util.spec_from_file_location('heroverse_original_format_cohorts',module_path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
raw=source.read_bytes();bundle,audit=select(json.loads(raw))
bundle=copy.deepcopy(bundle)
for row in bundle['snapshots']:
    if row['entity_type']=='VIDEO':
        # Lossless projection from this collector's observed public-only branch.
        # Original archived observations remain unchanged and are hash pinned.
        assert row['payload']['availability']=='public'
        row['payload'].update(public_fields_only=True,webpage_url=row['source_uri'])
audit['projection']={'fields_added':['public_fields_only','webpage_url'],
    'basis':'PUBLIC_ONLY_OFFICIAL_COLLECTOR_BRANCH_AND_EXACT_SOURCE_URI',
    'original_observations_changed':False}
path=out/'snapshots.json';path.write_text(json.dumps(bundle,ensure_ascii=False,sort_keys=True)+'\n')
cohorts=module.compile_format_cohorts(path)
(out/'cohorts.json').write_text(json.dumps(cohorts,ensure_ascii=False,sort_keys=True)+'\n')
audit.update(source_sha256=hashlib.sha256(raw).hexdigest(),
    filtered_snapshot_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    original_cohort_module_sha256=hashlib.sha256(module_path.read_bytes()).hexdigest(),
    group_summary=[{k:g[k] for k in ('channel_id','age_band','status','sample_count')}
        for g in cohorts['groups']])
(out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps({'eligible_videos':audit['eligible_videos'],'group_summary':audit['group_summary']}))
