"""Tab 3: Master Data Records - directory view, live filter, editor, export."""

from datetime import datetime
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk

from vendor_app.config import KEYS, LABELS
from vendor_app.export import export_records_to_excel
from vendor_app.gui.edit_dialog import EditVendorDialog
from vendor_app.gui.style import apply_dark_treeview_style


class MasterTab(ctk.CTkFrame):
    def __init__(self, master, store, on_data_changed=None):
        super().__init__(master, fg_color="transparent")
        self.store = store
        self.on_data_changed = on_data_changed
        self._build()
        self.refresh()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(top, text="Master Data Records", font=ctk.CTkFont(size=16, weight="bold")).pack(
            side="left"
        )

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh())
        ctk.CTkEntry(
            top, textvariable=self.search_var, placeholder_text="Search by Vendor Name or Code...", width=280
        ).pack(side="left", padx=16)

        ctk.CTkButton(top, text="Export All (.xlsx)", command=self.export_all).pack(side="right", padx=4)
        ctk.CTkButton(top, text="Edit Selected", command=self.edit_selected).pack(side="right", padx=4)
        self.count_label = ctk.CTkLabel(top, text="", text_color="#9a9a9a")
        self.count_label.pack(side="right", padx=16)

        apply_dark_treeview_style()
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ["sr_no"] + KEYS
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", style="Dark.Treeview")
        self.tree.heading("sr_no", text="Sr. No.")
        self.tree.column("sr_no", width=60, anchor="center")
        for key in KEYS:
            self.tree.heading(key, text=LABELS[key])
            self.tree.column(key, width=140, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

    def refresh(self):
        query = self.search_var.get() if hasattr(self, "search_var") else ""
        records = self.store.search(query)

        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, record in enumerate(records, start=1):
            self.tree.insert(
                "", "end", iid=record["vendor_code"], values=[i] + [record.get(k, "") for k in KEYS]
            )

        self.count_label.configure(text=f"{len(records)} record(s)")

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
