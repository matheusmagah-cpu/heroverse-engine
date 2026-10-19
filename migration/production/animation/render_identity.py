#!/usr/bin/env python3
"""Render identity for the animation backend (stdlib only).

  render_identity.py CRITERIA key=value [key=value ...]

`render_id(fields)` = sha256 hex of json.dumps(fields, sort_keys=True,
separators=(",", ":")). Any change of any field gives a new render_id; review
and approval bind to it.

The CLI builds exactly the fields named in the criteria `render_identity.fields`
(a name's first word is its key, so "bundle_sha256 (each file)" is
`bundle_sha256`). `criteria_sha256` is the sha256 of CRITERIA itself and is
never passed. Every other field is given as key=value:
  - a key ending in `_sha256` takes a path: a file gives its sha256; a directory
    gives {relative path: sha256} for each file in it (bundle_sha256); the same
    key given several times gives {file name: sha256} (e.g. one SRT per output);
  - any other key is a scalar: the value is parsed as JSON when it is a JSON
    number/boolean (samples=16 -> 16, fps=24 -> 24), otherwise kept as text
    (blender_version=4.3.2, resolution=1920x1080).
A missing or unknown field exits 1 (MISSING_FIELD / UNKNOWN_FIELD). Prints
{"render_id", "fields"} as JSON.
"""
import hashlib
import json
from pathlib import Path
import sys


def render_id(fields):
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def field_names(criteria):
    return [name.split()[0] for name in criteria["render_identity"]["fields"]]


def _hash_path(path):
    p = Path(path)
    if p.is_dir():
        return {f.relative_to(p).as_posix(): sha256_file(f) for f in sorted(p.rglob("*")) if f.is_file()}
    return sha256_file(p)


def _scalar(text):
    try:
        value = json.loads(text)
    except ValueError:
        return text
    return value if isinstance(value, (int, float, bool)) else text


def build_fields(criteria_path, pairs):
    criteria = json.loads(Path(criteria_path).read_text())
    names = field_names(criteria)
    given = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise ValueError("BAD_ARGUMENT %s" % pair)
        if key not in names or key == "criteria_sha256":
            raise ValueError("UNKNOWN_FIELD %s" % key)
        given.setdefault(key, []).append(value)
    fields = {"criteria_sha256": sha256_file(criteria_path)} if "criteria_sha256" in names else {}
    for key, values in given.items():
        if key.endswith("_sha256"):
            if len(values) == 1:
                fields[key] = _hash_path(values[0])
            else:
                names_seen = [Path(v).name for v in values]
                if len(set(names_seen)) != len(names_seen):
                    raise ValueError("DUPLICATE_FILE_NAME %s" % key)
                fields[key] = {Path(v).name: _hash_path(v) for v in values}
        else:
            if len(values) != 1:
                raise ValueError("REPEATED_SCALAR %s" % key)
            fields[key] = _scalar(values[0])
    missing = [n for n in names if n not in fields]
    if missing:
        raise ValueError("MISSING_FIELD %s" % " ".join(missing))
    return fields


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        fields = build_fields(argv[1], argv[2:])
    except (ValueError, OSError) as e:
        print(str(e))
        return 1
    print(json.dumps({"render_id": render_id(fields), "fields": fields}, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
