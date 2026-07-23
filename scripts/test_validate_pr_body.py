import unittest
from validate_pr_body import REQUIRED_REVIEW_ITEMS, validate


REVIEW = "\n".join(f"- [x] {item}" for item in REQUIRED_REVIEW_ITEMS)
BASE = f"""## Related task
- Issue: Closes #1
- Explicit human authorization:
  - Authorization source:
  - Goal:
  - Scope:

## Result
Done.

## Changes
Changed files.

## Verification
Tests passed.

## Agent self-review
{REVIEW}
"""


class ValidatePrBodyTests(unittest.TestCase):
    def test_valid_issue(self): self.assertEqual([], validate(BASE))
    def test_valid_authorization(self):
        body = BASE.replace("Closes #1", "").replace("  - Authorization source:\n  - Goal:\n  - Scope:", "  - Authorization source: chat\n  - Goal: fix\n  - Scope: scripts")
        self.assertEqual([], validate(body))
    def test_html_comment_is_allowed(self): self.assertEqual([], validate("<!-- 二选一，删除不适用项。 -->\n" + BASE))
    def test_both_paths(self): self.assertTrue(validate(BASE.replace("  - Authorization source:", "  - Authorization source: chat")))
    def test_no_paths(self): self.assertTrue(validate(BASE.replace("Closes #1", "")))
    def test_placeholder(self): self.assertTrue(validate(BASE.replace("#1", "#<number>")))
    def test_empty_sections(self):
        for heading in ("Result", "Changes", "Verification"):
            self.assertTrue(validate(BASE.replace(f"## {heading}\n" + {"Result":"Done.", "Changes":"Changed files.", "Verification":"Tests passed."}[heading], f"## {heading}")))
    def test_missing_review_item(self): self.assertTrue(validate(BASE.replace(f"- [x] {REQUIRED_REVIEW_ITEMS[0]}\n", "")))
    def test_unrelated_review_item_does_not_pass(self): self.assertTrue(validate(BASE.replace(REVIEW, "- [x] Reviewed")))
    def test_review_item_unchecked(self): self.assertTrue(validate(BASE.replace(f"[x] {REQUIRED_REVIEW_ITEMS[0]}", f"[ ] {REQUIRED_REVIEW_ITEMS[0]}")))
    def test_authorization_fields(self):
        for field in ("Authorization source: chat", "Goal: fix", "Scope: scripts"):
            body = BASE.replace("Closes #1", "").replace("  - Authorization source:\n  - Goal:\n  - Scope:", "  - Authorization source: chat\n  - Goal: fix\n  - Scope: scripts").replace(field, field.split(":")[0] + ":")
            self.assertTrue(validate(body))
    def test_invalid_issue(self): self.assertTrue(validate(BASE.replace("#1", "not-an-issue")))


if __name__ == "__main__":
    unittest.main()