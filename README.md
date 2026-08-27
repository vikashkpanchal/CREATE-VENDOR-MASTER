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

## Navigation

The application is three things, and the top bar says exactly that. Everything
else is a sub-tab inside one of them, so the top level never grows past what
you can scan in a glance:

| Tab | Sub-tabs |
|-----|----------|
| **Vendor Master** | Records · Search · Change Log |
| **Equipment Master** | Records · Search · De-mob Equipment · Dashboard · Change Log |
| **Communication** | Defective Invoice · Equipment Breakdown |

Every tab and sub-tab is built on first visit, so start-up stays fast.

## Working with master data

Both masters share the same screen design, and both behave the same way.

- **Two ways to edit.** In the **vendor master**, double-clicking a row opens
  the full record dialog. To change a single cell in either master, select it
  and press `Enter` (or `F2`, or right-click → Edit cell): an editor opens over
  the cell, `Enter` commits, `Esc` cancels, `Tab` moves on. In the equipment
  master double-click edits the cell directly. Every commit goes through the
  store, so the same validation applies as anywhere else and a rejected value
  is restored with the reason shown.
- **Copy out to Excel.** `Ctrl+C` copies the highlighted cell, or the whole
  selected block of rows as TSV, so it pastes into Excel as real cells.
  Right-click for Copy cell / Copy row(s) / Copy row(s) with headers.
- **Unlimited import.** "Import..." reads an `.xlsx`/`.xls`/`.csv`/`.tsv` of
  any size, and **"Paste Rows" opens an Excel-like grid** - one column per
  field, so you click the first cell you need and `Ctrl+V` a block straight
  out of Excel and it lands in the right columns. Type into it, arrow around
  it, `Tab`/`Enter` between cells. There is no row cap. Long imports run on a background thread behind a progress dialog that
  shows live row counts - the window keeps painting instead of going blank.
- **Full change log.** Each master keeps its own append-only log
  (`data/vendor_audit_log.csv`, `data/equipment_audit_log.csv`) recording every
  add, field-level edit and delete with a before/after diff, a timestamp and
  who made it. Each is filterable and exports to `.xlsx` on its own.
- **Dialogs always fit.** Every dialog sizes itself to the actual screen and
  reserves its buttons before its body, so Save can never end up off-screen.

### Vendors created automatically from equipment

Any vendor referenced by an equipment row that is not already in the vendor
master is created there automatically with its code and name - on single
edits and on bulk imports alike. The vendor master's log records the new
vendor; the equipment log records why it appeared. Contact details are left
blank for you to fill in (the Communication tab will prompt for a missing
email when it needs one).

## Equipment Master

Alongside the identification columns (Equipment Description, UOM, Capacity,
RO/RH, Vendor Code, Vendor Name, RH/RO Number, Technical ID, Reg No, RH Date,
**De-mob Date**, Plant) each machine carries its commercial terms: **Plant
Code, Validity End Date, ARC No, FO No, MCM/Shift Code, Disc (MCM/Shift),
MCM/Shift Rate, OT Code, DIC (OT), OT Rate**.

### Running vs de-mobbed

A machine with a **De-mob Date** has left site. That record is **closed**:

- it drops out of every "Running Equipment" count (the header badge, the
  Records grid and the dashboard all default to the running fleet);
- it is **locked** - its cells can no longer be edited; and
- its identifiers are released, so if that machine comes back it is entered
  as a **brand-new, fully editable record**. The closed record stays as
  history, and the change log records the de-mob and the new arrival.

The **De-mob Equipment** sub-tab does this in bulk: paste identifiers
(RH/RO Number, Technical ID or Reg No) in one column and the de-mob date in
the next, with a fallback date for any blanks. It reports what was closed,
what was already closed, and anything it could not find, and lists every
de-mobbed machine alongside as read-only.

Any one of RH/RO Number, Technical ID or Reg No identifies a machine, so
search and import both work from whichever you have; rows are matched and
merged on any shared identifier. Technical ID must be numeric.

### Dashboard

An interactive analytics view over the fleet. It opens on **Running
Equipment**; the Fleet filter switches to de-mobbed machines or to
everything.

The dimension filters (**vendor, equipment, capacity, RO/RH, plant, plant
code**) behave
like Excel's column filters: **multi-select** with checkboxes, a search box
and scrolling, and **cascading** - once one filter is applied the others
offer only the values still reachable, not the whole list. A selection that
a later filter makes unreachable is dropped, so the filters can never
deadlock into an empty screen. Every KPI, chart and the results table
recompute from the same filtered set.

- KPI tiles: running (or de-mobbed) equipment, distinct suppliers, equipment
  types, plants, and contracts whose validity ends within 30 days
- **Top 10 suppliers** and **top 10 equipment types** by count, as ranked
  bars with hover detail
- **RO vs RH** composition, and top capacities
- "Export Filtered (.xlsx)" writes exactly what the filters currently select

## Communication

Drafts vendor emails from pasted data. **One email per vendor** - a vendor
with five defective invoices or three broken machines receives a single email
listing all of them. Nothing is sent: every message is saved as an Outlook
**draft** in its own sub-folder for review.

- **Defective Invoice** - paste Vendor Code, Vendor Name, PO Number, Scroll
  No, Invoice No, Invoice Date, Invoice Amount, Remarks (a header row is
  detected and skipped). Drafts go to the Outlook folder **"Defective Invoice"**.
- **Equipment Breakdown** - a two-column grid you paste straight into from
  Excel: the identifier (RH/RO Number, Technical ID or Reg No) in the first
  column and that machine's **Remarks** in the second. Everything else is
  fetched from the Equipment Master, and the remark appears against its own
  machine in the email table. A machine referenced twice by different
  identifiers is listed once. Drafts go to **"Equipment Breakdown"**.

Recipient addresses come from the vendor master. If a vendor has no email on
file, a dialog lists those vendors so you can enter an address (saved back to
the vendor master and logged) or tick **Skip**.

The **CC address** is asked for once and reused. Change it via "Change CC" or
by clicking the CC pill: the dialog opens pre-filled so you can edit it in
place, validates before saving, and has a separate "Clear CC".

"Preview Selected" opens the exact email in your browser before any draft is
created. Email tables use a thick outer border, bold header row and
content-fitted columns, and the default Outlook signature is preserved.

**Outlook requirements:** Windows with Microsoft Outlook (Office 16 / Outlook
2016) and `pywin32`. Elsewhere the rest of the app works normally and the tab
says drafting is unavailable - preview still works everywhere.

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
  config.py                  field keys/labels, storage paths, wrapped table
                              headers, column widths, status values, de-mob field
  validators.py               field & record validation rules
  data_manager.py             VendorStore: load/save, upsert/merge, status,
                               delete, search - wired to the change log
  audit.py                    ChangeLog: append-only history for both masters
  equipment.py                EquipmentStore: equipment master, lookups, de-mob
  communication.py            group pasted rows into one email per vendor
  email_templates.py          email subjects/bodies + bordered HTML tables
  outlook.py                  Outlook draft creation (Windows/pywin32)
  settings.py                 persisted preferences (CC address)
  importer.py                 mass-import: parse rows from a file
  export.py                   .xlsx export (vendors, equipment, change logs)
  gui/
    theme.py                   design tokens: colors, fonts, spacing, status colors
    widgets.py                  reusable buttons/badges/cards
    toast.py                    non-blocking success/info notifications
    loading.py                  threaded progress dialog for long imports
    style.py                     themed, sortable, hoverable Treeview + scrollbars
    editable_table.py            in-place cell editing + copy-out to Excel
    scroll_canvas.py             2-axis scrollable canvas
    charts.py                    ranked-bar / split-bar charts on a Tk canvas
    filter_dropdown.py           Excel-style multi-select cascading filter
    paste_grid.py                reusable Excel-like paste grid (Ctrl+V)
    paste_dialog.py              "Paste Rows" dialog built on the paste grid
    main_window.py               app shell, branded header, 3 top-level tabs
    master_tabs.py                Vendor / Equipment master tabs + sub-tab host
    records_screen.py             shared editable master records screen
    master_screens.py             the two concrete master records screens
    search_tab.py                  vendor search
    master_tab.py                  vendor master directory + stat strip
    equipment_tab.py               equipment search
    demob_tab.py                   bulk de-mob + de-mobbed equipment list
    dashboard_tab.py               interactive equipment analytics
    audit_tab.py                   change log screen (serves both masters)
    communication_tab.py           the two email flows
    edit_dialog.py                 shared add/edit record + status dialog
    cc_dialog.py                   editable, pre-filled CC address dialog
    missing_email_dialog.py        collect absent vendor emails
data/                         local CSV stores, both change logs, settings (git-ignored)
```
