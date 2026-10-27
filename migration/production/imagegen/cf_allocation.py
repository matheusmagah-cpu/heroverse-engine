#!/usr/bin/env python3
"""The one predicate for "a FLUX image recorded on main" (E116): cf-images.yml commits each run's records as
"Record <pilot> images from Cloudflare Workers AI (<engine>, run <id>)", one <id>.json per image under images/.
episode_preflight.cf_images_today (git log) and ops/dispatch_guard.py (REST) both count today's FLUX images with it,
against episode_preflight.CF_DAILY_IMAGES."""

MARK = "images from Cloudflare Workers AI (flux"


def flux_record(subject, path):
    """True when `path`, added by a commit whose subject line is `subject`, is one FLUX image's record."""
    return MARK in (subject or "") and "/images/" in path and path.endswith(".json")
