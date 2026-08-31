"""One workbook in, one workbook out: every master in a single file.

The export writes four sheets - Vendor Master, Equipment Master, ARC Master,
FO Master - each with exactly the columns that master already exports, in the
same order. The import reads that file back and routes each sheet to its own
store through the same bulk upsert the individual imports use, so every rule
that applies to a normal import applies here: cell-level merge, validation
per row, and a change-log entry for what actually changed.

Sheets are matched by name, and a missing one is skipped rather than
treated as an error - a file carrying only the vendor sheet still loads.
"""

from vendor_app.config import (
    ARC_KEYS, ARC_LABELS, FO_KEYS, FO_LABELS,
)
from vendor_app.export import MASTER_SHEETS, export_all_masters_to_excel
from vendor_app.importer import (
    _read_table, arc_rows_from_frame, equipment_rows_from_frame, sheet_names,
    vendor_rows_from_frame,
)

# The order matters: vendors first so an equipment or ARC row that names one
# finds it already there, and contracts before the orders placed against them.
IMPORT_ORDER = ["vendors", "equipment", "arcs", "fos"]

LABELS = {
    "vendors": "Vendor Master",
    "equipment": "Equipment Master",
    "arcs": "ARC Master",
    "fos": "FO Master",
}


def export_all(vendor_store, equipment_store, arc_store, path: str) -> dict:
    """Write every master to `path`. Returns the row count per sheet."""
    return export_all_masters_to_excel(
        vendor_store.all_records(),
        equipment_store.all_records(),
        [arc_store.arc_row(r) for r in arc_store.all_arcs()],
        [arc_store.fo_row(r) for r in arc_store.all_fos()],
        path,
    )


def _rows_for(kind, frame):
    if kind == "vendors":
        return vendor_rows_from_frame(frame)
    if kind == "equipment":
        return equipment_rows_from_frame(frame)
    if kind == "arcs":
        return arc_rows_from_frame(frame, ARC_KEYS, ARC_LABELS)
    return arc_rows_from_frame(frame, FO_KEYS, FO_LABELS)


def import_all(path, vendor_store, equipment_store, arc_store, progress=None) -> dict:
    """Load every master sheet the file carries.

    Returns {kind: result} where each result is the usual
    {"added", "updated", "errors"}, plus "skipped" listing the masters whose
    sheet was not in the file at all.
    """
    present = set(sheet_names(path))
    results, skipped = {}, []
    def load_equipment(rows, report):
        """Running rows first, then the closed ones as their own records.

        A machine that left site and later came back has both a closed row
        and a running one under the same identifier. Feeding them all through
        the ordinary upsert would let the closed row merge into the running
        one and close the machine that is actually on site, so the two kinds
        go in separately.
        """
        from vendor_app.equipment import is_demobbed
        running = [r for r in rows if not is_demobbed(r)]
        closed = [r for r in rows if is_demobbed(r)]
        result = equipment_store.bulk_upsert(running, progress=report)
        if closed:
            closed_result = equipment_store.bulk_upsert_demobbed(
                closed, progress=report, allow_running_twin=True
            )
            result = {
                "added": result["added"] + closed_result["added"],
                "updated": result["updated"] + closed_result["updated"],
                "errors": result["errors"] + closed_result["errors"],
            }
        return result

    handlers = {
        "vendors": lambda rows, report: vendor_store.bulk_upsert(rows, progress=report),
        "equipment": load_equipment,
        "arcs": lambda rows, report: arc_store.bulk_upsert_arcs(rows, progress=report),
        "fos": lambda rows, report: arc_store.bulk_upsert_fos(rows, progress=report),
    }

    for step, kind in enumerate(IMPORT_ORDER, start=1):
        sheet = MASTER_SHEETS[kind]
        if present and sheet not in present:
            skipped.append(LABELS[kind])
            continue
        if progress is not None:
            progress(step, len(IMPORT_ORDER), f"Reading {sheet}...")
        try:
            frame = _read_table(path, sheet_name=sheet)
        except Exception:
            # A csv, or a workbook without that sheet: nothing to load rather
            # than a failure that abandons the masters after it.
            skipped.append(LABELS[kind])
            continue
        rows = [r for r in _rows_for(kind, frame) if any(str(v).strip() for v in r.values())]
        if not rows:
            results[kind] = {"added": 0, "updated": 0, "errors": []}
            continue
        results[kind] = handlers[kind](rows, None)

    results["skipped"] = skipped
    return results


def summarise(results: dict) -> str:
    """The one-line-per-master summary shown when an import finishes."""
    lines = []
    for kind in IMPORT_ORDER:
        result = results.get(kind)
        if result is None:
            continue
        line = (f"{LABELS[kind]}: added {result['added']:,}, "
                f"updated {result['updated']:,}")
        if result["errors"]:
            line += f", skipped {len(result['errors']):,}"
        lines.append(line)
    if results.get("skipped"):
        lines.append("Not in the file: " + ", ".join(results["skipped"]))
    return "\n".join(lines) or "Nothing to import."
