"""Application-wide constants: field definitions, storage paths, UI limits."""

import os

APP_TITLE = "Vendor Master Management System"

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
