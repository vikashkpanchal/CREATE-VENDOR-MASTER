"""Directly-editable master-data screen, shared by both masters.

One screen serves the vendor master and the equipment master: a full-width
editable grid, a live filter, unlimited file/paste import behind a progress
dialog, and export. Double-click any editable cell to change it in place;
every commit goes through the store, so validation and the change log apply
exactly as they do everywhere else.
"""

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vendor_app.gui import theme
from vendor_app.gui.editable_table import EditableTable
from vendor_app.gui.loading import run_with_loading
from vendor_app.gui.paste_dialog import PasteRowsDialog
from vendor_app.gui.toast import notify
from vendor_app.gui.util import debounce
from vendor_app.gui.widgets import card, danger_button, pill, primary_button, secondary_button


class RecordsScreen(ctk.CTkFrame):
    """Configured by the subclass/caller through these hooks:

    columns/headers/widths  the grid's shape
    editable_keys           which columns may be edited in place
    fetch()                 -> list of record dicts, already filtered
    row_values(record, i)   -> the row's cell values
    row_id(record)          -> stable id for the row
    commit(row_id, key, v)  -> error message or None
    import_rows(rows, prog) -> {"added","updated","errors",...}
    export(records, path)
    """

    TITLE = "Records"
    SUBTITLE = ""
    IMPORT_LABEL = "Import from File..."
    EXPORT_PREFIX = "Export"
    paste_keys = ()
    paste_labels = {}
    paste_note = ""

    DOUBLE_CLICK_EDITS = True

    def __init__(self, master, columns, headers, widths, editable_keys=(), on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.columns = columns
        self.headers = headers
        self.widths = widths
        self.editable_keys = set(editable_keys)
        self.on_data_changed = on_data_changed
        self._sort_key = None
        self._sort_desc = False
        self._rows = {}
        self._build()
        self.refresh()

    # -------------------------------------------------------------- hooks --
    def fetch(self, query): raise NotImplementedError
    def row_values(self, record, index): raise NotImplementedError
    def row_id(self, record): raise NotImplementedError
    def row_status(self, record): return None
    def commit(self, row_id, key, value): return None
    def import_rows(self, rows, progress=None): raise NotImplementedError
    def read_file(self, path): raise NotImplementedError
    def export(self, records, path): raise NotImplementedError
    def delete_record(self, record): return False
    def extra_actions(self, parent): pass
    def on_row_double_click(self, row_id, column_key): pass
    def is_row_locked(self, row_id): return False

    # -------------------------------------------------------------- build --
    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 10))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text=self.TITLE, font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text=self.SUBTITLE, font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        primary_button(actions, self.IMPORT_LABEL, self.import_from_file, width=170).pack(
            side="left", padx=(0, 8)
        )
        if self.paste_keys:
            secondary_button(actions, "Paste Rows", self.paste_rows, width=130).pack(
                side="left", padx=(0, 8)
            )
        secondary_button(
            actions, f"{self.EXPORT_PREFIX} (.xlsx)", self.export_all, width=150
        ).pack(side="left")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(
            toolbar, text="Search:", font=theme.small_font(), text_color=theme.TEXT_SECONDARY
        ).pack(side="left", padx=(0, 8))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add(
            "write", lambda *a: debounce(self, "_search_after", 200, self.refresh)
        )
        ctk.CTkEntry(
            toolbar, textvariable=self.search_var, width=300, height=32,
            placeholder_text="Filter records...",
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
        ).pack(side="left")
        self.count_pill = pill(toolbar, "0 records")
        self.count_pill.pack(side="left", padx=12)

        right_actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        right_actions.pack(side="right")
        danger_button(right_actions, "Delete Selected", self.delete_selected, width=150).pack(
            side="left", padx=(8, 0)
        )
        self.extra_actions(right_actions)

        ctk.CTkLabel(
            self,
            text="Double-click a cell to edit it in place  •  Enter commits, Esc cancels, "
                 "Tab moves on  •  Ctrl+C copies the selected cell or rows",
            font=theme.font(10), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 6))

        wrap = card(self, fg_color=theme.BG_CARD)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.table = EditableTable(
            wrap, self.columns, self.headers, self.widths,
            editable=self.editable_keys, on_edit=self._on_edit, on_sort=self._on_sort,
            double_click_edits=self.DOUBLE_CLICK_EDITS,
            on_double_click=self.on_row_double_click,
            is_row_locked=self.is_row_locked,
        )
        self.table.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

    # ------------------------------------------------------------ refresh --
    def _on_sort(self, key):
        if key == "sr_no":
            return
        if self._sort_key == key:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_key, self._sort_desc = key, False
        self.refresh()

    def refresh(self):
        if not hasattr(self, "table"):
            return
        records = self.fetch(self.search_var.get())
        if self._sort_key:
            records = sorted(
                records, key=lambda r: str(r.get(self._sort_key, "")).lower(),
                reverse=self._sort_desc,
            )

        self.table.clear()
        self._rows = {}
        for index, record in enumerate(records, start=1):
            row_id = self.table.add_row(
                index - 1, self.row_values(record, index),
                iid=self.row_id(record), status=self.row_status(record),
            )
            self._rows[row_id] = record
        self.table.set_headings(self._sort_key, self._sort_desc)
        self.count_pill.configure(
            text=f"  {len(records):,} record{'s' if len(records) != 1 else ''}  "
        )

    def _on_edit(self, row_id, key, value):
        error = self.commit(row_id, key, value)
        if error:
            return error
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()
        return None

    # ------------------------------------------------------------ import --
    def import_from_file(self):
        path = filedialog.askopenfilename(
            title="Import from File",
            filetypes=[("Spreadsheet files", "*.xlsx *.xls *.csv *.tsv"), ("All files", "*.*")],
        )
        if not path:
            return

        def work(report):
            report(message=f"Reading {path.rsplit('/', 1)[-1]}...")
            rows = self.read_file(path)
            if not rows:
                return {"added": 0, "updated": 0, "errors": [], "empty": True}
            report(0, len(rows), f"Importing {len(rows):,} row(s)...")
            return self.import_rows(
                rows, progress=lambda done, total: report(done, total),
            )

        run_with_loading(
            self, "Importing data", work, on_done=self._after_import,
            subtitle="Reading the file. The window stays responsive - please wait.",
        )

    def paste_rows(self):
        PasteRowsDialog(
            self, f"Paste {self.TITLE} Rows", list(self.paste_keys), self.paste_labels,
            self._apply_pasted, note=self.paste_note,
        )

    def _apply_pasted(self, rows):
        if not rows:
            return

        def work(report):
            report(0, len(rows), f"Importing {len(rows):,} pasted row(s)...")
            return self.import_rows(rows, progress=lambda d, t: report(d, t))

        run_with_loading(
            self, "Importing pasted rows", work, on_done=self._after_import,
            subtitle="Applying your pasted rows...",
        )

    def _after_import(self, result, error):
        if error is not None:
            messagebox.showerror("Import Failed", f"Could not import that data:\n{error}")
            return
        if result is None:
            return
        if result.get("empty"):
            messagebox.showwarning("No Rows Found", "No recognizable rows were found.")
            return

        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()

        summary = f"Added: {result['added']:,}  •  Updated: {result['updated']:,}"
        if result.get("vendors_created"):
            summary += f"  •  {result['vendors_created']:,} vendor(s) auto-created"
        if result["errors"]:
            lines = "\n".join(f"Row {i}: {err}" for i, err in result["errors"][:15])
            more = len(result["errors"]) - 15
            if more > 0:
                lines += f"\n...and {more:,} more"
            messagebox.showwarning(
                "Imported with Errors",
                f"{summary}\n\nRows skipped ({len(result['errors']):,}):\n{lines}",
            )
        else:
            notify(self, summary)

    # ------------------------------------------------------------ actions --
    def delete_selected(self):
        ids = self.table.selected_ids()
        if not ids:
            messagebox.showinfo("Select a Row", "Select one or more rows first.")
            return
        if not messagebox.askyesno(
            "Delete Records",
            f"Permanently delete {len(ids)} record(s)?\n\nThis cannot be undone.",
        ):
            return
        removed = sum(1 for row_id in ids if self.delete_record(self._rows.get(row_id)))
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()
        notify(self, f"{removed} record(s) deleted.", kind="error")

    def export_all(self):
        records = self.fetch(self.search_var.get())
        if not records:
            messagebox.showwarning("No Data", "There is nothing to export.")
            return
        default = f"{self.TITLE.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return

        def work(report):
            report(message=f"Writing {len(records):,} row(s)...")
            self.export(records, path)
            return {"path": path}

        run_with_loading(
            self, "Exporting", work,
            on_done=lambda result, error: (
                messagebox.showerror("Export Failed", str(error)) if error
                else notify(self, f"{len(records):,} row(s) exported to:\n{path}")
            ),
            subtitle="Building the spreadsheet...",
        )
