"""Master Data Records: full directory, live filter, editor, export."""

from datetime import datetime
from tkinter import messagebox, filedialog

import customtkinter as ctk

from vendor_app.config import KEYS, WRAPPED_LABELS, COLUMN_WIDTHS
from vendor_app.export import export_records_to_excel
from vendor_app.gui import theme
from vendor_app.gui.edit_dialog import EditVendorDialog
from vendor_app.gui.style import build_table, stripe_rows
from vendor_app.gui.widgets import card, primary_button, secondary_button, pill

COLUMNS = ["sr_no"] + KEYS


class MasterTab(ctk.CTkFrame):
    def __init__(self, master, store, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = store
        self.on_data_changed = on_data_changed
        self._build()
        self.refresh()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 12))

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Master Data Records", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="The complete vendor directory - filter, review and edit any record.",
            font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        secondary_button(actions, "Edit Selected", self.edit_selected).pack(side="left", padx=(0, 8))
        primary_button(actions, "Export All (.xlsx)", self.export_all, width=170).pack(side="left")

        self._build_stat_strip()

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
            width=340,
            height=32,
            fg_color=theme.BG_INPUT,
            border_color=theme.BG_INPUT_BORDER,
        ).pack(side="left")
        self.count_pill = pill(toolbar, "0 records")
        self.count_pill.pack(side="left", padx=12)

        table_wrap = card(self, fg_color=theme.BG_CARD)
        table_wrap.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        outer, self.tree = build_table(table_wrap, COLUMNS, WRAPPED_LABELS, COLUMN_WIDTHS)
        outer.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

    def _build_stat_strip(self):
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", padx=20, pady=(0, 14))

        self.stat_total = self._stat_card(strip, "Total Vendors")
        self.stat_owner = self._stat_card(strip, "With Owner Contact")
        self.stat_supervisor = self._stat_card(strip, "With Supervisor Contact")
        self.stat_multi_email = self._stat_card(strip, "With Multiple Emails")

    def _stat_card(self, parent, title):
        box = card(parent, fg_color=theme.BG_CARD)
        box.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkLabel(box, text=title, font=theme.small_font(), text_color=theme.TEXT_SECONDARY).pack(
            anchor="w", padx=16, pady=(14, 0)
        )
        value_label = ctk.CTkLabel(box, text="0", font=theme.display_font(), text_color=theme.TEXT_PRIMARY)
        value_label.pack(anchor="w", padx=16, pady=(0, 14))
        return value_label

    def refresh(self):
        from vendor_app.validators import split_emails

        query = self.search_var.get() if hasattr(self, "search_var") else ""
        records = self.store.search(query)

        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, record in enumerate(records, start=1):
            self.tree.insert(
                "", "end", iid=record["vendor_code"], values=[i] + [record.get(k, "") for k in KEYS]
            )
        stripe_rows(self.tree)

        self.count_pill.configure(text=f"  {len(records)} record{'s' if len(records) != 1 else ''}  ")

        all_records = self.store.all_records()
        total = len(all_records)
        with_owner = sum(1 for r in all_records if r.get("vendor_owner_contact"))
        with_supervisor = sum(1 for r in all_records if r.get("vendor_supervisor_contact"))
        with_multi_email = sum(1 for r in all_records if len(split_emails(r.get("vendor_email", ""))) > 1)

        self.stat_total.configure(text=str(total))
        self.stat_owner.configure(text=str(with_owner))
        self.stat_supervisor.configure(text=str(with_supervisor))
        self.stat_multi_email.configure(text=str(with_multi_email))

    def edit_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select a Row", "Select a vendor row first (or double-click it).")
            return

        code = selection[0]
        record = self.store.get(code)
        if not record:
            messagebox.showerror("Not Found", "This vendor record no longer exists.")
            self.refresh()
            return

        EditVendorDialog(self, self.store, record, on_saved=self._after_edit)

    def _after_edit(self):
        if self.on_data_changed:
            self.on_data_changed()
        self.refresh()

    def export_all(self):
        records = self.store.all_records()
        if not records:
            messagebox.showwarning("No Data", "There are no vendor records to export.")
            return

        default_name = f"Vendor_Master_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default_name, filetypes=[("Excel Workbook", "*.xlsx")]
        )
        if not path:
            return

        export_records_to_excel(records, path)
        messagebox.showinfo("Exported", f"Master data exported to:\n{path}")
