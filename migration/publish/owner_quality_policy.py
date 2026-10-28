"""Additional owner eligibility floor for new uploads, not an editorial review.

The caller supplies the actual (or independently bound) file hash. This pure
check neither generates a score nor substitutes for the canonical QA gates.
"""
import math
import re

# owner, 2026-10-20: "quero 9 pra cima"; owner, 2026-10-23: "9.5 para todos os vídeos em todas as etapas"
OWNER_FLOOR = 9.5


LONG_REVIEWERS = ("claude-session-reviewer", "gpt-6-astra-session-reviewer")
# Explicit session identities only: retain historical Claude reviews and record the GPT handoff truthfully.
SHORTS_REVIEWER = "gemini-3.8-flash"        # Shorts move to the Claude reviewer next (their pipeline is separate)


def check(review, output_sha256, reviewer=SHORTS_REVIEWER):
    """Check one designated model or an explicit tuple; long videos pass LONG_REVIEWERS. Never edit evidence."""
    if not isinstance(review, dict):
        return ["REVIEW_NOT_OBJECT"]
    problems = []
    if review.get("status") != "PASS":
        problems.append("REVIEW_NOT_PASS")
    models = (reviewer,) if isinstance(reviewer, str) else reviewer
    if not isinstance(models, tuple) or review.get("model") not in models:
        problems.append("REVIEW_MODEL_NOT_DESIGNATED")
    overall = review.get("overall")
    if (isinstance(overall, bool) or not isinstance(overall, (int, float))
            or (isinstance(overall, float) and not math.isfinite(overall))):
        problems.append("OVERALL_INVALID")
    elif not OWNER_FLOOR <= overall <= 10.0:
        problems.append("OVERALL_OUTSIDE_OWNER_RANGE")
    hashes = (output_sha256, review.get("output_sha256"))
    if any(not isinstance(h, str) or not re.fullmatch("[0-9a-f]{64}", h) for h in hashes):
        problems.append("INVALID_OUTPUT_SHA256")
    elif hashes[0] != hashes[1]:
        problems.append("REVIEW_NOT_FOR_THIS_FILE")
    return problems
