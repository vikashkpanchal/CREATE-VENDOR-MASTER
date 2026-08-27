"""Equipment Master dashboard - interactive analytics.

Every filter feeds one shared query, and everything on screen (KPI tiles,
both ranking charts, the RO/RH split and the results table) is recomputed
from that same filtered set, so what you see always agrees with itself.
The filtered rows are exportable exactly as shown.
"""

from datetime import datetime
from collections import Counter
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vendor_app.config import (
    EQUIPMENT_COLUMN_WIDTHS, EQUIPMENT_KEYS, EQUIPMENT_LABELS, EQUIPMENT_WRAPPED_LABELS,
    FLEET_ALL, FLEET_DEMOB, FLEET_RUNNING, FLEET_FILTER_VALUES,
)
from vendor_app.equipment import is_demobbed
from vendor_app.export import export_equipment_to_excel
from vendor_app.gui import theme
from vendor_app.gui.charts import BarChart, SplitBar
from vendor_app.gui.editable_table import EditableTable
from vendor_app.gui.filter_dropdown import FilterDropdown
from vendor_app.gui.toast import notify
from vendor_app.gui.util import debounce
from vendor_app.gui.widgets import card, primary_button, secondary_button

TABLE_COLUMNS = ["sr_no"] + EQUIPMENT_KEYS
TOP_N = 10

# The dimensions offered as Excel-style multi-select filters.
FILTER_FIELDS = [
    ("vendor_name", "Vendor"),
    ("equipment_description", "Equipment"),
    ("capacity", "Capacity"),
    ("ro_rh", "RO/RH"),
    ("plant", "Plant"),
    ("plant_code", "Plant Code"),
]


class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, equipment_store):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = equipment_store
        self.filtered = []
        self._filters = {}
        self._build()
        self.refresh()

    # -------------------------------------------------------------- build --
    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 10))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Equipment Analytics", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text="Filter the fleet and see who supplies what, at a glance.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        secondary_button(actions, "Reset Filters", self.reset_filters, width=130).pack(
            side="left", padx=(0, 8)
        )
        primary_button(actions, "Export Filtered (.xlsx)", self.export_filtered, width=190).pack(
            side="left"
        )

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.body = body

        self._build_filters(body)
        self._build_kpis(body)
        self._build_charts(body)
        self._build_table(body)

    def _build_filters(self, parent):
        box = card(parent, fg_color=theme.BG_CARD)
        box.pack(fill="x", pady=(0, 12))
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        # A wrapping grid, not one long row: on a laptop screen a single row
        # would push the last filters (Plant, Plant Code) off the edge.
        self._filter_cells = []

        search_holder = ctk.CTkFrame(row, fg_color="transparent")
        self._filter_cells.append(search_holder)
        ctk.CTkLabel(
            search_holder, text="Search", font=theme.font(10),
            text_color=theme.TEXT_MUTED, anchor="w",
        ).pack(anchor="w")
        self.search_var = ctk.StringVar()
        self.search_var.trace_add(
            "write", lambda *a: debounce(self, "_dash_search_after", 220, self.refresh)
        )
        ctk.CTkEntry(
            search_holder, textvariable=self.search_var, width=175, height=32,
            placeholder_text="Any field...",
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
        ).pack()

        # Fleet state is a single-choice filter and defaults to Running, so
        # the dashboard describes the fleet actually on site.
        fleet_holder = ctk.CTkFrame(row, fg_color="transparent")
        self._filter_cells.append(fleet_holder)
        ctk.CTkLabel(
            fleet_holder, text="Fleet", font=theme.font(10),
            text_color=theme.TEXT_MUTED, anchor="w",
        ).pack(anchor="w")
        self.fleet_var = ctk.StringVar(value=FLEET_RUNNING)
        ctk.CTkOptionMenu(
            fleet_holder, variable=self.fleet_var, values=FLEET_FILTER_VALUES,
            command=lambda *_: self.refresh(), width=175, height=32,
            fg_color=theme.BG_INPUT, button_color=theme.BG_CARD_ALT,
            button_hover_color=theme.BG_HOVER, dropdown_fg_color=theme.BG_CARD_ALT,
            font=theme.small_font(),
        ).pack()

        for key, label in FILTER_FIELDS:
            dropdown = FilterDropdown(row, label, on_change=self.refresh, width=175)
            self._filter_cells.append(dropdown)
            self._filters[key] = dropdown

        self._filter_row = row
        row.bind("<Configure>", lambda e: self._layout_filters(e.width))
        self._layout_filters(0)

    def _layout_filters(self, available_width):
        """Re-flow the filter controls into as many columns as will fit."""
        cell_width = 190
        columns = max(1, (available_width or 1200) // cell_width)
        if getattr(self, "_filter_columns", None) == columns:
            return
        self._filter_columns = columns
        for index, widget in enumerate(self._filter_cells):
            widget.grid(
                row=index // columns, column=index % columns,
                padx=(0, 12), pady=(0, 8), sticky="w",
            )

    def _build_kpis(self, parent):
        strip = ctk.CTkFrame(parent, fg_color="transparent")
        strip.pack(fill="x", pady=(0, 12))
        self.kpi = {}
        self.kpi_titles = {}
        for key, label in (
            ("equipment", "Running Equipment"),
            ("vendors", "Suppliers"),
            ("categories", "Equipment Types"),
            ("plants", "Plants"),
            ("expiring", "Validity < 30 days"),
        ):
            box = card(strip, fg_color=theme.BG_CARD)
            box.pack(side="left", fill="x", expand=True, padx=(0, 10))
            title_label = ctk.CTkLabel(
                box, text=label, font=theme.small_font(), text_color=theme.TEXT_SECONDARY
            )
            title_label.pack(anchor="w", padx=16, pady=(14, 0))
            value = ctk.CTkLabel(
                box, text="0", font=theme.display_font(), text_color=theme.TEXT_PRIMARY
            )
            value.pack(anchor="w", padx=16, pady=(0, 14))
            self.kpi[key] = value
            self.kpi_titles[key] = title_label

    def _build_charts(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))

        left = card(row, fg_color=theme.BG_CARD)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.vendor_chart = BarChart(left, f"Top {TOP_N} suppliers by equipment supplied")
        self.vendor_chart.pack(fill="both", expand=True)

        right = card(row, fg_color=theme.BG_CARD)
        right.pack(side="left", fill="both", expand=True)
        self.category_chart = BarChart(right, f"Top {TOP_N} equipment types")
        self.category_chart.pack(fill="both", expand=True)

        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 12))

        split_box = card(row2, fg_color=theme.BG_CARD)
        split_box.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.split = SplitBar(split_box, "RO vs RH split")
        self.split.pack(fill="x")

        cap_box = card(row2, fg_color=theme.BG_CARD)
        cap_box.pack(side="left", fill="both", expand=True)
        self.capacity_chart = BarChart(cap_box, f"Top {TOP_N} capacities")
        self.capacity_chart.pack(fill="both", expand=True)

    def _build_table(self, parent):
        box = card(parent, fg_color=theme.BG_CARD)
        box.pack(fill="both", expand=True)
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(
            head, text="Filtered equipment", font=theme.h2_font(), text_color=theme.TEXT_PRIMARY
        ).pack(side="left")
        self.table_count = ctk.CTkLabel(
            head, text="", font=theme.small_font(), text_color=theme.TEXT_MUTED
        )
        self.table_count.pack(side="left", padx=12)

        self.table = EditableTable(
            box, TABLE_COLUMNS, EQUIPMENT_WRAPPED_LABELS, EQUIPMENT_COLUMN_WIDTHS, height=10
        )
        self.table.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    # ------------------------------------------------------------ filters --
    def _fleet_base(self):
        """Records allowed by the fleet-state filter alone."""
        choice = self.fleet_var.get() if hasattr(self, "fleet_var") else FLEET_RUNNING
        if choice == FLEET_RUNNING:
            return self.store.running_records()
        if choice == FLEET_DEMOB:
            return self.store.demob_records()
        return self.store.all_records()

    def _search_ok(self, record, query):
        return not query or any(
            query in str(record.get(k, "")).lower() for k in EQUIPMENT_KEYS
        )

    def _narrow(self, records, exclude=None):
        """Apply every dimension filter except `exclude`.

        Excluding one filter is what makes the set cascade like Excel: a
        filter's own options are computed from the rows that survive all the
        OTHER filters, so it always offers exactly the values still reachable.
        """
        for key, dropdown in self._filters.items():
            if key == exclude:
                continue
            if dropdown.selected:
                records = [r for r in records if dropdown.matches(str(r.get(key, "")).strip())]
        return records

    def _refresh_filter_options(self):
        """Re-offer each filter the values still reachable through the others."""
        base = [r for r in self._fleet_base()
                if self._search_ok(r, self.search_var.get().strip().lower())]
        changed = False
        for key, dropdown in self._filters.items():
            reachable = sorted({
                str(r.get(key, "")).strip()
                for r in self._narrow(base, exclude=key)
                if str(r.get(key, "")).strip()
            })
            # A selection that is no longer reachable is dropped, which stops
            # cascading filters from locking into an empty result.
            changed = dropdown.set_values(reachable) or changed
        return changed

    def _apply_filters(self):
        records = [r for r in self._fleet_base()
                   if self._search_ok(r, self.search_var.get().strip().lower())]
        return self._narrow(records)

    def reset_filters(self):
        self.search_var.set("")
        self.fleet_var.set(FLEET_RUNNING)
        for dropdown in self._filters.values():
            dropdown.clear()
        self.refresh()

    # ------------------------------------------------------------ refresh --
    def refresh(self):
        if not hasattr(self, "table"):
            return
        self._refresh_filter_options()
        records = self._apply_filters()
        self.filtered = records

        self.kpi["equipment"].configure(text=f"{len(records):,}")
        self.kpi_titles["equipment"].configure(text=self._fleet_kpi_label())
        self.kpi["vendors"].configure(
            text=f"{len({r.get('vendor_code') for r in records if r.get('vendor_code')}):,}"
        )
        self.kpi["categories"].configure(
            text=f"{len({r.get('equipment_description') for r in records if r.get('equipment_description')}):,}"
        )
        self.kpi["plants"].configure(
            text=f"{len({r.get('plant') for r in records if r.get('plant')}):,}"
        )
        self.kpi["expiring"].configure(text=f"{self._expiring_count(records):,}")

        self.vendor_chart.set_data(self._top(records, "vendor_name"))
        self.category_chart.set_data(self._top(records, "equipment_description"))
        self.capacity_chart.set_data(self._top(records, "capacity"))

        ro_rh = Counter(
            (r.get("ro_rh") or "Unspecified").strip().upper() or "Unspecified" for r in records
        )
        self.split.set_data([
            ("RO", ro_rh.get("RO", 0)),
            ("RH", ro_rh.get("RH", 0)),
            ("Unspecified", sum(v for k, v in ro_rh.items() if k not in ("RO", "RH"))),
        ])

        self.table.clear()
        for i, record in enumerate(records[:500], start=1):
            self.table.add_row(i - 1, [i] + [record.get(k, "") for k in EQUIPMENT_KEYS])
        shown = min(len(records), 500)
        self.table_count.configure(
            text=f"showing {shown:,} of {len(records):,}"
            + ("  •  export for the full set" if len(records) > shown else "")
        )

    def _fleet_kpi_label(self):
        choice = self.fleet_var.get()
        if choice == FLEET_RUNNING:
            return "Running Equipment"
        if choice == FLEET_DEMOB:
            return "De-mob Equipment"
        return "Equipment Shown"

    @staticmethod
    def _top(records, key, limit=TOP_N):
        counts = Counter(
            str(r.get(key, "")).strip() for r in records if str(r.get(key, "")).strip()
        )
        return counts.most_common(limit)

    @staticmethod
    def _expiring_count(records):
        """Contracts whose validity ends within 30 days (or already has)."""
        today = datetime.now().date()
        count = 0
        for record in records:
            raw = str(record.get("validity_end_date", "")).strip()
            if not raw:
                continue
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d"):
                try:
                    end = datetime.strptime(raw, fmt).date()
                except ValueError:
                    continue
                if (end - today).days <= 30:
                    count += 1
                break
        return count

    # ------------------------------------------------------------- export --
    def export_filtered(self):
        if not self.filtered:
            messagebox.showwarning("No Data", "No equipment matches the current filters.")
            return
        default = f"Equipment_Analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return
        export_equipment_to_excel(self.filtered, path)
        notify(self, f"{len(self.filtered):,} filtered row(s) exported to:\n{path}")
