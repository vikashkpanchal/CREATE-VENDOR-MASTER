"""Application-wide constants: field definitions, storage paths, UI limits."""

import os

APP_TITLE = "Vendor Master Management System"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "vendor_master_store.csv")
AUDIT_FILE = os.path.join(DATA_DIR, "vendor_audit_log.csv")

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
    "plant",
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
    "plant": "Plant",
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
    "plant": "Plant",
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
    "plant": 120,
}

# Equipment lookup keys: pasting any ONE of these retrieves the full record.
EQUIPMENT_LOOKUP_KEYS = ["rh_ro_number", "technical_id", "reg_no"]

# Technical ID is numeric; RH/RO Number is alphanumeric; Reg No is free text.
EQUIPMENT_NUMERIC_FIELDS = {"technical_id"}

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
]

BREAKDOWN_EMAIL_HEADERS = {
    "equipment_description": "Equipment",
    "capacity": "Capacity",
    "uom": "UOM",
    "rh_ro_number": "RH Code",
    "technical_id": "Technical ID",
    "reg_no": "REG NO",
}

# Outlook draft folders (created under the default account's Inbox if absent).
OUTLOOK_DEFECTIVE_FOLDER = "Defective Invoice"
OUTLOOK_BREAKDOWN_FOLDER = "Equipment Breakdown"
