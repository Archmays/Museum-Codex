"""Validate the public MUSEUM-04 rights request Issue Form contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


REQUIRED_FIELDS = {
    "request_type": "dropdown",
    "affected_url": "input",
    "affected_record": "input",
    "public_description": "textarea",
    "desired_correction": "textarea",
    "rights_holder_relationship": "dropdown",
    "urgency": "textarea",
    "contact_preference": "dropdown",
    "sensitive_information": "checkboxes",
}
FORBIDDEN_FIELD_TYPES = {"file", "upload"}
FORBIDDEN_FIELD_TOKENS = ("upload", "attachment", "identity_document", "contract", "address", "phone", "email")
REQUIRED_SAFETY_TERMS = (
    "identity documents",
    "contracts",
    "authorization originals",
    "sensitive proof",
    "non-public channel",
)


def validate_issue_form(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [f"cannot parse {path}: {exc}"]
    if not isinstance(document, dict):
        return ["Issue Form root must be a mapping"]
    body = document.get("body")
    if not isinstance(body, list):
        return ["Issue Form body must be a list"]

    fields: dict[str, dict] = {}
    for index, item in enumerate(body):
        if not isinstance(item, dict):
            errors.append(f"body[{index}] must be a mapping")
            continue
        field_type = item.get("type")
        if field_type in FORBIDDEN_FIELD_TYPES:
            errors.append(f"body[{index}] uses forbidden field type {field_type!r}")
        field_id = item.get("id")
        if isinstance(field_id, str):
            if field_id in fields:
                errors.append(f"duplicate field id: {field_id}")
            fields[field_id] = item
            normalized_id = field_id.lower()
            if any(token in normalized_id for token in FORBIDDEN_FIELD_TOKENS):
                errors.append(f"forbidden sensitive-information field: {field_id}")

    for field_id, expected_type in REQUIRED_FIELDS.items():
        field = fields.get(field_id)
        if field is None:
            errors.append(f"missing field: {field_id}")
        elif field.get("type") != expected_type:
            errors.append(f"field {field_id} must use type {expected_type}")

    optional_relationship = fields.get("rights_holder_relationship", {}).get("validations", {})
    if isinstance(optional_relationship, dict) and optional_relationship.get("required") is True:
        errors.append("rights_holder_relationship must remain optional")

    affected_record = fields.get("affected_record", {}).get("attributes", {})
    if isinstance(affected_record, dict):
        label = str(affected_record.get("label", "")).lower()
        for term in ("artist", "artwork", "relationship", "release"):
            if term not in label:
                errors.append(f"affected_record label must include {term}")

    contact = fields.get("contact_preference", {})
    contact_text = str(contact).lower()
    if "no public email address is required" not in contact_text:
        errors.append("contact_preference must not require a public email address")

    safety = fields.get("sensitive_information", {})
    safety_text = str(safety).lower()
    for term in REQUIRED_SAFETY_TERMS:
        if term not in safety_text:
            errors.append(f"safety checkbox copy missing: {term}")
    options = safety.get("attributes", {}).get("options", []) if isinstance(safety, dict) else []
    if not isinstance(options, list) or len(options) < 2 or any(
        not isinstance(option, dict) or option.get("required") is not True for option in options
    ):
        errors.append("both safety acknowledgements must be required checkboxes")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path(".github/ISSUE_TEMPLATE/rights-or-attribution.yml"),
    )
    args = parser.parse_args()
    errors = validate_issue_form(args.path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS: {args.path} satisfies the MUSEUM-04 public rights request contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
