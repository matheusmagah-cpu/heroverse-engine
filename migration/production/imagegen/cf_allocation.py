#!/usr/bin/env python3
"""The one predicate for "a FLUX image recorded on main" (E116): cf-images.yml commits each run's records as
"Record <pilot> images from Cloudflare Workers AI (<engine>, run <id>)", one <id>.json per image under images/.
episode_preflight.cf_images_today (git log) and ops/dispatch_guard.py (REST) both count today's FLUX images with it,
against episode_preflight.CF_DAILY_IMAGES. scene-stills.yml commits its candidates the same way ("Record scene stills
images from Cloudflare Workers AI (flux, run <id>; ...)", one bible/stills/candidates/<cid>.json per image) to its
review branch claude/stills-<episode>-<run>; the guard reads those branches too."""

MARK = "images from Cloudflare Workers AI (flux"
STILLS_BRANCH = "claude/stills-"


def flux_record(subject, path):
    """True when `path`, added by a commit whose subject line is `subject`, is one FLUX image's record."""
    return (MARK in (subject or "") and path.endswith(".json")
            and ("/images/" in path or "/stills/candidates/" in path))
