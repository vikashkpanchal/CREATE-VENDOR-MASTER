"""ARC & FO analysis: the questions management actually asks of the masters.

Four of them drive everything else here:

    ARC Without FO          a contract exists but nothing has been ordered
    ARC vs FO Gap           ARC 10 Cr - FO 6 Cr leaves 4 Cr still to order
    ARC Expiring in 30 Days which contracts need action now
    FO Expiring in 30 Days  which orders need extending now

Everything is computed from the stored masters on demand - nothing here is
saved back - so a figure on the dashboard can never be stale with respect to
the ARC and FO records it came from.

An unreadable validity date is never guessed at. Those rows are counted under
"No Validity Date" and kept out of every expiry bucket, because calling such
a contract active (or expired) would put the wrong one in front of a reader.
"""

from collections import OrderedDict
from datetime import date

from vendor_app.arc import days_until, format_amount, parse_amount
from vendor_app.config import ACTION_WINDOW, EXPIRY_WINDOWS

ACTIVE = "Active"
EXPIRED = "Expired"
NO_DATE = "No Validity Date"

STATUS_ORDER = [ACTIVE, EXPIRED, NO_DATE]

# ------------------------------------------------------------- report shape --
# One label/width map serves every report table and every exported sheet, so a
# column means the same thing wherever it turns up.
LABELS = {
    "arc_no": "ARC No",
    "fo_no": "FO No",
    "vendor_code": "Vendor Code",
    "vendor_name": "Vendor Name",
    "description": "Description",
    "plant": "Plant",
    "purchasing_group": "Purchasing Group",
    "release_status": "Release Status",
    "start": "Validity Start",
    "end": "Validity End",
    "arc_value": "ARC Value",
    "fo_value": "FO Value",
    "difference": "Difference",
    "released_value": "Released Value",
    "open_value": "Open Value",
    "arc_count": "ARC Count",
    "fo_count": "FO Count",
    "days_left": "Days to Expiry",
    "expiry_status": "Expiry Status",
    "status": "Status",
}

WRAPPED_LABELS = {
    "arc_no": "ARC\nNo",
    "fo_no": "FO\nNo",
    "vendor_code": "Vendor\nCode",
    "vendor_name": "Vendor\nName",
    "description": "Description",
    "plant": "Plant",
    "purchasing_group": "Purchasing\nGroup",
    "release_status": "Release\nStatus",
    "start": "Validity\nStart",
    "end": "Validity\nEnd",
    "arc_value": "ARC\nValue",
    "fo_value": "FO\nValue",
    "difference": "Difference\n(ARC - FO)",
    "released_value": "Released\nValue",
    "open_value": "Open\nValue",
    "arc_count": "ARC\nCount",
    "fo_count": "FO\nCount",
    "days_left": "Days to\nExpiry",
    "expiry_status": "Expiry\nStatus",
    "status": "Status",
}

# Sized so the widest report still fits a 1480px window without horizontal
# scrolling - the tables are read for their figures, and a value column that
# needs scrolling to reach is a value column nobody looks at.
WIDTHS = {
    "arc_no": 135, "fo_no": 135, "vendor_code": 100, "vendor_name": 215,
    "description": 220, "plant": 95, "purchasing_group": 115,
    "release_status": 110, "start": 105, "end": 105,
    "arc_value": 125, "fo_value": 125, "difference": 135,
    "released_value": 125, "open_value": 115,
    "arc_count": 85, "fo_count": 85, "days_left": 100,
    "expiry_status": 140, "status": 110,
}

# Columns rendered as money, and as a right-aligned figure in the grid.
AMOUNT_COLUMNS = {"arc_value", "fo_value", "difference", "released_value", "open_value"}


def cell(row, key):
    """One report cell as text: amounts formatted, a missing date left blank."""
    value = row.get(key, "")
    if key in AMOUNT_COLUMNS:
        return format_amount(value or 0.0)
    if key == "days_left":
        return "" if value is None else str(value)
    return "" if value is None else str(value)


class Report:
    """A named table: its columns, its rows, and how to render one."""

    def __init__(self, key, title, columns, rows, note=""):
        self.key = key
        self.title = title
        self.columns = list(columns)
        self.rows = list(rows)
        self.note = note

    def __len__(self):
        return len(self.rows)

    def values(self, row):
        return [cell(row, key) for key in self.columns]

    def headers(self, wrapped=True):
        source = WRAPPED_LABELS if wrapped else LABELS
        return {key: source.get(key, key) for key in self.columns}


def _expiry_status(days_left):
    if days_left is None:
        return NO_DATE
    return EXPIRED if days_left < 0 else ACTIVE


def _bucket(days_left):
    """Which expiry band a row falls in, for the trend charts."""
    if days_left is None:
        return NO_DATE
    if days_left < 0:
        return "Expired"
    for index, window in enumerate(EXPIRY_WINDOWS):
        if days_left <= window:
            previous = EXPIRY_WINDOWS[index - 1] + 1 if index else 0
            return f"{previous}-{window} days"
    return f"Beyond {EXPIRY_WINDOWS[-1]} days"


BUCKET_ORDER = (
    ["Expired"]
    + [f"{(EXPIRY_WINDOWS[i - 1] + 1) if i else 0}-{w} days"
       for i, w in enumerate(EXPIRY_WINDOWS)]
    + [f"Beyond {EXPIRY_WINDOWS[-1]} days", NO_DATE]
)


class ArcAnalysis:
    """Every ARC/FO analysis, computed once against a single `today`.

    Building it walks the masters once and keeps the two enriched row sets;
    each analysis below is then a filter over those, which is what keeps the
    KPI cards, the charts and the tables agreeing with one another.
    """

    def __init__(self, store, today=None):
        self.store = store
        self.today = today or date.today()
        self.arcs = [self._arc_row(a) for a in store.all_arcs()]
        self.fos = [self._fo_row(f) for f in store.all_fos()]

    # ------------------------------------------------------------- rows --
    def _arc_row(self, record):
        arc_no = record.get("arc_no", "")
        target = parse_amount(record.get("arc_value", ""))
        fo_value = self.store.fo_value_for_arc(arc_no)
        left = days_until(record.get("arc_end_date", ""), self.today)
        return {
            "arc_no": arc_no,
            "vendor_code": record.get("vendor_code", ""),
            "vendor_name": record.get("vendor_name", ""),
            "description": record.get("arc_description", ""),
            "plant": record.get("plant", ""),
            "purchasing_group": record.get("purchasing_group", ""),
            "release_status": record.get("release_status", ""),
            "start": record.get("arc_start_date", ""),
            "end": record.get("arc_end_date", ""),
            "arc_value": target,
            "fo_count": len(self.store.fos_for_arc(arc_no)),
            "fo_value": fo_value,
            "difference": target - fo_value,
            "days_left": left,
            "expiry_status": _expiry_status(left),
            "status": record.get("status", ""),
        }

    def _fo_row(self, record):
        fo_no = record.get("fo_no", "")
        left = days_until(record.get("validity_end_date", ""), self.today)
        return {
            "fo_no": fo_no,
            "arc_no": record.get("arc_no", ""),
            "vendor_code": record.get("vendor_code", ""),
            "vendor_name": record.get("vendor_name", ""),
            "description": record.get("fo_description", ""),
            "plant": record.get("plant", ""),
            "purchasing_group": record.get("purchasing_group", ""),
            "start": record.get("fo_date", ""),
            "end": record.get("validity_end_date", ""),
            # The effective value: line items when the FO has them, its own
            # figure when it has none. Same rule the grids and the tree use.
            "fo_value": self.store.fo_total(fo_no),
            "released_value": parse_amount(record.get("released_value", "")),
            "open_value": parse_amount(record.get("open_value", "")),
            "days_left": left,
            "expiry_status": _expiry_status(left),
            "status": record.get("status", ""),
        }

    # ------------------------------------------------ 1-14: counts & values --
    def total_arc_count(self):
        return len(self.arcs)

    def total_arc_value(self):
        return sum(r["arc_value"] for r in self.arcs)

    def active_arcs(self):
        return [r for r in self.arcs if r["expiry_status"] == ACTIVE]

    def expired_arcs(self):
        return [r for r in self.arcs if r["expiry_status"] == EXPIRED]

    def total_fo_count(self):
        return len(self.fos)

    def total_fo_value(self):
        return sum(r["fo_value"] for r in self.fos)

    def active_fos(self):
        return [r for r in self.fos if r["expiry_status"] == ACTIVE]

    def expired_fos(self):
        return [r for r in self.fos if r["expiry_status"] == EXPIRED]

    @staticmethod
    def _expiring(rows, days):
        """Rows expiring within `days` - still live, so already-expired rows
        are excluded; they are their own, more urgent, category."""
        return sorted(
            [r for r in rows if r["days_left"] is not None and 0 <= r["days_left"] <= days],
            key=lambda r: r["days_left"],
        )

    def arcs_expiring(self, days=ACTION_WINDOW):
        return self._expiring(self.arcs, days)

    def fos_expiring(self, days=ACTION_WINDOW):
        return self._expiring(self.fos, days)

    # --------------------------------------------------- 15: ARC without FO --
    def arcs_without_fo(self):
        """A contract is in place but nothing has been ordered against it.

        The first thing management asks for, because it is money released and
        then forgotten. Sorted by value: the biggest idle contract first.
        """
        return sorted(
            [r for r in self.arcs if r["fo_count"] == 0],
            key=lambda r: r["arc_value"], reverse=True,
        )

    # ------------------------------------------ 16: ARC vs FO value gap --
    def value_difference(self):
        """Every ARC's released value against what has been ordered on it.

        Ranked by the size of the gap either way: a large positive gap is
        budget lying unused, a negative one means the FOs have over-run the
        contract, and both need to be at the top of the list.
        """
        rows = [r for r in self.arcs if r["arc_value"] or r["fo_value"]]
        return sorted(rows, key=lambda r: abs(r["difference"]), reverse=True)

    # ---------------------------------------------- 17: vendor-wise view --
    def vendor_analysis(self):
        """One row per vendor: contracts, orders, and the gap between them."""
        grouped = OrderedDict()
        for row in self.arcs:
            key = (row["vendor_code"], row["vendor_name"])
            bucket = grouped.setdefault(key, self._empty_vendor(key))
            bucket["arc_count"] += 1
            bucket["arc_value"] += row["arc_value"]
            bucket["fo_value"] += row["fo_value"]
            bucket["fo_count"] += row["fo_count"]

        # FOs whose ARC No matches no contract still belong to their vendor -
        # dropping them would understate that vendor's ordered value.
        known = {r["arc_no"].lower() for r in self.arcs}
        for row in self.fos:
            if row["arc_no"].lower() in known:
                continue
            key = (row["vendor_code"], row["vendor_name"])
            bucket = grouped.setdefault(key, self._empty_vendor(key))
            bucket["fo_count"] += 1
            bucket["fo_value"] += row["fo_value"]

        for bucket in grouped.values():
            bucket["difference"] = bucket["arc_value"] - bucket["fo_value"]
        return sorted(grouped.values(), key=lambda r: r["arc_value"], reverse=True)

    @staticmethod
    def _empty_vendor(key):
        code, name = key
        return {
            "vendor_code": code, "vendor_name": name or code or "(unnamed vendor)",
            "arc_count": 0, "fo_count": 0,
            "arc_value": 0.0, "fo_value": 0.0, "difference": 0.0,
        }

    # ------------------------------------------------------- 18-19: risk --
    def high_risk_arcs(self):
        """Expiring within 30 days AND under-ordered: the contract runs out
        with value still on it, so either it gets used or it gets renewed."""
        return [r for r in self.arcs_expiring(ACTION_WINDOW)
                if r["fo_value"] < r["arc_value"]]

    def high_risk_fos(self):
        """Expiring within 30 days - each one needs extending or closing."""
        return self.fos_expiring(ACTION_WINDOW)

    # ------------------------------------------------------------ charts --
    def status_counts(self, rows):
        counts = OrderedDict((s, 0) for s in STATUS_ORDER)
        for row in rows:
            counts[row["expiry_status"]] += 1
        return [(name, count) for name, count in counts.items() if count]

    def expiry_trend(self, rows):
        counts = OrderedDict((b, 0) for b in BUCKET_ORDER)
        for row in rows:
            counts[_bucket(row["days_left"])] += 1
        return [(name, count) for name, count in counts.items() if count]

    def vendor_value_series(self, limit=8):
        """Top vendors by ARC value, as (label, ARC value, FO value) triples."""
        return [
            (row["vendor_name"], row["arc_value"], row["fo_value"])
            for row in self.vendor_analysis()[:limit]
        ]

    # ---------------------------------------------------------- KPI cards --
    def kpis(self):
        """The nine headline figures, in the order the dashboard shows them."""
        return [
            ("total_arc", "Total ARC", f"{self.total_arc_count():,}", "neutral"),
            ("active_arc", "Active ARC", f"{len(self.active_arcs()):,}", "good"),
            ("expired_arc", "Expired ARC", f"{len(self.expired_arcs()):,}", "bad"),
            ("arc_without_fo", "ARC Without FO", f"{len(self.arcs_without_fo()):,}", "warn"),
            ("total_arc_value", "Total ARC Value", format_amount(self.total_arc_value()),
             "neutral"),
            ("total_fo", "Total FO", f"{self.total_fo_count():,}", "neutral"),
            ("total_fo_value", "Total FO Value", format_amount(self.total_fo_value()),
             "neutral"),
            ("arc_expiring", f"ARC Expiring in {ACTION_WINDOW} Days",
             f"{len(self.arcs_expiring()):,}", "warn"),
            ("fo_expiring", f"FO Expiring in {ACTION_WINDOW} Days",
             f"{len(self.fos_expiring()):,}", "warn"),
        ]

    # ----------------------------------------------------------- reports --
    ARC_COLUMNS = ["arc_no", "vendor_code", "vendor_name", "description", "plant",
                   "start", "end", "arc_value", "fo_count", "fo_value", "difference",
                   "days_left", "expiry_status"]
    FO_COLUMNS = ["fo_no", "arc_no", "vendor_code", "vendor_name", "plant",
                  "start", "end", "fo_value", "released_value", "open_value",
                  "days_left", "expiry_status"]

    def reports(self):
        """Every table the dashboard shows, in its layout order.

        The same list drives the on-screen sections and the exported
        workbook, so a sheet can never disagree with the panel above it.
        """
        window = ACTION_WINDOW
        return [
            Report("arc_without_fo", "ARC Without FO",
                   ["arc_no", "vendor_name", "description", "plant", "start", "end",
                    "arc_value", "days_left", "expiry_status"],
                   self.arcs_without_fo(),
                   "A contract is in place but no FO has been raised against it."),
            Report("arc_expiring", f"ARC Expiring in {window} Days",
                   ["arc_no", "vendor_name", "end", "days_left", "arc_value",
                    "fo_value", "difference", "plant"],
                   self.arcs_expiring(window),
                   "Soonest first - these are the contracts needing action now."),
            Report("fo_expiring", f"FO Expiring in {window} Days",
                   ["fo_no", "arc_no", "vendor_name", "end", "days_left",
                    "fo_value", "open_value", "plant"],
                   self.fos_expiring(window),
                   "Each of these orders needs extending or closing."),
            Report("value_difference", "ARC vs FO Value Difference",
                   ["arc_no", "vendor_name", "arc_value", "fo_count", "fo_value",
                    "difference", "end", "expiry_status"],
                   self.value_difference(),
                   "ARC Value minus the sum of its FOs - the balance still open."),
            Report("vendor_analysis", "Vendor Analysis",
                   ["vendor_code", "vendor_name", "arc_count", "fo_count",
                    "arc_value", "fo_value", "difference"],
                   self.vendor_analysis(),
                   "Contracts and orders per vendor, and the gap between them."),
            Report("high_risk_arc", "High Risk ARC",
                   ["arc_no", "vendor_name", "end", "days_left", "arc_value",
                    "fo_value", "difference"],
                   self.high_risk_arcs(),
                   f"Expiring within {window} days with FO value below the ARC value."),
            Report("high_risk_fo", "High Risk FO",
                   ["fo_no", "arc_no", "vendor_name", "end", "days_left",
                    "fo_value", "open_value"],
                   self.high_risk_fos(),
                   f"Expiring within {window} days."),
        ]

    def report(self, key):
        for report in self.reports():
            if report.key == key:
                return report
        raise KeyError(key)

    def full_reports(self):
        """The reports plus the two full masters, for the Excel export."""
        return [
            Report("arc_master", "ARC Master", self.ARC_COLUMNS, self.arcs),
            Report("fo_master", "FO Master", self.FO_COLUMNS, self.fos),
        ] + self.reports()

    def summary_rows(self):
        """The 19 analyses as a flat name/value sheet for the export."""
        windows = EXPIRY_WINDOWS
        rows = [
            ("Total ARC Count", f"{self.total_arc_count():,}"),
            ("Total ARC Value", format_amount(self.total_arc_value())),
            ("Active ARC", f"{len(self.active_arcs()):,}"),
            ("Expired ARC", f"{len(self.expired_arcs()):,}"),
        ]
        rows += [(f"ARC Expiring in Next {d} Days", f"{len(self.arcs_expiring(d)):,}")
                 for d in windows]
        rows += [
            ("Total FO Count", f"{self.total_fo_count():,}"),
            ("Total FO Value", format_amount(self.total_fo_value())),
            ("Active FO", f"{len(self.active_fos()):,}"),
            ("Expired FO", f"{len(self.expired_fos()):,}"),
        ]
        rows += [(f"FO Expiring in Next {d} Days", f"{len(self.fos_expiring(d)):,}")
                 for d in windows]
        rows += [
            ("ARC Without FO", f"{len(self.arcs_without_fo()):,}"),
            ("ARC vs FO Value Difference",
             format_amount(self.total_arc_value() - self.total_fo_value())),
            ("Vendors Covered", f"{len(self.vendor_analysis()):,}"),
            ("High Risk ARC", f"{len(self.high_risk_arcs()):,}"),
            ("High Risk FO", f"{len(self.high_risk_fos()):,}"),
        ]
        return rows
