"""
Validation engine service — field-level validation orchestrator (Section 5.1).

Provides a `validate_document()` function that takes extracted fields + template rules
and returns per-field validation results, optionally persisting to the DB.
"""
from __future__ import annotations

import re
import logging
from typing import Any, Optional
from datetime import datetime

from core.db import is_async_db, get_sync_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in pattern library
# ---------------------------------------------------------------------------
BUILTIN_PATTERNS: dict[str, str] = {
    "za_id_number": r"^\d{13}$",
    "za_company_reg": r"^\d{4}/\d{6}/\d{2}$",
    "email_rfc5322": r"^[\w\.\+\-]+@[\w\-]+\.[\w\-\.]+$",
    "phone_international": r"^\+[1-9]\d{1,14}$",
    "iban": r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$",
    "swift_bic": r"^[A-Z]{6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3})?$",
    "url_https": r"^https://[^\s/$.?#].[^\s]*$",
    "ipv4": r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$",
    "date_iso": r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$",
    "postal_code_za": r"^\d{4}$",
}


# ---------------------------------------------------------------------------
# Field-level validation logic
# ---------------------------------------------------------------------------
def validate_field(
    value: Any,
    rule_type: str,
    pattern: str | None = None,
    parameters: dict | None = None,
) -> tuple[str, str | None, Any]:
    """
    Validate a single value against a rule.

    Returns: (status, error_msg, cleaned_value)
             status is 'pass', 'fail', or 'warning'
    """
    params = parameters or {}
    raw = str(value) if value is not None else ""

    if rule_type == "required":
        if not raw.strip():
            return "fail", "Value is required", None
        return "pass", None, raw

    if rule_type == "regex":
        p = pattern or ""
        # Allow named built-in patterns
        if p in BUILTIN_PATTERNS:
            p = BUILTIN_PATTERNS[p]
        try:
            if re.match(p, raw):
                return "pass", None, raw
            return "fail", f"Does not match pattern: {p}", raw
        except re.error as e:
            return "fail", f"Invalid regex: {e}", raw

    if rule_type == "min_length":
        mn = int(params.get("min_length", params.get("min", 0)))
        if len(raw) < mn:
            return "fail", f"Minimum length {mn}, got {len(raw)}", raw
        return "pass", None, raw

    if rule_type == "max_length":
        mx = int(params.get("max_length", params.get("max", 9999)))
        if len(raw) > mx:
            return "fail", f"Maximum length {mx}, got {len(raw)}", raw
        return "pass", None, raw

    if rule_type == "min":
        try:
            mn = float(params.get("min", 0))
            if float(raw) < mn:
                return "fail", f"Value below minimum {mn}", raw
        except ValueError:
            return "fail", "Not a number", raw
        return "pass", None, raw

    if rule_type == "max":
        try:
            mx = float(params.get("max", 0))
            if float(raw) > mx:
                return "fail", f"Value above maximum {mx}", raw
        except ValueError:
            return "fail", "Not a number", raw
        return "pass", None, raw

    if rule_type == "enum":
        allowed = params.get("values", [])
        if raw not in allowed:
            return "fail", f"Value not in {allowed}", raw
        return "pass", None, raw

    if rule_type == "email":
        if re.match(BUILTIN_PATTERNS["email_rfc5322"], raw):
            return "pass", None, raw.lower().strip()
        return "fail", "Invalid email address", raw

    if rule_type == "phone_e164":
        cleaned = re.sub(r"[\s\-\(\)]", "", raw)
        if re.match(BUILTIN_PATTERNS["phone_international"], cleaned):
            return "pass", None, cleaned
        return "fail", "Invalid E.164 phone number", raw

    if rule_type == "iban_checksum":
        iban = raw.replace(" ", "").upper()
        if not re.match(BUILTIN_PATTERNS["iban"], iban):
            return "fail", "Invalid IBAN format", raw
        # ISO 13616 mod-97 check
        rearranged = iban[4:] + iban[:4]
        numeric = ""
        for ch in rearranged:
            numeric += str(ord(ch) - 55) if ch.isalpha() else ch
        if int(numeric) % 97 == 1:
            return "pass", None, iban
        return "fail", "IBAN checksum failed", raw

    if rule_type == "date_format":
        fmt = params.get("format", "%Y-%m-%d")
        try:
            datetime.strptime(raw, fmt)
            return "pass", None, raw
        except ValueError:
            return "fail", f"Date does not match format {fmt}", raw

    return "warning", f"Unknown rule type: {rule_type}", raw


# ---------------------------------------------------------------------------
# Document-level validation
# ---------------------------------------------------------------------------
def validate_document(
    data: dict[str, Any],
    rules: list[dict],
    *,
    document_id: str | None = None,
    persist: bool = True,
) -> list[dict]:
    """
    Validate all fields in *data* against the provided *rules*.

    Each rule dict should have: field_name, rule_type, pattern?, parameters?, message?

    Returns a list of result dicts: [{field_name, status, value, cleaned_value, error_msg, rule_violated}]
    Optionally persists results to the validation_results table.
    """
    results: list[dict] = []

    for rule in rules:
        field = rule["field_name"]
        value = data.get(field)
        status, err, cleaned = validate_field(
            value,
            rule["rule_type"],
            pattern=rule.get("pattern"),
            parameters=rule.get("parameters"),
        )
        if err and rule.get("message"):
            err = rule["message"]  # custom message override

        results.append({
            "field_name": field,
            "status": status,
            "value": str(value) if value is not None else "",
            "cleaned_value": str(cleaned) if cleaned is not None else None,
            "error_msg": err,
            "rule_violated": rule["rule_type"] if status == "fail" else None,
        })

    # Persist to DB if requested and available
    if persist and document_id and is_async_db():
        try:
            _persist_results(document_id, results)
        except Exception as exc:
            logger.warning("Failed to persist validation results: %s", exc)

    return results


def _persist_results(document_id: str, results: list[dict]) -> None:
    import uuid
    from core.models import ValidationResult as VRModel
    with get_sync_session() as session:
        for r in results:
            session.add(VRModel(
                id=str(uuid.uuid4()),
                document_id=document_id,
                field_name=r["field_name"],
                status=r["status"],
                value=r["value"],
                cleaned_value=r.get("cleaned_value"),
                error_msg=r.get("error_msg"),
                rule_violated=r.get("rule_violated"),
            ))
        session.commit()
