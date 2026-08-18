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
    "status",
    "vendor_name",
    "vendor_email",
    "vendor_owner_name",
    "vendor_owner_contact",
    "vendor_owner_email",
    "vendor_supervisor_name",
    "vendor_supervisor_contact",
    "vendor_supervisor_email",
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
    "vendor_owner_name": "Vendor Owner\nName",
    "vendor_owner_contact": "Vendor Owner\nContact Number",
    "vendor_owner_email": "Vendor Owner\nEmail ID",
    "vendor_supervisor_name": "Vendor Supervisor\nContact Name",
    "vendor_supervisor_contact": "Vendor Supervisor\nContact Number",
    "vendor_supervisor_email": "Vendor Supervisor\nEmail ID",
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
