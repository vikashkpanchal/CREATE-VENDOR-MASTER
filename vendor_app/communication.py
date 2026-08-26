"""Turn pasted rows into one outgoing email per vendor.

Both communication flows share the same shape: the user pastes rows, the
rows are grouped by vendor (so a vendor with five defective invoices or
three broken machines still receives exactly ONE email), and each group's
recipient address is resolved from the vendor master.

Rows whose vendor has no email on file are reported back as "unresolved"
so the UI can offer to add the address or skip that vendor.
"""

from vendor_app.config import DEFECTIVE_INVOICE_KEYS
from vendor_app.email_templates import (
    breakdown_body,
    breakdown_subject,
    defective_invoice_body,
    defective_invoice_subject,
)
from vendor_app.validators import normalize, split_emails


def parse_pasted_rows(text: str, keys: list) -> list:
    """Parse clipboard/textarea content (tab- or comma-separated) into dicts.

    Excel copies as tab-separated, which is the common case; a header row is
    detected and skipped so pasting straight from a sheet with headings works.
    """
    rows = []
    lines = [ln for ln in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]

    for line in lines:
        if not line.strip():
            continue
        cells = line.split("\t") if "\t" in line else line.split(",")
        cells = [c.strip() for c in cells]
        if not any(cells):
            continue
        record = {key: (cells[i] if i < len(cells) else "") for i, key in enumerate(keys)}
        rows.append(record)

    # Drop a header row if the first parsed row looks like column captions
    # rather than data (i.e. its vendor code is not numeric).
    if rows:
        first = rows[0]
        code = normalize(first.get("vendor_code", ""))
        first_values = " ".join(str(v).lower() for v in first.values())
        looks_like_header = (code and not code.isdigit()) or "vendor code" in first_values
        if looks_like_header:
            rows = rows[1:]

    return rows


def vendor_recipient(record: dict) -> str:
    """The address(es) to send to, in Outlook's ';'-separated form.

    Prefers the vendor's main email list, falling back to the contact person
    addresses so a vendor with only a contact email still gets reached.
    """
    if record is None:
        return ""
    for key in ("vendor_email", "vendor_owner_email", "vendor_supervisor_email"):
        addresses = split_emails(record.get(key, ""))
        if addresses:
            return "; ".join(addresses)
    return ""


def group_by_vendor(rows: list) -> dict:
    """Group parsed rows by vendor code, preserving first-seen order."""
    grouped = {}
    for row in rows:
        code = normalize(row.get("vendor_code", ""))
        if not code:
            continue
        grouped.setdefault(code, []).append(row)
    return grouped


def _vendor_name(store, code: str, rows: list) -> str:
    """Prefer the master's name; fall back to whatever was pasted."""
    record = store.get(code) if store else None
    if record and record.get("vendor_name"):
        return record["vendor_name"]
    for row in rows:
        if normalize(row.get("vendor_name", "")):
            return normalize(row["vendor_name"])
    return ""


def build_defective_invoice_messages(store, rows: list, skip_codes=None) -> dict:
    """One defective-invoice email per vendor.

    Returns {"messages": [...], "unresolved": [...], "skipped": [...]}, where
    unresolved entries name vendors with no email address on file.
    """
    skip_codes = {normalize(c) for c in (skip_codes or [])}
    grouped = group_by_vendor(rows)

    messages, unresolved, skipped = [], [], []
    for code, vendor_rows in grouped.items():
        name = _vendor_name(store, code, vendor_rows)
        if code in skip_codes:
            skipped.append({"vendor_code": code, "vendor_name": name, "rows": vendor_rows})
            continue

        record = store.get(code) if store else None
        to_addresses = vendor_recipient(record)
        if not to_addresses:
            unresolved.append(
                {
                    "vendor_code": code,
                    "vendor_name": name,
                    "rows": vendor_rows,
                    "in_master": record is not None,
                }
            )
            continue

        messages.append(
            {
                "vendor_code": code,
                "vendor_name": name,
                "to": to_addresses,
                "subject": defective_invoice_subject(name, code),
                "body_html": defective_invoice_body(name, code, vendor_rows),
                "row_count": len(vendor_rows),
                "label": f"{name} ({code})",
            }
        )

    return {"messages": messages, "unresolved": unresolved, "skipped": skipped}


def resolve_breakdown_rows(equipment_store, identifiers: list, remarks=None) -> dict:
    """Look up pasted RH/RO Numbers, Technical IDs or Reg Nos in the equipment
    master, attaching each row's Remarks.

    `identifiers` may be plain strings, or (identifier, remarks) pairs; a
    parallel `remarks` list is also accepted. Every other field on the email
    comes from the equipment master, since these identifiers are unique.

    Returns {"records": [...], "missing": [...]}. The returned records are
    COPIES - the caller's remarks must never be written into the stored
    equipment master.
    """
    pairs = []
    for index, item in enumerate(identifiers):
        if isinstance(item, (tuple, list)):
            identifier = normalize(item[0])
            note = normalize(item[1]) if len(item) > 1 else ""
        else:
            identifier = normalize(item)
            note = normalize(remarks[index]) if remarks and index < len(remarks) else ""
        if identifier:
            pairs.append((identifier, note))

    records, missing = [], []
    seen_identifiers = set()
    seen_machines = {}             # id(record) -> position in `records`

    for identifier, note in pairs:
        key = identifier.lower()
        if key in seen_identifiers:
            continue
        seen_identifiers.add(key)

        found = equipment_store.lookup(identifier)
        if found is None:
            missing.append(identifier)
            continue

        # The same machine can be referenced by its RH/RO Number, Technical ID
        # AND Reg No - list it once, and keep the first remark given for it
        # (appending any later, different remark rather than losing it).
        machine = id(found)
        if machine in seen_machines:
            existing = records[seen_machines[machine]]
            if note and note not in existing["remarks"]:
                existing["remarks"] = (
                    f"{existing['remarks']}; {note}" if existing["remarks"] else note
                )
            continue

        row = dict(found)          # copy: never mutate the stored record
        row["remarks"] = note
        seen_machines[machine] = len(records)
        records.append(row)

    return {"records": records, "missing": missing}


def build_breakdown_messages(store, equipment_records: list, skip_codes=None) -> dict:
    """One equipment-breakdown email per vendor, listing all their machines."""
    skip_codes = {normalize(c) for c in (skip_codes or [])}

    grouped = {}
    for record in equipment_records:
        code = normalize(record.get("vendor_code", ""))
        if not code:
            continue
        grouped.setdefault(code, []).append(record)

    messages, unresolved, skipped = [], [], []
    for code, equipment in grouped.items():
        name = _vendor_name(store, code, equipment)
        if code in skip_codes:
            skipped.append({"vendor_code": code, "vendor_name": name, "rows": equipment})
            continue

        record = store.get(code) if store else None
        to_addresses = vendor_recipient(record)
        if not to_addresses:
            unresolved.append(
                {
                    "vendor_code": code,
                    "vendor_name": name,
                    "rows": equipment,
                    "in_master": record is not None,
                }
            )
            continue

        messages.append(
            {
                "vendor_code": code,
                "vendor_name": name,
                "to": to_addresses,
                "subject": breakdown_subject(name, code),
                "body_html": breakdown_body(name, code, equipment),
                "row_count": len(equipment),
                "label": f"{name} ({code})",
            }
        )

    return {"messages": messages, "unresolved": unresolved, "skipped": skipped}


def parse_identifiers(text: str) -> list:
    """Split pasted identifiers on newlines/tabs/commas, preserving order."""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    for sep in ("\t", ","):
        raw = raw.replace(sep, "\n")
    seen, out = set(), []
    for token in raw.split("\n"):
        value = token.strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out
