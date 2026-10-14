"""Apply a hash-bound admission guard to a new shadow; preserve frozen v1."""
import hashlib, json, shutil
from pathlib import Path
SOURCE_SHA = '83782468c936676211fc77dcc09bcc15c9949e7a09c753de1c501a4ccc106a3e'
MODULE = 'hero_engine/phase6_intelligence.py'
def apply(source, destination, guard):
    source, destination, guard = map(lambda x: Path(x).resolve(), (source, destination, guard))
    if destination.exists() or destination == source or source in destination.parents:
        raise PermissionError('NEW_SEPARATE_SHADOW_REQUIRED')
    raw = (source / MODULE).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise PermissionError('PREDICTION_SOURCE_IDENTITY_CHANGED')
    guard_raw = guard.read_bytes(); guard_hash = hashlib.sha256(guard_raw).hexdigest()
    anchor = '    cutoff = _parse(str(feature_snapshot["captured_at"]))\n'
    text = raw.decode('utf-8')
    if text.count(anchor) != 1:
        raise PermissionError('EXACT_PREDICTION_ANCHOR_REQUIRED')
    inserted = ('    from . import prediction_provenance_guard as _prediction_guard\n'
                f'    if hashlib.sha256(Path(_prediction_guard.__file__).read_bytes()).hexdigest() != "{guard_hash}":\n'
                '        raise PermissionError("PREDICTION_GUARD_IDENTITY_CHANGED")\n'
                '    _prediction_guard.require_prediction_basis(feature_snapshot, comparable_outcomes)\n')
    text = text.replace(anchor, inserted + anchor)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__'))
    (destination / MODULE).write_text(text, encoding='utf-8')
    (destination / 'hero_engine/prediction_provenance_guard.py').write_bytes(guard_raw)
    receipt = {'version': 'prediction-provenance-shadow-v1', 'original_sha256': SOURCE_SHA,
               'shadow_sha256': hashlib.sha256(text.encode()).hexdigest(), 'guard_sha256': guard_hash,
               'original_preserved': True, 'status': 'SHADOW_GUARD_NOT_DEPLOYED',
               'calibrated_forecast_available': False, 'production_ready': False}
    (destination / 'prediction-provenance-overlay.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt
