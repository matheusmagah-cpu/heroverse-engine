"""Additional owner eligibility floor for new uploads, not an editorial review.

The caller supplies the actual (or independently bound) file hash. This pure
check neither generates a score nor substitutes for the canonical QA gates.
"""
import math
import re

# owner, 2026-10-20: "quero 9 pra cima"; owner, 2026-10-23: "9.5 para todos os vídeos em todas as etapas"
OWNER_FLOOR = 9.5


LONG_REVIEWER = "claude-session-reviewer"  # owner 2026-10-24: replaces gemini-3.8-flash for long videos
SHORTS_REVIEWER = "gemini-3.8-flash"        # Shorts move to the Claude reviewer next (their pipeline is separate)


def check(review, output_sha256, reviewer=SHORTS_REVIEWER):
    """Return categorical problems without modifying the review evidence. Long videos pass LONG_REVIEWER."""
    if not isinstance(review, dict):
        return ["REVIEW_NOT_OBJECT"]
    problems = []
    if review.get("status") != "PASS":
        problems.append("REVIEW_NOT_PASS")
    if review.get("model") != reviewer:
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
