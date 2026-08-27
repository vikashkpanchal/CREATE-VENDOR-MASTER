"""The three ARC & FO record screens, built on RecordsScreen.

Each level of the hierarchy gets the same treatment the other masters have -
search, unlimited import, Excel-like paste, in-place editing, export and a
change log - so there is nothing new to learn moving between them.

The derived columns (FO count, ARC value, line count, FO total) are shown
read-only, because they are computed from the level below and typing into
them would only create a figure that disagrees with its own detail.
"""

import customtkinter as ctk

from vendor_app.config import (
    ARC_COLUMN_WIDTHS, ARC_DERIVED_KEYS, ARC_DISPLAY_COLUMNS, ARC_KEYS, ARC_LABELS,
    ARC_LINE_COLUMN_WIDTHS, ARC_LINE_KEYS, ARC_LINE_LABELS, ARC_LINE_WRAPPED_LABELS,
    ARC_WRAPPED_LABELS, FO_COLUMN_WIDTHS, FO_DERIVED_KEYS, FO_DISPLAY_COLUMNS, FO_KEYS,
    FO_LABELS, FO_WRAPPED_LABELS,
)
from vendor_app.export import (
    export_arc_lines_to_excel, export_arcs_to_excel, export_fos_to_excel,
)
from vendor_app.importer import _normalize_header, _read_table
from vendor_app.validators import ValidationError
from vendor_app.gui.records_screen import RecordsScreen


# The headers a raw ME3L / SAP FO download actually carries, mapped onto our
# fields. Without these an untouched export has to be renamed column by column
# before it will import, which is exactly the manual step this module removes.
HEADER_ALIASES = {
    # ARC / outline agreement
    "agreement no": "arc_no",
    "agreement": "arc_no",
    "outline agreement": "arc_no",
    "contract no": "arc_no",
    "purchasing document": "arc_no",
    "short text": "arc_description",
    "description": "arc_description",
    "target value": "arc_value",
    "arc value": "arc_value",
    "arc value (target value)": "arc_value",
    "net value": "arc_value",
    "validity start": "arc_start_date",
    "validity start date": "arc_start_date",
    "valid from": "arc_start_date",
    "validity end": "arc_end_date",
    "validity end date": "arc_end_date",
    "valid to": "arc_end_date",
    "purchasing group": "purchasing_group",
    "purchasing grp": "purchasing_group",
    "pur group": "purchasing_group",
    "release status": "release_status",
    "release indicator": "release_status",
    "vendor": "vendor_name",
    "supplier": "vendor_name",
    "supplier name": "vendor_name",
    "vendor no": "vendor_code",
    "supplier code": "vendor_code",
    "plant code": "plant",
    # FO / frame order
    "fo": "fo_no",
    "frame order": "fo_no",
    "frame order no": "fo_no",
    "fo start date": "fo_date",
    "fo start": "fo_date",
    "fo end date": "validity_end_date",
    "fo end": "validity_end_date",
    "fo validity end": "validity_end_date",
    "released value": "released_value",
    "open value": "open_value",
    "balance value": "open_value",
    "fo value": "fo_value",
}


def _load_rows(path, keys, labels):
    """Read a spreadsheet of rows for one level, matching headers by label.

    Three header shapes are accepted, in order: our own exported labels, the
    SAP/ME3L headers above, and our internal snake_case column names - so an
    export from this app, a raw download and the stored CSV all import.
    """
    frame = _read_table(path)
    label_to_key = {_normalize_header(v): k for k, v in labels.items()}
    columns = {}
    for column in frame.columns:
        header = _normalize_header(column)
        key = label_to_key.get(header)
        if key is None:
            alias = HEADER_ALIASES.get(header)
            # An alias only applies to the level being imported: "Description"
            # must not drop an FO's text onto an ARC field, and vice versa.
            key = alias if alias in keys else None
        if key is None and header.replace(" ", "_") in keys:
            key = header.replace(" ", "_")
        if key is not None and key not in columns:
            columns[key] = column
    return [
        {key: str(row.get(column, "")).strip() for key, column in columns.items()}
        for _, row in frame.iterrows()
    ]


class ArcRecordsScreen(RecordsScreen):
    """The ARC master itself - the key every amendment is filed against."""

    TITLE = "ARC Records"
    SUBTITLE = ("The master agreement, in ME3L column order. Double-click a row to "
                "open the full ARC. FO Value and the difference against the ARC's "
                "target are rolled up from the FOs, not typed in.")
    DOUBLE_CLICK_EDITS = False
    IMPORT_LABEL = "Import ARCs..."
    paste_keys = tuple(ARC_KEYS)
    paste_labels = ARC_LABELS
    paste_note = ("Paste ARC rows copied from Excel, one contract per line. "
                  "ARC No is the key and is required.")

    def __init__(self, master, store, on_data_changed=None):
        self.store = store
        super().__init__(
            master, ["sr_no"] + ARC_DISPLAY_COLUMNS, ARC_WRAPPED_LABELS, ARC_COLUMN_WIDTHS,
            editable_keys=set(ARC_KEYS) - {"arc_no"}, on_data_changed=on_data_changed,
        )

    def fetch(self, query):
        rows = [self.store.arc_row(a) for a in self.store.all_arcs()]
        needle = (query or "").strip().lower()
        if not needle:
            return rows
        return [r for r in rows
                if any(needle in str(r.get(k, "")).lower() for k in ARC_DISPLAY_COLUMNS)]

    def row_id(self, record):
        return record["arc_no"]

    def row_values(self, record, index):
        return [index] + [record.get(k, "") for k in ARC_DISPLAY_COLUMNS]

    def commit(self, row_id, key, value):
        if key in ARC_DERIVED_KEYS:
            return ("FO count, FO value and the difference are rolled up from the FOs - "
                    "edit the FOs, or the ARC's own target value, instead.")
        try:
            self.store.update_arc_field(row_id, key, value)
        except ValidationError as exc:
            return str(exc)
        except Exception as exc:
            return str(exc)
        return None

    def read_file(self, path):
        return _load_rows(path, ARC_KEYS, ARC_LABELS)

    def import_rows(self, rows, progress=None):
        return self.store.bulk_upsert_arcs(rows, progress=progress)

    def export(self, records, path):
        return export_arcs_to_excel(records, path)

    def delete_record(self, record):
        return bool(record) and self.store.delete_arc(record["arc_no"])

    def on_row_double_click(self, row_id, column_key):
        self.open_dialog(row_id)

    def open_dialog(self, arc_no):
        from vendor_app.gui.arc_dialogs import ArcDialog
        record = self.store.arcs.find(arc_no)
        if record is None:
            return
        ArcDialog(self, self.store, record, on_saved=self._after_dialog)

    def extra_actions(self, parent):
        from vendor_app.gui.widgets import secondary_button
        secondary_button(parent, "Edit ARC", self._edit_selected, width=120).pack(
            side="left", padx=(0, 8)
        )
        secondary_button(parent, "+ Add ARC", self._add, width=120).pack(side="left")

    def _edit_selected(self):
        ids = self.table.selected_ids()
        if not ids:
            from tkinter import messagebox
            messagebox.showinfo("Select a Row", "Select an ARC first, or double-click it.")
            return
        self.open_dialog(ids[0])

    def _add(self):
        from vendor_app.gui.arc_dialogs import ArcDialog
        ArcDialog(self, self.store, None, on_saved=self._after_dialog)

    def _after_dialog(self):
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()


class FoRecordsScreen(RecordsScreen):
    """The FOs: sub-parts of an ARC, many per contract."""

    TITLE = "FO Records"
    SUBTITLE = ("Framework orders issued under an ARC, in SAP FO report column order. "
                "Every FO names its ARC. FO Total is the sum of its line items "
                "once it has any.")
    DOUBLE_CLICK_EDITS = False
    IMPORT_LABEL = "Import FOs..."
    paste_keys = tuple(FO_KEYS)
    paste_labels = FO_LABELS
    paste_note = ("Paste FO rows copied from Excel, one order per line. "
                  "FO No and ARC No are both required.")

    def __init__(self, master, store, on_data_changed=None):
        self.store = store
        super().__init__(
            master, ["sr_no"] + FO_DISPLAY_COLUMNS, FO_WRAPPED_LABELS, FO_COLUMN_WIDTHS,
            editable_keys=set(FO_KEYS) - {"fo_no"}, on_data_changed=on_data_changed,
        )

    def fetch(self, query):
        rows = [self.store.fo_row(f) for f in self.store.all_fos()]
        needle = (query or "").strip().lower()
        if not needle:
            return rows
        return [r for r in rows
                if any(needle in str(r.get(k, "")).lower() for k in FO_DISPLAY_COLUMNS)]

    def row_id(self, record):
        return record["fo_no"]

    def row_values(self, record, index):
        return [index] + [record.get(k, "") for k in FO_DISPLAY_COLUMNS]

    def commit(self, row_id, key, value):
        if key in FO_DERIVED_KEYS:
            return "FO Total and line count are rolled up from the line items."
        try:
            self.store.update_fo_field(row_id, key, value)
        except ValidationError as exc:
            return str(exc)
        except Exception as exc:
            return str(exc)
        return None

    def read_file(self, path):
        return _load_rows(path, FO_KEYS, FO_LABELS)

    def import_rows(self, rows, progress=None):
        return self.store.bulk_upsert_fos(rows, progress=progress)

    def export(self, records, path):
        return export_fos_to_excel(records, path)

    def delete_record(self, record):
        return bool(record) and self.store.delete_fo(record["fo_no"])

    def on_row_double_click(self, row_id, column_key):
        self.open_dialog(row_id)

    def open_dialog(self, fo_no):
        from vendor_app.gui.arc_dialogs import FoDialog
        record = self.store.fos.find(fo_no)
        if record is None:
            return
        FoDialog(self, self.store, record, on_saved=self._after_dialog)

    def extra_actions(self, parent):
        from vendor_app.gui.widgets import secondary_button
        secondary_button(parent, "Edit FO", self._edit_selected, width=110).pack(
            side="left", padx=(0, 8)
        )
        secondary_button(parent, "+ Add FO", self._add, width=110).pack(side="left")

    def _edit_selected(self):
        ids = self.table.selected_ids()
        if not ids:
            from tkinter import messagebox
            messagebox.showinfo("Select a Row", "Select an FO first, or double-click it.")
            return
        self.open_dialog(ids[0])

    def _add(self):
        from vendor_app.gui.arc_dialogs import FoDialog
        FoDialog(self, self.store, None, on_saved=self._after_dialog)

    def _after_dialog(self):
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()


class ArcLineItemsScreen(RecordsScreen):
    """The line items - the references an FO's value is built from."""

    TITLE = "Line Items"
    SUBTITLE = ("The reference rows behind each FO. Line Value is taken as entered, "
                "or computed as Quantity x Rate when it is left blank.")
    IMPORT_LABEL = "Import Line Items..."
    paste_keys = tuple(ARC_LINE_KEYS)
    paste_labels = ARC_LINE_LABELS
    paste_note = ("Paste line items copied from Excel. Each line references its FO No; "
                  "leave Line Value blank to have Quantity x Rate used instead.")

    def __init__(self, master, store, on_data_changed=None):
        self.store = store
        super().__init__(
            master, ["sr_no"] + ARC_LINE_KEYS, ARC_LINE_WRAPPED_LABELS,
            ARC_LINE_COLUMN_WIDTHS, editable_keys=set(ARC_LINE_KEYS),
            on_data_changed=on_data_changed,
        )

    def fetch(self, query):
        # Return the STORED records, never enriched copies: an in-place edit
        # has to land on the object the store actually holds.
        rows = self.store.all_lines()
        needle = (query or "").strip().lower()
        if not needle:
            return rows
        return [r for r in rows
                if any(needle in str(r.get(k, "")).lower() for k in ARC_LINE_KEYS)]

    def row_id(self, record):
        return f"line-{id(record)}"

    def row_values(self, record, index):
        # Line Value is displayed as Quantity x Rate when it was left blank,
        # so the grid shows what the line is worth without inventing stored data.
        display = self.store.line_row(record)
        return [index] + [display.get(k, "") for k in ARC_LINE_KEYS]

    def commit(self, row_id, key, value):
        record = self._rows.get(row_id)
        try:
            self.store.update_line_field(record, key, value)
        except ValidationError as exc:
            return str(exc)
        except Exception as exc:
            return str(exc)
        return None

    def read_file(self, path):
        return _load_rows(path, ARC_LINE_KEYS, ARC_LINE_LABELS)

    def import_rows(self, rows, progress=None):
        return self.store.bulk_upsert_lines(rows, progress=progress)

    def export(self, records, path):
        return export_arc_lines_to_excel(records, path)

    def delete_record(self, record):
        return bool(record) and self.store.delete_line(record)
