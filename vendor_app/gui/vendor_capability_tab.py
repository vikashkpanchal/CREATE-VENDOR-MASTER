"""Supply Capability - which vendor can supply which kind of equipment.

Two ways of reading the same fact, because two different questions get
asked of it:

  By Vendor     what each supplier can send, and whether they are a
                specialist in one machine or carry a mixed fleet
  By Equipment  who can send a particular machine - the question that gets
                asked when one is needed on site and the usual supplier
                cannot cover it

Both are read out of the equipment master's own history, de-mobbed records
included: a vendor whose three tippers have left site can still supply
tippers. What is on site today is carried alongside as its own column
rather than replacing that.
"""

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vendor_app import vendor_analytics as va
from vendor_app.export import export_report_to_excel
from vendor_app.gui import theme
from vendor_app.gui.editable_table import EditableTable
from vendor_app.gui.filter_dropdown import FilterDropdown
from vendor_app.gui.style import ROW_HEIGHT_CHOICES, ROW_HEIGHT_DEFAULT
from vendor_app.gui.toast import notify
from vendor_app.gui.util import debounce
from vendor_app.gui.widgets import card, pill, primary_button, secondary_button, wrap_children

BY_VENDOR = "By Vendor"
BY_EQUIPMENT = "By Equipment"

PROFILE_VALUES = [va.SPECIALIST, va.MULTI]


class VendorCapabilityTab(ctk.CTkFrame):
    def __init__(self, master, vendor_store, equipment_store):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = vendor_store
        self.equipment_store = equipment_store
        self.mode = BY_VENDOR
        self.rows = []
        self._build()
        self.refresh()

    # -------------------------------------------------------------- build --
    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew")
        wrap_children(left)
        ctk.CTkLabel(
            left, text="Supply Capability", font=theme.h1_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text="Which vendor can supply which kind of equipment - read "
                       "from every machine they have ever had on site.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        primary_button(actions, "Export (.xlsx)", self.export, width=150).pack(side="left")

        # The view switch sits on its own full-width row, left-aligned with
        # the controls it drives. A switch tucked into the top-right corner
        # is the one people miss.
        switch_row = ctk.CTkFrame(self, fg_color="transparent")
        switch_row.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(
            switch_row, text="VIEW", font=theme.label_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 10))
        self.mode_switch = ctk.CTkSegmentedButton(
            switch_row, values=[BY_VENDOR, BY_EQUIPMENT],
            command=self._on_mode_change,
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.BG_CARD_ALT, unselected_hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY, font=theme.font(12, "bold"), height=34,
        )
        self.mode_switch.set(BY_VENDOR)
        self.mode_switch.pack(side="left")

        self.summary_pill = pill(switch_row, "")
        self.summary_pill.pack(side="left", padx=14)

        self._build_filters()
        self._build_table()

    def _build_filters(self):
        box = card(self, fg_color=theme.BG_CARD)
        box.pack(fill="x", padx=20, pady=(0, 10))
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)

        search_holder = ctk.CTkFrame(row, fg_color="transparent")
        search_holder.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(
            search_holder, text="Search", font=theme.font(10),
            text_color=theme.TEXT_MUTED, anchor="w",
        ).pack(anchor="w")
        self.search_var = ctk.StringVar()
        self.search_var.trace_add(
            "write", lambda *a: debounce(self, "_cap_search_after", 220, self.refresh)
        )
        ctk.CTkEntry(
            search_holder, textvariable=self.search_var, width=230, height=32,
            placeholder_text="Vendor or equipment...",
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
        ).pack(anchor="w")

        self.equipment_filter = FilterDropdown(
            row, "Equipment Type", on_change=self.refresh, width=210
        )
        self.equipment_filter.pack(side="left", padx=(0, 16))

        self.profile_filter = FilterDropdown(
            row, "Supplier Profile", on_change=self.refresh, width=180
        )
        self.profile_filter.pack(side="left", padx=(0, 16))

        secondary_button(row, "Reset", self.reset_filters, width=100).pack(side="left")

        view = ctk.CTkFrame(row, fg_color="transparent")
        view.pack(side="right")
        ctk.CTkLabel(
            view, text="Row height:", font=theme.font(10), text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))
        self.row_height_var = ctk.StringVar(value=ROW_HEIGHT_DEFAULT)
        ctk.CTkOptionMenu(
            view, variable=self.row_height_var,
            values=[name for name, _px in ROW_HEIGHT_CHOICES],
            command=lambda *_: self.table.set_row_height(
                dict(ROW_HEIGHT_CHOICES)[self.row_height_var.get()]
            ),
            width=120, height=28, fg_color=theme.BG_INPUT,
            button_color=theme.BG_CARD_ALT, button_hover_color=theme.BG_HOVER,
            dropdown_fg_color=theme.BG_CARD_ALT, font=theme.font(10),
            dropdown_font=theme.font(10),
        ).pack(side="left")

    def _build_table(self):
        wrap = card(self, fg_color=theme.BG_CARD)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(wrap, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        self.table_title = ctk.CTkLabel(
            head, text="", font=theme.h2_font(), text_color=theme.TEXT_PRIMARY
        )
        self.table_title.pack(side="left")
        self.table_count = ctk.CTkLabel(
            head, text="", font=theme.small_font(), text_color=theme.TEXT_MUTED
        )
        self.table_count.pack(side="left", padx=12)

        self.table_holder = ctk.CTkFrame(wrap, fg_color="transparent")
        self.table_holder.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.table_holder.grid_rowconfigure(0, weight=1)
        self.table_holder.grid_columnconfigure(0, weight=1)
        self.table = None
        self._rebuild_table()

    def _rebuild_table(self):
        """The two views have different columns, so the grid is rebuilt when
        the view changes rather than being reshaped in place."""
        if self.table is not None:
            self.table.destroy()
        report = self._empty_report()
        self.table = EditableTable(
            self.table_holder, report.columns, report.headers(), report.widths,
        )
        self.table.grid(row=0, column=0, sticky="nsew")

    def _empty_report(self):
        if self.mode == BY_VENDOR:
            return va.capability_report([])
        return va.type_report([])

    # ------------------------------------------------------------ filters --
    def _on_mode_change(self, value):
        self.mode = value
        self._rebuild_table()
        self.refresh()

    def reset_filters(self):
        self.search_var.set("")
        self.equipment_filter.clear()
        self.profile_filter.clear()
        self.refresh()

    def _matches(self, row, needle):
        if not needle:
            return True
        return any(needle in str(row.get(key, "")).lower() for key in row
                   if not key.startswith("_"))

    # ------------------------------------------------------------ refresh --
    def refresh(self):
        if self.table is None:
            return
        caps = va.capability_rows(self.store, self.equipment_store)
        summary = va.capability_summary(caps)
        self.summary_pill.configure(
            text=f"{summary['suppliers']:,} suppliers  •  "
                 f"{summary['specialists']:,} specialist  •  "
                 f"{summary['multi']:,} multi-equipment"
        )

        kinds = sorted({kind for row in caps for kind in row["_types"]}, key=str.lower)
        self.equipment_filter.set_values(kinds)
        self.profile_filter.set_values(PROFILE_VALUES)

        wanted_kinds = self.equipment_filter.selected
        needle = self.search_var.get().strip().lower()

        if self.mode == BY_VENDOR:
            rows = caps
            if wanted_kinds:
                rows = [r for r in rows if any(
                    self.equipment_filter.matches(kind) for kind in r["_types"]
                )]
            if self.profile_filter.selected:
                rows = [r for r in rows if self.profile_filter.matches(r["profile"])]
            rows = [r for r in rows if self._matches(r, needle)]
            rows = [dict(r, sr_no=i) for i, r in enumerate(rows, start=1)]
            report = va.capability_report(rows)
            self.table_title.configure(text="Vendors and what they can supply")
        else:
            rows = va.type_rows(self.store, self.equipment_store)
            if wanted_kinds:
                rows = [r for r in rows if self.equipment_filter.matches(r["equipment_type"])]
            rows = [r for r in rows if self._matches(r, needle)]
            rows = [dict(r, sr_no=i) for i, r in enumerate(rows, start=1)]
            report = va.type_report(rows)
            self.table_title.configure(text="Equipment and who can supply it")

        self.rows = rows
        self.report = report
        self.table.clear()
        for index, row in enumerate(report.rows):
            self.table.add_row(index, report.values(row))
        self.table_count.configure(
            text=f"{len(report):,} row{'s' if len(report) != 1 else ''}"
        )

    # ------------------------------------------------------------- export --
    def export(self):
        if not self.rows:
            messagebox.showwarning(
                "No Data", "Nothing matches the current filters.", parent=self
            )
            return
        stem = "Vendor_Supply_Capability" if self.mode == BY_VENDOR else "Equipment_Supply_Coverage"
        default = f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return
        export_report_to_excel(self.report, path)
        notify(self, f"{len(self.rows):,} row(s) exported to:\n{path}")
