# Vendor Master Management System

A pure-Python desktop application for creating, importing, searching and
maintaining a vendor master dataset, with clean Excel export.

- **UI:** `customtkinter` (dark theme) with a consistent design system —
  branded header, cobalt accent, card layout, stat tiles, wrapped
  two-line table headers, zebra-striped rows (`vendor_app/gui/theme.py`)
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
directory second, and reach for bulk import only when onboarding or
refreshing many vendors at once.

### 1. Search Vendor Details
- **Single Vendor Search** — enter one Vendor Code to view a full profile
  card (grouped into Vendor / Owner / Supervisor sections), with an "Edit
  This Vendor Record" button to update it in place.
- **Multi Vendor Search** — paste/enter a list of Vendor Codes (one per
  line) to see all matches side-by-side in a table, with an "Export Search
  Results (.xlsx)" button.

### 2. Master Data Records
The full vendor directory, led by a stat strip (Total Vendors, With Owner
Contact, With Supervisor Contact, With Multiple Emails), with a live
search bar that filters by name or code as you type. Double-click a row
(or select it and click "Edit Selected") to edit it. "Export All (.xlsx)"
writes every record to a formatted spreadsheet.

### 3. Import & Update Grid
An Excel-like grid (100 rows max, for smooth, lag-free bulk entry) with
wrapped, zebra-striped rows. Paste directly from Excel with `Ctrl+V`;
navigate cells with the arrow keys, `Tab`, and `Enter`. "Save Grid to
Master" validates every non-blank row and upserts it into the master
dataset, reporting how many were added/updated and listing any row-level
errors.

## Tables

Master Data Records and Multi Vendor Search results both use the same
themed table component (`vendor_app/gui/style.py`): headers are always
pre-wrapped onto two clean lines and never truncated or hidden, rows are
zebra-striped for readability, and both a vertical and a horizontal
scrollbar are always available so wide tables scroll into view instead of
squeezing columns unreadably thin.

## Excel export layout

Exports always follow the field order above, with the "Vendor Email ID"
column dynamically expanded into "Vendor Email ID 1", "Vendor Email ID 2",
etc. — as wide as the vendor with the most email addresses in that export.
Headers are bold, wrapped, and the header row is frozen.

## Project layout

```
main.py                      entry point
vendor_app/
  config.py                  field keys/labels, storage path, grid row cap,
                              wrapped table headers, column widths
  validators.py               field & record validation rules
  data_manager.py             VendorStore: load/save, upsert/merge, search
  export.py                   dynamic-column .xlsx export
  gui/
    theme.py                   design tokens: colors, fonts, spacing
    widgets.py                  reusable buttons/badges/cards
    style.py                     themed Treeview + wrapped headers + scrollbars
    scroll_canvas.py             2-axis scrollable canvas (bulk grid)
    main_window.py               app shell, branded header, 3-tab layout
    search_tab.py                 Tab 1 — single/multi search
    master_tab.py                  Tab 2 — master directory + stat strip
    grid_tab.py                     Tab 3 — bulk entry grid
    edit_dialog.py                   shared add/edit record dialog
data/                         local CSV store (git-ignored)
```
