"""ARC value calculation: three input columns priced into a contract annexure.

You give it, per machine: **Technical ID**, the **Extension Date** the order
is being revised up to, and the **Working Shift** (12 or 24). Everything
else is looked up:

    Technical ID -> equipment master  ARC No, MCM/shift code + description +
                                      rate, OT code + description + rate,
                                      and the validity end date
    ARC No       -> ARC & FO master   vendor code, vendor name, plant
    Vendor Code  -> vendor master     vendor type

Two dates drive the whole calculation:

    Existing Order Calculation upto = the equipment's validity end date
    Revised Order Calculation upto  = the extension date you gave

and the months between them are the MCM quantity.

**Machines are counted, not listed.** Within one ARC, every machine sharing
the same MCM code, description, rates, OT code, shift and pair of dates is
one line, with the count in Eqp Qty. Anything that differs - a different
rate, a 24-hour deployment beside a 12-hour one, a different extension date
- is its own line, because those cannot share a quantity or a value.

Each such line prints as one row, or two when the machine carries overtime:

    MCM row   Service Code = Service Code- MCM/Shift, Description = Service
              Code Description, UOM = MCM, Rate = MCM Rate, Qty = months,
              Value = Eqp Qty x months x rate
    OT row    Service Code = Service Code-OT, Description = OT Service
              Description, UOM = H,
              Rate = OT rate, Qty = Eqp Qty x months x 26 x hours-per-day
              (2 on a 12-hour shift, 11 on a 24-hour one),
              Value = Qty x rate

The Eqp Qty sits on the MCM row only: it is already inside the OT quantity,
so repeating it there would double the overtime value.
"""

from collections import OrderedDict
from datetime import date

from vendor_app.arc import document_key, format_date, parse_amount, parse_date, split_vendor
from vendor_app.config import (
    MCM_UOM, OT_HOURS_PER_DAY, OT_UOM, WORKING_DAYS_PER_MONTH, WORKING_SHIFT_VALUES,
)
from vendor_app.validators import normalize

# Row kinds, so the grid and the workbook can style a total differently from
# a priced line without re-deriving what a row is.
LINE_MCM = "mcm"
LINE_OT = "ot"
LINE_ARC_TOTAL = "arc_total"
LINE_GRAND_TOTAL = "grand_total"


def month_span(existing, revised) -> int:
    """Whole months between two dates - the MCM quantity.

    Counted on the calendar, not on days: 28.02.2026 to 31.12.2026 is ten
    months, and so is 01.02.2026 to 01.12.2026. That is how the annexure
    prices an extension - by the months it spans - and it is why the day of
    the month is deliberately ignored.

    Zero when the revised date is not after the existing one; the caller
    reports that row rather than pricing a negative extension.
    """
    start, end = parse_date(existing), parse_date(revised)
    if start is None or end is None:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return max(0, months)


def normalise_shift(value) -> str:
    """'12', '24', '12 hours', '24 Hrs' -> '12' / '24'; anything else ''."""
    text = normalize(value).upper().replace("HOURS", "").replace("HRS", "")
    text = text.replace("HR", "").replace("H", "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text if text in WORKING_SHIFT_VALUES else ""


class Problem:
    """One thing wrong with one input row, named so it can be acted on."""

    def __init__(self, technical_id, message):
        self.technical_id = normalize(technical_id)
        self.message = message

    def __str__(self):
        return f"{self.technical_id or '(blank Technical ID)'}: {self.message}"


class ArcValueCalculator:
    """Turns input rows into the priced annexure, and says what it could not do."""

    def __init__(self, equipment_store, arc_store, vendor_store):
        self.equipment = equipment_store
        self.arcs = arc_store
        self.vendors = vendor_store

    # ------------------------------------------------------------ lookups --
    def _arc_header(self, arc_no):
        """The contract's header from the ARC & FO master, or {} if absent."""
        if not normalize(arc_no):
            return {}
        return self.arcs.header_for(arc_no) if self.arcs is not None else {}

    def _vendor_of(self, header, machine):
        """(code, name), from the contract when it is on file, else the machine.

        The ARC & FO master is asked first because the order is being raised
        against that contract - if the two masters disagree about the vendor,
        the contract is the one being priced.
        """
        code, name = split_vendor(header.get("vendor_supplying_plant", ""))
        if not code:
            code = normalize(machine.get("vendor_code", ""))
        if not name:
            name = normalize(machine.get("vendor_name", ""))
        return code, name

    def _vendor_type(self, code):
        if not code or self.vendors is None:
            return ""
        record = self.vendors.get(normalize(code))
        return normalize(record.get("vendor_type", "")) if record else ""

    def _arc_sort_key(self, arc_no):
        """Oldest contract first: by the contract's own start, then its number.

        A contract that is not in the ARC & FO master has no start date, so
        it sorts after the ones that do rather than being guessed at.
        """
        header = self._arc_header(arc_no)
        start = parse_date(header.get("validity_start", "")) \
            or parse_date(header.get("document_date", ""))
        return (start is None, start or date.max, document_key(arc_no))

    # -------------------------------------------------------- calculation --
    def calculate(self, input_rows):
        """Return (lines, problems). `input_rows` are dicts with technical_id,
        extension_date and working_shift."""
        problems = []
        groups = OrderedDict()

        for raw in input_rows:
            technical_id = normalize(raw.get("technical_id", ""))
            if not technical_id:
                continue

            machine = self.equipment.lookup(technical_id) if self.equipment else None
            if machine is None:
                problems.append(Problem(technical_id, "not found in the equipment master"))
                continue

            shift = normalise_shift(raw.get("working_shift", ""))
            if not shift:
                problems.append(Problem(
                    technical_id,
                    "Working Shift must be "
                    + " or ".join(WORKING_SHIFT_VALUES)
                    + f" - got '{normalize(raw.get('working_shift', ''))}'",
                ))
                continue

            existing = normalize(machine.get("validity_end_date", ""))
            revised = normalize(raw.get("extension_date", ""))
            if not existing:
                problems.append(Problem(technical_id,
                                        "has no Validity End Date on the equipment master"))
                continue
            if parse_date(revised) is None:
                problems.append(Problem(technical_id,
                                        f"Extension Date '{revised}' is not a date"))
                continue

            months = month_span(existing, revised)
            if months <= 0:
                problems.append(Problem(
                    technical_id,
                    f"Extension Date {format_date(revised)} is not after the validity "
                    f"end {format_date(existing)} - nothing to price",
                ))
                continue

            arc_no = normalize(machine.get("arc_no", ""))
            if not arc_no:
                problems.append(Problem(technical_id,
                                        "has no ARC No on the equipment master"))
                continue
            header = self._arc_header(arc_no)
            if not header:
                problems.append(Problem(
                    technical_id,
                    f"ARC {arc_no} is not in the ARC & FO master - vendor and plant "
                    "taken from the equipment record",
                ))

            code, name = self._vendor_of(header, machine)
            plant = normalize(header.get("plant", "")) \
                or normalize(machine.get("plant_code", ""))

            # One line per category: same contract, same codes, same rates,
            # same shift and the same pair of dates. Anything else is a
            # different line, because it cannot share a quantity or a value.
            key = (
                document_key(arc_no), shift,
                normalize(machine.get("mcm_shift_code", "")),
                normalize(machine.get("disc_mcm_shift", "")),
                normalize(machine.get("mcm_shift_rate", "")),
                normalize(machine.get("ot_code", "")),
                normalize(machine.get("dic_ot", "")),
                normalize(machine.get("ot_rate", "")),
                format_date(existing), format_date(revised),
            )
            group = groups.get(key)
            if group is None:
                group = groups[key] = {
                    "arc_no": arc_no,
                    "vendor_code": code,
                    "vendor_name": name,
                    "vendor_type": self._vendor_type(code),
                    "plant": plant,
                    "working_shift": shift,
                    "mcm_code": normalize(machine.get("mcm_shift_code", "")),
                    "mcm_desc": normalize(machine.get("disc_mcm_shift", "")),
                    "mcm_rate": parse_amount(machine.get("mcm_shift_rate", "")),
                    "ot_code": normalize(machine.get("ot_code", "")),
                    "ot_desc": normalize(machine.get("dic_ot", "")),
                    "ot_rate": parse_amount(machine.get("ot_rate", "")),
                    "existing": format_date(existing),
                    "revised": format_date(revised),
                    "months": months,
                    "count": 0,
                    "machines": [],
                }
            group["count"] += 1
            group["machines"].append(technical_id)

        return self._lines(groups), problems

    def _arc_summary(self, serial, categories, impact):
        """One Annexure 1 row: the contract as it stands, and this amendment.

        The revised validity end is the LATEST of the contract's own end date
        and every revised date priced against it here - extending one machine
        to a date beyond the contract necessarily extends the contract.
        """
        arc_no = categories[0]["arc_no"]
        header = self._arc_header(arc_no)
        existing_value = parse_amount(header.get("target_value", ""))

        candidates = [parse_date(header.get("validity_end", ""))]
        candidates += [parse_date(group["revised"]) for group in categories]
        latest = max([d for d in candidates if d is not None], default=None)

        return {
            "sr_no": serial,
            "arc_no": arc_no,
            "work_order_date": format_date(header.get("document_date", "")),
            "plant": categories[0]["plant"],
            "vendor_code": categories[0]["vendor_code"],
            "vendor_name": categories[0]["vendor_name"],
            "existing_value": existing_value,
            "impact": impact,
            "revised_value": existing_value + impact,
            "validity_start": format_date(header.get("validity_start", "")),
            "validity_end": latest.strftime("%d.%m.%Y") if latest else "",
        }

    def _lines(self, groups):
        """Group the categories under their contracts and price each one."""
        by_arc = OrderedDict()
        for group in groups.values():
            by_arc.setdefault(document_key(group["arc_no"]), []).append(group)

        ordered = sorted(
            by_arc.items(),
            key=lambda item: self._arc_sort_key(item[1][0]["arc_no"]),
        )

        lines = []
        serial = 0
        grand_eqp = grand_value = 0.0
        for _key, categories in ordered:
            serial += 1
            # Within a contract the categories stay in the order the input
            # named them. Only the contracts themselves are sorted (oldest
            # first); imposing a second sort inside one would move rows the
            # person who built the input list expects to find where they put
            # them.
            arc_eqp = arc_value = 0.0
            first_of_arc = True
            for group in categories:
                mcm_value = group["count"] * group["months"] * group["mcm_rate"]
                lines.append({
                    "kind": LINE_MCM,
                    "sr_no": str(serial) if first_of_arc else "",
                    "vendor_code": group["vendor_code"],
                    "vendor_name": group["vendor_name"],
                    "vendor_type": group["vendor_type"],
                    "working_shift": group["working_shift"],
                    "plant": group["plant"],
                    "arc_no": group["arc_no"],
                    "service_code": group["mcm_code"],
                    "equipment_description": group["mcm_desc"],
                    "eqp_qty": group["count"],
                    "qty": group["months"],
                    "uom": MCM_UOM,
                    "monthly_rate": group["mcm_rate"],
                    "value": mcm_value,
                    "existing_upto": group["existing"],
                    "revised_upto": group["revised"],
                    "machines": list(group["machines"]),
                })
                first_of_arc = False
                arc_eqp += group["count"]
                arc_value += mcm_value

                if not group["ot_code"]:
                    continue
                # The equipment count is already inside this quantity, which
                # is why Eqp Qty stays blank on an OT row.
                hours = OT_HOURS_PER_DAY[group["working_shift"]]
                ot_qty = (group["count"] * group["months"]
                          * WORKING_DAYS_PER_MONTH * hours)
                ot_value = ot_qty * group["ot_rate"]
                lines.append({
                    "kind": LINE_OT,
                    "sr_no": "",
                    "vendor_code": group["vendor_code"],
                    "vendor_name": group["vendor_name"],
                    "vendor_type": group["vendor_type"],
                    "working_shift": group["working_shift"],
                    "plant": group["plant"],
                    "arc_no": group["arc_no"],
                    "service_code": group["ot_code"],
                    "equipment_description": group["ot_desc"],
                    "eqp_qty": "",
                    "qty": ot_qty,
                    "uom": OT_UOM,
                    "monthly_rate": group["ot_rate"],
                    "value": ot_value,
                    "existing_upto": group["existing"],
                    "revised_upto": group["revised"],
                    "machines": [],
                })
                arc_value += ot_value

            lines.append({
                "kind": LINE_ARC_TOTAL,
                "sr_no": "", "vendor_code": "", "vendor_name": "", "vendor_type": "",
                "working_shift": "", "plant": "",
                "arc_no": f"{categories[0]['arc_no']} Total",
                "service_code": "", "equipment_description": "",
                "eqp_qty": arc_eqp, "qty": "", "uom": "", "monthly_rate": "",
                "value": arc_value, "existing_upto": "", "revised_upto": "",
                "machines": [],
                # What Annexure 1 needs about this contract, computed here so
                # the summary is a roll-up of these very rows rather than a
                # second, independently derived answer.
                "summary": self._arc_summary(serial, categories, arc_value),
            })
            grand_eqp += arc_eqp
            grand_value += arc_value

        if lines:
            lines.append({
                "kind": LINE_GRAND_TOTAL,
                "sr_no": "", "vendor_code": "", "vendor_name": "", "vendor_type": "",
                "working_shift": "", "plant": "", "arc_no": "", "service_code": "",
                "equipment_description": "", "eqp_qty": grand_eqp, "qty": "",
                "uom": "", "monthly_rate": "", "value": grand_value,
                "existing_upto": "", "revised_upto": "", "machines": [],
            })
        return lines


def format_number(value) -> str:
    """A quantity or a rupee figure for the grid: grouped, no trailing .0."""
    if value == "" or value is None:
        return ""
    if isinstance(value, str):
        return value
    if abs(value - round(value)) < 0.005:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"
