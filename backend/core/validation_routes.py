"""
Validation Engine API routes.
Delegates field-level regex validation and type enforcement.
CPU-heavy batch validation is delegated to the Rust service when available.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validation", tags=["Validation"])

# ===== Built-in Pattern Library =====
PATTERNS = {
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


# ===== Models =====
class ValidationRule(BaseModel):
    field_name: str
    rule_type: str  # required, regex, min_length, max_length, min, max, date_format, enum, email, phone_e164, iban_checksum
    pattern: Optional[str] = None
    message: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ValidationRequest(BaseModel):
    data: Dict[str, Any]
    rules: List[ValidationRule]


class ValidationResult(BaseModel):
    field_name: str
    status: str  # pass, fail, warning
    value: str
    cleaned_value: Optional[str] = None
    error_msg: Optional[str] = None
    rule_violated: Optional[str] = None


class PatternTestRequest(BaseModel):
    pattern: str
    value: str


# ===== Validation Logic =====
def validate_field(value: Any, rule: ValidationRule) -> ValidationResult:
    """Validate a single field against a rule"""
    str_value = str(value) if value is not None else ""

    if rule.rule_type == "required":
        if not str_value.strip():
            return ValidationResult(
                field_name=rule.field_name, status="fail",
                value=str_value, error_msg=rule.message or "Field is required",
                rule_violated="required",
            )

    elif rule.rule_type == "regex":
        if rule.pattern and not re.match(rule.pattern, str_value):
            return ValidationResult(
                field_name=rule.field_name, status="fail",
                value=str_value,
                error_msg=rule.message or f"Does not match pattern: {rule.pattern}",
                rule_violated="regex",
            )

    elif rule.rule_type == "min_length":
        min_len = int(rule.parameters.get("min", 0)) if rule.parameters else 0
        if len(str_value) < min_len:
            return ValidationResult(
                field_name=rule.field_name, status="fail",
                value=str_value,
                error_msg=rule.message or f"Minimum length: {min_len}",
                rule_violated="min_length",
            )

    elif rule.rule_type == "max_length":
        max_len = int(rule.parameters.get("max", 9999)) if rule.parameters else 9999
        if len(str_value) > max_len:
            return ValidationResult(
                field_name=rule.field_name, status="fail",
                value=str_value,
                error_msg=rule.message or f"Maximum length: {max_len}",
                rule_violated="max_length",
            )

    elif rule.rule_type in ("min", "max"):
        try:
            num_val = float(str_value)
            bound = float(rule.parameters.get(rule.rule_type, 0)) if rule.parameters else 0
            if rule.rule_type == "min" and num_val < bound:
                return ValidationResult(
                    field_name=rule.field_name, status="fail",
                    value=str_value,
                    error_msg=rule.message or f"Minimum value: {bound}",
                    rule_violated=rule.rule_type,
                )
            if rule.rule_type == "max" and num_val > bound:
                return ValidationResult(
                    field_name=rule.field_name, status="fail",
                    value=str_value,
                    error_msg=rule.message or f"Maximum value: {bound}",
                    rule_violated=rule.rule_type,
                )
        except ValueError:
            return ValidationResult(
                field_name=rule.field_name, status="fail",
                value=str_value, error_msg="Not a valid number",
                rule_violated="type_check",
            )

    elif rule.rule_type == "enum":
        allowed = [v.strip().lower() for v in (rule.pattern or "").split(",")]
        if str_value.lower() not in allowed:
            return ValidationResult(
                field_name=rule.field_name, status="fail",
                value=str_value,
                error_msg=rule.message or f"Must be one of: {', '.join(allowed)}",
                rule_violated="enum",
            )

    elif rule.rule_type == "email":
        if not re.match(PATTERNS["email_rfc5322"], str_value):
            return ValidationResult(
                field_name=rule.field_name, status="fail",
                value=str_value, error_msg="Invalid email address",
                rule_violated="email",
            )

    elif rule.rule_type == "phone_e164":
        if not re.match(PATTERNS["phone_international"], str_value):
            return ValidationResult(
                field_name=rule.field_name, status="fail",
                value=str_value, error_msg="Does not match E.164 phone format",
                rule_violated="phone_e164",
            )

    elif rule.rule_type == "iban_checksum":
        if not re.match(PATTERNS["iban"], str_value):
            return ValidationResult(
                field_name=rule.field_name, status="fail",
                value=str_value, error_msg="Invalid IBAN format",
                rule_violated="iban_checksum",
            )

    return ValidationResult(
        field_name=rule.field_name, status="pass",
        value=str_value, cleaned_value=str_value.strip(),
    )


# ===== Endpoints =====
@router.post("/rules", status_code=201)
async def create_validation_ruleset(rules: List[ValidationRule]):
    """Create a validation ruleset"""
    return {"message": "Ruleset created", "rule_count": len(rules), "rules": rules}


@router.get("/rules")
async def list_rulesets():
    """List all validation rulesets"""
    return {"rulesets": []}


@router.post("/validate", response_model=List[ValidationResult])
async def validate_data(req: ValidationRequest):
    """Run batch field validation — delegates to Rust when available, falls back to Python."""
    # Try Rust service first for regex-based rules
    regex_rules = [r for r in req.rules if r.rule_type == "regex" and r.pattern]
    if regex_rules:
        try:
            from core.rust_bridge import validate_batch as rust_validate_batch
            rust_items = [
                {"field": r.field_name, "value": str(req.data.get(r.field_name, "")), "pattern": r.pattern}
                for r in regex_rules
            ]
            rust_results = await rust_validate_batch(rust_items)
            rust_map = {r["field"]: r for r in rust_results}
        except Exception as e:
            logger.warning("Rust validation unavailable, falling back to Python: %s", e)
            rust_map = {}
    else:
        rust_map = {}

    results = []
    for rule in req.rules:
        # Use Rust result if available for this field
        if rule.field_name in rust_map and rule.rule_type == "regex":
            rr = rust_map[rule.field_name]
            results.append(ValidationResult(
                field_name=rule.field_name,
                status="pass" if rr.get("valid") else "fail",
                value=str(req.data.get(rule.field_name, "")),
                cleaned_value=str(req.data.get(rule.field_name, "")).strip() if rr.get("valid") else None,
                error_msg=rr.get("error") or (rule.message if not rr.get("valid") else None),
                rule_violated=rule.rule_type if not rr.get("valid") else None,
            ))
        else:
            value = req.data.get(rule.field_name)
            result = validate_field(value, rule)
            results.append(result)
    return results


@router.get("/patterns")
async def list_patterns():
    """List all built-in validation patterns"""
    return {
        "patterns": [
            {"name": name, "pattern": pattern}
            for name, pattern in PATTERNS.items()
        ]
    }


@router.post("/test-pattern")
async def test_pattern_endpoint(req: PatternTestRequest):
    """Test a regex pattern against a sample value — delegates to Rust when available."""
    try:
        from core.rust_bridge import test_pattern as rust_test_pattern
        result = await rust_test_pattern(req.pattern, [req.value])
        if result.get("valid_pattern"):
            matches = result.get("results", [])
            match = matches[0].get("matches", False) if matches else False
            return {"match": match, "pattern": req.pattern, "value": req.value, "engine": "rust"}
    except Exception as e:
        logger.debug("Rust test-pattern unavailable, using Python: %s", e)

    try:
        match = bool(re.match(req.pattern, req.value))
        return {"match": match, "pattern": req.pattern, "value": req.value, "engine": "python"}
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex: {str(e)}")
