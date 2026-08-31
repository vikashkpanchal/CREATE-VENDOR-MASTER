"""Field-level and record-level validation rules for vendor data.

Rules implemented (per business spec):
  * Vendor Code is mandatory and must be numeric (digits only).
  * Owner/Supervisor contact numbers must be digits only, when provided.
  * Vendor Name and email fields have no length limits.
  * Multiple emails in "Vendor Email ID" must be separated by ';' (not ',').
  * Vendor Type is one of exactly two values, CAD or MARKET.
  * All fields other than Vendor Code are optional and never raise on blank.
"""

from vendor_app.config import KEYS, VENDOR_TYPE_VALUES


class ValidationError(Exception):
    """Raised when a single field fails validation.

    Carries the human-readable field label so callers (grid import, edit
    dialogs) can surface a precise, actionable message to the user.
    """

    def __init__(self, field_label: str, message: str):
        self.field_label = field_label
        self.message = message
        super().__init__(f"{field_label}: {message}")


def normalize(value) -> str:
    """Coerce any incoming cell value (None, float, str, ...) to a stripped str."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def split_emails(value) -> list:
    """Split a semicolon-separated email string into a clean list."""
    text = normalize(value)
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def validate_vendor_code(value) -> str:
    code = normalize(value)
    if not code:
        raise ValidationError("Vendor Code", "is required")
    if not code.isdigit():
        raise ValidationError("Vendor Code", "must be a number")
    return code


def validate_contact_number(value, field_label: str) -> str:
    number = normalize(value)
    if not number:
        return ""
    if not number.isdigit():
        raise ValidationError(field_label, "must contain digits only")
    return number


def validate_multi_email_field(value, field_label: str) -> str:
    """Validate the multi-email 'Vendor Email ID' field.

    Multiple addresses must be separated by ';'. A comma anywhere in the
    value (outside of being part of a single stray token) is treated as a
    misuse of the separator and rejected so bad data never enters storage.
    """
    text = normalize(value)
    if not text:
        return ""
    if "," in text:
        raise ValidationError(
            field_label,
            "multiple emails must be separated by semicolons (;), not commas",
        )
    return text


def validate_single_email_field(value, field_label: str) -> str:
    text = normalize(value)
    if not text:
        return ""
    if ";" in text or "," in text:
        raise ValidationError(field_label, "must contain a single email address")
    return text


def validate_choice(value, field_label: str, allowed) -> str:
    """One of `allowed`, in that spelling, or nothing at all.

    Case and surrounding space are forgiven, because a pasted column will
    not be consistent about them. A value outside the list is not: silently
    accepting it would create a category nobody agreed to, and every count
    by that field would then be wrong.
    """
    text = normalize(value)
    if not text:
        return ""
    upper = text.upper()
    if upper in allowed:
        return upper
    raise ValidationError(
        field_label, "must be " + " or ".join(allowed) + f" - got '{text}'"
    )


def validate_vendor_type(value, field_label: str) -> str:
    """CAD or MARKET, in that spelling, or nothing at all.

    Case and surrounding space are forgiven, because a pasted column will
    not be consistent about them and "cad" plainly means CAD. A third value
    is not forgiven: silently accepting it would create a category nobody
    agreed to, and every count by vendor type would then be wrong.
    """
    return validate_choice(value, field_label, VENDOR_TYPE_VALUES)


def validate_record(raw: dict) -> dict:
    """Validate and normalize a raw record dict (keyed by KEYS).

    Returns a cleaned dict with every key in KEYS present. Raises
    ValidationError on the first field that fails validation.
    """
    from vendor_app.config import LABELS

    cleaned = {k: "" for k in KEYS}

    cleaned["vendor_code"] = validate_vendor_code(raw.get("vendor_code", ""))
    cleaned["vendor_name"] = normalize(raw.get("vendor_name", ""))
    cleaned["vendor_email"] = validate_multi_email_field(
        raw.get("vendor_email", ""), LABELS["vendor_email"]
    )
    cleaned["vendor_owner_name"] = normalize(raw.get("vendor_owner_name", ""))
    cleaned["vendor_owner_contact"] = validate_contact_number(
        raw.get("vendor_owner_contact", ""), LABELS["vendor_owner_contact"]
    )
    cleaned["vendor_owner_email"] = validate_single_email_field(
        raw.get("vendor_owner_email", ""), LABELS["vendor_owner_email"]
    )
    cleaned["vendor_supervisor_name"] = normalize(raw.get("vendor_supervisor_name", ""))
    cleaned["vendor_supervisor_contact"] = validate_contact_number(
        raw.get("vendor_supervisor_contact", ""), LABELS["vendor_supervisor_contact"]
    )
    cleaned["vendor_supervisor_email"] = validate_single_email_field(
        raw.get("vendor_supervisor_email", ""), LABELS["vendor_supervisor_email"]
    )
    cleaned["vendor_type"] = validate_vendor_type(
        raw.get("vendor_type", ""), LABELS["vendor_type"]
    )
    cleaned["city"] = normalize(raw.get("city", ""))
    cleaned["state"] = normalize(raw.get("state", ""))
    return cleaned


def is_blank_record(raw: dict) -> bool:
    """True when every field in the raw record is empty (safe to skip)."""
    return not any(normalize(raw.get(k, "")) for k in KEYS)
