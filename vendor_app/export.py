"""Excel export of vendor records.

Every vendor's emails stay exactly as entered - one semicolon-separated
string in a single "Vendor Email ID" column. They are deliberately NOT
split across "Vendor Email ID 1/2/3..." columns, so an exported sheet can
be edited and re-imported without the address list changing shape.
"""

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from vendor_app.config import KEYS, LABELS

HEADER_FILL = "1F6AA5"
HEADER_FONT_COLOR = "FFFFFF"
SHEET_NAME = "Vendor Master"


def build_export_dataframe(records: list) -> pd.DataFrame:
    """One row per vendor, one column per field, in the mandated order.

    "Vendor Email ID" holds the vendor's full semicolon-separated address
    list verbatim - no fanning out into numbered columns.
    """
    columns = [
        "Sr. No.",
        LABELS["vendor_code"],
        LABELS["vendor_name"],
        LABELS["vendor_email"],
        LABELS["vendor_owner_name"],
        LABELS["vendor_owner_contact"],
        LABELS["vendor_owner_email"],
        LABELS["vendor_supervisor_name"],
        LABELS["vendor_supervisor_contact"],
        LABELS["vendor_supervisor_email"],
        "Status",
    ]

    rows = []
    for i, record in enumerate(records, start=1):
        row = {"Sr. No.": i}
        for key in KEYS:
            row[LABELS[key]] = record.get(key, "")
        row["Status"] = record.get("status", "Active")
        rows.append(row)

    return pd.DataFrame(rows, columns=columns)


def _style_worksheet(worksheet, columns):
    header_fill = PatternFill("solid", fgColor=HEADER_FILL)
    header_font = Font(bold=True, color=HEADER_FONT_COLOR)
    wrap_center = Alignment(wrap_text=True, vertical="center", horizontal="center")

    for col_idx, col_name in enumerate(columns, start=1):
        cell = worksheet.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = wrap_center

        data_lengths = [
            len(str(worksheet.cell(row=r, column=col_idx).value or ""))
            for r in range(2, worksheet.max_row + 1)
        ]
        max_len = max([len(col_name)] + data_lengths)
        worksheet.column_dimensions[cell.column_letter].width = min(max(max_len + 4, 14), 42)

    worksheet.freeze_panes = "A2"
    worksheet.row_dimensions[1].height = 32


def export_records_to_excel(records: list, path: str) -> str:
    """Write `records` to a formatted .xlsx workbook at `path`. Returns path."""
    df = build_export_dataframe(records)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=SHEET_NAME)
        _style_worksheet(writer.sheets[SHEET_NAME], list(df.columns))
    return path


def export_audit_log_to_excel(entries: list, path: str) -> str:
    """Write audit trail `entries` (most-recent-first dicts, see audit.py)
    to a formatted .xlsx workbook at `path`. Returns path."""
    from vendor_app.config import AUDIT_COLUMNS, AUDIT_WRAPPED_LABELS

    headers = [AUDIT_WRAPPED_LABELS.get(col, col).replace("\n", " ") for col in AUDIT_COLUMNS]
    rows = [{headers[i]: entry.get(col, "") for i, col in enumerate(AUDIT_COLUMNS)} for entry in entries]
    df = pd.DataFrame(rows, columns=headers)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Audit Log")
        _style_worksheet(writer.sheets["Audit Log"], headers)
    return path


def export_equipment_to_excel(records: list, path: str) -> str:
    """Write equipment master `records` to a formatted .xlsx at `path`."""
    from vendor_app.config import EQUIPMENT_KEYS, EQUIPMENT_LABELS

    columns = ["Sr. No."] + [EQUIPMENT_LABELS[k] for k in EQUIPMENT_KEYS]
    rows = []
    for i, record in enumerate(records, start=1):
        row = {"Sr. No.": i}
        for key in EQUIPMENT_KEYS:
            row[EQUIPMENT_LABELS[key]] = record.get(key, "")
        rows.append(row)

    df = pd.DataFrame(rows, columns=columns)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Equipment Master")
        _style_worksheet(writer.sheets["Equipment Master"], columns)
    return path
