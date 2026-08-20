"""HTML bodies for the outgoing vendor emails.

Kept free of any Outlook/win32com dependency so the exact wording and
table markup can be built and checked on any platform; outlook.py is the
only piece that actually talks to Outlook.

Tables are rendered with a thick outer border, bold header row, and no
fixed width so Outlook sizes columns to their content ("autofit").
"""

from html import escape

from vendor_app.config import (
    BREAKDOWN_EMAIL_COLUMNS,
    BREAKDOWN_EMAIL_HEADERS,
    DEFECTIVE_INVOICE_EMAIL_COLUMNS,
    DEFECTIVE_INVOICE_LABELS,
)

FONT_STACK = "Calibri, Arial, sans-serif"
BODY_STYLE = f"font-family:{FONT_STACK}; font-size:11pt; color:#000000;"

BILLING_ADDRESS_LINES = [
    "Reliance Industries Limited,",
    "At Navagam Via Khodiyar Colony,",
    "1, P.O.-Navagam/ Kana Chhikari,",
    "Navagam,",
    "Jamnagar, Gujarat - 361006",
]


def vendor_display(vendor_name: str, vendor_code: str) -> str:
    """'Acme Supplies (1001)' - the form used in both subject and salutation."""
    name = (vendor_name or "").strip() or "(name not on file)"
    return f"{name} ({(vendor_code or '').strip()})"


def _para(text: str) -> str:
    return f'<p style="{BODY_STYLE} margin:0 0 10pt 0;">{text}</p>'


def build_table(headers: list, rows: list) -> str:
    """A thick-bordered, bold-header, autofit-width HTML table.

    No table-level width is set and cells use white-space:nowrap, so Outlook
    (and Word, which renders Outlook's HTML) sizes each column to its content
    rather than stretching the table to the full page width.
    """
    head_cells = "".join(
        '<th style="border:1.5pt solid #000000; padding:5pt 9pt; '
        'background-color:#D9D9D9; font-weight:bold; text-align:center; '
        f'white-space:nowrap; font-family:{FONT_STACK}; font-size:10pt;">{escape(str(h))}</th>'
        for h in headers
    )

    body_rows = []
    for row in rows:
        cells = "".join(
            '<td style="border:1pt solid #000000; padding:4pt 9pt; '
            f'font-family:{FONT_STACK}; font-size:10pt; vertical-align:top;">{escape(str(v or ""))}</td>'
            for v in row
        )
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        '<table cellspacing="0" cellpadding="0" '
        'style="border-collapse:collapse; border:2.25pt solid #000000; margin:0 0 12pt 0;">'
        f"<thead><tr>{head_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


# ----------------------------------------------------- defective invoice --
def defective_invoice_subject(vendor_name: str, vendor_code: str) -> str:
    return f"Defective Invoice || {vendor_display(vendor_name, vendor_code)}"


def defective_invoice_body(vendor_name: str, vendor_code: str, invoices: list) -> str:
    """`invoices` is this vendor's list of pasted invoice dicts - all of them
    go into the single table, so each vendor receives exactly one email."""
    headers = ["Sr No"] + [
        DEFECTIVE_INVOICE_LABELS[k] for k in DEFECTIVE_INVOICE_EMAIL_COLUMNS
    ]
    rows = [
        [i] + [inv.get(k, "") for k in DEFECTIVE_INVOICE_EMAIL_COLUMNS]
        for i, inv in enumerate(invoices, start=1)
    ]

    address = "<br>".join(escape(line) for line in BILLING_ADDRESS_LINES)

    return (
        f'<div style="{BODY_STYLE}">'
        + _para(f"To, M/s. {escape(vendor_display(vendor_name, vendor_code))}")
        + _para(
            "The invoice(s) listed below have been marked as defective during "
            "Accounts Payable verification and require correction before further processing."
        )
        + _para(
            "Kindly review the remarks mentioned against each invoice and submit the "
            "revised digitally signed invoice(s) at the earliest for payment processing."
        )
        + build_table(headers, rows)
        + _para(
            "<b>Note:</b> For Battery/NEI Project invoices, kindly ensure the following "
            "billing address is correctly mentioned in the revised invoice:"
        )
        + f'<p style="{BODY_STYLE} margin:0 0 10pt 0;">{address}</p>'
        + _para(
            "Please ensure that all observations are addressed before re-submission. "
            "The revised invoice must be uploaded on the Vendor Portal for processing."
        )
        + _para(
            "Additionally, kindly share a copy of the revised invoice through return email "
            "after successful upload on the portal for our record and necessary follow-up."
        )
        + _para(
            "We request you to submit the corrected invoice(s) on priority to avoid delays "
            "in invoice processing and payment."
        )
        + "</div>"
    )


# -------------------------------------------------- equipment breakdown --
def breakdown_subject(vendor_name: str, vendor_code: str) -> str:
    return (
        "Hired vehicle breakdown at Reliance, Jamnagar || "
        f"{vendor_display(vendor_name, vendor_code)}"
    )


def breakdown_body(vendor_name: str, vendor_code: str, equipment: list) -> str:
    """`equipment` is every broken-down machine for this vendor - one table,
    one email per vendor."""
    headers = [BREAKDOWN_EMAIL_HEADERS[k] for k in BREAKDOWN_EMAIL_COLUMNS]
    rows = [[eq.get(k, "") for k in BREAKDOWN_EMAIL_COLUMNS] for eq in equipment]

    return (
        f'<div style="{BODY_STYLE}">'
        + _para("To,<br>M/s. " + escape(vendor_display(vendor_name, vendor_code)))
        + _para(
            "<b>Subject: Hired vehicle breakdown Battery Project at Reliance, Jamnagar</b>"
        )
        + _para(
            "We regret to inform that vehicle hired by Reliance from your company is under "
            "breakdown as per latest site report. This is not acceptable."
        )
        + _para(
            "As you know, any machinery breakdown is directly impacting the project progress "
            "and set targets. Looking to the long association of yours with Company, we are "
            "expecting your kind support and cooperation in streamlining deployed machines at "
            "Reliance Site."
        )
        + _para(
            "You are hereby advised to take all necessary actions to restore the aforementioned "
            "machine within seven (7) days from the date of receipt of this communication. "
            "Failure to do so shall compel the Company to initiate appropriate contractual "
            "actions, including but not limited to the imposition of penalties, recovery of dues, "
            "and, as a last resort, de-hiring of the said machine."
        )
        + _para(
            "Hired P&amp;M detail is mentioned below, kindly revert with action taken and firm "
            "restoring date via return email."
        )
        + build_table(headers, rows)
        + "</div>"
    )
