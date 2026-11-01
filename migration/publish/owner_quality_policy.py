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


def evidence_valid(review):
    """Validate the session evidence shape, not whether anyone actually watched it."""
    if not isinstance(review, dict):
        return False
    evidence, issues = review.get("evidence"), review.get("issues")
    return (isinstance(evidence, list) and bool(evidence) and isinstance(issues, list)
            and all(isinstance(s, str) and bool(s.strip()) for s in evidence + issues))


def score_valid(value):
    """Scores are finite real numbers on the rubric's 0-10 scale, never booleans."""
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and 0 <= value <= 10)


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


# E251 (owner, 2026-11-01): the compilation track of a long is gated on defects, like the buzzy Short (E250), not on
# the 9.5 floor. Only the compilation of an arc's public Shorts uses it (prepublish_gate.COMPILATION).
COMPILATION_BLOCKING = ("a", "b", "e")
COMPILATION_CATEGORIES = ("a", "b", "c", "d", "e", "f", "info")
COMPILATION_DECIDER = "claude-session-reviewer"


def compilation_problems(review, output_sha256):
    """The defect gate: a designated reviewer's file bound to this master, every issue classified exactly once, no
    unresolved [a] speech cut off, [b] scene against its line or story order, [e] policy, and a publish decision by
    the decider with a note. Scores are information and gate nothing. Never edits evidence."""
    if not isinstance(review, dict):
        return ["REVIEW_NOT_OBJECT"]
    out = []
    if review.get("model") not in LONG_REVIEWERS:
        out.append("REVIEW_MODEL_NOT_DESIGNATED")
    hashes = (output_sha256, review.get("output_sha256"))
    if any(not isinstance(h, str) or not re.fullmatch("[0-9a-f]{64}", h) for h in hashes):
        out.append("INVALID_OUTPUT_SHA256")
    elif hashes[0] != hashes[1]:
        out.append("REVIEW_NOT_FOR_THIS_FILE")
    if not evidence_valid(review):
        out.append("REVIEW_EVIDENCE_INVALID")
    decision = review.get("publish_decision")
    if not (isinstance(decision, dict) and decision.get("decision") == "publish"
            and decision.get("by") == COMPILATION_DECIDER
            and isinstance(decision.get("note"), str) and decision["note"].strip()):
        out.append("REVIEW_DECISION_MISSING")
    issues = review.get("issues") if isinstance(review.get("issues"), list) else []
    defects = review.get("defects")
    if not isinstance(defects, list) or not all(
            isinstance(d, dict) and d.get("category") in COMPILATION_CATEGORIES and type(d.get("resolved")) is bool
            and type(d.get("issue")) is int and 0 <= d["issue"] < len(issues) for d in defects):
        return out + ["REVIEW_DEFECTS_INVALID"]
    if any(d["category"] in COMPILATION_BLOCKING and not d["resolved"] for d in defects):
        out.append("REVIEW_DEFECT_UNRESOLVED")
    if len({d["issue"] for d in defects}) != len(defects) or {d["issue"] for d in defects} != set(range(len(issues))):
        out.append("REVIEW_DEFECTS_INVALID")
    return out
