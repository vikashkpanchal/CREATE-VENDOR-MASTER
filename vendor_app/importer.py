"""Mass-import support for the bulk entry grid (SAP/Oracle-style "upload
from file"): load vendor rows from an existing .xlsx/.xls/.csv/.tsv file
into the same raw-record shape the grid uses, ready to validate/upsert.

Tolerant of:
  - our own exported layout (Sr. No., Vendor Code, ..., dynamic
    "Vendor Email ID 1..N" columns, ...) - those are rejoined with ';'
  - a plain single "Vendor Email ID" column
  - header names in any case/spacing, matched against config.LABELS
  - a re-import of our own internal CSV store (snake_case headers)

Unrecognized columns are ignored rather than raising, since a file may
carry extra columns (Sr. No., Status, timestamps, ...) we don't need here.
"""

import re

import pandas as pd

from vendor_app.config import KEYS, LABELS, LEGACY_LABELS

# Current headers plus the pre-rename Owner/Supervisor headers, so a sheet
# exported by an older build still imports onto the right fields.
_LABEL_TO_KEY = {label.lower(): key for key, label in LABELS.items()}
_LABEL_TO_KEY.update({label.lower(): key for key, label in LEGACY_LABELS.items()})
_EMAIL_COLUMN_RE = re.compile(r"^vendor email id\s*\d*$", re.IGNORECASE)


def _normalize_header(text) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


def _read_table(path: str) -> pd.DataFrame:
    lower = path.lower()
    if lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, dtype=str)
    elif lower.endswith(".tsv"):
        df = pd.read_csv(path, dtype=str, sep="\t")
    else:
        df = pd.read_csv(path, dtype=str)
    return df.fillna("")


def load_records_from_file(path: str) -> list:
    """Return a list of raw record dicts (keyed like KEYS) parsed from `path`."""
    df = _read_table(path)

    email_columns = []
    field_columns = {}  # key -> source column name
    for col in df.columns:
        header = _normalize_header(col)
        if _EMAIL_COLUMN_RE.match(header):
            email_columns.append(col)
            continue
        if header in _LABEL_TO_KEY:
            field_columns[_LABEL_TO_KEY[header]] = col
            continue
        snake = header.replace(" ", "_")
        if snake in KEYS:
            field_columns[snake] = col

    records = []
    for _, row in df.iterrows():
        record = {key: str(row.get(col, "")).strip() for key, col in field_columns.items()}
        if email_columns:
            emails = [str(row.get(c, "")).strip() for c in email_columns]
            emails = [e for e in emails if e and e.lower() != "nan"]
            if emails:
                record["vendor_email"] = ";".join(emails)
        records.append(record)
    return records
