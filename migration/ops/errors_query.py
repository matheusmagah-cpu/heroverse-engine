#!/usr/bin/env python3
"""E263: query ERRORS.json without reading it whole.
  errors_query.py E262          print one entry
  errors_query.py --grep word   ids and one-line errors that match
  errors_query.py --class name  ids of that class (to build `prior` lists)"""
import json
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parent / "ERRORS.json"


def classes(e):
    c = e.get("class")
    return [c] if isinstance(c, str) else list(c or [])


def run(argv, errors):
    if len(argv) == 2 and argv[0] == "--class":
        return [e["id"] for e in errors if argv[1] in classes(e)]
    if len(argv) == 2 and argv[0] == "--grep":
        w = argv[1].lower()
        return [f"{e['id']}: {str(e.get('error', ''))[:160]}" for e in errors
                if w in json.dumps(e, ensure_ascii=False).lower()]
    if len(argv) == 1 and not argv[0].startswith("-"):
        hit = [e for e in errors if e["id"].lower() == argv[0].lower()]
        return [json.dumps(hit[0], indent=2, ensure_ascii=False)] if hit else []
    raise SystemExit(__doc__)


def main(argv=None):
    errors = json.loads(PATH.read_text())["errors"]
    out = run(sys.argv[1:] if argv is None else argv, errors)
    print("\n".join(out))
    return 0 if out else 1


if __name__ == "__main__":
    sys.exit(main())
