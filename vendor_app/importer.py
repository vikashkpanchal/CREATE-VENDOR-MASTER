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


def _read_table(path: str, sheet_name=0) -> pd.DataFrame:
    """One sheet of a workbook, or the whole of a csv/tsv, as strings.

    `sheet_name` is ignored for csv/tsv, which have only one table; for a
    workbook it names the sheet to read, so a single file carrying several
    masters can be taken apart one at a time.
    """
    lower = path.lower()
    if lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, dtype=str, sheet_name=sheet_name)
    elif lower.endswith(".tsv"):
        df = pd.read_csv(path, dtype=str, sep="\t")
    else:
        df = pd.read_csv(path, dtype=str)
    return df.fillna("")


def sheet_names(path: str) -> list:
    """The sheets in a workbook; a single unnamed one for a csv/tsv."""
    if not path.lower().endswith((".xlsx", ".xls")):
        return []
    import openpyxl

    book = openpyxl.load_workbook(path, read_only=True)
    try:
        return list(book.sheetnames)
    finally:
        book.close()


def load_records_from_file(path: str, sheet_name=0) -> list:
    """Return a list of raw record dicts (keyed like KEYS) parsed from `path`."""
    return vendor_rows_from_frame(_read_table(path, sheet_name))


def vendor_rows_from_frame(df) -> list:
    """Vendor rows out of an already-read table.

    Split from the file reader so one workbook of several masters can be
    taken apart sheet by sheet without re-opening it each time.
    """
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


# ------------------------------------------------- the other three masters --
_EQUIPMENT_LABEL_TO_KEY = None


def equipment_rows_from_frame(df) -> list:
    """Equipment rows out of an already-read table, headers matched by label."""
    global _EQUIPMENT_LABEL_TO_KEY
    if _EQUIPMENT_LABEL_TO_KEY is None:
        from vendor_app.config import EQUIPMENT_LABELS
        _EQUIPMENT_LABEL_TO_KEY = {
            _normalize_header(label): key for key, label in EQUIPMENT_LABELS.items()
        }
    from vendor_app.config import EQUIPMENT_KEYS

    columns = {}
    for col in df.columns:
        header = _normalize_header(col)
        if header in _EQUIPMENT_LABEL_TO_KEY:
            columns[_EQUIPMENT_LABEL_TO_KEY[header]] = col
        elif header.replace(" ", "_") in EQUIPMENT_KEYS:
            columns[header.replace(" ", "_")] = col
    return [
        {key: str(row.get(col, "")).strip() for key, col in columns.items()}
        for _, row in df.iterrows()
    ]


def load_equipment_from_file(path: str, sheet_name=0) -> list:
    """Parse an .xlsx/.csv/.tsv of equipment rows, matching headers by name."""
    return equipment_rows_from_frame(_read_table(path, sheet_name))


# The headers a raw ME3L / SAP FO download carries, beyond our own labels. SAP
# abbreviates column names differently between layouts, so an untouched export
# still has to land on the right fields without being renamed first.
ARC_HEADER_ALIASES = {
    # Table 1 - ARC data (ME3L)
    "purchasing doc.": "purchasing_document",
    "purch.doc.": "purchasing_document",
    "purchasing document no": "purchasing_document",
    "agreement no": "purchasing_document",
    "outline agreement": "purchasing_document",
    "contract no": "purchasing_document",
    "contract no.": "purchasing_document",
    "doc. date": "document_date",
    "doc.date": "document_date",
    "document date": "document_date",
    "vendor/supplying plant": "vendor_supplying_plant",
    "vendor / supplying plant": "vendor_supplying_plant",
    "supplying plant": "vendor_supplying_plant",
    "short text": "short_text",
    "material short text": "short_text",
    "validity per. start": "validity_start",
    "validity per.start": "validity_start",
    "validity start": "validity_start",
    "valid from": "validity_start",
    "validity period end": "validity_end",
    "validity end": "validity_end",
    "valid to": "validity_end",
    "target val. (header)": "target_value",
    "target val.": "target_value",
    "target value": "target_value",
    "target val": "target_value",
    "release indicator": "release_indicator",
    "release ind.": "release_indicator",
    "rel. indicator": "release_indicator",
    "release status": "release_status",
    "rel. status": "release_status",
    "po history/release documentation": "po_history",
    "po history": "po_history",
    "release documentation": "po_history",
    "purchasing group": "purchasing_group",
    "purchasing grp": "purchasing_group",
    "pur. group": "purchasing_group",
    "item": "item",
    "plant": "plant",
    # Table 2 - framework & contract tracking
    "serial no.": "serial_no",
    "serial no": "serial_no",
    "sr. no.": "serial_no",
    "contr.pur.group": "contract_pur_group",
    "contr. pur. group": "contract_pur_group",
    "contract purchasing group": "contract_pur_group",
    "header text": "header_text",
    "vendor": "vendor",
    "vendor code": "vendor",
    "vendor name": "vendor_name",
    "contract value": "contract_value",
    "requisitioner": "requisitioner",
    "frame numbers": "frame_numbers",
    "frame number": "frame_numbers",
    "frame order": "frame_numbers",
    "fo no": "frame_numbers",
    "fo.valdt.start": "fo_validity_start",
    "fo valdt start": "fo_validity_start",
    "fo validity start": "fo_validity_start",
    "fo.valdt.end": "fo_validity_end",
    "fo valdt end": "fo_validity_end",
    "fo validity end": "fo_validity_end",
    "frame pur.group": "frame_pur_group",
    "frame pur group": "frame_pur_group",
    "description": "description",
    "req.tracking no.": "req_tracking_no",
    "req tracking no": "req_tracking_no",
    "tracking no": "req_tracking_no",
    "released value": "released_value",
    "actual value": "actual_value",
    "opening value": "opening_value",
}


def arc_rows_from_frame(df, keys, labels) -> list:
    """ARC or FO rows out of an already-read table.

    Three header shapes are accepted, in order: the spec's own column names,
    the abbreviations a raw download uses, and our internal column names - so
    an export from this app, an untouched SAP file and the stored CSV all
    import. A column matching none of them is ignored rather than rejected:
    a real export always carries extras we do not need.
    """
    label_to_key = {_normalize_header(v): k for k, v in labels.items()}
    columns = {}
    for column in df.columns:
        header = _normalize_header(column)
        key = label_to_key.get(header)
        if key is None:
            alias = ARC_HEADER_ALIASES.get(header)
            # An alias only applies to the table being imported, so an FO's
            # "Description" can never land on a contract field, or the reverse.
            key = alias if alias in keys else None
        if key is None and header.replace(" ", "_").replace(".", "") in keys:
            key = header.replace(" ", "_").replace(".", "")
        if key is not None and key not in columns:
            columns[key] = column
    return [
        {key: str(row.get(column, "")).strip() for key, column in columns.items()}
        for _, row in df.iterrows()
    ]


def load_arc_rows_from_file(path, keys, labels, sheet_name=0) -> list:
    return arc_rows_from_frame(_read_table(path, sheet_name), keys, labels)
