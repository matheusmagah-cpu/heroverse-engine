"""Resolve pinned legacy file bindings in the migrated root without rewriting history."""
import hashlib
from pathlib import Path,PureWindowsPath
LEGACY_ROOT=PureWindowsPath(r'C:\Users\mathe\OneDrive\Área de Trabalho\Modelagem Youtube')
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def resolve_bound_file(root,location,expected_sha256):
 root=Path(root).resolve()
 if not isinstance(location,str) or not isinstance(expected_sha256,str) or len(expected_sha256.removeprefix('sha256:'))!=64:raise PermissionError('INVALID_FILE_BINDING')
 win=PureWindowsPath(location)
 if win.drive:
  try:relative=win.relative_to(LEGACY_ROOT)
  except ValueError:raise PermissionError('UNAPPROVED_LEGACY_ROOT')
  if '..' in relative.parts:raise PermissionError('PATH_TRAVERSAL')
  path=root.joinpath(*relative.parts)
 else:
  p=Path(location);path=p if p.is_absolute() else root/p
 resolved=path.resolve()
 if not resolved.is_relative_to(root):raise PermissionError('BOUND_FILE_OUTSIDE_MIGRATED_ROOT')
 if not resolved.is_file():raise FileNotFoundError(str(resolved.relative_to(root)))
 if digest(resolved)!=expected_sha256.removeprefix('sha256:'):raise PermissionError('BOUND_FILE_HASH_MISMATCH')
 return resolved
