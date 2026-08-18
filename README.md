# Vendor Master Management System

A pure-Python desktop application for creating, importing, searching and
maintaining a vendor master dataset, with SAP/Oracle-style vendor
lifecycle management, a full audit trail, and clean Excel export.

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
| 4 | Vendor Email ID | No length limit; multiple addresses separated by `;` (not `,`) — expands to "Vendor Email ID 1", "Vendor Email ID 2", ... on export |
| 5 | Vendor Owner Name | Optional |
| 6 | Vendor Owner Contact Number | Optional; digits only if provided |
| 7 | Vendor Owner Email ID | Optional; single address |
| 8 | Vendor Supervisor Contact Name | Optional |
| 9 | Vendor Supervisor Contact Number | Optional; digits only if provided |
| 10 | Vendor Supervisor Email ID | Optional; single address |

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
- Owner/Supervisor contact numbers must contain digits only, when provided.
- Multiple emails in "Vendor Email ID" must be separated by `;`. A `,` is rejected.
- Every other field is optional — a blank cell never raises an error.
- **Cell-level partial merge (upsert):** saving a record whose Vendor Code
  already exists only overwrites the non-blank fields you provided; blank
  cells leave the previously stored value untouched. This applies to grid
  saves and to the edit dialog alike.

## Tabs

Tab order matches day-to-day use: look someone up first, browse the
directory second, reach for bulk import when onboarding or refreshing many
vendors at once, and check the audit trail when you need to know who
changed what.

### 1. Search Vendor Details
- **Single Vendor Search** — enter one Vendor Code to view a full profile
  card (grouped into Vendor / Owner / Supervisor sections, with a status
  pill), with buttons to edit it or toggle Active/Inactive on the spot.
- **Multi Vendor Search** — paste/enter a list of Vendor Codes (one per
  line) to see all matches side-by-side in a sortable table, with an
  "Export Search Results (.xlsx)" button.

### 2. Master Data Records
The full vendor directory, led by a stat strip (Total / Active / Inactive /
Blocked), a live search bar, and a Status filter. Columns are sortable
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
`.xlsx`/`.xls`/`.csv`/`.tsv` file into the grid (tolerant of header casing
and of our own dynamic "Vendor Email ID N" export columns) for review
before saving. "Save Grid to Master" validates every non-blank row and
upserts it into the master dataset, reporting how many were added/updated
and listing any row-level errors.

### 4. Audit Log
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

The master/search `.xlsx` exports always follow the 10-field layout above,
with "Vendor Email ID" dynamically expanded into "Vendor Email ID 1",
"Vendor Email ID 2", etc. — as wide as the vendor with the most email
addresses in that export. Headers are bold, wrapped, and the header row is
frozen. The Audit Log export uses its own layout (timestamp, vendor,
action, details, changed by).

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
    audit_tab.py                     Tab 4 — audit trail
    edit_dialog.py                    shared add/edit record + status dialog
data/                         local CSV store + audit log (git-ignored)
```
