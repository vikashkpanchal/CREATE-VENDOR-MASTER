"""De-mob Equipment: close machines out of the running fleet.

Paste a list of identifiers (RH/RO Number, Technical ID or Reg No) with the
date each machine left site. De-mobbing stamps the De-mob Date on the
record, which:

  * drops it out of the Running Equipment counts everywhere,
  * FREEZES it - its cells can no longer be edited, and
  * frees the identifier, so if that machine comes back it is entered as a
    brand-new, fully editable record rather than reopening the closed one.
"""

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vendor_app.config import (
    EQUIPMENT_COLUMN_WIDTHS, EQUIPMENT_KEYS, EQUIPMENT_WRAPPED_LABELS,
)
from vendor_app.gui import theme
from vendor_app.gui.editable_table import EditableTable
from vendor_app.gui.loading import run_with_loading
from vendor_app.gui.paste_grid import PasteGrid
from vendor_app.gui.toast import notify
from vendor_app.export import export_equipment_to_excel
from vendor_app.gui.widgets import (
    card, danger_button, pill, primary_button, secondary_button, section_label,
    wrap_children,
)

COLUMNS = ["sr_no"] + EQUIPMENT_KEYS


class DemobTab(ctk.CTkFrame):
    def __init__(self, master, equipment_store, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = equipment_store
        self.on_data_changed = on_data_changed
        self._rows = {}
        self._build()
        self.refresh()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 10))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        wrap_children(left)
        ctk.CTkLabel(
            left, text="De-mob Equipment", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Close machines out of the running fleet. A de-mobbed record is locked; "
                 "if the machine returns, add it again as a fresh record.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        panel = card(split, fg_color=theme.BG_CARD, width=560)
        panel.pack(side="left", fill="y", padx=(0, 14))
        panel.pack_propagate(False)
        section_label(panel, "MACHINES TO DE-MOB").pack(anchor="w", padx=16, pady=(16, 0))
        ctk.CTkLabel(
            panel,
            text="Paste straight from Excel: the identifier (RH/RO Number, Technical ID "
                 "or Reg No) in the first column and the de-mob date in the second.",
            font=theme.small_font(), text_color=theme.TEXT_MUTED,
            justify="left", wraplength=520,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # Buttons reserved before the grid so they stay on screen.
        secondary_button(panel, "Clear", self.clear_input, width=528).pack(
            side="bottom", padx=16, pady=(0, 16)
        )
        primary_button(panel, "De-mob These Machines", self.run_demob, width=528).pack(
            side="bottom", padx=16, pady=(10, 6)
        )

        today = datetime.now().strftime("%Y-%m-%d")
        date_row = ctk.CTkFrame(panel, fg_color="transparent")
        date_row.pack(side="bottom", fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            date_row, text="Fill blank dates with:", font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))
        self.default_date = ctk.StringVar(value=today)
        ctk.CTkEntry(
            date_row, textvariable=self.default_date, width=150, height=30,
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
        ).pack(side="left")

        self.grid = PasteGrid(
            panel,
            columns=[("identifier", "RH / Technical ID / Reg No"), ("demob_date", "De-mob Date")],
            widths=[22, 26],
            rows=80,
        )
        self.grid.pack(fill="both", expand=True, padx=16, pady=4)

        right = ctk.CTkFrame(split, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(right, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        # Reserved column for the actions, so a long caption cannot push them
        # off the right edge.
        toolbar.grid_columnconfigure(0, weight=1)
        toolbar.grid_columnconfigure(1, weight=0)

        caption = ctk.CTkFrame(toolbar, fg_color="transparent")
        caption.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            caption, text="Already de-mobbed", font=theme.h2_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")
        self.count_pill = pill(caption, "0", fg=theme.BG_CARD_ALT, tc=theme.TEXT_SECONDARY)
        self.count_pill.pack(side="left", padx=12)
        ctk.CTkLabel(
            caption, text="Locked and read-only.",
            font=theme.small_font(), text_color=theme.TEXT_MUTED,
        ).pack(side="left")

        actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        secondary_button(actions, "Import De-mob...", self.import_demobbed, width=160).pack(
            side="left", padx=(0, 8)
        )
        secondary_button(actions, "Export (.xlsx)", self.export_demobbed, width=140).pack(
            side="left", padx=(0, 8)
        )
        danger_button(actions, "Delete Selected", self.delete_selected, width=150).pack(
            side="left"
        )

        wrap = card(right, fg_color=theme.BG_CARD)
        wrap.grid(row=1, column=0, sticky="nsew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.table = EditableTable(
            wrap, COLUMNS, EQUIPMENT_WRAPPED_LABELS, EQUIPMENT_COLUMN_WIDTHS
        )
        self.table.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

    # ----------------------------------------------- the de-mobbed list --
    def export_demobbed(self):
        records = self.store.demob_records()
        if not records:
            messagebox.showwarning("No Data", "There is no de-mobbed equipment to export.")
            return
        default = f"Demobbed_Equipment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return
        export_equipment_to_excel(records, path)
        notify(self, f"{len(records):,} de-mobbed record(s) exported to:\n{path}")

    def import_demobbed(self):
        path = filedialog.askopenfilename(
            title="Import De-mobbed Equipment",
            filetypes=[("Spreadsheet files", "*.xlsx *.xls *.csv *.tsv"),
                       ("All files", "*.*")],
        )
        if not path:
            return

        def work(report):
            report(message="Reading the file...")
            from vendor_app.gui.equipment_tab import load_equipment_from_file
            rows = load_equipment_from_file(path)
            if not rows:
                return {"added": 0, "updated": 0, "errors": [], "empty": True}
            report(0, len(rows), f"Importing {len(rows):,} closed record(s)...")
            return self.store.bulk_upsert_demobbed(
                rows, progress=lambda done, total: report(done, total)
            )

        run_with_loading(
            self, "Importing de-mobbed equipment", work, on_done=self._after_import,
            subtitle="Every row must carry a De-mob Date - that is what makes it "
                     "a closed record.",
        )

    def _after_import(self, result, error):
        if error is not None:
            messagebox.showerror("Import Failed", f"Could not import that file:\n{error}")
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

    def delete_selected(self):
        ids = self.table.selected_ids()
        records = [self._rows[i] for i in ids if i in self._rows]
        if not records:
            messagebox.showinfo("Select a Row", "Select one or more de-mobbed rows first.")
            return
        if not messagebox.askyesno(
            "Delete De-mobbed Records",
            f"Permanently delete {len(records)} closed record(s)?\n\n"
            "This removes them from the equipment master entirely and cannot "
            "be undone.",
        ):
            return
        removed = self.store.delete_many(records)
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()
        notify(self, f"{removed} de-mobbed record(s) deleted.", kind="error")

    # ------------------------------------------------------------ actions --
    def clear_input(self):
        self.grid.clear()

    def run_demob(self):
        rows = self.grid.get_rows()
        rows = [r for r in rows if r.get("identifier", "").strip()]
        if not rows:
            messagebox.showinfo(
                "Nothing to De-mob",
                "Enter at least one RH/RO Number, Technical ID or Reg No.",
            )
            return

        fallback = self.default_date.get().strip()
        missing_dates = [r for r in rows if not r.get("demob_date", "").strip()]
        if missing_dates and not fallback:
            messagebox.showwarning(
                "De-mob Date Missing",
                f"{len(missing_dates)} row(s) have no de-mob date, and no fallback date "
                "is set. Enter a date per row, or fill the 'Fill blank dates with' box.",
            )
            return
        for row in rows:
            if not row.get("demob_date", "").strip():
                row["demob_date"] = fallback

        if not messagebox.askyesno(
            "De-mob Equipment",
            f"De-mob {len(rows)} machine(s)?\n\n"
            "Each record will be closed and locked against further edits. "
            "If a machine returns to site, add it again as a new record.",
        ):
            return

        def work(report):
            report(0, len(rows), f"De-mobbing {len(rows):,} machine(s)...")
            return self.store.demob_many(rows, progress=lambda d, t: report(d, t))

        run_with_loading(
            self, "De-mobbing equipment", work, on_done=self._after_demob,
            subtitle="Closing these machines out of the running fleet...",
        )

    def _after_demob(self, result, error):
        if error is not None:
            messagebox.showerror("De-mob Failed", str(error))
            return
        if result is None:
            return

        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()

        summary = f"De-mobbed: {result['demobbed']:,}"
        problems = []
        if result["already"]:
            problems.append(
                f"Already de-mobbed ({len(result['already'])}): "
                + ", ".join(result["already"][:10])
                + (" ..." if len(result["already"]) > 10 else "")
            )
        if result["missing"]:
            problems.append(
                f"Not found in the equipment master ({len(result['missing'])}): "
                + ", ".join(result["missing"][:10])
                + (" ..." if len(result["missing"]) > 10 else "")
            )
        if result["errors"]:
            problems.append(
                "Errors:\n" + "\n".join(f"Row {i}: {err}" for i, err in result["errors"][:10])
            )

        if problems:
            messagebox.showwarning("De-mob Completed with Notes", summary + "\n\n" + "\n\n".join(problems))
        else:
            notify(self, f"{result['demobbed']:,} machine(s) de-mobbed.")
            self.grid.clear()

    def refresh(self):
        if not hasattr(self, "table"):
            return
        records = self.store.demob_records()
        self.table.clear()
        # Row ids are kept so a selection can be turned back into the stored
        # records that Delete Selected has to remove.
        self._rows = {}
        for index, record in enumerate(records, start=1):
            row_id = self.table.add_row(
                index - 1, [index] + [record.get(k, "") for k in EQUIPMENT_KEYS],
                iid=f"demob-{index}",
            )
            self._rows[row_id] = record
        self.count_pill.configure(text=f"  {len(records):,} machine(s)  ")
