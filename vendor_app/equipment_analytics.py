"""The lists behind the equipment dashboard's figures.

Every KPI tile is a count of something, and the next question is always
"which ones?". These builders hand back the exact rows a figure was
computed from, in the same shape the ARC dashboard's reports use, so the
same detail pop-up and the same Excel writer serve both.

Nothing here recomputes a figure: each report is built from the very list
the tile counted, so the pop-up can never disagree with the card.
"""

from datetime import date

from vendor_app.arc import parse_date
from vendor_app.config import (
    EQUIPMENT_COLUMN_WIDTHS, EQUIPMENT_KEYS, EQUIPMENT_LABELS,
    EQUIPMENT_WRAPPED_LABELS,
)

# The equipment grid, plus the summary columns the grouped reports use.
ROW_COLUMNS = ["sr_no"] + list(EQUIPMENT_KEYS)
GROUP_WIDTHS = {"sr_no": 64, "name": 320, "count": 120}

EXPIRING_DAYS = 30


class EquipmentReport:
    """A named table of equipment rows or grouped counts.

    Deliberately the same surface as arc_analytics.Report - title, columns,
    headers(), values(row) - so KpiDetailDialog and export_report_to_excel
    take it without knowing which dashboard it came from.
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
    dict(EQUIPMENT_WRAPPED_LABELS), dict(EQUIPMENT_LABELS, sr_no="Sr. No."),
)


def rows_report(key, title, records, note=""):
    """The machines themselves, numbered, in the order the dashboard has them."""
    rows = []
    for index, record in enumerate(records, start=1):
        row = {k: record.get(k, "") for k in EQUIPMENT_KEYS}
        row["sr_no"] = index
        rows.append(row)
    return EquipmentReport(
        key, title, ROW_COLUMNS, rows, _ROW_HEADERS,
        dict(EQUIPMENT_COLUMN_WIDTHS, sr_no=64), note,
    )


def group_report(key, title, records, field, value_label, note=""):
    """One row per distinct value, with how many machines carry it.

    This is what a "how many suppliers" figure actually counts, so it is
    what opening that figure shows - and the count column makes the list
    answer the follow-up question too.
    """
    counts = {}
    for record in records:
        value = str(record.get(field, "")).strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
    rows = [
        {"sr_no": index, "name": name, "count": count}
        for index, (name, count) in enumerate(ordered, start=1)
    ]
    headers = (
        {"sr_no": "Sr.\nNo.", "name": value_label, "count": "Equipment\nCount"},
        {"sr_no": "Sr. No.", "name": value_label, "count": "Equipment Count"},
    )
    return EquipmentReport(key, title, ["sr_no", "name", "count"], rows, headers,
                           GROUP_WIDTHS, note)


# ----------------------------------------------------------- the figures --
def without_fo(records) -> list:
    """Machines carrying no FO number.

    Without an FO there is no frame order to bill against and no contract to
    read the ARC No and Plant Code from, so these are the rows that keep the
    rest of the master from linking up.
    """
    return [r for r in records if not str(r.get("fo_no", "")).strip()]


def expired(records, today=None) -> list:
    today = today or date.today()
    out = []
    for record in records:
        end = parse_date(record.get("validity_end_date", ""))
        if end is not None and (end - today).days < 0:
            out.append(record)
    return out


def expiring(records, days=EXPIRING_DAYS, today=None) -> list:
    today = today or date.today()
    out = []
    for record in records:
        end = parse_date(record.get("validity_end_date", ""))
        if end is None:
            continue
        left = (end - today).days
        if 0 <= left <= days:
            out.append(record)
    return out


def report_for(key, records, fleet_label="Equipment") -> EquipmentReport:
    """The report behind one KPI tile, by the tile's key."""
    if key == "equipment":
        return rows_report(key, fleet_label, records,
                           "Every machine that matches the current filters.")
    if key == "vendors":
        return group_report(key, "Suppliers", records, "vendor_name", "Supplier",
                            "Each supplier with the number of machines it has on hire.")
    if key == "categories":
        return group_report(key, "Equipment Types", records, "equipment_description",
                            "Equipment Type",
                            "Each equipment type with how many are deployed.")
    if key == "plants":
        return group_report(key, "Plants", records, "plant", "Plant",
                            "Each plant with the number of machines on site.")
    if key == "expired":
        return rows_report(key, "Expired Equipment", expired(records),
                           "Validity end date is already in the past.")
    if key == "expiring":
        return rows_report(key, f"Expiring in {EXPIRING_DAYS} Days", expiring(records),
                           f"Validity ends within the next {EXPIRING_DAYS} days.")
    if key == "no_fo":
        return rows_report(key, "Equipment Without FO", without_fo(records),
                           "No FO number on the machine, so no ARC No or Plant "
                           "Code can be derived for it.")
    raise KeyError(key)
