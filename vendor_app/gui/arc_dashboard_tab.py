"""ARC & FO Management Dashboard.

Laid out in the order the questions get asked:

    KPI cards
    ARC Expiry Analysis          status, release position, trend, what expires in 30 days
    FO Expiry Analysis           the same, for the frame orders
    ARC Without FO               a contract with nothing ordered against it
    Pending Approval             release indicator S - nothing can be ordered yet
    ARC vs FO Value Difference   target 10 Cr - released 6 Cr leaves 4 Cr to order
    Vendor Analysis              contracts vs frame orders, per vendor
    High Risk                    expiring soon and under-ordered
    Export Reports               every table above, as one workbook

Everything on screen comes from one ArcAnalysis built at refresh, so the
cards, the charts and the tables can never disagree with each other. Nothing
is computed twice and nothing is stored - the dashboard is a read of Table 1 and
Table 2 as they stand right now, rolled to the entity each figure belongs
to: a contract is one purchasing document, a frame order is one frame
number, and a repeated header value is never counted or summed twice.
"""

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vendor_app.arc import format_amount
from vendor_app.arc_analytics import ACTIVE, EXPIRED, NO_DATE, WIDTHS, ArcAnalysis
from vendor_app.config import RELEASE_INDICATORS, RELEASE_PENDING, RELEASE_RELEASED
from vendor_app.export import export_arc_analysis_to_excel, export_report_to_excel
from vendor_app.gui import theme
from vendor_app.gui.charts import BarChart, GroupedBarChart, PieChart
from vendor_app.gui.editable_table import EditableTable
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, pill, primary_button, secondary_button

# Status colours carry meaning here, so they are the semantic tokens rather
# than the categorical series hues: expired is a problem, active is not.
STATUS_COLORS = {
    ACTIVE: theme.SUCCESS,
    EXPIRED: theme.DANGER,
    NO_DATE: theme.TEXT_MUTED,
}

# The release indicator is a go/no-go, so it gets the same semantic reading:
# released is usable, pending for approval is not.
RELEASE_COLORS = {
    RELEASE_INDICATORS[RELEASE_RELEASED]: theme.SUCCESS,
    RELEASE_INDICATORS[RELEASE_PENDING]: theme.WARNING,
    "Not stated": theme.TEXT_MUTED,
}

TONE_COLORS = {
    "neutral": theme.TEXT_PRIMARY,
    "good": theme.SUCCESS,
    "warn": theme.WARNING,
    "bad": theme.DANGER,
}

# A report table grows with its content up to this, then scrolls. A fixed
# height would leave an empty seven-row well under a one-row answer, which
# reads as "something is missing" rather than "there is one of these".
MAX_TABLE_ROWS = 8
MIN_TABLE_ROWS = 2


class ArcDashboardTab(ctk.CTkFrame):
    def __init__(self, master, store):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = store
        self.analysis = None
        self._tables = {}      # report key -> (EditableTable, count pill, Report)
        self._build()
        self.refresh()

    # -------------------------------------------------------------- build --
    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 10))
        # grid, not pack: the action buttons get a reserved column, so they
        # cannot be squeezed off the right edge by a long title block.
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            left, text="ARC & FO Management Dashboard", font=theme.h1_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        self.subtitle = ctk.CTkLabel(
            left, text="", font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        )
        self.subtitle.pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        secondary_button(actions, "Refresh", self.refresh, width=110).pack(
            side="left", padx=(0, 8)
        )
        primary_button(
            actions, "Export All Reports (.xlsx)", self.export_all, width=210
        ).pack(side="left")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.body = body

        # One analysis lays the whole page out - the cards' labels, each
        # section's title and every table's columns come from it. refresh()
        # then rebuilds it and pours the current figures into that shape.
        self.analysis = ArcAnalysis(self.store)
        self._build_kpis(body)
        self._build_arc_expiry(body)
        self._build_fo_expiry(body)
        self._build_report_section(body, "arc_without_fo")
        self._build_report_section(body, "pending_release")
        self._build_report_section(body, "value_difference")
        self._build_vendor_section(body)
        self._build_report_section(body, "high_risk_arc")
        self._build_report_section(body, "high_risk_fo")
        self._build_export_section(body)

    # --------------------------------------------------------- KPI cards --
    # Nine cards never fit one row on a laptop, so they reflow the same way
    # the equipment filters do: fixed-width cells, column count computed from
    # the panel's real width. Nothing is ever pushed off the edge.
    KPI_WIDTH = 218

    def _build_kpis(self, parent):
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.pack(fill="x", pady=(0, 14))
        self._kpi_holder = holder
        self._kpi_cards = {}
        self._kpi_cells = []
        self._kpi_columns = None

        for key, label, value, tone in self.analysis.kpis():
            box = card(holder, fg_color=theme.BG_CARD)
            ctk.CTkLabel(
                box, text=label, font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
                anchor="w", justify="left", wraplength=self.KPI_WIDTH - 34,
            ).pack(anchor="w", padx=16, pady=(14, 2))
            figure = ctk.CTkLabel(
                box, text=value, font=theme.display_font(), text_color=TONE_COLORS[tone],
            )
            figure.pack(anchor="w", padx=16, pady=(0, 14))
            self._kpi_cards[key] = figure
            self._kpi_cells.append(box)

        holder.bind("<Configure>", lambda e: self._layout_kpis(e.width))
        self.after(60, lambda: self._layout_kpis(holder.winfo_width()))

    def _layout_kpis(self, available_width):
        usable = max(0, available_width or 0)
        if usable < self.KPI_WIDTH:
            columns = 1 if usable else 3
        else:
            columns = max(1, min(len(self._kpi_cells), usable // self.KPI_WIDTH))
        if self._kpi_columns == columns:
            return
        self._kpi_columns = columns
        for index, box in enumerate(self._kpi_cells):
            box.grid(
                row=index // columns, column=index % columns,
                padx=(0, 10), pady=(0, 10), sticky="ew",
            )
        for column in range(columns):
            self._kpi_holder.grid_columnconfigure(
                column, weight=1, minsize=self.KPI_WIDTH, uniform="kpi"
            )
        # Trailing columns from a wider layout must lose their weight, or the
        # last row of cards keeps stretching into space that is no longer used.
        for column in range(columns, len(self._kpi_cells)):
            self._kpi_holder.grid_columnconfigure(column, weight=0, minsize=0, uniform="")

    # ---------------------------------------------------------- sections --
    def _section(self, parent, title, note=""):
        """A titled card with a reserved right-hand column for its actions."""
        box = card(parent, fg_color=theme.BG_CARD)
        box.pack(fill="x", pady=(0, 14))

        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 8))
        head.grid_columnconfigure(0, weight=1)
        head.grid_columnconfigure(1, weight=0)
        head.grid_columnconfigure(2, weight=0)

        text = ctk.CTkFrame(head, fg_color="transparent")
        text.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            text, text=title, font=theme.h2_font(), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        if note:
            ctk.CTkLabel(
                text, text=note, font=theme.small_font(), text_color=theme.TEXT_MUTED,
                anchor="w", justify="left",
            ).pack(anchor="w", pady=(2, 0))
        return box, head

    def _report_table(self, parent, head, report_key, report):
        """The count badge, per-report export button and read-only grid."""
        count = pill(head, "0 rows")
        count.grid(row=0, column=1, padx=(12, 8))
        secondary_button(
            head, "Export (.xlsx)", lambda k=report_key: self.export_report(k), width=140,
        ).grid(row=0, column=2)

        table = EditableTable(
            parent, report.columns, report.headers(), WIDTHS, height=MIN_TABLE_ROWS,
        )
        table.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._tables[report_key] = (table, count)
        return table

    def _build_report_section(self, parent, report_key):
        report = self.analysis.report(report_key)
        box, head = self._section(parent, report.title, report.note)
        self._report_table(box, head, report_key, report)

    def _build_arc_expiry(self, parent):
        report = self.analysis.report("arc_expiring")
        box, head = self._section(
            parent, "ARC Expiry Analysis",
            "Which contracts are live, which have lapsed, and which need action now.",
        )
        charts = ctk.CTkFrame(box, fg_color="transparent")
        charts.pack(fill="x", padx=16, pady=(0, 6))
        for column in range(3):
            charts.grid_columnconfigure(column, weight=1, uniform="chart")

        self.arc_pie = PieChart(charts, "ARC status", colors=STATUS_COLORS)
        self.arc_pie.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.release_pie = PieChart(
            charts, "Release position", colors=RELEASE_COLORS,
            empty_text="No release indicator on file.",
        )
        self.release_pie.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        self.arc_trend = BarChart(charts, "ARC expiry trend", empty_text="No ARCs yet.")
        self.arc_trend.grid(row=0, column=2, sticky="nsew")

        self._report_table(box, head, "arc_expiring", report)

    def _build_fo_expiry(self, parent):
        report = self.analysis.report("fo_expiring")
        box, head = self._section(
            parent, "FO Expiry Analysis",
            "The same read on the orders: what is running, what has lapsed, "
            "and what needs extending.",
        )
        charts = ctk.CTkFrame(box, fg_color="transparent")
        charts.pack(fill="x", padx=16, pady=(0, 6))
        charts.grid_columnconfigure(0, weight=1, uniform="chart")
        charts.grid_columnconfigure(1, weight=1, uniform="chart")

        self.fo_pie = PieChart(charts, "FO status", colors=STATUS_COLORS)
        self.fo_pie.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.fo_trend = BarChart(charts, "FO expiry trend", empty_text="No FOs yet.")
        self.fo_trend.grid(row=0, column=1, sticky="nsew")

        self._report_table(box, head, "fo_expiring", report)

    def _build_vendor_section(self, parent):
        report = self.analysis.report("vendor_analysis")
        box, head = self._section(parent, report.title, report.note)
        self.vendor_chart = GroupedBarChart(
            box, "ARC value vs FO value by vendor",
            series=("ARC Value", "FO Value"), formatter=format_amount,
            empty_text="No vendor values yet.",
        )
        self.vendor_chart.pack(fill="x", padx=8, pady=(0, 4))
        self._report_table(box, head, "vendor_analysis", report)

    def _build_export_section(self, parent):
        box = card(parent, fg_color=theme.BG_CARD)
        box.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            box, text="Export Reports", font=theme.h2_font(), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            box,
            text="One workbook: the headline analyses on the first sheet, then the "
                 "ARC and FO masters and every table above, each on its own sheet.",
            font=theme.small_font(), text_color=theme.TEXT_MUTED,
            anchor="w", justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        primary_button(
            box, "Export All Reports (.xlsx)", self.export_all, width=220
        ).pack(anchor="w", padx=16, pady=(0, 16))

    # ------------------------------------------------------------ refresh --
    def refresh(self):
        if not self._tables:
            return
        self.analysis = ArcAnalysis(self.store)
        analysis = self.analysis

        for key, _label, value, _tone in analysis.kpis():
            self._kpi_cards[key].configure(text=value)

        self.subtitle.configure(
            text=f"{analysis.total_arc_count():,} ARC(s) worth "
                 f"{format_amount(analysis.total_arc_value())} against "
                 f"{analysis.total_fo_count():,} FO(s) worth "
                 f"{format_amount(analysis.total_fo_value())}  •  as at "
                 f"{analysis.today.strftime('%d-%b-%Y')}"
        )

        self.arc_pie.set_data(analysis.status_counts(analysis.arcs))
        self.release_pie.set_data(analysis.release_counts())
        self.fo_pie.set_data(analysis.status_counts(analysis.fos))
        self.arc_trend.set_data(analysis.expiry_trend(analysis.arcs))
        self.fo_trend.set_data(analysis.expiry_trend(analysis.fos))
        self.vendor_chart.set_data(analysis.vendor_value_series())

        for report in analysis.reports():
            entry = self._tables.get(report.key)
            if entry is None:
                continue
            table, count = entry
            table.clear()
            for index, row in enumerate(report.rows[:200]):
                table.add_row(index, report.values(row))
            shown = min(len(report.rows), 200)
            table.tree.configure(
                height=max(MIN_TABLE_ROWS, min(MAX_TABLE_ROWS, shown))
            )
            text = f"{len(report.rows):,} row{'s' if len(report.rows) != 1 else ''}"
            if shown < len(report.rows):
                text += f" - showing {shown:,}, export for all"
            count.configure(text=f"  {text}  ")

    # ------------------------------------------------------------- export --
    def _ask_path(self, stem):
        default = f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )

    def export_report(self, report_key):
        report = self.analysis.report(report_key)
        if not report.rows:
            messagebox.showinfo("Nothing to Export", f"{report.title} is empty.")
            return
        path = self._ask_path(report.title.replace(" ", "_"))
        if not path:
            return
        export_report_to_excel(report, path)
        notify(self, f"{len(report.rows):,} row(s) exported to:\n{path}")

    def export_all(self):
        if self.analysis is None:
            return
        if not self.analysis.arcs and not self.analysis.fos:
            messagebox.showwarning(
                "No Data", "Import ARC and FO data before exporting the reports."
            )
            return
        path = self._ask_path("ARC_FO_Dashboard")
        if not path:
            return
        export_arc_analysis_to_excel(self.analysis, path)
        notify(self, f"All ARC & FO reports exported to:\n{path}")
