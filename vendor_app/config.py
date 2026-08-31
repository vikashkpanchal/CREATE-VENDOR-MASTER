"""Application-wide constants: field definitions, storage paths, UI limits."""

import os

APP_TITLE = "P&M Master Management System"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "vendor_master_store.csv")
AUDIT_FILE = os.path.join(DATA_DIR, "vendor_audit_log.csv")
EQUIPMENT_AUDIT_FILE = os.path.join(DATA_DIR, "equipment_audit_log.csv")

# Bulk entry grid is capped at 100 rows to keep the UI smooth and lag-free.
MAX_GRID_ROWS = 100

# Internal field keys, in the exact order required by the spec (Sr. No. is
# generated automatically and is not part of the editable/stored key set).
KEYS = [
    "vendor_code",
    "vendor_name",
    "vendor_email",
    "vendor_owner_name",
    "vendor_owner_contact",
    "vendor_owner_email",
    "vendor_supervisor_name",
    "vendor_supervisor_contact",
    "vendor_supervisor_email",
    # Appended after the nine mandated fields, never inserted among them, so
    # the contractual grid/export layout keeps its exact order.
    "vendor_type",
    "city",
    "state",
]

# Human-readable labels shown in the grid, search results, master table and
# exported spreadsheet.
LABELS = {
    "vendor_code": "Vendor Code",
    "vendor_name": "Vendor Name",
    "vendor_email": "Vendor Email ID",
    "vendor_owner_name": "Contact Person1 Name",
    "vendor_owner_contact": "Contact Person1 Contact Number",
    "vendor_owner_email": "Contact Person1 Email ID",
    "vendor_supervisor_name": "Contact Person2 Name",
    "vendor_supervisor_contact": "Contact Person2 Contact Number",
    "vendor_supervisor_email": "Contact Person2 Email ID",
    "vendor_type": "Vendor Type",
    "city": "City",
    "state": "State",
}

# A vendor is one of exactly two things, so the field is a choice rather than
# free text: a dropdown in the dialog, and anything else rejected on import
# or in-place edit. Case and surrounding space are forgiven ("cad", " Market ")
# because a pasted sheet will not be consistent about them; a third value is
# not, because it would quietly create a category nobody agreed to.
VENDOR_TYPE_VALUES = ["CAD", "MARKET"]

# Header names used by earlier versions of this app. Kept so that importing a
# spreadsheet exported before the Owner/Supervisor -> Contact Person1/2 rename
# still maps onto the right fields.
LEGACY_LABELS = {
    "vendor_owner_name": "Vendor Owner Name",
    "vendor_owner_contact": "Vendor Owner Contact Number",
    "vendor_owner_email": "Vendor Owner Email ID",
    "vendor_supervisor_name": "Vendor Supervisor Contact Name",
    "vendor_supervisor_contact": "Vendor Supervisor Contact Number",
    "vendor_supervisor_email": "Vendor Supervisor Email ID",
}

# --------------------------------------------------------------- lifecycle --
# Vendor lifecycle status (SAP/Oracle-style "vendor block" concept), kept as
# operational metadata alongside the 9 core business fields above rather
# than inside KEYS - it never alters the mandated grid/export field layout.
STATUS_VALUES = ["Active", "Inactive", "Blocked"]
STATUS_DEFAULT = "Active"

# Operational metadata persisted per vendor in addition to KEYS.
META_FIELDS = ["status", "created_at", "updated_at"]

# Full set of columns written to the internal CSV store.
STORE_FIELDS = KEYS + META_FIELDS

# On-screen table column order (Master Data Records, Multi Vendor Search).
# Deliberately separate from KEYS: KEYS is the exact, contractual field
# order for the bulk-entry grid and the .xlsx export; DISPLAY_COLUMNS is
# free to add operational columns like Status for on-screen browsing only.
DISPLAY_COLUMNS = [
    "vendor_code",
    "vendor_name",
    "vendor_email",
    "vendor_owner_name",
    "vendor_owner_contact",
    "vendor_owner_email",
    "vendor_supervisor_name",
    "vendor_supervisor_contact",
    "vendor_supervisor_email",
    "vendor_type",
    "city",
    "state",
    "status",
]

# Two-line wrapped header text for Treeview-based tables (Master Data
# Records, Multi Vendor Search results). Deliberately pre-wrapped rather
# than auto word-wrapped, so every header renders exactly two clean lines
# and is never clipped or truncated.
WRAPPED_LABELS = {
    "sr_no": "Sr.\nNo.",
    "status": "Status",
    "vendor_code": "Vendor\nCode",
    "vendor_name": "Vendor\nName",
    "vendor_email": "Vendor Email\nID",
    "vendor_owner_name": "Contact Person1\nName",
    "vendor_owner_contact": "Contact Person1\nContact Number",
    "vendor_owner_email": "Contact Person1\nEmail ID",
    "vendor_supervisor_name": "Contact Person2\nName",
    "vendor_supervisor_contact": "Contact Person2\nContact Number",
    "vendor_supervisor_email": "Contact Person2\nEmail ID",
    "vendor_type": "Vendor\nType",
    "city": "City",
    "state": "State",
}

# Per-column pixel widths, sized so the wrapped two-line header above always
# fits on-screen without truncation. Tables scroll horizontally beyond this,
# rather than squeezing columns until headers/content become unreadable.
COLUMN_WIDTHS = {
    "sr_no": 64,
    "status": 130,
    "vendor_code": 110,
    "vendor_name": 260,
    "vendor_email": 300,
    "vendor_owner_name": 170,
    "vendor_owner_contact": 170,
    "vendor_owner_email": 200,
    "vendor_supervisor_name": 190,
    "vendor_supervisor_contact": 180,
    "vendor_supervisor_email": 200,
    "vendor_type": 130,
    "city": 160,
    "state": 170,
}

# Fields that must contain digits only when provided.
NUMERIC_FIELDS = {"vendor_code", "vendor_owner_contact", "vendor_supervisor_contact"}

# Fields that may hold multiple semicolon-separated email addresses.
MULTI_EMAIL_FIELDS = {"vendor_email"}

# Fields that hold at most a single email address.
SINGLE_EMAIL_FIELDS = {"vendor_owner_email", "vendor_supervisor_email"}

# ----------------------------------------------------------------- audit --
AUDIT_COLUMNS = ["timestamp", "vendor_code", "vendor_name", "action", "details", "actor"]

AUDIT_WRAPPED_LABELS = {
    "timestamp": "Date &\nTime",
    "vendor_code": "Vendor\nCode",
    "vendor_name": "Vendor\nName",
    "action": "Action",
    "details": "Details",
    "actor": "Changed\nBy",
}

AUDIT_COLUMN_WIDTHS = {
    "timestamp": 150,
    "vendor_code": 100,
    "vendor_name": 200,
    "action": 130,
    "details": 420,
    "actor": 120,
}

# The equipment master keeps its own change log, keyed by the machine's
# identifier rather than a vendor code.
EQUIPMENT_AUDIT_COLUMNS = [
    "timestamp", "equipment_id", "equipment_description", "action", "details", "actor",
]

EQUIPMENT_AUDIT_WRAPPED_LABELS = {
    "timestamp": "Date &\nTime",
    "equipment_id": "Equipment\nID",
    "equipment_description": "Equipment\nDescription",
    "action": "Action",
    "details": "Details",
    "actor": "Changed\nBy",
}

EQUIPMENT_AUDIT_COLUMN_WIDTHS = {
    "timestamp": 150,
    "equipment_id": 130,
    "equipment_description": 220,
    "action": 130,
    "details": 420,
    "actor": 120,
}

# ------------------------------------------------------------- settings --
# Small app-level preferences (e.g. the CC address used on every outgoing
# email), stored once and reused so the user is only ever asked a single time.
SETTINGS_FILE = os.path.join(DATA_DIR, "app_settings.json")

# ------------------------------------------------------ equipment master --
EQUIPMENT_FILE = os.path.join(DATA_DIR, "equipment_master.csv")

# Equipment fields, in the exact order required (Sr. No. is generated).
EQUIPMENT_KEYS = [
    "equipment_description",
    "uom",
    "capacity",
    "ro_rh",
    "vendor_code",
    "vendor_name",
    "rh_ro_number",
    "technical_id",
    "reg_no",
    "rh_date",
    "demob_date",
    "plant",
    # --- commercial / contract columns ---
    "plant_code",
    "validity_end_date",
    "arc_no",
    "fo_no",
    "mcm_shift_code",
    "disc_mcm_shift",
    "mcm_shift_rate",
    "ot_code",
    "dic_ot",
    "ot_rate",
    "shift",
    "lease_type",
]

EQUIPMENT_LABELS = {
    "equipment_description": "Equipment Description",
    "uom": "UOM",
    "capacity": "Capacity",
    "ro_rh": "RO/RH",
    "vendor_code": "Vendor Code",
    "vendor_name": "Vendor Name",
    "rh_ro_number": "RH/RO Number",
    "technical_id": "Technical ID",
    "reg_no": "Reg No",
    "rh_date": "RH Date",
    "demob_date": "De-mob Date",
    "plant": "Plant",
    "plant_code": "Plant Code",
    "validity_end_date": "Validity End Date",
    "arc_no": "ARC No",
    "fo_no": "FO No",
    "mcm_shift_code": "MCM/Shift Code",
    "disc_mcm_shift": "Disc (MCM/Shift)",
    "mcm_shift_rate": "MCM/Shift Rate",
    "ot_code": "OT Code",
    "dic_ot": "DIC (OT)",
    "ot_rate": "OT Rate",
    "shift": "Shift",
    "lease_type": "Lease Type",
}

EQUIPMENT_WRAPPED_LABELS = {
    "sr_no": "Sr.\nNo.",
    "equipment_description": "Equipment\nDescription",
    "uom": "UOM",
    "capacity": "Capacity",
    "ro_rh": "RO/RH",
    "vendor_code": "Vendor\nCode",
    "vendor_name": "Vendor\nName",
    "rh_ro_number": "RH/RO\nNumber",
    "technical_id": "Technical\nID",
    "reg_no": "Reg\nNo",
    "rh_date": "RH\nDate",
    "demob_date": "De-mob\nDate",
    "plant": "Plant",
    "plant_code": "Plant\nCode",
    "validity_end_date": "Validity\nEnd Date",
    "arc_no": "ARC\nNo",
    "fo_no": "FO\nNo",
    "mcm_shift_code": "MCM/Shift\nCode",
    "disc_mcm_shift": "Disc\n(MCM/Shift)",
    "mcm_shift_rate": "MCM/Shift\nRate",
    "ot_code": "OT\nCode",
    "dic_ot": "DIC\n(OT)",
    "ot_rate": "OT\nRate",
    "shift": "Shift",
    "lease_type": "Lease\nType",
}

EQUIPMENT_COLUMN_WIDTHS = {
    "sr_no": 64,
    "equipment_description": 260,
    "uom": 90,
    "capacity": 120,
    "ro_rh": 100,
    "vendor_code": 110,
    "vendor_name": 240,
    "rh_ro_number": 140,
    "technical_id": 130,
    "reg_no": 140,
    "rh_date": 120,
    "demob_date": 130,
    "plant": 120,
    "plant_code": 110,
    "validity_end_date": 140,
    "arc_no": 130,
    "fo_no": 130,
    "mcm_shift_code": 140,
    "disc_mcm_shift": 140,
    "mcm_shift_rate": 130,
    "ot_code": 110,
    "dic_ot": 110,
    "ot_rate": 110,
    "shift": 100,
    "lease_type": 120,
}

# Equipment lookup keys: pasting any ONE of these retrieves the full record.
# A machine is hired one of two ways, so Lease Type is a choice rather than
# free text - the same rule Vendor Type follows.
LEASE_TYPE_VALUES = ["DRY", "WET"]

EQUIPMENT_LOOKUP_KEYS = ["rh_ro_number", "technical_id", "reg_no"]

# Technical ID is numeric; RH/RO Number is alphanumeric; Reg No is free text.
EQUIPMENT_NUMERIC_FIELDS = {"technical_id"}

# Columns treated as amounts on the dashboard / rate roll-ups.
EQUIPMENT_RATE_FIELDS = {"mcm_shift_rate", "ot_rate", "disc_mcm_shift", "dic_ot"}

# Columns the equipment change log and dashboard treat as dates.
EQUIPMENT_DATE_FIELDS = {"rh_date", "validity_end_date", "demob_date"}

# A machine with a De-mob Date has left site. Such a record is FROZEN: its
# cells can no longer be edited, it is excluded from "running" counts, and
# if that same machine comes back it is entered as a brand-new record
# rather than reopening the closed one.
DEMOB_FIELD = "demob_date"

# Running/De-mob filter values used on the dashboard and records screens.
FLEET_RUNNING = "Running Equipment"
FLEET_DEMOB = "De-mob Equipment"
FLEET_ALL = "All Equipment"
FLEET_FILTER_VALUES = [FLEET_RUNNING, FLEET_DEMOB, FLEET_ALL]

# Equipment search results are capped at 50 records per the spec.
MAX_EQUIPMENT_SEARCH_RESULTS = 50

# --------------------------------------------------------- communication --
# Columns the user pastes into the Defective Invoice communication tab.
DEFECTIVE_INVOICE_KEYS = [
    "vendor_code",
    "vendor_name",
    "po_number",
    "scroll_no",
    "invoice_no",
    "invoice_date",
    "invoice_amount",
    "remarks",
]

DEFECTIVE_INVOICE_LABELS = {
    "vendor_code": "Vendor Code",
    "vendor_name": "Vendor Name",
    "po_number": "PO Number",
    "scroll_no": "Scroll No",
    "invoice_no": "Invoice No",
    "invoice_date": "Invoice Date",
    "invoice_amount": "Invoice Amount",
    "remarks": "Remarks",
}

# Columns shown in the generated defective-invoice email table (Sr No first).
DEFECTIVE_INVOICE_EMAIL_COLUMNS = [
    "po_number",
    "scroll_no",
    "invoice_no",
    "invoice_date",
    "invoice_amount",
    "remarks",
]

# Columns shown in the generated equipment-breakdown email table.
BREAKDOWN_EMAIL_COLUMNS = [
    "equipment_description",
    "capacity",
    "uom",
    "rh_ro_number",
    "technical_id",
    "reg_no",
    "remarks",
]

BREAKDOWN_EMAIL_HEADERS = {
    "equipment_description": "Equipment",
    "capacity": "Capacity",
    "uom": "UOM",
    "rh_ro_number": "RH Code",
    "technical_id": "Technical ID",
    "reg_no": "REG NO",
    "remarks": "Remarks",
}

# Outlook draft folders (created under the default account's Inbox if absent).
OUTLOOK_DEFECTIVE_FOLDER = "Defective Invoice"
OUTLOOK_BREAKDOWN_FOLDER = "Equipment Breakdown"

# ======================================================= ARC & FO master ==
# An ARC (Annual Rate Contract) is the master agreement and the key every
# amendment is filed against. FOs (Framework Orders) are its sub-parts: one
# ARC can carry many FOs, and the ARC's total value is the aggregate of the
# FO values beneath it - never a number typed in on its own. Line items sit
# one level further down and act as the references behind an FO's value.
#
#     ARC  (arc_no)              master key, holds the amendments
#      +-- FO  (fo_no)           sub-part, many per ARC
#           +-- Line item        reference rows behind the FO's value
#
ARC_FILE = os.path.join(DATA_DIR, "arc_master.csv")
FO_FILE = os.path.join(DATA_DIR, "fo_master.csv")
ARC_AUDIT_FILE = os.path.join(DATA_DIR, "arc_audit_log.csv")

# --- Table 1: ARC data (ME3L export) ---------------------------------------
# One row per LINE ITEM of a purchasing document, exactly as the export
# produces it. The header facts - vendor, validity, target value, release -
# repeat on every item of the same document, so anything computed per
# contract is taken from the header ONCE and never summed across the
# duplicates. That single rule is what keeps a contract's value honest.
ARC_KEYS = [
    "plant",
    "purchasing_group",
    "purchasing_document",
    "document_date",
    "vendor_supplying_plant",
    "item",
    "short_text",
    "validity_start",
    "validity_end",
    "target_value",
    "release_indicator",
    "release_status",
    "po_history",
]

ARC_LABELS = {
    "plant": "Plant",
    "purchasing_group": "Purchasing Group",
    "purchasing_document": "Purchasing Document",
    "document_date": "Document Date",
    "vendor_supplying_plant": "Vendor/supplying plant",
    "item": "Item",
    "short_text": "Short Text",
    "validity_start": "Validity Per. Start",
    "validity_end": "Validity Period End",
    "target_value": "Target Val. (Header)",
    "release_indicator": "Release indicator",
    "release_status": "Release status",
    "po_history": "PO history/release documentation",
}

# A row is identified by its document and its item number: one purchasing
# document carries many items, and re-importing must land on the same row.
ARC_KEY_FIELDS = ("purchasing_document", "item")

# Header-level columns: identical on every item of a document. Read once per
# document, never added up.
ARC_HEADER_KEYS = [
    "plant", "purchasing_group", "purchasing_document", "document_date",
    "vendor_supplying_plant", "validity_start", "validity_end",
    "target_value", "release_indicator", "release_status",
]

# Release indicator: is the contract usable yet?
RELEASE_RELEASED = "R"
RELEASE_PENDING = "S"
RELEASE_INDICATORS = {
    RELEASE_RELEASED: "Released",
    RELEASE_PENDING: "Pending for approval",
}

# Release status: how far up the approval chain a document has travelled.
# The codes are counts of X, so they sort naturally by level.
RELEASE_STATUS_LEVELS = {
    "X": "Release by Buyer",
    "XX": "Release by PV",
    "XXX": "Release by R2",
    "XXXX": "Release by R4",
    "XXXXX": "Release by R6",
}


def describe_release_indicator(code: str) -> str:
    """'R' -> 'R - Released'. An unknown code is shown as it came."""
    code = (code or "").strip().upper()
    if not code:
        return ""
    meaning = RELEASE_INDICATORS.get(code)
    return f"{code} - {meaning}" if meaning else code


def describe_release_status(code: str) -> str:
    """'XXX' -> 'XXX - Release by R2'."""
    code = (code or "").strip().upper()
    if not code:
        return ""
    meaning = RELEASE_STATUS_LEVELS.get(code)
    return f"{code} - {meaning}" if meaning else code


# Columns the ARC grid derives per DOCUMENT and repeats on its items, the way
# the source report repeats the header value.
ARC_DERIVED_KEYS = ["frame_orders", "ordered_value", "value_difference"]

ARC_DERIVED_LABELS = {
    "frame_orders": "Frame Orders",
    "ordered_value": "Released Against",
    "value_difference": "Difference (Target - Released)",
}

ARC_DISPLAY_COLUMNS = ARC_KEYS + ARC_DERIVED_KEYS

ARC_WRAPPED_LABELS = {
    "sr_no": "Sr.\nNo.",
    "plant": "Plant",
    "purchasing_group": "Purchasing\nGroup",
    "purchasing_document": "Purchasing\nDocument",
    "document_date": "Document\nDate",
    "vendor_supplying_plant": "Vendor /\nsupplying plant",
    "item": "Item",
    "short_text": "Short\nText",
    "validity_start": "Validity Per.\nStart",
    "validity_end": "Validity\nPeriod End",
    "target_value": "Target Val.\n(Header)",
    "frame_orders": "Frame\nOrders",
    "ordered_value": "Released\nAgainst",
    "value_difference": "Difference\n(Target - Released)",
    "release_indicator": "Release\nindicator",
    "release_status": "Release\nstatus",
    "po_history": "PO history /\nrelease documentation",
}

ARC_COLUMN_WIDTHS = {
    "sr_no": 64,
    "plant": 90,
    "purchasing_group": 120,
    "purchasing_document": 160,
    "document_date": 120,
    "vendor_supplying_plant": 260,
    "item": 70,
    "short_text": 280,
    "validity_start": 120,
    "validity_end": 120,
    "target_value": 150,
    "frame_orders": 100,
    "ordered_value": 150,
    "value_difference": 170,
    "release_indicator": 190,
    "release_status": 180,
    "po_history": 300,
}

# Pre-rename columns, so a store written by an earlier build still loads.
ARC_LEGACY_COLUMNS = {
    "arc_no": "purchasing_document",
    "arc_description": "short_text",
    "arc_start_date": "validity_start",
    "arc_end_date": "validity_end",
    "arc_value": "target_value",
}

# --- Table 2: framework & contract tracking --------------------------------
# One row per ITEM of a frame order. Contract No., Contract Value and the two
# contract validity dates map straight from Table 1 (Purchasing Document,
# Target Val. (Header), Validity Per. Start / Period End) and repeat here the
# same way - so they, too, are read once per contract rather than summed.
FO_KEYS = [
    "serial_no",
    "plant",
    "contract_no",
    "contract_pur_group",
    "header_text",
    "vendor",
    "vendor_name",
    "contract_value",
    "validity_start",
    "validity_end",
    "requisitioner",
    "frame_numbers",
    "fo_validity_start",
    "fo_validity_end",
    "item",
    "frame_pur_group",
    "description",
    "req_tracking_no",
    "released_value",
    "actual_value",
    "opening_value",
]

FO_LABELS = {
    "serial_no": "Serial No.",
    "plant": "Plant",
    "contract_no": "Contract No.",
    "contract_pur_group": "Contr.Pur.Group",
    "header_text": "Header Text",
    "vendor": "Vendor",
    "vendor_name": "Vendor Name",
    "contract_value": "Contract Value",
    "validity_start": "Validity Start",
    "validity_end": "Validity End",
    "requisitioner": "Requisitioner",
    "frame_numbers": "Frame Numbers",
    "fo_validity_start": "FO.Valdt.Start",
    "fo_validity_end": "FO.Valdt.End",
    "item": "Item",
    "frame_pur_group": "Frame Pur.Group",
    "description": "Description",
    "req_tracking_no": "Req.Tracking No.",
    "released_value": "Released Value",
    "actual_value": "Actual Value",
    "opening_value": "Opening Value",
}

FO_KEY_FIELDS = ("frame_numbers", "item")

# Repeated from the contract on every row of every frame order under it.
FO_HEADER_KEYS = [
    "plant", "contract_no", "contract_pur_group", "header_text",
    "vendor", "vendor_name", "contract_value", "validity_start", "validity_end",
]

# Per-item money columns - these DO add up within their frame order. The
# header columns above never do.
FO_ITEM_VALUE_KEYS = ["released_value", "actual_value", "opening_value"]

FO_DERIVED_KEYS = ["fo_items", "fo_released_total"]

FO_DERIVED_LABELS = {
    "fo_items": "Items on FO",
    "fo_released_total": "FO Released Total",
}

FO_DISPLAY_COLUMNS = FO_KEYS + FO_DERIVED_KEYS

FO_WRAPPED_LABELS = {
    "sr_no": "Sr.\nNo.",
    "serial_no": "Serial\nNo.",
    "plant": "Plant",
    "contract_no": "Contract\nNo.",
    "contract_pur_group": "Contr.Pur.\nGroup",
    "header_text": "Header\nText",
    "vendor": "Vendor",
    "vendor_name": "Vendor\nName",
    "contract_value": "Contract\nValue",
    "validity_start": "Validity\nStart",
    "validity_end": "Validity\nEnd",
    "requisitioner": "Requisitioner",
    "frame_numbers": "Frame\nNumbers",
    "fo_validity_start": "FO.Valdt.\nStart",
    "fo_validity_end": "FO.Valdt.\nEnd",
    "item": "Item",
    "frame_pur_group": "Frame Pur.\nGroup",
    "description": "Description",
    "req_tracking_no": "Req.Tracking\nNo.",
    "fo_items": "Items\non FO",
    "fo_released_total": "FO Released\nTotal",
    "released_value": "Released\nValue",
    "actual_value": "Actual\nValue",
    "opening_value": "Opening\nValue",
}

FO_COLUMN_WIDTHS = {
    "sr_no": 64,
    "serial_no": 90,
    "plant": 90,
    "contract_no": 160,
    "contract_pur_group": 130,
    "header_text": 250,
    "vendor": 110,
    "vendor_name": 230,
    "contract_value": 140,
    "validity_start": 120,
    "validity_end": 120,
    "requisitioner": 150,
    "frame_numbers": 160,
    "fo_validity_start": 130,
    "fo_validity_end": 130,
    "item": 70,
    "frame_pur_group": 130,
    "description": 260,
    "req_tracking_no": 140,
    "fo_items": 100,
    "fo_released_total": 150,
    "released_value": 140,
    "actual_value": 130,
    "opening_value": 140,
}

FO_LEGACY_COLUMNS = {
    "fo_no": "frame_numbers",
    "arc_no": "contract_no",
    "fo_description": "description",
    "vendor_code": "vendor",
    "fo_date": "fo_validity_start",
    "validity_end_date": "fo_validity_end",
    "fo_value": "released_value",
    "open_value": "opening_value",
}

# Fields carrying money/quantity, parsed leniently (commas and currency
# symbols are tolerated) so a figure pasted straight out of Excel still adds up.
# Every date column in the two tables. They are normalised to DD.MM.YYYY on
# the way in and rendered that way on the way out, so a validity period reads
# the same everywhere no matter what shape the export wrote it in.
ARC_DATE_FIELDS = ("document_date", "validity_start", "validity_end")
FO_DATE_FIELDS = ("validity_start", "validity_end",
                  "fo_validity_start", "fo_validity_end")

ARC_NUMERIC_FIELDS = {
    "target_value", "contract_value",
    "released_value", "actual_value", "opening_value",
}

# The expiry horizons every ARC/FO analysis is bucketed against. 30 days is
# the one management acts on, so it leads and is the one the KPI cards and
# the risk tables use.
EXPIRY_WINDOWS = [30, 60, 90]
ACTION_WINDOW = EXPIRY_WINDOWS[0]

# The ARC master keeps its own change log, keyed by the purchasing document -
# which is exactly what makes the contract the key every amendment is filed
# against, whether the change was to the contract, a frame order or an item.
ARC_AUDIT_COLUMNS = ["timestamp", "arc_no", "reference", "action", "details", "actor"]

ARC_AUDIT_WRAPPED_LABELS = {
    "timestamp": "Date &\nTime",
    "arc_no": "Purchasing\nDocument",
    "reference": "Item / Frame\nOrder",
    "action": "Action",
    "details": "Details",
    "actor": "Changed\nBy",
}

ARC_AUDIT_COLUMN_WIDTHS = {
    "timestamp": 150,
    "arc_no": 140,
    "reference": 190,
    "action": 130,
    "details": 420,
    "actor": 120,
}

# --------------------------------------------------- per-flow CC addresses --
# Each communication flow keeps its OWN CC row: the people copied on a
# defective-invoice chase are rarely the people copied on a breakdown.
CC_DEFECTIVE_KEY = "cc_email_defective"
CC_BREAKDOWN_KEY = "cc_email_breakdown"

CC_FLOW_LABELS = {
    CC_DEFECTIVE_KEY: "Defective Invoice CC",
    CC_BREAKDOWN_KEY: "Equipment Breakdown CC",
}


# =================================================== ARC value calculation ==
# Three columns in, one priced annexure out. The input names a machine and
# how long its order is being extended; everything else is looked up:
#
#   Technical ID  -> equipment master : ARC No, MCM/shift + OT codes, their
#                                       descriptions and rates, validity end
#   ARC No        -> ARC & FO master  : vendor code, vendor name, plant
#   Vendor Code   -> vendor master    : vendor type
#
ARC_VALUE_INPUT_KEYS = ["technical_id", "extension_date", "working_shift"]

ARC_VALUE_INPUT_LABELS = {
    "technical_id": "Technical ID",
    "extension_date": "Extension Date",
    "working_shift": "Working Shift",
}

ARC_VALUE_INPUT_WRAPPED_LABELS = {
    "sr_no": "Sr.\nNo.",
    "technical_id": "Technical\nID",
    "extension_date": "Extension\nDate",
    "working_shift": "Working\nShift",
}

ARC_VALUE_INPUT_WIDTHS = {
    "sr_no": 64, "technical_id": 220, "extension_date": 190, "working_shift": 160,
}

# A machine runs one of two shift patterns, and the shift decides how much
# overtime a month carries.
WORKING_SHIFT_VALUES = ["12", "24"]

# Overtime hours earned per working day, by shift length, and the working
# days in a month. OT quantity = equipment count x months x days x hours.
OT_HOURS_PER_DAY = {"12": 2, "24": 11}
WORKING_DAYS_PER_MONTH = 26

# The unit each of the two lines is priced in. The MCM line is a monthly
# charge; the OT line is priced by the hour.
MCM_UOM = "MCM"
OT_UOM = "H"

ARC_VALUE_COLUMNS = [
    "sr_no",
    "vendor_code",
    "vendor_name",
    "vendor_type",
    "working_shift",
    "plant",
    "arc_no",
    "service_code",
    "equipment_description",
    "eqp_qty",
    "qty",
    "uom",
    "monthly_rate",
    "value",
    "existing_upto",
    "revised_upto",
]

ARC_VALUE_LABELS = {
    "sr_no": "Sr. No",
    "vendor_code": "Vendor Code",
    "vendor_name": "Vendor Name",
    "vendor_type": "Vendor Type",
    "working_shift": "Working Shift",
    "plant": "Plant",
    "arc_no": "ARC No",
    "service_code": "Service Code",
    "equipment_description": "Equipment Description",
    "eqp_qty": "Eqp Qty",
    "qty": "Qty.",
    "uom": "UOM",
    "monthly_rate": "Monthly Rate(Rs.)",
    "value": "Value (Rs.)",
    "existing_upto": "Existing Order Calculation upto(Date)",
    "revised_upto": "Revised Order Calculation upto (Date)",
}

ARC_VALUE_WRAPPED_LABELS = {
    "sr_no": "Sr.\nNo",
    "vendor_code": "Vendor\nCode",
    "vendor_name": "Vendor\nName",
    "vendor_type": "Vendor\nType",
    "working_shift": "Working\nShift",
    "plant": "Plant",
    "arc_no": "ARC\nNo",
    "service_code": "Service\nCode",
    "equipment_description": "Equipment\nDescription",
    "eqp_qty": "Eqp\nQty",
    "qty": "Qty.",
    "uom": "UOM",
    "monthly_rate": "Monthly Rate\n(Rs.)",
    "value": "Value\n(Rs.)",
    "existing_upto": "Existing Order\nCalculation upto",
    "revised_upto": "Revised Order\nCalculation upto",
}

# Annexure 1: one row per contract, summarising Annexure 2.
ARC_SUMMARY_COLUMNS = [
    "sr_no", "arc_no", "work_order_date", "plant", "vendor_code", "vendor_name",
    "existing_value", "revised_value", "impact", "validity_start", "validity_end",
]

ARC_SUMMARY_LABELS = {
    "sr_no": "Sr no.",
    "arc_no": "ARC No.",
    "work_order_date": "Work Order Date",
    "plant": "Plant",
    "vendor_code": "Vendor Code",
    "vendor_name": "Vendor Name",
    "existing_value": "Existing ARC value (Rs.)",
    "revised_value": "Revised Arc Value (Rs.)",
    "impact": "Impact (Rs.)",
    "validity_start": "ARC Validity Start Date",
    "validity_end": "ARC Validity End Date",
}

ARC_VALUE_COLUMN_WIDTHS = {
    "sr_no": 64,
    "vendor_code": 110,
    "vendor_name": 240,
    "vendor_type": 110,
    "working_shift": 100,
    "plant": 90,
    "arc_no": 140,
    "service_code": 110,
    "equipment_description": 300,
    "eqp_qty": 90,
    "qty": 100,
    "uom": 80,
    "monthly_rate": 140,
    "value": 150,
    "existing_upto": 150,
    "revised_upto": 150,
}
