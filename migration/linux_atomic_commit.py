"""Linux evidence commit: same-filesystem atomic link, never replace a receipt."""
import os
from pathlib import Path
import stat
import uuid

def resident(path, *, exists=True):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item == path and not exists and not item.exists():
            continue
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('linked evidence path forbidden')
    return path

def commit_new(source, destination):
    source = resident(source)
    destination = resident(destination, exists=False)
    if destination.exists():
        raise FileExistsError('immutable receipt already exists')
    if not destination.parent.is_dir():
        raise ValueError('existing resident evidence parent required')
    temporary = destination.parent / ('.' + destination.name + '.' + uuid.uuid4().hex + '.complete')
    raw = source.read_bytes()
    with temporary.open('xb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    # Atomic create-if-absent on the same filesystem; failure retains preimage.
    os.link(temporary, destination, follow_symlinks=False)
    directory = os.open(destination.parent, os.O_DIRECTORY | os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    if destination.read_bytes() != raw:
        raise ValueError('committed evidence differs; preserve all files')
    return {'destination': str(destination), 'retained_complete': str(temporary),
            'bytes': len(raw), 'replacement_performed': False,
            'release_authority': False}
