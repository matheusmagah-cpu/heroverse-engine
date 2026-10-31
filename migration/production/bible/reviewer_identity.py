"""Truthful session attribution for new Bible-production approvals (E149).

Old approvals without a model remain historical records: never relabel them as a new review.
Every new writer requires an explicit identity from the publication policy's one allowlist.
This validates attribution, not whether somebody actually watched or whether quality passed.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "publish"))
from owner_quality_policy import LONG_REVIEWERS  # noqa: E402


def valid(record):
    """Legacy absence is preserved; a present null, empty, or unknown model is never accepted."""
    return isinstance(record, dict) and ("model" not in record or record["model"] in LONG_REVIEWERS)


def require(model):
    if model not in LONG_REVIEWERS:
        raise SystemExit(f"REVIEWER_IDENTITY_REFUSED {model!r} (explicit --reviewer from {LONG_REVIEWERS})")
    return model
