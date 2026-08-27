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
}

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
}

# Equipment lookup keys: pasting any ONE of these retrieves the full record.
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
ARC_LINE_ITEM_FILE = os.path.join(DATA_DIR, "arc_line_items.csv")
ARC_AUDIT_FILE = os.path.join(DATA_DIR, "arc_audit_log.csv")

# --- ARC (the master) ------------------------------------------------------
# The stored column set follows the ME3L export the ARC data is pulled out of,
# in that report's own order, so a downloaded sheet imports without being
# reshaped first. The four fields after Release Status are the app's own
# (amendment tracking, lifecycle and notes) and are simply left blank by an
# untouched ME3L file.
ARC_KEYS = [
    "arc_no",
    "vendor_code",
    "vendor_name",
    "arc_description",
    "arc_start_date",       # ME3L: Validity Start
    "arc_end_date",         # ME3L: Validity End
    "arc_value",            # ME3L: ARC Value / Target Value
    "plant",
    "purchasing_group",
    "release_status",
    "amendment_no",
    "amendment_date",
    "status",
    "remarks",
]

ARC_LABELS = {
    "arc_no": "ARC No",
    "vendor_code": "Vendor Code",
    "vendor_name": "Vendor Name",
    "arc_description": "ARC Description",
    "arc_start_date": "Validity Start",
    "arc_end_date": "Validity End",
    "arc_value": "ARC Value (Target)",
    "plant": "Plant",
    "purchasing_group": "Purchasing Group",
    "release_status": "Release Status",
    "amendment_no": "Amendment No",
    "amendment_date": "Amendment Date",
    "status": "Status",
    "remarks": "Remarks",
}

# Columns the ARC grid derives rather than stores. The target value is what
# SAP released; the FO sum is what has actually been ordered against it, and
# the difference between the two is the balance still open on the contract -
# the figure this module exists to keep honest.
ARC_DERIVED_KEYS = ["fo_count", "fo_value_total", "value_difference"]

ARC_DERIVED_LABELS = {
    "fo_count": "FO Count",
    "fo_value_total": "FO Value (Sum)",
    "value_difference": "Difference (ARC - FO)",
}

ARC_DISPLAY_COLUMNS = ARC_KEYS[:7] + ARC_DERIVED_KEYS + ARC_KEYS[7:]

ARC_WRAPPED_LABELS = {
    "sr_no": "Sr.\nNo.",
    "arc_no": "ARC\nNo",
    "vendor_code": "Vendor\nCode",
    "vendor_name": "Vendor\nName",
    "arc_description": "ARC\nDescription",
    "arc_start_date": "Validity\nStart",
    "arc_end_date": "Validity\nEnd",
    "arc_value": "ARC Value\n(Target)",
    "fo_count": "FO\nCount",
    "fo_value_total": "FO Value\n(Sum)",
    "value_difference": "Difference\n(ARC - FO)",
    "plant": "Plant",
    "purchasing_group": "Purchasing\nGroup",
    "release_status": "Release\nStatus",
    "amendment_no": "Amendment\nNo",
    "amendment_date": "Amendment\nDate",
    "status": "Status",
    "remarks": "Remarks",
}

ARC_COLUMN_WIDTHS = {
    "sr_no": 64,
    "arc_no": 150,
    "vendor_code": 110,
    "vendor_name": 230,
    "arc_description": 260,
    "arc_start_date": 120,
    "arc_end_date": 120,
    "arc_value": 140,
    "fo_count": 90,
    "fo_value_total": 140,
    "value_difference": 150,
    "plant": 120,
    "purchasing_group": 130,
    "release_status": 120,
    "amendment_no": 120,
    "amendment_date": 130,
    "status": 110,
    "remarks": 240,
}

ARC_STATUS_VALUES = ["Active", "Amended", "Expired", "Closed"]
ARC_STATUS_DEFAULT = "Active"

# --- FO (the sub-part) -----------------------------------------------------
# Mirrors the SAP FO report's columns. FO No leads because it is this table's
# key and the grid's first column; ARC No follows immediately, since an FO
# only means anything as a sub-part of its contract.
FO_KEYS = [
    "fo_no",
    "arc_no",
    "vendor_code",
    "vendor_name",
    "fo_description",
    "fo_date",              # SAP: FO Start Date
    "validity_end_date",    # SAP: FO End Date
    "fo_value",
    "released_value",
    "open_value",
    "plant",
    "purchasing_group",
    "status",
    "remarks",
]

FO_LABELS = {
    "fo_no": "FO No",
    "arc_no": "ARC No",
    "vendor_code": "Vendor Code",
    "vendor_name": "Vendor Name",
    "fo_description": "FO Description",
    "fo_date": "FO Start Date",
    "validity_end_date": "FO End Date",
    "fo_value": "FO Value",
    "released_value": "Released Value",
    "open_value": "Open Value",
    "plant": "Plant",
    "purchasing_group": "Purchasing Group",
    "status": "Status",
    "remarks": "Remarks",
}

# An FO's effective value comes from its line items when it has any, so the
# grid shows both the entered figure and the rolled-up one.
FO_DERIVED_KEYS = ["line_count", "fo_total"]

FO_DERIVED_LABELS = {
    "line_count": "Line Items",
    "fo_total": "FO Total (Effective)",
}

FO_DISPLAY_COLUMNS = FO_KEYS[:10] + FO_DERIVED_KEYS + FO_KEYS[10:]

FO_WRAPPED_LABELS = {
    "sr_no": "Sr.\nNo.",
    "fo_no": "FO\nNo",
    "arc_no": "ARC\nNo",
    "vendor_code": "Vendor\nCode",
    "vendor_name": "Vendor\nName",
    "fo_description": "FO\nDescription",
    "fo_date": "FO Start\nDate",
    "validity_end_date": "FO End\nDate",
    "fo_value": "FO Value\n(Entered)",
    "released_value": "Released\nValue",
    "open_value": "Open\nValue",
    "line_count": "Line\nItems",
    "fo_total": "FO Total\n(Effective)",
    "plant": "Plant",
    "purchasing_group": "Purchasing\nGroup",
    "status": "Status",
    "remarks": "Remarks",
}

FO_COLUMN_WIDTHS = {
    "sr_no": 64,
    "fo_no": 150,
    "arc_no": 150,
    "vendor_code": 110,
    "vendor_name": 230,
    "fo_description": 240,
    "fo_date": 120,
    "validity_end_date": 120,
    "fo_value": 130,
    "released_value": 130,
    "open_value": 130,
    "line_count": 90,
    "fo_total": 150,
    "plant": 120,
    "purchasing_group": 130,
    "status": 110,
    "remarks": 240,
}

FO_STATUS_VALUES = ["Open", "Partially Executed", "Executed", "Closed"]
FO_STATUS_DEFAULT = "Open"

# --- Line items (the references) ------------------------------------------
ARC_LINE_KEYS = [
    "arc_no",
    "fo_no",
    "line_no",
    "item_code",
    "item_description",
    "uom",
    "quantity",
    "rate",
    "line_value",
    "reference",
    "remarks",
]

ARC_LINE_LABELS = {
    "arc_no": "ARC No",
    "fo_no": "FO No",
    "line_no": "Line No",
    "item_code": "Item Code",
    "item_description": "Item Description",
    "uom": "UOM",
    "quantity": "Quantity",
    "rate": "Rate",
    "line_value": "Line Value",
    "reference": "Reference",
    "remarks": "Remarks",
}

ARC_LINE_WRAPPED_LABELS = {
    "sr_no": "Sr.\nNo.",
    "arc_no": "ARC\nNo",
    "fo_no": "FO\nNo",
    "line_no": "Line\nNo",
    "item_code": "Item\nCode",
    "item_description": "Item\nDescription",
    "uom": "UOM",
    "quantity": "Quantity",
    "rate": "Rate",
    "line_value": "Line\nValue",
    "reference": "Reference",
    "remarks": "Remarks",
}

ARC_LINE_COLUMN_WIDTHS = {
    "sr_no": 64,
    "arc_no": 150,
    "fo_no": 150,
    "line_no": 80,
    "item_code": 130,
    "item_description": 300,
    "uom": 90,
    "quantity": 110,
    "rate": 120,
    "line_value": 130,
    "reference": 180,
    "remarks": 240,
}

# Fields carrying money/quantity, parsed leniently (commas and currency
# symbols are tolerated) so a figure pasted straight out of Excel still adds up.
ARC_NUMERIC_FIELDS = {
    "quantity", "rate", "line_value",
    "arc_value", "fo_value", "released_value", "open_value",
}

# The expiry horizons every ARC/FO analysis is bucketed against. 30 days is
# the one management acts on, so it leads and is the one the KPI cards and
# the risk tables use.
EXPIRY_WINDOWS = [30, 60, 90]
ACTION_WINDOW = EXPIRY_WINDOWS[0]

# The ARC master keeps its own change log, keyed by ARC No - which is exactly
# what makes the ARC the master key for every amendment beneath it.
ARC_AUDIT_COLUMNS = ["timestamp", "arc_no", "reference", "action", "details", "actor"]

ARC_AUDIT_WRAPPED_LABELS = {
    "timestamp": "Date &\nTime",
    "arc_no": "ARC\nNo",
    "reference": "FO / Line\nReference",
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
