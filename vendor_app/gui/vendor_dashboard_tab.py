"""Vendor Master dashboard - who is on the master, and in what state.

The figures answer the questions asked of a supplier list: how many are
active, how many are CAD against MARKET, who has no email address on file,
and who has nothing running on site. Every tile opens the rows behind it,
exactly as the equipment dashboard does, and every list exports.

The one action on this screen is Sync Vendor Status, which brings the
master in line with the equipment master: a vendor is Active while a
machine of theirs is running and Inactive once none is. It is a button
rather than something automatic, so a status never changes under somebody
who is looking at it.
"""

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vendor_app import vendor_analytics as va
from vendor_app.export import export_records_to_excel
from vendor_app.gui import theme
from vendor_app.gui.charts import BarChart, PieChart, SplitBar
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, primary_button, secondary_button, wrap_children

TOP_N = 10


class VendorDashboardTab(ctk.CTkFrame):
    # Eight tiles, laid out the way the equipment dashboard lays out its
    # seven: fixed-width cells, the column count read from the panel's real
    # width, never more than two rows deep so nothing runs off a 14" screen.
    KPI_WIDTH = 200
    MAX_KPI_ROWS = 2

    def __init__(self, master, vendor_store, equipment_store, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = vendor_store
        self.equipment_store = equipment_store
        self.on_data_changed = on_data_changed
        self.figures = {}
        self._build()
        self.refresh()

    # -------------------------------------------------------------- build --
    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew")
        wrap_children(left)
        ctk.CTkLabel(
            left, text="Vendor Analytics", font=theme.h1_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text="Who is on the master, what state they are in, and who "
                       "has nothing running on site.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        secondary_button(actions, "Sync Vendor Status", self.sync_status, width=175).pack(
            side="left", padx=(0, 8)
        )
        primary_button(actions, "Export Vendors (.xlsx)", self.export_all, width=190).pack(
            side="left"
        )

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.body = body

        self._build_status_banner(body)
        self._build_kpis(body)
        self._build_charts(body)

    def _build_status_banner(self, parent):
        """The one line that says the master and the fleet disagree.

        It only appears when they actually do - a banner that is always
        there is one nobody reads.
        """
        self.banner = card(parent, fg_color=theme.BG_CARD_ALT)
        row = ctk.CTkFrame(self.banner, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)
        self.banner_label = ctk.CTkLabel(
            row, text="", font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            anchor="w", justify="left", wraplength=820,
        )
        self.banner_label.pack(side="left")
        secondary_button(row, "Sync Now", self.sync_status, width=110).pack(
            side="right", padx=(12, 0)
        )

    def _build_kpis(self, parent):
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.pack(fill="x", pady=(0, 12))
        self._kpi_holder = holder
        self._kpi_cells = []
        self._kpi_columns = None
        self.kpi = {}
        for key in va.FIGURE_ORDER:
            label = va.FIGURE_TITLES[key][0]
            box = card(holder, fg_color=theme.BG_CARD)
            title_label = ctk.CTkLabel(
                box, text=label, font=theme.small_font(),
                text_color=theme.TEXT_SECONDARY, anchor="w", justify="left",
                wraplength=self.KPI_WIDTH - 34,
            )
            title_label.pack(anchor="w", padx=16, pady=(14, 0))
            value = ctk.CTkLabel(
                box, text="0", font=theme.display_font(), text_color=theme.TEXT_PRIMARY
            )
            value.pack(anchor="w", padx=16, pady=(0, 2))
            hint = ctk.CTkLabel(
                box, text="double-click to view", font=theme.font(9),
                text_color=theme.TEXT_MUTED,
            )
            hint.pack(anchor="w", padx=16, pady=(0, 12))
            for widget in (box, title_label, value, hint):
                widget.bind("<Button-1>", lambda e, k=key: self.open_kpi(k))
                widget.bind("<Double-Button-1>", lambda e, k=key: self.open_kpi(k))
                widget.configure(cursor="hand2")
            box.bind("<Enter>", lambda e, b=box: b.configure(border_color=theme.ACCENT))
            box.bind("<Leave>", lambda e, b=box: b.configure(border_color=theme.BORDER_SOFT))
            self.kpi[key] = value
            self._kpi_cells.append(box)

        holder.bind("<Configure>", lambda e: self._layout_kpis(e.width))
        self.after(60, lambda: self._layout_kpis(holder.winfo_width()))

    def _layout_kpis(self, available_width):
        usable = max(0, available_width or 0)
        cap = -(-len(self._kpi_cells) // self.MAX_KPI_ROWS)      # ceil
        if usable < self.KPI_WIDTH:
            columns = 1 if usable else cap
        else:
            columns = max(1, min(cap, usable // self.KPI_WIDTH))
        if self._kpi_columns == columns:
            return
        self._kpi_columns = columns
        for index, box in enumerate(self._kpi_cells):
            box.grid(row=index // columns, column=index % columns,
                     padx=(0, 10), pady=(0, 10), sticky="ew")
        for column in range(columns):
            self._kpi_holder.grid_columnconfigure(
                column, weight=1, minsize=self.KPI_WIDTH, uniform="vkpi"
            )
        for column in range(columns, len(self._kpi_cells)):
            self._kpi_holder.grid_columnconfigure(column, weight=0, minsize=0, uniform="")

    def _build_charts(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))

        left = card(row, fg_color=theme.BG_CARD)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.status_chart = PieChart(
            left, "Vendors by status",
            colors={"Active": "#34b871", "Inactive": "#8a94a6", "Blocked": "#d95926"},
        )
        self.status_chart.pack(fill="both", expand=True)

        right = card(row, fg_color=theme.BG_CARD)
        right.pack(side="left", fill="both", expand=True)
        self.type_split = SplitBar(right, "CAD vs MARKET")
        self.type_split.pack(fill="x")
        self.email_split = SplitBar(right, "Email ID on file")
        self.email_split.pack(fill="x", pady=(4, 0))

        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 12))

        supply_box = card(row2, fg_color=theme.BG_CARD)
        supply_box.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.supply_chart = BarChart(
            supply_box, f"Top {TOP_N} vendors by machines running",
            empty_text="No equipment is running yet.",
        )
        self.supply_chart.pack(fill="both", expand=True)

        breadth_box = card(row2, fg_color=theme.BG_CARD)
        breadth_box.pack(side="left", fill="both", expand=True)
        self.breadth_chart = BarChart(
            breadth_box, f"Top {TOP_N} vendors by kinds of equipment supplied",
            empty_text="No equipment has been supplied yet.",
        )
        self.breadth_chart.pack(fill="both", expand=True)

    # ------------------------------------------------------------ refresh --
    def refresh(self):
        if not hasattr(self, "kpi"):
            return
        self.figures = va.figures(self.store, self.equipment_store)
        for key in va.FIGURE_ORDER:
            count, _rows = self.figures.get(key, (0, []))
            self.kpi[key].configure(text=f"{count:,}")

        out_of_step = self.figures.get("status_mismatch", (0, []))[0]
        if out_of_step:
            self.banner_label.configure(
                text=f"{out_of_step:,} vendor(s) disagree with the equipment master. "
                     "A vendor is Active while a machine of theirs is running, and "
                     "Inactive once none is - Blocked vendors are left alone."
            )
            self.banner.pack(fill="x", pady=(0, 12), before=self._kpi_holder)
        else:
            self.banner.pack_forget()

        counts = {}
        for record in self.store.all_records():
            counts[va.status_of(record)] = counts.get(va.status_of(record), 0) + 1
        self.status_chart.set_data(sorted(counts.items(), key=lambda kv: -kv[1]))

        self.type_split.set_data([
            ("CAD", self.figures["cad"][0]),
            ("MARKET", self.figures["market"][0]),
            ("Not set", self.figures["no_type"][0]),
        ])
        self.email_split.set_data([
            ("Email on file", self.figures["total"][0] - self.figures["no_email"][0]),
            ("No email", self.figures["no_email"][0]),
        ])

        caps = va.capability_rows(self.store, self.equipment_store)
        self.supply_chart.set_data([
            (r["vendor_name"] or r["vendor_code"], r["running"])
            for r in sorted(caps, key=lambda r: -r["running"])[:TOP_N] if r["running"]
        ])
        self.breadth_chart.set_data([
            (r["vendor_name"] or r["vendor_code"], r["type_count"])
            for r in caps[:TOP_N]
        ])

    # --------------------------------------------------------- drill-down --
    def open_kpi(self, key):
        """Open the vendors behind one figure, ready to export."""
        from vendor_app.gui.kpi_dialog import KpiDetailDialog
        existing = getattr(self, "_kpi_dialog", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return
        report = va.figure_report(key, self.figures)
        self._kpi_dialog = KpiDetailDialog(
            self, report, figure=self.kpi[key].cget("text"),
            caption=report.note, widths=report.widths,
        )

    # ------------------------------------------------------------- action --
    def sync_status(self):
        """Bring vendor statuses in line with the equipment master."""
        preview = self.store.sync_statuses(dry_run=True)
        if not preview["changed"]:
            notify(self, "Every vendor already agrees with the equipment master.")
            return
        lines = []
        if preview["to_inactive"]:
            lines.append(f"{preview['to_inactive']:,} vendor(s) will be set Inactive "
                         "- no machine of theirs is running.")
        if preview["to_active"]:
            lines.append(f"{preview['to_active']:,} vendor(s) will be set Active "
                         "- a machine of theirs is running.")
        if preview["blocked"]:
            lines.append(f"{preview['blocked']:,} Blocked vendor(s) will be left alone.")
        if not messagebox.askyesno(
            "Sync Vendor Status", "\n".join(lines) + "\n\nApply these changes?",
            parent=self,
        ):
            return
        result = self.store.sync_statuses()
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()
        notify(self, f"{result['changed']:,} vendor status(es) updated. "
                     "Every change is in the vendor change log.")

    # ------------------------------------------------------------- export --
    def export_all(self):
        records = self.store.all_records()
        if not records:
            messagebox.showwarning("No Data", "There are no vendors to export.", parent=self)
            return
        default = f"Vendor_Analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return
        export_records_to_excel(records, path)
        notify(self, f"{len(records):,} vendor(s) exported to:\n{path}")
