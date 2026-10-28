import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owner_quality_policy as policy  # noqa: E402

SHA = "a" * 64


def review(**updates):
    return {"status": "PASS", "model": "gemini-3.8-flash", "overall": 9.5,
            "output_sha256": SHA, **updates}


class OwnerQualityPolicy(unittest.TestCase):
    def test_long_reviewers_are_explicit_and_do_not_expand_the_shorts_policy(self):
        self.assertEqual(policy.LONG_REVIEWERS, ("claude-session-reviewer", "gpt-6-astra-session-reviewer"))
        self.assertEqual(policy.SHORTS_REVIEWER, "gemini-3.8-flash")
        for model in policy.LONG_REVIEWERS:
            with self.subTest(model=model):
                r = review(model=model)
                self.assertEqual(policy.check(r, SHA, policy.LONG_REVIEWERS), [])
                self.assertIn("REVIEW_MODEL_NOT_DESIGNATED", policy.check(r, SHA))
        for model in ("gpt-6-astra", "gpt-6-astra-session-reviewer-other", "gemini-3.8-flash", None, True):
            with self.subTest(unknown_model=model):
                self.assertIn("REVIEW_MODEL_NOT_DESIGNATED",
                              policy.check(review(model=model), SHA, policy.LONG_REVIEWERS))

    def test_each_long_reviewer_still_requires_pass_floor_and_file_binding(self):
        for model in ("claude-session-reviewer", "gpt-6-astra-session-reviewer"):
            for changes, expected in (({"status": "FAIL"}, "REVIEW_NOT_PASS"),
                                      ({"overall": 9.49}, "OVERALL_OUTSIDE_OWNER_RANGE"),
                                      ({"overall": float("nan")}, "OVERALL_INVALID"),
                                      ({"output_sha256": "b" * 64}, "REVIEW_NOT_FOR_THIS_FILE")):
                with self.subTest(model=model, changes=changes):
                    self.assertIn(expected, policy.check(review(model=model, **changes), SHA,
                                                         policy.LONG_REVIEWERS))

    def test_inclusive_range(self):
        for value in (9.5, 9.7, 10, 10.0):
            with self.subTest(value=value):
                self.assertEqual(policy.check(review(overall=value), SHA), [])

    def test_below_floor_above_ten_and_invalid_scores_fail_closed(self):
        for value in (8.5, 8.99, 9, 9.0, 9.3, 9.49, -1, 10.01, 11, 10 ** 400, float("nan"), float("inf"),
                      float("-inf"), True, False, None, "9", [], {}):
            with self.subTest(value=value):
                self.assertTrue(policy.check(review(overall=value), SHA))
        missing = review()
        del missing["overall"]
        self.assertEqual(policy.check(missing, SHA), ["OVERALL_INVALID"])

    def test_requires_dictionary_pass_and_designated_model(self):
        for value in (None, [], "PASS", 9, True):
            with self.subTest(value=value):
                self.assertEqual(policy.check(value, SHA), ["REVIEW_NOT_OBJECT"])
        for field, values in (("status", (None, "FAIL", "ERROR", "pass", True)),
                              ("model", (None, "gemini-3.6-flash", "gemini-3.5-flash-lite", True))):
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertTrue(policy.check(review(**{field: value}), SHA))
            missing = review()
            del missing[field]
            self.assertTrue(policy.check(missing, SHA))

    def test_hashes_must_be_valid_lowercase_and_match(self):
        for value in (None, "", "abc", "a" * 63, "a" * 65, "A" * 64, "g" * 64, SHA + "\n", 9, True, []):
            with self.subTest(value=value):
                self.assertIn("INVALID_OUTPUT_SHA256", policy.check(review(), value))
                self.assertIn("INVALID_OUTPUT_SHA256", policy.check(review(output_sha256=value), SHA))
        self.assertEqual(policy.check(review(output_sha256="b" * 64), SHA), ["REVIEW_NOT_FOR_THIS_FILE"])
        missing = review()
        del missing["output_sha256"]
        self.assertEqual(policy.check(missing, SHA), ["INVALID_OUTPUT_SHA256"])

    def test_does_not_mutate_evidence_or_claim_editorial_approval(self):
        original = review(overall=8.5, issues=[{"text": "preserve the original verdict"}])
        before = copy.deepcopy(original)
        self.assertEqual(policy.check(original, SHA), ["OVERALL_OUTSIDE_OWNER_RANGE"])
        self.assertEqual(original, before)
        self.assertEqual(original["status"], "PASS")
        self.assertEqual(policy.check(review(status="FAIL", overall=9.5), SHA), ["REVIEW_NOT_PASS"])


if __name__ == "__main__":
    unittest.main()
