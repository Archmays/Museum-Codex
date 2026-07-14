from pathlib import Path
import unittest

from scripts.validate_museum_04_issue_form import REQUIRED_FIELDS, validate_issue_form


ROOT = Path(__file__).resolve().parents[1]


class Museum04IssueFormTests(unittest.TestCase):
    def test_committed_issue_form_satisfies_contract(self) -> None:
        errors = validate_issue_form(ROOT / ".github/ISSUE_TEMPLATE/rights-or-attribution.yml")
        self.assertEqual(errors, [])

    def test_contract_covers_all_nine_public_fields(self) -> None:
        self.assertEqual(len(REQUIRED_FIELDS), 9)


if __name__ == "__main__":
    unittest.main()
