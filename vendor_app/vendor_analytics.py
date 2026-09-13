"""The vendor master read sideways: its figures, its status rule, and who
can supply what.

Three things live here, and all three are derived from the two masters
rather than stored anywhere:

  * the dashboard's figures, each with the exact rows behind it;
  * the status rule - a vendor is Active while a machine of theirs is on
    site, and Inactive once none is (see status_review);
  * the supply capability matrix - which vendor has supplied which kind of
    equipment, read out of the equipment master's own history.

Nothing here writes. status_review only reports what is out of step; the
vendor store applies it when the user asks for it.
"""

from vendor_app.config import (
    COLUMN_WIDTHS, DISPLAY_COLUMNS, LABELS, STATUS_DEFAULT, VENDOR_TYPE_VALUES,
    WRAPPED_LABELS,
)
from vendor_app.validators import normalize, split_emails

# The vendor grid, as the Records screen shows it.
ROW_COLUMNS = ["sr_no"] + list(DISPLAY_COLUMNS)
ROW_WIDTHS = dict(COLUMN_WIDTHS, sr_no=64)

STATUS_ACTIVE = STATUS_DEFAULT          # "Active"
STATUS_INACTIVE = "Inactive"
STATUS_BLOCKED = "Blocked"


class VendorReport:
    """A named table of vendor rows or grouped counts.

    Same surface as arc_analytics.Report and equipment_analytics.
    EquipmentReport - title, columns, headers(), values(row) - so the one
    detail pop-up and the one Excel writer serve every dashboard.
    """

    def __init__(self, key, title, columns, rows, headers, widths, note=""):
        self.key = key
        self.title = title
        self.columns = list(columns)
        self.rows = list(rows)
        self.widths = widths
        self.note = note
        self._headers = headers

    def __len__(self):
        return len(self.rows)

    def values(self, row):
        return [("" if row.get(key) is None else str(row.get(key, "")))
                for key in self.columns]

    def headers(self, wrapped=True):
        wrapped_source, plain_source = self._headers
        source = wrapped_source if wrapped else plain_source
        return {key: source.get(key, key) for key in self.columns}


_ROW_HEADERS = (
    dict(WRAPPED_LABELS, sr_no="Sr.\nNo."),
    dict(LABELS, sr_no="Sr. No.", status="Status"),
)


def vendor_rows_report(key, title, records, note=""):
    """The vendors themselves, numbered, in the master's own order."""
    rows = []
    for index, record in enumerate(records, start=1):
        row = {k: record.get(k, "") for k in DISPLAY_COLUMNS}
        row["sr_no"] = index
        rows.append(row)
    return VendorReport(key, title, ROW_COLUMNS, rows, _ROW_HEADERS, ROW_WIDTHS, note)


# ---------------------------------------------------------------- figures --
def code_of(record) -> str:
    return normalize((record or {}).get("vendor_code", ""))


def has_email(record) -> bool:
    """Any address at all, on any of the three email columns.

    A vendor is only reachable if somebody's address is on file; which of
    the three columns carries it does not matter to whether an email can be
    sent, so all three count.
    """
    return bool(
        split_emails(record.get("vendor_email", ""))
        or normalize(record.get("vendor_owner_email", ""))
        or normalize(record.get("vendor_supervisor_email", ""))
    )


def status_of(record) -> str:
    return normalize((record or {}).get("status", "")) or STATUS_ACTIVE


def running_codes(equipment_store) -> set:
    """Vendor codes with at least one machine still on site."""
    if equipment_store is None:
        return set()
    return {
        code_of(record) for record in equipment_store.running_records()
        if code_of(record)
    }


def supplying_codes(equipment_store) -> set:
    """Vendor codes named anywhere in the equipment master, past or present."""
    if equipment_store is None:
        return set()
    return {
        code_of(record) for record in equipment_store.all_records()
        if code_of(record)
    }


def status_review(vendor_store, equipment_store) -> dict:
    """Which vendors disagree with the equipment master, and how.

    The rule: a vendor is Active while at least one machine of theirs is
    running, and Inactive once none is. A machine that has been de-mobbed
    no longer keeps its supplier open - the vendor has nothing on site.

    Blocked is left alone. It is a decision somebody made about the vendor,
    not a reading of the fleet, and re-deriving it from equipment would
    quietly re-open a supplier who was stopped on purpose.

    Returns {"to_inactive": [...], "to_active": [...], "blocked": [...]},
    each a list of vendor records. Nothing is written here.
    """
    running = running_codes(equipment_store)
    to_inactive, to_active, blocked = [], [], []
    for record in vendor_store.all_records():
        status, code = status_of(record), code_of(record)
        if status == STATUS_BLOCKED:
            blocked.append(record)
            continue
        if code in running:
            if status != STATUS_ACTIVE:
                to_active.append(record)
        elif status == STATUS_ACTIVE:
            to_inactive.append(record)
    return {"to_inactive": to_inactive, "to_active": to_active, "blocked": blocked}


def figures(vendor_store, equipment_store) -> dict:
    """Every dashboard figure, with the rows behind each one.

    Returns {key: (count, [records])} so a tile and its drill-down can never
    be computed from two different lists.
    """
    records = vendor_store.all_records()
    running = running_codes(equipment_store)
    supplying = supplying_codes(equipment_store)
    review = status_review(vendor_store, equipment_store)

    by_status = {}
    for record in records:
        by_status.setdefault(status_of(record), []).append(record)

    def by_type(wanted):
        return [r for r in records
                if normalize(r.get("vendor_type", "")).upper() == wanted]

    groups = {
        "total": records,
        "active": by_status.get(STATUS_ACTIVE, []),
        "inactive": by_status.get(STATUS_INACTIVE, []),
        "blocked": by_status.get(STATUS_BLOCKED, []),
        "cad": by_type("CAD"),
        "market": by_type("MARKET"),
        "no_type": [r for r in records
                    if normalize(r.get("vendor_type", "")).upper()
                    not in {v.upper() for v in VENDOR_TYPE_VALUES}],
        "no_email": [r for r in records if not has_email(r)],
        "with_equipment": [r for r in records if code_of(r) in running],
        "no_equipment": [r for r in records if code_of(r) not in running],
        "never_supplied": [r for r in records if code_of(r) not in supplying],
        "status_mismatch": review["to_inactive"] + review["to_active"],
    }
    return {key: (len(rows), rows) for key, rows in groups.items()}


# The tiles, in the order the dashboard shows them: what the figure is
# called, and the sentence that explains the list behind it.
FIGURE_TITLES = {
    "total": ("Total Vendors", "Every vendor on the master."),
    "active": ("Active Vendors", "Status Active."),
    "inactive": ("Inactive Vendors", "Status Inactive."),
    "blocked": ("Blocked Vendors", "Status Blocked - stopped on purpose, and "
                                   "never re-opened by the status sync."),
    "cad": ("CAD Vendors", "Vendor Type CAD."),
    "market": ("MARKET Vendors", "Vendor Type MARKET."),
    "no_type": ("Vendor Type Missing", "Neither CAD nor MARKET on the record."),
    "no_email": ("No Email ID", "No address on any of the three email columns, "
                                "so nothing can be sent to them."),
    "with_equipment": ("Vendors With Equipment", "At least one machine of theirs "
                                                 "is running on site."),
    "no_equipment": ("Vendors Without Equipment", "No machine of theirs is running "
                                                  "on site right now."),
    "never_supplied": ("Never Supplied", "Not named on a single equipment record, "
                                         "running or de-mobbed."),
    "status_mismatch": ("Status Out Of Step", "Their status disagrees with the "
                                              "equipment master - press Sync "
                                              "Vendor Status to bring them in line."),
}

FIGURE_ORDER = [
    "total", "active", "inactive", "cad", "market",
    "no_email", "no_equipment", "status_mismatch",
]


def figure_report(key, figures_map) -> VendorReport:
    """The vendors behind one tile, ready for the pop-up and for export."""
    title, note = FIGURE_TITLES.get(key, (key, ""))
    _count, rows = figures_map.get(key, (0, []))
    return vendor_rows_report(key, title, rows, note)


# ------------------------------------------------------- supply capability --
CAPABILITY_COLUMNS = ["sr_no", "vendor_code", "vendor_name", "vendor_type",
                      "status", "type_count", "running", "total", "profile",
                      "equipment_types"]

CAPABILITY_HEADERS = (
    {"sr_no": "Sr.\nNo.", "vendor_code": "Vendor\nCode", "vendor_name": "Vendor\nName",
     "vendor_type": "Vendor\nType", "status": "Status", "type_count": "Equipment\nTypes",
     "running": "Running\nNow", "total": "Supplied\n(All Time)",
     "profile": "Supplier\nProfile", "equipment_types": "Equipment They Can Supply"},
    {"sr_no": "Sr. No.", "vendor_code": "Vendor Code", "vendor_name": "Vendor Name",
     "vendor_type": "Vendor Type", "status": "Status", "type_count": "Equipment Types",
     "running": "Running Now", "total": "Supplied (All Time)",
     "profile": "Supplier Profile", "equipment_types": "Equipment They Can Supply"},
)

CAPABILITY_WIDTHS = {
    "sr_no": 64, "vendor_code": 110, "vendor_name": 230, "vendor_type": 110,
    "status": 100, "type_count": 110, "running": 100, "total": 130,
    "profile": 140, "equipment_types": 460,
}

TYPE_COLUMNS = ["sr_no", "equipment_type", "vendor_count", "running", "total", "vendors"]

TYPE_HEADERS = (
    {"sr_no": "Sr.\nNo.", "equipment_type": "Equipment\nType", "vendor_count": "Vendors\nAble To Supply",
     "running": "Running\nNow", "total": "Supplied\n(All Time)", "vendors": "Vendors"},
    {"sr_no": "Sr. No.", "equipment_type": "Equipment Type", "vendor_count": "Vendors Able To Supply",
     "running": "Running Now", "total": "Supplied (All Time)", "vendors": "Vendors"},
)

TYPE_WIDTHS = {
    "sr_no": 64, "equipment_type": 260, "vendor_count": 150,
    "running": 100, "total": 130, "vendors": 520,
}

SPECIALIST = "Specialist"
MULTI = "Multi-equipment"


def _equipment_type(record) -> str:
    return normalize(record.get("equipment_description", ""))


def capability_index(equipment_store) -> dict:
    """{vendor code: {"name", "types": {type: {"total", "running"}}}}.

    Read from the WHOLE equipment master, de-mobbed records included: a
    vendor who supplied three tippers that have since left site can still
    supply tippers, and that is the question this answers. What is on site
    today is carried alongside as its own count rather than replacing it.
    """
    index = {}
    if equipment_store is None:
        return index
    from vendor_app.equipment import is_demobbed

    for record in equipment_store.all_records():
        code = code_of(record)
        kind = _equipment_type(record)
        if not code or not kind:
            continue
        entry = index.setdefault(code, {"name": "", "types": {}})
        if not entry["name"]:
            entry["name"] = normalize(record.get("vendor_name", ""))
        counts = entry["types"].setdefault(kind, {"total": 0, "running": 0})
        counts["total"] += 1
        if not is_demobbed(record):
            counts["running"] += 1
    return index


def capability_rows(vendor_store, equipment_store) -> list:
    """One row per vendor that has ever supplied something, richest first.

    A vendor who supplies one kind of machine is a Specialist; one who
    supplies several is Multi-equipment. That split is the whole point of
    the view: it is the difference between "who else could send a tipper"
    and "who can cover a mixed requirement on one order".
    """
    index = capability_index(equipment_store)
    rows = []
    for code, entry in index.items():
        vendor = vendor_store.get(code) if vendor_store is not None else None
        kinds = entry["types"]
        running = sum(c["running"] for c in kinds.values())
        total = sum(c["total"] for c in kinds.values())
        listed = sorted(kinds.items(), key=lambda kv: (-kv[1]["total"], kv[0].lower()))
        rows.append({
            "vendor_code": code,
            "vendor_name": (vendor or {}).get("vendor_name", "") or entry["name"],
            "vendor_type": (vendor or {}).get("vendor_type", ""),
            "status": status_of(vendor) if vendor else "Not on vendor master",
            "type_count": len(kinds),
            "running": running,
            "total": total,
            "profile": SPECIALIST if len(kinds) == 1 else MULTI,
            "equipment_types": ", ".join(
                f"{kind} ({counts['total']})" for kind, counts in listed
            ),
            "_types": {kind for kind in kinds},
        })
    rows.sort(key=lambda r: (-r["type_count"], -r["total"], r["vendor_name"].lower()))
    for index_no, row in enumerate(rows, start=1):
        row["sr_no"] = index_no
    return rows


def capability_report(rows, title="Vendor Supply Capability", note="") -> VendorReport:
    return VendorReport(
        "capability", title, CAPABILITY_COLUMNS, rows,
        CAPABILITY_HEADERS, CAPABILITY_WIDTHS,
        note or "Which vendor has supplied which kind of equipment, read from "
                "the equipment master including de-mobbed machines.",
    )


def type_rows(vendor_store, equipment_store) -> list:
    """One row per equipment type: who can supply it, and how many they have.

    The reverse of the capability view, and the one that answers the
    question actually asked on site - "we need another 14T hydra, who has
    one?" - including whether anybody does.
    """
    index = capability_index(equipment_store)
    kinds = {}
    for code, entry in index.items():
        vendor = vendor_store.get(code) if vendor_store is not None else None
        name = (vendor or {}).get("vendor_name", "") or entry["name"] or code
        for kind, counts in entry["types"].items():
            bucket = kinds.setdefault(kind, {"vendors": {}, "running": 0, "total": 0})
            bucket["vendors"][code] = name
            bucket["running"] += counts["running"]
            bucket["total"] += counts["total"]

    rows = []
    for kind, bucket in kinds.items():
        names = sorted(bucket["vendors"].values(), key=str.lower)
        rows.append({
            "equipment_type": kind,
            "vendor_count": len(names),
            "running": bucket["running"],
            "total": bucket["total"],
            "vendors": ", ".join(names),
            "_codes": set(bucket["vendors"]),
        })
    rows.sort(key=lambda r: (-r["vendor_count"], -r["total"], r["equipment_type"].lower()))
    for index_no, row in enumerate(rows, start=1):
        row["sr_no"] = index_no
    return rows


def type_report(rows, title="Equipment Supply Coverage", note="") -> VendorReport:
    return VendorReport(
        "coverage", title, TYPE_COLUMNS, rows, TYPE_HEADERS, TYPE_WIDTHS,
        note or "Each kind of equipment and every vendor who has supplied it.",
    )


def capability_summary(rows) -> dict:
    """Headline counts for the capability screen."""
    specialists = [r for r in rows if r["profile"] == SPECIALIST]
    return {
        "suppliers": len(rows),
        "specialists": len(specialists),
        "multi": len(rows) - len(specialists),
        "widest": max((r["type_count"] for r in rows), default=0),
    }
