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
from tkinter import messagebox

import customtkinter as ctk

from vendor_app.config import (
    EQUIPMENT_COLUMN_WIDTHS, EQUIPMENT_KEYS, EQUIPMENT_WRAPPED_LABELS,
)
from vendor_app.gui import theme
from vendor_app.gui.editable_table import EditableTable
from vendor_app.gui.loading import run_with_loading
from vendor_app.gui.paste_grid import PasteGrid
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, pill, primary_button, secondary_button, section_label, wrap_children

COLUMNS = ["sr_no"] + EQUIPMENT_KEYS


class DemobTab(ctk.CTkFrame):
    def __init__(self, master, equipment_store, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = equipment_store
        self.on_data_changed = on_data_changed
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
        ctk.CTkLabel(
            toolbar, text="Already de-mobbed", font=theme.h2_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")
        self.count_pill = pill(toolbar, "0", fg=theme.BG_CARD_ALT, tc=theme.TEXT_SECONDARY)
        self.count_pill.pack(side="left", padx=12)
        ctk.CTkLabel(
            toolbar, text="These records are locked and read-only.",
            font=theme.small_font(), text_color=theme.TEXT_MUTED,
        ).pack(side="left")

        wrap = card(right, fg_color=theme.BG_CARD)
        wrap.grid(row=1, column=0, sticky="nsew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.table = EditableTable(
            wrap, COLUMNS, EQUIPMENT_WRAPPED_LABELS, EQUIPMENT_COLUMN_WIDTHS
        )
        self.table.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

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
        for index, record in enumerate(records, start=1):
            self.table.add_row(index - 1, [index] + [record.get(k, "") for k in EQUIPMENT_KEYS])
        self.count_pill.configure(text=f"  {len(records):,} machine(s)  ")
