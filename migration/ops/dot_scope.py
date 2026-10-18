#!/usr/bin/env python3
"""Scope check of a Dot delivery: every file the PR changes must match the task's ALLOWED PATHS.

The task issue carries a fenced block opened by ```allowed with one glob per line (fnmatch, "*" does not cross "/").
A Dot branch is dot/<issue>-<slug>; a PR from any other branch is not a Dot delivery and is not checked here.
usage: dot_scope.py BRANCH ISSUE_BODY_FILE CHANGED_FILES_FILE   (exit 0 = inside scope)
"""
import re
import sys
from fnmatch import fnmatchcase

BLOCK = re.compile(r"```allowed\s*\n(.*?)```", re.S)


def allowed(body):
    m = BLOCK.search(body or "")
    return [l.strip() for l in m.group(1).splitlines() if l.strip() and not l.strip().startswith("#")] if m else None


def match(path, glob):
    return path.count("/") == glob.count("/") and fnmatchcase(path, glob)


def check(body, changed):
    globs = allowed(body)
    if globs is None:
        return ["NO_ALLOWED_BLOCK in the task issue (Claude must add it)"]
    return [f"OUT_OF_SCOPE {p}" for p in changed if not any(match(p, g) for g in globs)]


def issue_of(branch):
    m = re.match(r"dot/(\d+)-", branch or "")
    return int(m.group(1)) if m else None


if __name__ == "__main__":
    branch, body_file, changed_file = sys.argv[1:4]
    if issue_of(branch) is None:
        print("NOT_A_DOT_BRANCH"); sys.exit(0)
    changed = [l.strip() for l in open(changed_file) if l.strip()]
    problems = check(open(body_file).read(), changed)
    print("\n".join(problems) or f"IN_SCOPE {len(changed)} files")
    sys.exit(1 if problems else 0)
