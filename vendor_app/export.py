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


def export_audit_log_to_excel(entries: list, path: str, columns=None, headers=None) -> str:
    """Write change-log `entries` (most-recent-first dicts, see audit.py) to a
    formatted .xlsx workbook at `path`. `columns`/`headers` let the equipment
    log export with its own column set. Returns path."""
    from vendor_app.config import AUDIT_COLUMNS, AUDIT_WRAPPED_LABELS

    columns = list(columns or AUDIT_COLUMNS)
    header_map = headers or AUDIT_WRAPPED_LABELS
    headers = [header_map.get(col, col).replace("\n", " ") for col in columns]
    rows = [{headers[i]: entry.get(col, "") for i, col in enumerate(columns)} for entry in entries]
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


def _export_simple(records: list, path: str, columns_keys, labels, sheet_name) -> str:
    """Shared writer for the ARC/FO/line-item sheets: Sr. No. then one column
    per key, in the order the grid shows them."""
    columns = ["Sr. No."] + [labels[k] for k in columns_keys]
    rows = []
    for i, record in enumerate(records, start=1):
        row = {"Sr. No.": i}
        for key in columns_keys:
            row[labels[key]] = record.get(key, "")
        rows.append(row)

    df = pd.DataFrame(rows, columns=columns)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        _style_worksheet(writer.sheets[sheet_name], columns)
    return path


def export_arcs_to_excel(records: list, path: str) -> str:
    """ARC master, including the derived FO count and aggregated ARC value."""
    from vendor_app.config import ARC_DERIVED_LABELS, ARC_DISPLAY_COLUMNS, ARC_LABELS

    labels = dict(ARC_LABELS)
    labels.update(ARC_DERIVED_LABELS)
    return _export_simple(records, path, ARC_DISPLAY_COLUMNS, labels, "ARC Master")


def export_fos_to_excel(records: list, path: str) -> str:
    from vendor_app.config import FO_DERIVED_LABELS, FO_DISPLAY_COLUMNS, FO_LABELS

    labels = dict(FO_LABELS)
    labels.update(FO_DERIVED_LABELS)
    return _export_simple(records, path, FO_DISPLAY_COLUMNS, labels, "FO Master")


def export_arc_lines_to_excel(records: list, path: str) -> str:
    from vendor_app.config import ARC_LINE_KEYS, ARC_LINE_LABELS

    return _export_simple(records, path, ARC_LINE_KEYS, ARC_LINE_LABELS, "ARC Line Items")


def export_report_to_excel(report, path: str) -> str:
    """Write one ARC/FO analysis report (see arc_analytics.Report) to .xlsx."""
    headers = [report.headers(wrapped=False)[key] for key in report.columns]
    rows = [dict(zip(headers, report.values(row))) for row in report.rows]
    df = pd.DataFrame(rows, columns=headers)

    sheet = report.title[:31]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet)
        _style_worksheet(writer.sheets[sheet], headers)
    return path


def export_arc_analysis_to_excel(analysis, path: str) -> str:
    """The whole ARC & FO dashboard as one workbook.

    Sheet 1 is the 19 headline analyses; every table on the dashboard then
    follows on its own sheet, in the order the dashboard shows them, so the
    workbook reads the same way the screen does.
    """
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary = pd.DataFrame(analysis.summary_rows(), columns=["Analysis", "Value"])
        summary.to_excel(writer, index=False, sheet_name="Summary")
        _style_worksheet(writer.sheets["Summary"], ["Analysis", "Value"])

        used = {"Summary"}
        for report in analysis.full_reports():
            headers = [report.headers(wrapped=False)[key] for key in report.columns]
            rows = [dict(zip(headers, report.values(row))) for row in report.rows]
            # An empty report still gets its sheet: "nothing is expiring" is
            # an answer, and a missing tab reads as a missing analysis.
            frame = pd.DataFrame(rows, columns=headers)

            sheet = report.title[:31]
            suffix = 2
            while sheet in used:
                sheet = f"{report.title[:28]} {suffix}"
                suffix += 1
            used.add(sheet)

            frame.to_excel(writer, index=False, sheet_name=sheet)
            _style_worksheet(writer.sheets[sheet], headers)
    return path
