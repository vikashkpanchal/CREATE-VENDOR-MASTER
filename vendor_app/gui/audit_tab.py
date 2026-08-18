"""Audit Log: SAP/Oracle-style change history for every vendor record.

Every add, field-level update, status change and delete performed through
VendorStore is captured by AuditLog and shown here, newest first, with a
free-text filter and its own Excel export.
"""

from datetime import datetime
from tkinter import messagebox, filedialog

import customtkinter as ctk

from vendor_app.config import AUDIT_COLUMNS, AUDIT_WRAPPED_LABELS, AUDIT_COLUMN_WIDTHS
from vendor_app.export import export_audit_log_to_excel
from vendor_app.validators import normalize
from vendor_app.gui import theme
from vendor_app.gui.style import build_table, insert_row
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, primary_button, pill

ACTION_FILTERS = ["All Actions", "Added", "Updated", "Status Change", "Deleted"]


class AuditLogTab(ctk.CTkFrame):
    def __init__(self, master, audit_log):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.audit_log = audit_log
        self._build()
        self.refresh()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 12))

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Audit Log", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="A complete, append-only change history - every add, update, status change and delete.",
            font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        primary_button(header, "Export Audit Log (.xlsx)", self.export_log, width=200).pack(side="right")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(toolbar, text="Search:", font=theme.small_font(), text_color=theme.TEXT_SECONDARY).pack(
            side="left", padx=(0, 8)
        )
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh())
        ctk.CTkEntry(
            toolbar,
            textvariable=self.search_var,
            placeholder_text="Search by Vendor Name or Vendor Code...",
            width=300,
            height=32,
            fg_color=theme.BG_INPUT,
            border_color=theme.BG_INPUT_BORDER,
        ).pack(side="left")

        ctk.CTkLabel(toolbar, text="Action:", font=theme.small_font(), text_color=theme.TEXT_SECONDARY).pack(
            side="left", padx=(16, 8)
        )
        self.action_filter = ctk.StringVar(value="All Actions")
        ctk.CTkOptionMenu(
            toolbar,
            variable=self.action_filter,
            values=ACTION_FILTERS,
            command=lambda *_: self.refresh(),
            width=160,
            height=32,
            fg_color=theme.BG_INPUT,
            button_color=theme.BG_CARD_ALT,
            button_hover_color=theme.BG_HOVER,
            dropdown_fg_color=theme.BG_CARD_ALT,
        ).pack(side="left")

        self.count_pill = pill(toolbar, "0 entries")
        self.count_pill.pack(side="left", padx=12)

        table_wrap = card(self, fg_color=theme.BG_CARD)
        table_wrap.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        outer, self.tree = build_table(table_wrap, AUDIT_COLUMNS, AUDIT_WRAPPED_LABELS, AUDIT_COLUMN_WIDTHS)
        outer.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

    def _filtered_entries(self):
        entries = self.audit_log.all_entries()
        action = self.action_filter.get() if hasattr(self, "action_filter") else "All Actions"
        if action != "All Actions":
            entries = [e for e in entries if e.get("action") == action]
        q = normalize(self.search_var.get()).lower() if hasattr(self, "search_var") else ""
        if q:
            entries = [
                e for e in entries
                if q in e.get("vendor_code", "").lower() or q in e.get("vendor_name", "").lower()
            ]
        return entries

    def refresh(self):
        entries = self._filtered_entries()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, entry in enumerate(entries):
            insert_row(self.tree, i, values=[entry.get(col, "") for col in AUDIT_COLUMNS])
        self.count_pill.configure(text=f"  {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}  ")

    def export_log(self):
        entries = self._filtered_entries()
        if not entries:
            messagebox.showwarning("No Data", "There are no audit log entries to export.")
            return
        default_name = f"Vendor_Audit_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default_name, filetypes=[("Excel Workbook", "*.xlsx")]
        )
        if not path:
            return
        export_audit_log_to_excel(entries, path)
        notify(self, f"Audit log exported to:\n{path}", kind="success")
