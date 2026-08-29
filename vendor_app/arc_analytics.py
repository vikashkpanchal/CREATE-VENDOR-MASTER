"""ARC & FO analysis: the questions management actually asks of the masters.

Four of them drive everything else here:

    ARC Without FO          a contract exists but nothing has been ordered
    ARC vs FO Gap           target 10 Cr - released 6 Cr leaves 4 Cr to order
    ARC Expiring in 30 Days which contracts need action now
    FO Expiring in 30 Days  which frame orders need extending now

Both inputs are line-item level, so every figure here is computed on the
right entity rather than on the raw rows:

    an ARC   is one PURCHASING DOCUMENT, its header read once
    an FO    is one FRAME NUMBER, its item values added up

Counting rows instead would report a five-item contract as five contracts,
and summing the repeated Target Val. (Header) would report it as worth five
times what it is. Neither is possible here, because nothing counts or sums
a repeated header value.

An unreadable validity date is never guessed at. Those rows are counted
under "No Validity Date" and kept out of every expiry bucket, because
calling such a contract active - or expired - would put the wrong one in
front of a reader.
"""

from collections import OrderedDict
from datetime import date

from vendor_app.arc import days_until, format_amount, parse_amount, split_vendor
from vendor_app.config import (
    ACTION_WINDOW, EXPIRY_WINDOWS, RELEASE_INDICATORS, RELEASE_PENDING,
    RELEASE_RELEASED, describe_release_indicator, describe_release_status,
)
from vendor_app.validators import normalize

ACTIVE = "Active"
EXPIRED = "Expired"
NO_DATE = "No Validity Date"

STATUS_ORDER = [ACTIVE, EXPIRED, NO_DATE]

# ------------------------------------------------------------- report shape --
# One label/width map serves every report table and every exported sheet, so a
# column means the same thing wherever it turns up. The names are the ones the
# source reports use, so a reader recognises them without translating.
LABELS = {
    "document": "Purchasing Document",
    "frame": "Frame Number",
    "contract_no": "Contract No.",
    "vendor_code": "Vendor",
    "vendor_name": "Vendor Name",
    "description": "Short Text / Description",
    "plant": "Plant",
    "purchasing_group": "Purchasing Group",
    "requisitioner": "Requisitioner",
    "req_tracking_no": "Req.Tracking No.",
    "start": "Validity Start",
    "end": "Validity End",
    "target_value": "Target Val. (Header)",
    "released": "Released Value",
    "actual": "Actual Value",
    "opening": "Opening Value",
    "difference": "Difference",
    "frame_count": "Frame Orders",
    "item_count": "Items",
    "arc_count": "ARC Count",
    "days_left": "Days to Expiry",
    "expiry_status": "Expiry Status",
    "release_indicator": "Release indicator",
    "release_status": "Release status",
}

WRAPPED_LABELS = {
    "document": "Purchasing\nDocument",
    "frame": "Frame\nNumber",
    "contract_no": "Contract\nNo.",
    "vendor_code": "Vendor",
    "vendor_name": "Vendor\nName",
    "description": "Short Text /\nDescription",
    "plant": "Plant",
    "purchasing_group": "Purchasing\nGroup",
    "requisitioner": "Requisitioner",
    "req_tracking_no": "Req.Tracking\nNo.",
    "start": "Validity\nStart",
    "end": "Validity\nEnd",
    "target_value": "Target Val.\n(Header)",
    "released": "Released\nValue",
    "actual": "Actual\nValue",
    "opening": "Opening\nValue",
    "difference": "Difference\n(Target - Released)",
    "frame_count": "Frame\nOrders",
    "item_count": "Items",
    "arc_count": "ARC\nCount",
    "days_left": "Days to\nExpiry",
    "expiry_status": "Expiry\nStatus",
    "release_indicator": "Release\nindicator",
    "release_status": "Release\nstatus",
}

# Sized so the widest report still fits a 1480px window: a value column that
# needs scrolling to reach is a value column nobody looks at.
WIDTHS = {
    "document": 160, "frame": 150, "contract_no": 155, "vendor_code": 100,
    "vendor_name": 215, "description": 230, "plant": 90, "purchasing_group": 110,
    "requisitioner": 140, "req_tracking_no": 130,
    "start": 105, "end": 105,
    "target_value": 135, "released": 130, "actual": 125, "opening": 125,
    "difference": 165, "frame_count": 100, "item_count": 80, "arc_count": 85,
    "days_left": 100, "expiry_status": 140,
    "release_indicator": 175, "release_status": 165,
}

AMOUNT_COLUMNS = {"target_value", "released", "actual", "opening", "difference"}


def cell(row, key):
    """One report cell as text: amounts formatted, a missing date left blank."""
    value = row.get(key, "")
    if key in AMOUNT_COLUMNS:
        return format_amount(value or 0.0)
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

    Building it walks both tables once and keeps one row per contract and
    one per frame order; each analysis below is then a filter over those,
    which is what keeps the KPI cards, the charts and the tables agreeing.
    """

    def __init__(self, store, today=None):
        self.store = store
        self.today = today or date.today()
        self.arcs = [self._arc_row(entry) for entry in store.documents().values()]
        self.fos = self._fo_rows()

    # ------------------------------------------------------------- rows --
    def _arc_row(self, entry):
        header = entry["header"]
        document = entry["document"]
        target = parse_amount(header.get("target_value", ""))
        released = self.store.released_against(document)
        left = days_until(header.get("validity_end", ""), self.today)
        code, name = split_vendor(header.get("vendor_supplying_plant", ""))
        # The contract's own text comes off its first item that has one -
        # the header itself carries no description in this export.
        text = next((normalize(r.get("short_text", "")) for r in entry["items"]
                     if normalize(r.get("short_text", ""))), "")
        indicator = normalize(header.get("release_indicator", "")).upper()
        return {
            "document": document,
            "vendor_code": code,
            "vendor_name": name or code,
            "description": text,
            "plant": header.get("plant", ""),
            "purchasing_group": header.get("purchasing_group", ""),
            "start": header.get("validity_start", ""),
            "end": header.get("validity_end", ""),
            "target_value": target,
            "item_count": len(entry["items"]),
            "frame_count": len(self.store.frames_for_document(document)),
            "released": released,
            "difference": target - released,
            "days_left": left,
            "expiry_status": _expiry_status(left),
            "indicator_code": indicator,
            "release_indicator": describe_release_indicator(indicator),
            "release_status": describe_release_status(header.get("release_status", "")),
        }

    def _fo_rows(self):
        grouped = OrderedDict()
        for record in self.store.all_fos():
            grouped.setdefault(normalize(record.get("frame_numbers", "")), []).append(record)

        rows = []
        for frame, items in grouped.items():
            first = items[0]
            left = days_until(first.get("fo_validity_end", ""), self.today)
            rows.append({
                "frame": frame,
                "contract_no": normalize(first.get("contract_no", "")),
                "vendor_code": normalize(first.get("vendor", "")),
                "vendor_name": normalize(first.get("vendor_name", ""))
                               or normalize(first.get("vendor", "")),
                "description": next(
                    (normalize(r.get("description", "")) for r in items
                     if normalize(r.get("description", ""))), ""),
                "plant": normalize(first.get("plant", "")),
                "purchasing_group": normalize(first.get("frame_pur_group", "")),
                "requisitioner": normalize(first.get("requisitioner", "")),
                "req_tracking_no": normalize(first.get("req_tracking_no", "")),
                "start": normalize(first.get("fo_validity_start", "")),
                "end": normalize(first.get("fo_validity_end", "")),
                # Item-level money adds up within the frame order; the
                # contract value repeated on these rows never does.
                "released": sum(parse_amount(r.get("released_value", "")) for r in items),
                "actual": sum(parse_amount(r.get("actual_value", "")) for r in items),
                "opening": sum(parse_amount(r.get("opening_value", "")) for r in items),
                "item_count": len(items),
                "days_left": left,
                "expiry_status": _expiry_status(left),
            })
        return rows

    # ------------------------------------------------ 1-14: counts & values --
    def total_arc_count(self):
        return len(self.arcs)

    def total_arc_value(self):
        return sum(r["target_value"] for r in self.arcs)

    def active_arcs(self):
        return [r for r in self.arcs if r["expiry_status"] == ACTIVE]

    def expired_arcs(self):
        return [r for r in self.arcs if r["expiry_status"] == EXPIRED]

    def total_fo_count(self):
        return len(self.fos)

    def total_fo_value(self):
        return sum(r["released"] for r in self.fos)

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

        The first thing management asks for, because it is value released
        and then forgotten. Biggest contract first.
        """
        return sorted(
            [r for r in self.arcs if r["frame_count"] == 0],
            key=lambda r: r["target_value"], reverse=True,
        )

    # ------------------------------------------ 16: ARC vs FO value gap --
    def value_difference(self):
        """Each contract's target against what has been released on it.

        Ranked by the size of the gap either way: a large positive gap is
        contract value lying unused, a negative one means the frame orders
        have over-run the contract, and both belong at the top.
        """
        rows = [r for r in self.arcs if r["target_value"] or r["released"]]
        return sorted(rows, key=lambda r: abs(r["difference"]), reverse=True)

    # ---------------------------------------------- 17: vendor-wise view --
    def vendor_analysis(self):
        """One row per vendor: contracts, orders, and the gap between them."""
        grouped = OrderedDict()
        for row in self.arcs:
            key = (row["vendor_code"], row["vendor_name"])
            bucket = grouped.setdefault(key, self._empty_vendor(key))
            bucket["arc_count"] += 1
            bucket["target_value"] += row["target_value"]
            bucket["released"] += row["released"]
            bucket["frame_count"] += row["frame_count"]

        # A frame order against a contract that is not in Table 1 still
        # belongs to its vendor; dropping it would understate that vendor.
        known = {r["document"].lower() for r in self.arcs}
        for row in self.fos:
            if row["contract_no"].lower() in known:
                continue
            key = (row["vendor_code"], row["vendor_name"])
            bucket = grouped.setdefault(key, self._empty_vendor(key))
            bucket["frame_count"] += 1
            bucket["released"] += row["released"]

        for bucket in grouped.values():
            bucket["difference"] = bucket["target_value"] - bucket["released"]
        return sorted(grouped.values(), key=lambda r: r["target_value"], reverse=True)

    @staticmethod
    def _empty_vendor(key):
        code, name = key
        return {
            "vendor_code": code, "vendor_name": name or code or "(unnamed vendor)",
            "arc_count": 0, "frame_count": 0,
            "target_value": 0.0, "released": 0.0, "difference": 0.0,
        }

    # ------------------------------------------------------- 18-19: risk --
    def high_risk_arcs(self):
        """Expiring within 30 days with value still unreleased: the contract
        runs out with money on it, so it gets used or it gets renewed."""
        return [r for r in self.arcs_expiring(ACTION_WINDOW)
                if r["released"] < r["target_value"]]

    def high_risk_fos(self):
        """Expiring within 30 days - each needs extending or closing."""
        return self.fos_expiring(ACTION_WINDOW)

    # ------------------------------------------------------- release view --
    def pending_release(self):
        """Release indicator S: approved for nothing yet, so unusable.

        Sorted by the approval level already reached, then by value, so the
        ones furthest along - and worth most - are dealt with first.
        """
        rows = [r for r in self.arcs if r["indicator_code"] == RELEASE_PENDING]
        return sorted(rows, key=lambda r: (-len(r["release_status"]), -r["target_value"]))

    def release_counts(self):
        """Contracts by release indicator, labelled by what the code means.

        The chart carries the meaning rather than the letter: "Pending for
        approval" is the fact a reader acts on, and the code itself is in
        the tables for anyone matching back to SAP.
        """
        counts = OrderedDict()
        for row in self.arcs:
            label = RELEASE_INDICATORS.get(row["indicator_code"], "") or "Not stated"
            counts[label] = counts.get(label, 0) + 1
        return list(counts.items())

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
        """Top vendors by contract value, as (label, target, released)."""
        return [
            (row["vendor_name"], row["target_value"], row["released"])
            for row in self.vendor_analysis()[:limit]
        ]

    # ---------------------------------------------------------- KPI cards --
    def kpis(self):
        """The headline figures, in the order the dashboard shows them."""
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
            ("pending_release", "Pending Approval (S)",
             f"{len(self.pending_release()):,}", "warn"),
        ]

    # ----------------------------------------------------------- reports --
    ARC_COLUMNS = ["document", "vendor_code", "vendor_name", "description", "plant",
                   "purchasing_group", "start", "end", "target_value", "item_count",
                   "frame_count", "released", "difference", "days_left",
                   "expiry_status", "release_indicator", "release_status"]
    FO_COLUMNS = ["frame", "contract_no", "vendor_code", "vendor_name", "description",
                  "plant", "requisitioner", "req_tracking_no", "start", "end",
                  "item_count", "released", "actual", "opening",
                  "days_left", "expiry_status"]

    def reports(self):
        """Every table the dashboard shows, in its layout order.

        The same list drives the on-screen sections and the exported
        workbook, so a sheet can never disagree with the panel above it.
        """
        window = ACTION_WINDOW
        return [
            Report("arc_without_fo", "ARC Without FO",
                   ["document", "vendor_name", "description", "plant", "start", "end",
                    "target_value", "days_left", "expiry_status"],
                   self.arcs_without_fo(),
                   "A contract is in place but no frame order has been raised on it."),
            Report("arc_expiring", f"ARC Expiring in {window} Days",
                   ["document", "vendor_name", "end", "days_left", "target_value",
                    "released", "difference", "plant"],
                   self.arcs_expiring(window),
                   "Soonest first - these are the contracts needing action now."),
            Report("fo_expiring", f"FO Expiring in {window} Days",
                   ["frame", "contract_no", "vendor_name", "end", "days_left",
                    "released", "opening", "plant"],
                   self.fos_expiring(window),
                   "Each of these frame orders needs extending or closing."),
            Report("value_difference", "ARC vs FO Value Difference",
                   ["document", "vendor_name", "target_value", "frame_count",
                    "released", "difference", "end", "expiry_status"],
                   self.value_difference(),
                   "Target Val. (Header) minus what has been released against it - "
                   "the balance still open. The header value is read once per "
                   "contract, never summed across its items."),
            Report("pending_release", "Pending Approval (Release indicator S)",
                   ["document", "vendor_name", "target_value", "release_status",
                    "start", "end", "plant", "purchasing_group"],
                   self.pending_release(),
                   "Not yet released, so nothing can be ordered against them. "
                   "Furthest through the approval chain first."),
            Report("vendor_analysis", "Vendor Analysis",
                   ["vendor_code", "vendor_name", "arc_count", "frame_count",
                    "target_value", "released", "difference"],
                   self.vendor_analysis(),
                   "Contracts and frame orders per vendor, and the gap between them."),
            Report("high_risk_arc", "High Risk ARC",
                   ["document", "vendor_name", "end", "days_left", "target_value",
                    "released", "difference"],
                   self.high_risk_arcs(),
                   f"Expiring within {window} days with less released than the "
                   "contract's target value."),
            Report("high_risk_fo", "High Risk FO",
                   ["frame", "contract_no", "vendor_name", "end", "days_left",
                    "released", "opening"],
                   self.high_risk_fos(),
                   f"Expiring within {window} days."),
        ]

    # KPI id -> the rows that figure is counting. Clicking a card opens
    # exactly these, so a number on the dashboard can always be taken apart
    # into the contracts or frame orders it came from.
    def kpi_report(self, key):
        window = ACTION_WINDOW
        if key == "total_arc":
            return Report("kpi_total_arc", "All Contracts", self.ARC_COLUMNS,
                          sorted(self.arcs, key=lambda r: -r["target_value"]),
                          "Every purchasing document in Table 1 - one row per "
                          "contract, not per item.")
        if key == "active_arc":
            return Report("kpi_active_arc", "Active ARC", self.ARC_COLUMNS,
                          sorted(self.active_arcs(), key=lambda r: r["days_left"]),
                          "Contracts whose validity has not yet passed, soonest "
                          "to expire first.")
        if key == "expired_arc":
            return Report("kpi_expired_arc", "Expired ARC", self.ARC_COLUMNS,
                          sorted(self.expired_arcs(), key=lambda r: r["days_left"]),
                          "Contracts whose Validity Period End is in the past.")
        if key == "total_arc_value":
            return Report("kpi_arc_value", "Total ARC Value", self.ARC_COLUMNS,
                          sorted(self.arcs, key=lambda r: -r["target_value"]),
                          "Target Val. (Header) per contract, read once each - "
                          "these are the figures the total adds up.")
        if key == "total_fo":
            return Report("kpi_total_fo", "All Frame Orders", self.FO_COLUMNS,
                          sorted(self.fos, key=lambda r: -r["released"]),
                          "Every frame number in Table 2 - one row per order, "
                          "not per item.")
        if key == "total_fo_value":
            return Report("kpi_fo_value", "Total FO Value", self.FO_COLUMNS,
                          sorted(self.fos, key=lambda r: -r["released"]),
                          "Released Value summed within each frame order - these "
                          "are the figures the total adds up.")
        if key == "arc_without_fo":
            return self.report("arc_without_fo")
        if key == "arc_expiring":
            return self.report("arc_expiring")
        if key == "fo_expiring":
            return self.report("fo_expiring")
        if key == "pending_release":
            return self.report("pending_release")
        raise KeyError(key)

    def report(self, key):
        for report in self.reports():
            if report.key == key:
                return report
        raise KeyError(key)

    def full_reports(self):
        """The reports plus both masters rolled to their entity, for export."""
        return [
            Report("arc_master", "ARC Contracts", self.ARC_COLUMNS, self.arcs),
            Report("fo_master", "Frame Orders", self.FO_COLUMNS, self.fos),
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
            ("Pending Approval (Release indicator S)", f"{len(self.pending_release()):,}"),
            ("Released (Release indicator R)",
             f"{sum(1 for r in self.arcs if r['indicator_code'] == RELEASE_RELEASED):,}"),
        ]
        return rows
