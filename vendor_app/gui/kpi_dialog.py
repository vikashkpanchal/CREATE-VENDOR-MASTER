"""The pop-up behind a dashboard figure.

Every KPI card is a count or a total of something, and the natural next
question is always "which ones?". Clicking a card opens this: the exact rows
that figure was computed from, in a read-only grid, with the same row-height
control and the same export the other tables have.

It reads the rows it is handed rather than recomputing anything, so what it
shows can never differ from the card that opened it.
"""

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vendor_app.arc_analytics import WIDTHS
from vendor_app.export import export_report_to_excel
from vendor_app.gui import theme
from vendor_app.gui.editable_table import EditableTable
from vendor_app.gui.style import ROW_HEIGHT_CHOICES, ROW_HEIGHT_DEFAULT
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, pill, primary_button, secondary_button


class KpiDetailDialog(ctk.CTkToplevel):
    def __init__(self, master, report, figure="", caption="", widths=None):
        super().__init__(master)
        self.report = report
        # The ARC widths by default; another dashboard hands in its own, so
        # one pop-up serves every set of columns.
        self.widths = widths or getattr(report, "widths", None) or WIDTHS
        self.configure(fg_color=theme.BG_SURFACE)
        self.title(report.title)

        screen_h, screen_w = self.winfo_screenheight(), self.winfo_screenwidth()
        width = min(1280, max(720, screen_w - 120))
        height = min(760, max(420, screen_h - 140))
        self.geometry(
            f"{width}x{height}+{max(0, (screen_w - width) // 2)}"
            f"+{max(0, (screen_h - height) // 4)}"
        )
        self.minsize(680, 380)
        self.transient(master)
        self.grab_set()

        self._build(figure, caption)
        self.after(50, lambda: self.table.tree.focus_set())
        self.bind("<Escape>", lambda e: self.destroy())

    def _build(self, figure, caption):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 8))
        # Reserved column for the buttons, so a long title cannot push them off.
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew")
        title_row = ctk.CTkFrame(left, fg_color="transparent")
        title_row.pack(anchor="w", fill="x")
        ctk.CTkLabel(
            title_row, text=self.report.title, font=theme.h1_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")
        if figure:
            ctk.CTkLabel(
                title_row, text=figure, font=theme.display_font(),
                text_color=theme.ACCENT,
            ).pack(side="left", padx=(14, 0))
        note = caption or self.report.note
        if note:
            ctk.CTkLabel(
                left, text=note, font=theme.small_font(),
                text_color=theme.TEXT_SECONDARY, anchor="w", justify="left",
                wraplength=760,
            ).pack(anchor="w", pady=(4, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        primary_button(actions, "Export (.xlsx)", self.export, width=150).pack(
            side="left", padx=(0, 8)
        )
        secondary_button(actions, "Close", self.destroy, width=100).pack(side="left")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 8))
        self.count_pill = pill(
            toolbar,
            f"{len(self.report):,} row{'s' if len(self.report) != 1 else ''}",
        )
        self.count_pill.pack(side="left")
        ctk.CTkLabel(
            toolbar,
            text="Arrow keys walk the grid  •  Ctrl+C copies the cell or rows",
            font=theme.font(10), text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=12)

        view = ctk.CTkFrame(toolbar, fg_color="transparent")
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
            width=120, height=26,
            fg_color=theme.BG_INPUT, button_color=theme.BG_CARD_ALT,
            button_hover_color=theme.BG_HOVER, dropdown_fg_color=theme.BG_CARD_ALT,
            font=theme.font(10), dropdown_font=theme.font(10),
        ).pack(side="left")

        wrap = card(self, fg_color=theme.BG_CARD)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.table = EditableTable(
            wrap, self.report.columns, self.report.headers(), self.widths,
        )
        self.table.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        for index, row in enumerate(self.report.rows):
            self.table.add_row(index, self.report.values(row))
        if not self.report.rows:
            ctk.CTkLabel(
                wrap, text="Nothing matches this figure right now.",
                font=theme.body_font(), text_color=theme.TEXT_MUTED,
            ).grid(row=0, column=0)

    def export(self):
        if not self.report.rows:
            messagebox.showinfo("Nothing to Export", "This list is empty.", parent=self)
            return
        default = (f"{self.report.title.replace(' ', '_')}_"
                   f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")], parent=self,
        )
        if not path:
            return
        export_report_to_excel(self.report, path)
        notify(self.master, f"{len(self.report):,} row(s) exported to:\n{path}")
