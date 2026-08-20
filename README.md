# Vendor Master Management System

A pure-Python desktop application for creating, importing, searching and
maintaining a vendor master dataset, with SAP/Oracle-style vendor
lifecycle management, a full audit trail, an equipment (rental/hire)
master, Outlook email drafting, and clean Excel export.

- **UI:** `customtkinter` (dark theme) with a consistent design system —
  branded header, cobalt accent, card layout, stat tiles, wrapped
  two-line table headers, zebra/status-tinted rows, row hover, sortable
  columns, non-blocking toast notifications (`vendor_app/gui/theme.py`)
- **Data processing / export:** `pandas` + `openpyxl`
- **Storage:** local CSV under `data/` (internal only — the app is what you
  export to `.xlsx` from, not the other way around)

## Setup

```bash
pip install -r requirements.txt
python main.py
```

Requires Python 3.9+ and a desktop environment (Tk). On Linux you may also
need the OS-level Tk package, e.g. `sudo apt install python3-tk`.

## Data fields

Every vendor record uses this exact field order:

| # | Field | Notes |
|---|-------|-------|
| 1 | Sr. No. | Auto-generated (1, 2, 3, ...) — not stored, computed for display/export |
| 2 | Vendor Code | **Required, unique, numeric** — primary key |
| 3 | Vendor Name | No length limit |
| 4 | Vendor Email ID | No length limit; multiple addresses separated by `;` (not `,`) — exported as-is in one column |
| 5 | Contact Person1 Name | Optional |
| 6 | Contact Person1 Contact Number | Optional; digits only if provided |
| 7 | Contact Person1 Email ID | Optional; single address |
| 8 | Contact Person2 Name | Optional |
| 9 | Contact Person2 Contact Number | Optional; digits only if provided |
| 10 | Contact Person2 Email ID | Optional; single address |

Sheets exported by older builds (which used "Vendor Owner ..." /
"Vendor Supervisor ..." headers, and split emails across "Vendor Email ID
1/2/3" columns) still import correctly.

These 9 core fields (plus generated Sr. No.) are the exact, contractual
layout for the bulk-entry grid and the `.xlsx` export — untouched by the
operational metadata below.

### Operational metadata (SAP/Oracle-style)

Kept alongside the 9 core fields but never inside them, so the mandated
grid/export layout never changes:

- **Status** — `Active` / `Inactive` / `Blocked` (like SAP's vendor-block
  concept). Defaults to Active. Changed via the Edit dialog's Status
  dropdown, or a one-click Deactivate/Reactivate button in Master Data
  Records and the Search profile card. Shown as a colored pill and tints
  its table row (Blocked = red, Inactive = muted).
- **Created / Last Updated timestamps** — set automatically on every write.

## Validation rules

- Vendor Code is mandatory and must be a number.
- Contact Person1/Person2 numbers must contain digits only, when provided.
- Multiple emails in "Vendor Email ID" must be separated by `;`. A `,` is rejected.
- Every other field is optional — a blank cell never raises an error.
- **Cell-level partial merge (upsert):** saving a record whose Vendor Code
  already exists only overwrites the non-blank fields you provided; blank
  cells leave the previously stored value untouched. This applies to grid
  saves and to the edit dialog alike.

## Tabs

Tab order matches day-to-day use: look someone up first, browse the
directory second, reach for bulk import when onboarding or refreshing many
vendors at once, then the equipment master and the outgoing-email flows,
and finally the audit trail when you need to know who changed what.

### 1. Search Vendor Details
- **Single Vendor Search** — enter one Vendor Code to view a full profile
  card (grouped into Vendor / Contact Person 1 / Contact Person 2 sections, with a status
  pill), with buttons to edit it or toggle Active/Inactive on the spot.
- **Multi Vendor Search** — paste/enter a list of Vendor Codes (one per
  line) to see all matches side-by-side in a sortable table, with an
  "Export Search Results (.xlsx)" button.

### 2. Master Data Records
The full vendor directory, led by a stat strip (Total / Active / Inactive /
Blocked) — **click any tile to filter the table to those vendors**, e.g.
click "Blocked" to list every blocked vendor — plus a live search bar and a
Status filter. Status is shown as the last column. Columns are sortable
(click a header to sort, click again to reverse). "+ Add Vendor" creates a
new record; "Edit Selected" or a double-click edits one; "Deactivate
Selected" toggles Active/Inactive; "Delete Permanently" removes a record
outright (confirmed, and logged to the audit trail — prefer Deactivate for
anything reversible). "Export All (.xlsx)" writes every record to a
formatted spreadsheet.

### 3. Import & Update Grid
An Excel-like grid (100 rows max, for smooth, lag-free bulk entry) with
wrapped, zebra-striped rows, scrolling in both directions. Paste directly
from Excel with `Ctrl+V`; navigate cells with the arrow keys, `Tab`, and
`Enter`. "Import from File..." loads vendor rows straight from an existing
`.xlsx`/`.xls`/`.csv`/`.tsv` file into the grid (tolerant of header casing,
of legacy "Vendor Owner/Supervisor" headers and of older split
"Vendor Email ID N" columns) for review
before saving. "Save Grid to Master" validates every non-blank row and
upserts it into the master dataset, reporting how many were added/updated
and listing any row-level errors.

### 4. Equipment Master
Equipment supplied by vendors on a rental/hire basis (not every vendor
hires equipment out, so this is its own dataset). Columns: Sr No,
Equipment Description, UOM, Capacity, RO/RH, Vendor Code, Vendor Name,
RH/RO Number, Technical ID, Reg No, RH Date, Plant.

- **Equipment Records** — the full list with live filter, sortable
  columns, "+ Paste Rows", "Import from File...", export and delete.
- **Single Search** — paste any ONE of RH/RO Number, Technical ID or
  Reg No to pull up that machine's full profile.
- **Multi Search** — paste a list of identifiers (any mix of the three)
  to retrieve all matching records, capped at 50 results, with export.

Technical ID must be numeric; RH/RO Number is alphanumeric. Rows are
matched and merged on any shared identifier.

### 5. Communication
Drafts vendor emails from pasted data. **One email per vendor** — a vendor
with five defective invoices or three broken machines receives a single
email listing all of them. Nothing is sent: every message is saved as an
Outlook **draft** in its own sub-folder for review.

- **Defective Invoice Communication** — paste Vendor Code, Vendor Name, PO
  Number, Scroll No, Invoice No, Invoice Date, Invoice Amount, Remarks (a
  header row is detected and skipped). Drafts land in the Outlook folder
  **"Defective Invoice"**.
- **Equipment Breakdown Communication** — paste RH/RO Numbers or Technical
  IDs; every other detail is fetched from the Equipment Master, since those
  identifiers are unique. Drafts land in **"Equipment Breakdown"**.

Recipient addresses come from the vendor master. If a vendor has no email
on file, a dialog lists those vendors so you can either enter an address
(saved straight back to the vendor master, and logged in the audit trail)
or tick **Skip** to leave that vendor out of the run.

The **CC address** applied to every outgoing email is asked for exactly
once and then reused; change it any time via "Change CC" in the tab header.

"Preview Selected" opens the exact email (subject, To, Cc and the full
formatted body) in your browser before any draft is created. Email tables
use a thick outer border, bold header row and content-fitted column widths,
and the user's default Outlook signature is preserved beneath the body.

**Outlook requirements:** Windows with Microsoft Outlook (tested against
Office 16 / Outlook 2016) and the `pywin32` package. On any other platform
the rest of the app works normally and the Communication tab says drafts
are unavailable — "Preview Selected" still works everywhere.

### 6. Audit Log
A complete, append-only change history (`data/vendor_audit_log.csv`) —
every add, field-level update, status change and delete, with a
timestamp, a human-readable before/after summary, and who made the change.
Filterable by vendor name/code and by action type, with its own
"Export Audit Log (.xlsx)" button.

## Tables

Master Data Records, Multi Vendor Search results, and the Audit Log all
use the same themed table component (`vendor_app/gui/style.py`): headers
are always pre-wrapped onto two clean lines and never truncated or
hidden, both a vertical and a horizontal scrollbar are always available so
wide tables scroll into view instead of squeezing columns unreadably thin,
rows are zebra-striped and highlight on hover, and any column header can
be clicked to sort (ascending, then descending).

## Excel export layout

The master/search `.xlsx` exports follow the 10-field layout above plus a
Status column. **Email addresses are exported exactly as entered** — the
full semicolon-separated list stays in a single "Vendor Email ID" cell and
is never split across numbered columns, so an exported sheet can be edited
and re-imported without the address list changing shape. Headers are bold,
wrapped, and the header row is frozen. The Audit Log and Equipment Master
exports use their own layouts.

## Project layout

```
main.py                      entry point
vendor_app/
  config.py                  field keys/labels, storage paths, grid row cap,
                              wrapped table headers, column widths, status values
  validators.py               field & record validation rules
  data_manager.py             VendorStore: load/save, upsert/merge, status,
                               delete, search - wired to the audit trail
  audit.py                    AuditLog: append-only change history
  equipment.py                EquipmentStore: equipment master + lookups
  communication.py            group pasted rows into one email per vendor
  email_templates.py          email subjects/bodies + bordered HTML tables
  outlook.py                  Outlook draft creation (Windows/pywin32)
  settings.py                 persisted preferences (CC address)
  importer.py                 mass-import: parse vendor rows from a file
  export.py                   dynamic-column .xlsx export (vendors + audit log)
  gui/
    theme.py                   design tokens: colors, fonts, spacing, status colors
    widgets.py                  reusable buttons/badges/cards
    toast.py                    non-blocking success/info notifications
    style.py                     themed, sortable, hoverable Treeview + scrollbars
    scroll_canvas.py             2-axis scrollable canvas (bulk grid)
    main_window.py               app shell, branded header, 4-tab layout
    search_tab.py                 Tab 1 — single/multi search
    master_tab.py                  Tab 2 — master directory + stat strip
    grid_tab.py                     Tab 3 — bulk entry grid + file import
    equipment_tab.py                 Tab 4 — equipment master + searches
    communication_tab.py              Tab 5 — the two email flows
    audit_tab.py                       Tab 6 — audit trail
    edit_dialog.py                      shared add/edit record + status dialog
    missing_email_dialog.py              collect absent vendor emails
    paste_dialog.py                       generic 'paste rows' dialog
data/                         local CSV stores, audit log, settings (git-ignored)
```
