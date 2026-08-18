"""Excel export with dynamically expanded 'Vendor Email ID N' columns.

The internal store keeps every vendor's emails as one semicolon-separated
string. At export time we compute the widest email list across the given
records and fan that single field out into "Vendor Email ID 1", "Vendor
Email ID 2", ... columns so the spreadsheet always matches the exact
required layout.
"""

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from vendor_app.validators import split_emails

HEADER_FILL = "1F6AA5"
HEADER_FONT_COLOR = "FFFFFF"
SHEET_NAME = "Vendor Master"


def build_export_dataframe(records: list) -> pd.DataFrame:
    max_emails = 1
    for record in records:
        max_emails = max(max_emails, len(split_emails(record.get("vendor_email", ""))))

    columns = ["Sr. No.", "Vendor Code", "Vendor Name"]
    columns += [f"Vendor Email ID {i + 1}" for i in range(max_emails)]
    columns += [
        "Vendor Owner Name",
        "Vendor Owner Contact Number",
        "Vendor Owner Email ID",
        "Vendor Supervisor Contact Name",
        "Vendor Supervisor Contact Number",
        "Vendor Supervisor Email ID",
    ]

    rows = []
    for i, record in enumerate(records, start=1):
        emails = split_emails(record.get("vendor_email", ""))
        row = {
            "Sr. No.": i,
            "Vendor Code": record.get("vendor_code", ""),
            "Vendor Name": record.get("vendor_name", ""),
        }
        for j in range(max_emails):
            row[f"Vendor Email ID {j + 1}"] = emails[j] if j < len(emails) else ""
        row["Vendor Owner Name"] = record.get("vendor_owner_name", "")
        row["Vendor Owner Contact Number"] = record.get("vendor_owner_contact", "")
        row["Vendor Owner Email ID"] = record.get("vendor_owner_email", "")
        row["Vendor Supervisor Contact Name"] = record.get("vendor_supervisor_name", "")
        row["Vendor Supervisor Contact Number"] = record.get("vendor_supervisor_contact", "")
        row["Vendor Supervisor Email ID"] = record.get("vendor_supervisor_email", "")
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
