"""The two ARC & FO record screens, built on RecordsScreen.

    ARC Records  Table 1 - ARC data (ME3L export), one row per contract item
    FO Records   Table 2 - framework & contract tracking, one row per FO item

Both get the same treatment the other masters have - search, unlimited
import, Excel-like paste, in-place editing, export and a change log - so
there is nothing new to learn moving between them.

The derived columns (frame orders, released against, difference, FO totals)
are shown read-only: they are computed across the rows of a contract or a
frame order, and typing into one would only create a figure that disagrees
with its own detail. The decoded release columns are read-only in the grid
too, and chosen from a list in the record dialog.
"""

import customtkinter as ctk

from vendor_app.config import (
    ARC_COLUMN_WIDTHS, ARC_DERIVED_KEYS, ARC_DISPLAY_COLUMNS, ARC_KEYS, ARC_KEY_FIELDS,
    ARC_LABELS, ARC_WRAPPED_LABELS, FO_COLUMN_WIDTHS, FO_DERIVED_KEYS,
    FO_DISPLAY_COLUMNS, FO_KEYS, FO_KEY_FIELDS, FO_LABELS, FO_WRAPPED_LABELS,
    describe_release_indicator, describe_release_status,
)
from vendor_app.export import export_arcs_to_excel, export_fos_to_excel
from vendor_app.importer import load_arc_rows_from_file
from vendor_app.validators import ValidationError
from vendor_app.gui import theme
from vendor_app.gui.records_screen import RecordsScreen

def _load_rows(path, keys, labels):
    """One sheet of ARC or FO rows, read through the shared import layer."""
    return load_arc_rows_from_file(path, keys, labels)


class _ArcScreenBase(RecordsScreen):
    """Shared wiring for two grids whose rows are keyed on several columns.

    Both open showing the input table exactly as it arrives - the report's
    own columns, in the report's own order, and nothing else. The computed
    columns are real but they are not part of the file, so they are added on
    request and always after the input set, never interleaved into it.
    """

    KEY_FIELDS = ()
    TABLE_ATTR = ""
    INPUT_KEYS = ()
    DERIVED_KEYS = ()
    INPUT_NOTE = "the input file's columns"

    def extra_view_controls(self, parent):
        self.show_computed = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            parent, text="Computed columns", variable=self.show_computed,
            command=self.apply_column_choice, font=theme.font(10),
            text_color=theme.TEXT_SECONDARY, checkbox_width=16, checkbox_height=16,
            corner_radius=4, border_width=1, fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, border_color=theme.BG_INPUT_BORDER,
        ).pack(side="left", padx=(0, 16))

    def apply_column_choice(self):
        columns = ["sr_no"] + list(self.INPUT_KEYS)
        if self.show_computed.get():
            columns += list(self.DERIVED_KEYS)
        self.set_columns(columns)

    def row_values(self, record, index):
        # Driven by the CURRENT column set, so toggling the computed columns
        # needs no second row builder.
        return [index] + [record.get(k, "") for k in self.columns[1:]]

    def table_of(self):
        return getattr(self.store, self.TABLE_ATTR)

    def row_id(self, record):
        return self.table_of().row_id(self.table_of().key_of(record))

    def _selected_record(self):
        ids = self.table.selected_ids()
        if not ids:
            from tkinter import messagebox
            messagebox.showinfo("Select a Row", "Select a row first, or double-click it.")
            return None
        return self._rows.get(ids[0])

    def _after_dialog(self):
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()


class ArcRecordsScreen(_ArcScreenBase):
    """Table 1: ARC data, one row per item of a purchasing document."""

    TITLE = "ARC Records"
    SUBTITLE = ("Table 1 - ARC data (ME3L export), shown exactly as the file "
                "arrives: one row per contract item, the report's own columns in "
                "its own order. Tick Computed columns to add what the app works "
                "out across a contract.")
    DOUBLE_CLICK_EDITS = False
    IMPORT_LABEL = "Import ARC Data..."
    KEY_FIELDS = ARC_KEY_FIELDS
    TABLE_ATTR = "arcs"
    INPUT_KEYS = tuple(ARC_KEYS)
    DERIVED_KEYS = tuple(ARC_DERIVED_KEYS)
    paste_keys = tuple(ARC_KEYS)
    paste_labels = ARC_LABELS
    paste_note = ("Paste ARC rows copied from the ME3L export, one line item per row. "
                  "Purchasing Document identifies the contract and Item the line "
                  "within it.")

    # Decoded in the grid, so they read as words rather than as X's; the
    # underlying code is chosen from a list in the record dialog.
    READ_ONLY_KEYS = {"release_indicator", "release_status"}

    def __init__(self, master, store, on_data_changed=None):
        self.store = store
        super().__init__(
            master, ["sr_no"] + list(ARC_KEYS), ARC_WRAPPED_LABELS, ARC_COLUMN_WIDTHS,
            editable_keys=set(ARC_KEYS) - set(ARC_KEY_FIELDS) - self.READ_ONLY_KEYS,
            on_data_changed=on_data_changed,
        )

    def fetch(self, query):
        rows = [self.store.arc_row(a) for a in self.store.all_arcs()]
        for row in rows:
            row["release_indicator"] = describe_release_indicator(row.get("release_indicator"))
            row["release_status"] = describe_release_status(row.get("release_status"))
        needle = (query or "").strip().lower()
        if not needle:
            return rows
        return [r for r in rows
                if any(needle in str(r.get(k, "")).lower() for k in ARC_DISPLAY_COLUMNS)]

    def commit(self, row_id, key, value):
        if key in ARC_DERIVED_KEYS:
            return ("Frame orders, released value and the difference are computed "
                    "across the contract - edit the frame orders, or the contract's "
                    "own Target Val. (Header), instead.")
        if key in self.READ_ONLY_KEYS:
            return ("Release indicator and status are codes - open the record "
                    "(double-click the row) to choose one.")
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
        return bool(record) and self.store.delete_arc(self.row_id(record))

    def on_row_double_click(self, row_id, column_key):
        self.open_dialog(self._rows.get(row_id))

    def open_dialog(self, record):
        from vendor_app.gui.arc_dialogs import ArcDialog
        ArcDialog(self, self.store, record, on_saved=self._after_dialog)

    def extra_actions(self, parent):
        from vendor_app.gui.widgets import secondary_button
        secondary_button(parent, "Edit Row", self._edit_selected, width=110).pack(
            side="left", padx=(0, 8)
        )
        secondary_button(parent, "+ Add Item", self._add, width=120).pack(side="left")

    def _edit_selected(self):
        record = self._selected_record()
        if record is not None:
            self.open_dialog(record)

    def _add(self):
        self.open_dialog(None)


class FoRecordsScreen(_ArcScreenBase):
    """Table 2: framework & contract tracking, one row per frame order item."""

    TITLE = "FO Records"
    SUBTITLE = ("Table 2 - framework & contract tracking, shown exactly as the "
                "file arrives: one row per frame order item, in the report's own "
                "column order. Contract No., Contract Value and the contract "
                "validity dates map from Table 1.")
    DOUBLE_CLICK_EDITS = False
    IMPORT_LABEL = "Import FO Data..."
    KEY_FIELDS = FO_KEY_FIELDS
    TABLE_ATTR = "fos"
    INPUT_KEYS = tuple(FO_KEYS)
    DERIVED_KEYS = tuple(FO_DERIVED_KEYS)
    paste_keys = tuple(FO_KEYS)
    paste_labels = FO_LABELS
    paste_note = ("Paste frame order rows copied from the tracking report. "
                  "Frame Numbers and Item identify the row; Contract No. ties it "
                  "back to its purchasing document.")

    def __init__(self, master, store, on_data_changed=None):
        self.store = store
        super().__init__(
            master, ["sr_no"] + list(FO_KEYS), FO_WRAPPED_LABELS, FO_COLUMN_WIDTHS,
            editable_keys=set(FO_KEYS) - set(FO_KEY_FIELDS),
            on_data_changed=on_data_changed,
        )

    def fetch(self, query):
        rows = [self.store.fo_row(f) for f in self.store.all_fos()]
        needle = (query or "").strip().lower()
        if not needle:
            return rows
        return [r for r in rows
                if any(needle in str(r.get(k, "")).lower() for k in FO_DISPLAY_COLUMNS)]

    def commit(self, row_id, key, value):
        if key in FO_DERIVED_KEYS:
            return "The FO totals are summed from this frame order's items."
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
        return bool(record) and self.store.delete_fo(self.row_id(record))

    def on_row_double_click(self, row_id, column_key):
        self.open_dialog(self._rows.get(row_id))

    def open_dialog(self, record):
        from vendor_app.gui.arc_dialogs import FoDialog
        FoDialog(self, self.store, record, on_saved=self._after_dialog)

    def extra_actions(self, parent):
        from vendor_app.gui.widgets import secondary_button
        secondary_button(parent, "Edit Row", self._edit_selected, width=110).pack(
            side="left", padx=(0, 8)
        )
        secondary_button(parent, "+ Add Item", self._add, width=120).pack(side="left")

    def _edit_selected(self):
        record = self._selected_record()
        if record is not None:
            self.open_dialog(record)

    def _add(self):
        self.open_dialog(None)
