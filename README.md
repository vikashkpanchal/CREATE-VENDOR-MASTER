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
| 11 | Vendor Type | Optional; **CAD or MARKET only** |
| 12 | City | Optional |
| 13 | State | Optional |

Sheets exported by older builds (which used "Vendor Owner ..." /
"Vendor Supervisor ..." headers, and split emails across "Vendor Email ID
1/2/3" columns) still import correctly.

The 9 core fields (plus generated Sr. No.) are the exact, contractual
layout for the bulk-entry grid and the `.xlsx` export. **Vendor Type, City and State are
appended after them, never inserted among them**, so that order is
untouched — as is the operational metadata below.

### A vendor with equipment on site stays Active

A vendor cannot be set Inactive or Blocked while machines are still running
under its name — the attempt is refused, naming how many. Closing one would
leave equipment on the ground belonging to a vendor the system says is
finished, and every count of active suppliers, every breakdown email and
every ARC raised against them would be reasoning from a vendor that is not
supposed to exist. De-mob the machines first; the vendor closes the moment
the last one is off site.

### Vendor Type

A vendor is one of exactly two things, so the field is a choice rather than
free text:

- The record dialog offers a dropdown — `(not set)`, `CAD`, `MARKET`. There
  is no way to type a third value into it.
- Import, paste and in-place cell edits go through the same rule. Case and
  surrounding space are forgiven (`cad`, ` Market ` are accepted and stored
  as `CAD` / `MARKET`), because a pasted column will not be consistent about
  them. Anything else is **rejected with the row named**, rather than
  quietly creating a category nobody agreed to.
- Blank is allowed, so existing vendors do not have to be classified before
  anything else will save, and — like every other field — a blank on
  re-import never overwrites a type already stored.
- Typing `CAD` or `MARKET` into the Vendor Records search filters to that
  type. The match is on the whole word, so searching a name containing "ca"
  does not drag in every CAD vendor.

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
| **ARC Value Calculation** | Input · Calculated annexure · Export |
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
Code, Validity End Date, ARC No, FO No, Service Code- MCM/Shift, Service Code
Description, MCM Rate, Service Code-OT, OT Service Description, OT Rate**.

The five service-code columns were previously headed MCM/Shift Code, Disc
(MCM/Shift), MCM/Shift Rate, OT Code and DIC (OT). A sheet carrying either
spelling imports onto the right fields, so files exported by an older build
still load. Only the headings changed: the ARC value calculation reads these
columns by field, not by label, so **its figures are unaffected** by the
rename.

### Dates

**Every date column — RH Date, De-mob Date and Validity End Date — is
DD.MM.YYYY**, matching the ARC and FO masters. Whatever shape a date arrives
in (an Excel serial, `2024-03-05 00:00:00`, `5-Jan-2026`, `31/12/2025`) it is
re-stamped on the way in: on import, on paste, on a single-cell edit in the
grid, and on load, so a file written by an older build reads back in the new
format. A cell that is not a date at all is left exactly as typed.

### ARC No and Plant Code are derived

A machine belongs to a frame order, and that FO already knows which contract
it was placed against — so **ARC No is read from the FO No** rather than
typed a second time and left to disagree with it. The contract in turn knows
its plant, so **Plant Code is read from that ARC**.

Both are only ever filled in or corrected from the masters. When the FO No is
blank, or the frame order or contract is not on file, **whatever was typed
stays** — which is what makes manual entry the fallback rather than something
the app overwrites. The derivation runs on every add, import, paste and
single-cell edit; **Re-link ARC / Plant** on the Records screen re-runs it
across the whole fleet, for when a frame order is loaded or a contract's
plant is corrected after the machines were entered. Every change it makes is
written to the change log.

### Shift and Lease Type

Two more columns on every machine: **Shift**, and **Lease Type**, which is
`DRY` or `WET` and nothing else — a dropdown in the record dialog, and the
same forgiving-case, reject-anything-else rule Vendor Type follows.

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

That list has its own **Export (.xlsx)**, **Import De-mob...** and **Delete
Selected**. The import matches *closed* records only, so re-importing a list
this app exported updates those same rows instead of creating a second copy
of every machine, and it can never reopen or silently close a machine that is
currently on site — closing one is the De-mob action's job, which writes its
own change-log entry. Every imported row must carry a De-mob Date; that is
what makes it a closed record. Delete removes closed records from the master
permanently.

Any one of RH/RO Number, Technical ID or Reg No identifies a machine, so
search and import both work from whichever you have; rows are matched and
merged on any shared identifier. Technical ID must be numeric.

### Dashboard

An interactive analytics view over the fleet. It opens on **Running
Equipment**; the Fleet filter switches to de-mobbed machines or to
everything.

Its seven KPI tiles are **Running Equipment, Suppliers, Equipment Types,
Plants, Expired Equipment, Expiring in 30 Days** and **Equipment Without
FO**. Expired and expiring are kept as two separate numbers rather than one:
a machine whose validity has run out is a different problem from one that is
about to, and rolling them together hides the first inside the second. A date
that cannot be read is counted as neither. **Equipment Without FO** counts
the machines carrying no FO number — without one there is no frame order to
bill against, and no contract to read the ARC No and Plant Code from.

**Every tile opens.** Double-click (or click) any figure and the rows behind
it appear in a read-only grid with the same row-height control the other
tables have, and its own **Export (.xlsx)**. The pop-up is built from the
very list the tile counted, on the filters in force, so it can never disagree
with the card that opened it. A count-of-distinct tile — Suppliers,
Equipment Types, Plants — opens as one row per value with the number of
machines against it, which is what that figure actually counts.

The tiles reflow to fit: fixed-width cells, the column count computed from
the panel's real width, and never more than two rows deep, so nothing is ever
pushed off the edge of a 14" laptop.

The filter panel is **two rows of four**, always: capping the column count is
what keeps all eight filters on screen rather than spread into one strip that
runs off the edge of a laptop.

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
- **ARC Records / FO Records** open showing the input table exactly as it
  arrives - the report's own columns, in the report's own order, and nothing
  else. Tick **Computed columns** to append what the app works out across a
  contract or a frame order; they are always added after the input set, never
  interleaved into it. The grids have the same search, unlimited import,
  Excel-like paste, in-place editing and export as every other master, and a
  row is keyed on its document and item (or frame number and item), so
  re-importing the same export updates those rows instead of doubling them.
- **The join is on the number, not on the text.** A contract number is what
  ties the two files together, and the two files do not always write it
  identically: the same document arrives as `4600001201` from one export and
  as `4600001201.0` from a numeric column, `0004600001203` zero-padded,
  `4,600,001,204` once a separator has been applied, or `' 4600001205 `
  with Excel's text marker and padding. Every identity comparison - which
  frame orders belong to a contract, which contract has none, which rows are
  the same row on re-import - is made on the canonical number, so those are
  one contract rather than two. Item numbers match the same way (`10` and
  `00010`). Only the *form* of a number is normalised; two genuinely
  different numbers can never collide.
- **ARC Without FO** therefore means exactly what it says: a purchasing
  document that no row in Table 2 names as its Contract No. When frame orders
  name a contract that is not in Table 1 at all, that section says so - the
  two problems together mean the files are not lining up, which is different
  from a contract genuinely having no orders. Those rows are listed on the
  **FO Without a Contract** sheet of the export: a data-quality answer rather
  than a management figure, so not a dashboard section.
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

**Every KPI card is clickable.** Click a figure and a pop-up lists the exact
rows it was counted or summed from - the contracts behind "Total ARC", the
frame orders behind "Total FO Value", the two contracts behind "ARC Without
FO" - with the same row-height control and its own Excel export. A number on
this page can always be taken apart into the rows it came from.

**KPI cards** - Total ARC · Active ARC · Expired ARC · ARC Without FO ·
Total ARC Value · Total FO · Total FO Value · ARC Expiring in 30 Days ·
FO Expiring in 30 Days · Pending Approval (S). They reflow into as many
columns as the window fits, so none is ever pushed off the edge, and a
figure's type size steps down as it gets longer so a crore-scale total is
read rather than clipped.

**Sections, in the order the questions get asked:**

| Section | Answers |
| --- | --- |
| ARC Expiry Analysis | status donut, release position, expiry trend (expired / 0-30 / 31-60 / 61-90 / beyond), and the contracts expiring in 30 days, soonest first |
| FO Expiry Analysis | the same read on the frame orders - which need extending |
| ARC Without FO | a contract against which not one frame order has been raised, biggest first |
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
`31-Mar-2027`, and Excel's `2027-03-31 00:00:00`) and then shown in exactly
one shape: **DD.MM.YYYY, never with a time**. That applies to every date in
the ARC & FO Master - the grids, the structure tree, the record dialogs, the
dashboard tables and the exported workbook - and the value is normalised on
the way in, so the stored file carries it that way too. A cell that is not a
date at all ("TBD on award") is left exactly as written rather than
reformatted into a guess, and a date that cannot be read is **never guessed
at**: the row is counted under "No Validity Date" and kept out of every
expiry bucket, because calling such a contract active - or expired - would
put the wrong one in front of a reader.

## ARC Value Calculation

Three input columns priced into a contract-amendment annexure. You give it,
per machine:

| Input | |
| --- | --- |
| Technical ID | the machine |
| Extension Date | what the order is being revised up to |
| Working Shift | `12` or `24` |

Everything else is looked up:

```
Technical ID -> equipment master   ARC No, Service Code- MCM/Shift + Service
                                   Code Description + MCM Rate, Service Code-OT
                                   + OT Service Description + OT Rate,
                                   validity end
ARC No       -> ARC & FO master    vendor code, vendor name, plant
Vendor Code  -> vendor master      vendor type
```

Two dates drive the whole calculation:

- **Existing Order Calculation upto** = the equipment's Validity End Date
- **Revised Order Calculation upto** = the Extension Date you gave

and the **months between them are the MCM quantity** — counted on the
calendar, so 28.02.2026 to 31.12.2026 is 10 months.

**Machines are counted, not listed.** Within one contract, every machine
sharing the same MCM code, description, rates, OT code, shift and pair of
dates becomes one line, with the count in **Eqp Qty**. Anything that differs
— a different rate, a 24-hour deployment beside a 12-hour one, a different
extension date — is its own line, because those cannot share a quantity or a
value.

Each line prints as one row, or two when the machine carries overtime:

| | Service Code | Equipment Description | UOM | Monthly Rate | Qty. | Value |
| --- | --- | --- | --- | --- | --- | --- |
| MCM row | Service Code- MCM/Shift | Service Code Description | `MCM` | MCM Rate | months | Eqp Qty × months × rate |
| OT row *(only when an OT code exists)* | Service Code-OT | OT Service Description | `H` | OT Rate | Eqp Qty × months × 26 × hours/day | Qty × rate |

Overtime hours per working day come from the shift: **2** on a 12-hour
deployment, **11** on a 24-hour one, over **26** working days a month. The
Eqp Qty sits on the MCM row only — it is already inside the OT quantity, so
repeating it there would double the overtime value.

Contracts are ordered **oldest first**, by the ARC's own validity start (then
its document date, then its number); within a contract the categories stay in
the order the input named them. Each contract gets a **subtotal row** for Eqp
Qty and Value, and the sheet ends with a grand total, banded as they are in
the source workbook.

Anything that cannot be priced is listed under **NOT PRICED** rather than
dropped — a Technical ID not in the equipment master, a shift that is not
12 or 24, an unreadable Extension Date, an extension that is not after the
validity end, a machine with no ARC No, or an ARC that is not in the ARC & FO
master (that one still prices, using the equipment record's own vendor and
plant, and says so).

### The workbook

Two sheets, Calibri 10 throughout. Headers are **black on white**, bold and
bordered - this annexure gets printed and signed, and the bold and the border
already say "header" without a band of colour. Total rows are bold on a very
light blue.

**Annexure 2** is the calculation, with those sixteen columns. Every
multiplication and every total is written as a live Excel **formula**, not a
number this app worked out — `=J4*K4*M4` for a line's value, `=J4*K4*26*2`
for an overtime quantity, `=SUBTOTAL(9,...)` for each contract's subtotal and
the grand total. The sheet can be audited cell by cell, a rate corrected in
place, and everything above and below it follows. `SUBTOTAL` also ignores the
nested subtotals in its own range and re-totals whatever a filter leaves
visible, which is how the source workbook does it.

**Annexure 1** summarises it, one row per ARC, in Annexure 2's own contract
order:

| Column | Where it comes from |
| --- | --- |
| Sr no., ARC No. | the contract |
| Work Order Date | the ARC record's Document Date |
| Plant, Vendor Code, Vendor Name | as on the priced rows |
| Existing ARC value (Rs.) | the ARC record's Target Val. (Header) |
| Impact (Rs.) | **read from Annexure 2's subtotal cell** — `='Annexure 2'!N6` |
| Revised Arc Value (Rs.) | `= Existing + Impact` |
| ARC Validity Start Date | the ARC record's Validity Per. Start |
| ARC Validity End Date | the **latest** of the ARC's own validity end and every revised date priced against it — extending one machine past the contract necessarily extends the contract |

Because Impact is a reference rather than a copy, the two sheets cannot
drift: correct a rate in Annexure 2 and Annexure 1 follows.

## All data in one file

Two buttons in the app header, on screen from the moment it opens:

- **Export All Data** writes one workbook with four sheets - **Vendor
  Master**, **Equipment Master**, **ARC Master**, **FO Master** - each with
  exactly the columns that master already exports, in the same order. It is a
  backup you can read by eye, edit, and hand straight back.
- **Import All Data...** reads that file in again, routing each sheet to its
  own store through the same bulk import a single master uses. Every rule
  still applies: cell-level merge (a blank cell never overwrites what is
  stored), validation per row, and a change-log entry for what actually
  changed. Nothing is deleted.

Sheets are matched by name and loaded vendors-first, so an equipment or ARC
row that names a vendor finds it already there, and contracts land before the
frame orders placed against them. A sheet the file does not carry is skipped
and named in the summary rather than treated as an error - a file with only
the vendor sheet still loads.

Equipment goes in two passes, running rows then closed ones. A machine that
left site and later came back legitimately has **both** a closed record and a
running one under the same identifier; one pass would let the closed row merge
into the running one and close the machine that is actually on site.
(Identical closed duplicates still collapse into one - that is the same
machine closed on the same date, not two events.)

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

Every grid in the app shares the same behaviour:

- **The header row is fixed.** It stays put while the rows scroll under it,
  at any row height, and a column is never drawn narrower than its own title -
  the header is the only thing on screen that says what a column *is*, so it
  is the one piece of text that is never allowed to be cut.
- **Big grids stay fast.** Every "which frame orders belong to this
  contract", "what has been released against it" and "what does this frame
  order add up to" comes off one index built in a single pass and dropped
  whenever either table changes, instead of re-scanning the other table per
  row per column. On 1,200 contract items and 2,700 frame-order rows that
  took the ARC read path from **28.7s to 0.20s**.
- **Row height is adjustable** - Compact, Normal, Tall or Extra tall - from
  the control above each grid. The dashboard has one control for all its
  tables; each drill-down pop-up has its own.
- **Nothing sits off the edge on a small screen.** The window opens no larger
  than the display it opens on, every header keeps a reserved column for its
  action buttons, titles wrap rather than pushing them away, and the
  Equipment Master filter panel is capped at two rows of four so all eight
  filters - Plant and Plant Code included - are always in view, with its seven
  KPI tiles capped the same way. Verified on a 1366x768 (14") display across
  every tab.

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
  arc_value.py                ARC value calculation: input rows -> priced annexure
  workbook.py                 all four masters in one file, out and back in
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
    kpi_dialog.py                the rows behind a clicked dashboard figure
    filter_dropdown.py           Excel-style multi-select cascading filter
    paste_grid.py                reusable Excel-like paste grid (Ctrl+V)
    paste_dialog.py              "Paste Rows" dialog built on the paste grid
    main_window.py               app shell, branded header, 5 top-level tabs
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
    arc_value_tab.py               ARC value calculation: input, result, export
    arc_dialogs.py                 contract-item and frame-order-item modals
    dashboard_tab.py               interactive equipment analytics
    audit_tab.py                   change log screen (serves both masters)
    communication_tab.py           the two email flows
    edit_dialog.py                 shared add/edit record + status dialog
    cc_dialog.py                   editable, pre-filled per-flow CC address dialog
    missing_email_dialog.py        collect absent vendor emails
data/                         local CSV stores, all three change logs, settings (git-ignored)
```
