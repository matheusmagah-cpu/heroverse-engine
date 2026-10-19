"""Teach the native frozen-artifact reader explicit hash-bound legacy resolution."""
import hashlib
from pathlib import Path
PIN='1850a90009b9fc939eb86eca51f778d198bca12939b5985143f37a8bb80d123d'
def apply(root):
 root=Path(root).resolve();p=root/'hero_engine/phase5_youtube_publisher.py';raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=PIN:raise PermissionError('NATIVE_PUBLISHER_IDENTITY_CHANGED')
 text=raw.decode();start=text.index('def _validate_release(');end=text.index('\ndef _validate_current_release',start);part=text[start:end]
 anchor='    Draft202012Validator(_read(root / "schemas/phase5_release_gate.schema.json")).validate(release)'
 if part.count(anchor)!=1 or part.count('path = Path(artifact["path"])')!=1 or part.count('path = Path(human["path"])')!=1:raise PermissionError('EXACT_READER_ANCHORS_REQUIRED')
 part=part.replace(anchor,'    from .legacy_cloud_bindings import resolve_bound_file\n'+anchor).replace('path = Path(artifact["path"])','path = resolve_bound_file(root, artifact["path"], artifact["sha256"])').replace('path = Path(human["path"])','path = resolve_bound_file(root, human["path"], human["sha256"])')
 helper=Path(__file__).with_name('path_bindings.py').read_bytes()
 target=root/'hero_engine/legacy_cloud_bindings.py'
 if target.exists():raise PermissionError('READER_ADAPTER_ALREADY_EXISTS')
 target.write_bytes(helper);p.write_text(text[:start]+part+text[end:])
 return {'original_publisher_sha256':PIN,'shadow_publisher_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'resolver_sha256':hashlib.sha256(helper).hexdigest(),'historical_receipts_rewritten':False,'current_release_recomputation_preserved':True,'production_authorized':False}
