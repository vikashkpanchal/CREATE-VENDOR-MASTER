# P&M Master Management System

A pure-Python desktop application for creating, importing, searching and
maintaining the plant & machinery masters: vendors, equipment, and the
rate contracts behind them. SAP/Oracle-style lifecycle management, a full
audit trail on every master, Outlook email drafting, and clean Excel export.

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

The application is four things, and the top bar says exactly that. Everything
else is a sub-tab inside one of them, so the top level never grows past what
you can scan in a glance:

| Tab | Sub-tabs |
|-----|----------|
| **Vendor Master** | Records · Search · Change Log |
| **Equipment Master** | Records · Search · De-mob Equipment · Dashboard · Change Log |
| **ARC & FO Master** | Dashboard · Structure · ARC Records · FO Records · Change Log |
| **Communication** | Defective Invoice · Equipment Breakdown |

Every tab and sub-tab is built on first visit, so start-up stays fast.

## Working with master data

Both masters share the same screen design, and both behave the same way.

- **Two ways to edit, the same in every master.** Double-clicking a row opens
  the **full record dialog** - the whole vendor, machine, ARC or FO in one
  place. To change a single cell instead, select it and press `Enter` (or
  `F2`, or right-click → Edit cell): an editor opens over the cell, `Enter`
  commits, `Esc` cancels, `Tab` moves on. Every commit goes through the store,
  so the same validation applies as anywhere else and a rejected value is
  restored with the reason shown.
- **Excel-like navigation and copy.** The grids are for reading and copying
  from, so a single click never starts an edit. Arrow keys walk the selected
  cell around, `Home`/`End` jump to the first/last column and `Ctrl+Home`/
  `Ctrl+End` to the first/last row. `Ctrl+C` copies the highlighted cell, or
  the whole selected block of rows as TSV, so it pastes into Excel as real
  cells. Right-click for Copy cell / Copy row(s) / Copy row(s) with headers.
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

The filter panel is a uniform grid that **reflows to the window width** -
narrow the app and the filters wrap onto another line rather than running off
the right edge, so every one of them stays reachable.

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

## ARC & FO Master

The contract layer beneath the equipment. Two inputs, both at line-item
granularity, exactly as the reports produce them:

```
Table 1  ARC data (ME3L export)     one row per ITEM of a purchasing document
Table 2  Framework & contract       one row per ITEM of a frame order
         tracking

Purchasing Document  (the contract - the key everything is filed against)
 |  header facts repeat on every item: vendor, validity, target value, release
 +-- Item                  Table 1: what the contract covers
 +-- Frame Number (FO)     Table 2: an order placed against the contract
      +-- Item             Table 2: what that order released
```

- **The header value is read once, never summed.** Target Val. (Header)
  repeats on every item of a contract, and Contract Value repeats again on
  every row of every frame order under it. Adding those columns up would
  report a five-item contract as worth five times what it is, so nothing in
  the app ever does. Per-item money - Released, Actual and Opening Value -
  *does* add up, because those figures belong to the item rather than to the
  header.
- **Counts are of entities, not rows.** An ARC is one purchasing document; an
  FO is one frame number. A five-item contract is one ARC, and a three-item
  frame order is one FO.
- **The purchasing document is the master key.** Every frame order names one
  contract, and every change anywhere - to a contract item or a frame order
  item - is recorded in one change log against that document number.
- **What has been released is never typed.** A frame order's total is the sum
  of its items; a contract's released value is the sum across its frame
  orders; and the **difference against Target Val. (Header)** is the balance
  still open. Those columns are read-only in the grids and read-outs in the
  dialogs, so a total can never disagree with its own detail.
- **Release codes read as words.** `R`/`S` and `X`...`XXXXX` are shown decoded
  ("R - Released", "XXX - Release by R2") in the grids and chosen from a list
  in the record dialog; the raw code is what gets stored, so a row still
  matches SAP.
- **Structure** shows each document with the items it covers and the frame
  orders placed against it, released against target in one cell.
- **ARC Records / FO Records** are the flat grids, with the same search,
  unlimited import, Excel-like paste, in-place editing and export as every
  other master. A row is keyed on its document and item (or frame number and
  item), so re-importing the same export updates those rows instead of
  doubling them.
- A frame order whose Contract No. matches no document is **not dropped** - it
  is grouped under "(no contract on file)", counted on its own KPI tile, and
  still credited to its vendor, so a typo stays visible.
- Deleting a contract's last item takes its frame orders with it; both are
  recorded in the log.

### Table 1: ARC data (ME3L export)

| Column | Meaning |
| --- | --- |
| Plant | Plant code / identifier |
| Purchasing Group | Procurement group code |
| Purchasing Document | PO / Contract No. cum ARC No. |
| Document Date | Order/creation date (`DD.MM.YYYY`) |
| Vendor/supplying plant | Vendor code then name, e.g. `100234 Vendor Name` |
| Item | Line item number (many per document) |
| Short Text | Material or service description |
| Validity Per. Start | Contract validity start (`DD.MM.YYYY`) |
| Validity Period End | Contract validity end (`DD.MM.YYYY`) |
| Target Val. (Header) | Total planned contract value - repeated across items, **never summed** |
| Release indicator | `R` released · `S` pending for approval |
| Release status | `X` buyer · `XX` PV · `XXX` R2 · `XXXX` R4 · `XXXXX` R6 |
| PO history/release documentation | Follow-on history and documentation text |

The combined **Vendor/supplying plant** column is stored exactly as the export
writes it; the code and the name are split out for the vendor master and the
vendor-wise analysis without reshaping the column.

### Table 2: framework & contract tracking

| Column | Meaning |
| --- | --- |
| Serial No. | Record identifier |
| Plant | Plant code / identifier |
| Contract No. | Contract / ARC document number |
| Contr.Pur.Group | Contract purchasing group |
| Header Text | Header-level description / notes |
| Vendor | Vendor numeric code |
| Vendor Name | Vendor name |
| Contract Value | Total contract value |
| Validity Start | Contract validity start |
| Validity End | Contract validity end |
| Requisitioner | Requisitioner name / ID |
| Frame Numbers | Framework agreement / order number |
| FO.Valdt.Start | Frame order validity start |
| FO.Valdt.End | Frame order validity end |
| Item | Line item number |
| Frame Pur.Group | Framework agreement purchasing group |
| Description | Item description |
| Req.Tracking No. | Purchase requisition tracking number |
| Released Value | Value released against the contract |
| Actual Value | Actual utilised / consumed value |
| Opening Value | Opening balance value |

**Field mapping, Table 1 → Table 2** - these four are the same fact seen from
the other side, and are treated as header values on both:

| Table 1 | Table 2 |
| --- | --- |
| Purchasing Document | Contract No. |
| Target Val. (Header) | Contract Value |
| Validity Per. Start | Validity Start |
| Validity Period End | Validity End |

Headers are matched three ways in turn: the column names above, the
abbreviations a raw download carries (`Purch.Doc.`, `Doc. Date`, `Target
Val.`, `Valid From/To`, `Purchasing Grp`, `Rel. Status`, ...), and the
internal column names. Unrecognised columns are ignored, not rejected.

### Dashboard

The first sub-tab, and the reason the data is kept. Built from one pass over
both tables, so the cards, the charts and the tables always agree.

**KPI cards** - Total ARC · Active ARC · Expired ARC · ARC Without FO ·
Total ARC Value · Total FO · Total FO Value · ARC Expiring in 30 Days ·
FO Expiring in 30 Days · Pending Approval (S). They reflow into as many
columns as the window fits, so none is ever pushed off the edge.

**Sections, in the order the questions get asked:**

| Section | Answers |
| --- | --- |
| ARC Expiry Analysis | status donut, release position, expiry trend (expired / 0-30 / 31-60 / 61-90 / beyond), and the contracts expiring in 30 days, soonest first |
| FO Expiry Analysis | the same read on the frame orders - which need extending |
| ARC Without FO | a contract is in place but nothing has been ordered against it, biggest first |
| Pending Approval | release indicator `S` - nothing can be ordered against these yet, furthest through the approval chain first |
| ARC vs FO Value Difference | `Target Val. (Header) - released against it`, ranked by the size of the gap either way |
| Vendor Analysis | contract value against released value per vendor, as paired bars and as a table |
| High Risk ARC / FO | expiring within 30 days, and (for a contract) with value still unreleased |
| Export Reports | every table above in one workbook |

Nineteen analyses back those sections: ARC and FO counts, values, active and
expired counts, 30/60/90-day expiry buckets for both, ARC Without FO, the ARC
vs FO gap, the vendor-wise comparison, and the two risk lists.

**Export** writes one `.xlsx`: the headline analyses on a `Summary` sheet,
then both masters rolled to their entity and every dashboard table, each on
its own sheet. Each section also exports on its own. An empty report still
gets its sheet - "nothing is expiring" is an answer, and a missing tab reads
as a missing one.

**Dates** are read leniently (`31.03.2027`, `2027-03-31`, `31/03/2027`,
`31-Mar-2027`, ...). A date that cannot be read is **never guessed at**: the
row is counted under "No Validity Date" and kept out of every expiry bucket,
because calling such a contract active - or expired - would put the wrong one
in front of a reader.

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

**Each flow keeps its own CC row.** The people copied on an invoice chase are
rarely the people copied on a breakdown, so the Defective Invoice and
Equipment Breakdown panels each carry their own CC address, shown and edited
on that panel. Each is asked for once, on first use of that flow, and reused
from then on; changing one leaves the other untouched. Change either via its
"Change CC" button or by clicking its CC pill: the dialog opens pre-filled so
you can edit it in place, validates before saving, and has a separate
"Clear CC". An address saved by an earlier single-CC build is carried across
to both rows on first run, so nothing is lost and you are not asked again.

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
  arc.py                      ArcStore: Table 1 + Table 2, with entity roll-up
  arc_analytics.py            the 19 ARC/FO analyses: expiry, gaps, risk, vendors
  communication.py            group pasted rows into one email per vendor
  email_templates.py          email subjects/bodies + bordered HTML tables
  outlook.py                  Outlook draft creation (Windows/pywin32)
  settings.py                 persisted preferences (per-flow CC addresses)
  importer.py                 mass-import: parse rows from a file
  export.py                   .xlsx export (vendors, equipment, ARC/FO, reports)
  gui/
    theme.py                   design tokens: colors, fonts, spacing, status colors
    widgets.py                  reusable buttons/badges/cards
    toast.py                    non-blocking success/info notifications
    loading.py                  threaded progress dialog for long imports
    style.py                     themed, sortable, hoverable Treeview + scrollbars
    editable_table.py            in-place cell editing + copy-out to Excel
    scroll_canvas.py             2-axis scrollable canvas
    charts.py                    ranked-bar / split-bar / donut / paired-bar charts
    filter_dropdown.py           Excel-style multi-select cascading filter
    paste_grid.py                reusable Excel-like paste grid (Ctrl+V)
    paste_dialog.py              "Paste Rows" dialog built on the paste grid
    main_window.py               app shell, branded header, 4 top-level tabs
    master_tabs.py                Vendor / Equipment master tabs + sub-tab host
    records_screen.py             shared editable master records screen
    master_screens.py             the two concrete master records screens
    search_tab.py                  vendor search
    master_tab.py                  vendor master directory + stat strip
    equipment_tab.py               equipment search
    demob_tab.py                   bulk de-mob + de-mobbed equipment list
    equipment_dialog.py            full machine record modal
    arc_screens.py                 the Table 1 and Table 2 records screens
    arc_structure_tab.py           the contract -> item / frame order view
    arc_dashboard_tab.py           ARC & FO management dashboard
    arc_dialogs.py                 contract-item and frame-order-item modals
    dashboard_tab.py               interactive equipment analytics
    audit_tab.py                   change log screen (serves both masters)
    communication_tab.py           the two email flows
    edit_dialog.py                 shared add/edit record + status dialog
    cc_dialog.py                   editable, pre-filled per-flow CC address dialog
    missing_email_dialog.py        collect absent vendor emails
data/                         local CSV stores, all three change logs, settings (git-ignored)
```
