"""Master Data Records: full directory, live filter, status lifecycle,
sortable columns, editor, export."""

from datetime import datetime
from tkinter import messagebox, filedialog

import customtkinter as ctk

from vendor_app.config import DISPLAY_COLUMNS, STATUS_VALUES, WRAPPED_LABELS, COLUMN_WIDTHS
from vendor_app.export import export_records_to_excel
from vendor_app.gui import theme
from vendor_app.gui.edit_dialog import EditVendorDialog
from vendor_app.gui.style import build_table, insert_row, set_heading_text
from vendor_app.gui.toast import notify
from vendor_app.gui.util import debounce
from vendor_app.gui.widgets import card, primary_button, secondary_button, danger_button, pill

COLUMNS = ["sr_no"] + DISPLAY_COLUMNS


class MasterTab(ctk.CTkFrame):
    def __init__(self, master, store, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = store
        self.on_data_changed = on_data_changed
        self._sort_key = None
        self._sort_desc = False
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
            text="The complete vendor directory - filter, sort, review and edit any record.",
            font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        primary_button(actions, "+ Add Vendor", self.add_vendor, width=140).pack(side="left", padx=(0, 8))
        secondary_button(actions, "Edit Selected", self.edit_selected).pack(side="left", padx=(0, 8))
        primary_button(actions, "Export All (.xlsx)", self.export_all, width=170).pack(side="left")

        self._build_stat_strip()

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(toolbar, text="Search:", font=theme.small_font(), text_color=theme.TEXT_SECONDARY).pack(
            side="left", padx=(0, 8)
        )
        self.search_var = ctk.StringVar()
        self.search_var.trace_add(
            "write", lambda *args: debounce(self, "_search_after_id", 200, self.refresh)
        )
        ctk.CTkEntry(
            toolbar,
            textvariable=self.search_var,
            placeholder_text="Search by Vendor Name or Vendor Code...",
            width=300,
            height=32,
            fg_color=theme.BG_INPUT,
            border_color=theme.BG_INPUT_BORDER,
        ).pack(side="left")

        ctk.CTkLabel(toolbar, text="Status:", font=theme.small_font(), text_color=theme.TEXT_SECONDARY).pack(
            side="left", padx=(16, 8)
        )
        self.status_filter = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            toolbar,
            variable=self.status_filter,
            values=["All"] + STATUS_VALUES,
            command=lambda *_: self.refresh(),
            width=130,
            height=32,
            fg_color=theme.BG_INPUT,
            button_color=theme.BG_CARD_ALT,
            button_hover_color=theme.BG_HOVER,
            dropdown_fg_color=theme.BG_CARD_ALT,
        ).pack(side="left")

        self.count_pill = pill(toolbar, "0 records")
        self.count_pill.pack(side="left", padx=12)

        row_actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        row_actions.pack(side="right")
        danger_button(row_actions, "Delete Permanently", self.delete_selected, width=170).pack(
            side="left", padx=(8, 0)
        )
        self.toggle_status_btn = secondary_button(
            row_actions, "Deactivate Selected", self.toggle_status_selected, width=170
        )
        self.toggle_status_btn.pack(side="left")

        table_wrap = card(self, fg_color=theme.BG_CARD)
        table_wrap.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        outer, self.tree = build_table(table_wrap, COLUMNS, WRAPPED_LABELS, COLUMN_WIDTHS, on_sort=self._on_sort)
        outer.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_toggle_label())

    def _build_stat_strip(self):
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", padx=20, pady=(0, 14))

        self.stat_total = self._stat_card(strip, "Total Vendors")
        self.stat_active = self._stat_card(strip, "🟢 Active")
        self.stat_inactive = self._stat_card(strip, "⚪ Inactive")
        self.stat_blocked = self._stat_card(strip, "🔴 Blocked")

    def _stat_card(self, parent, title):
        box = card(parent, fg_color=theme.BG_CARD)
        box.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkLabel(box, text=title, font=theme.small_font(), text_color=theme.TEXT_SECONDARY).pack(
            anchor="w", padx=16, pady=(14, 0)
        )
        value_label = ctk.CTkLabel(box, text="0", font=theme.display_font(), text_color=theme.TEXT_PRIMARY)
        value_label.pack(anchor="w", padx=16, pady=(0, 14))
        return value_label

    # ------------------------------------------------------------ sorting --
    def _on_sort(self, key):
        if key == "sr_no":
            return
        if self._sort_key == key:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_key = key
            self._sort_desc = False
        self.refresh()

    def _row_values(self, record):
        values = []
        for key in DISPLAY_COLUMNS:
            if key == "status":
                values.append(theme.format_status(record.get("status", "Active")))
            else:
                values.append(record.get(key, ""))
        return values

    # ------------------------------------------------------------ refresh --
    def refresh(self):
        query = self.search_var.get() if hasattr(self, "search_var") else ""
        status = self.status_filter.get() if hasattr(self, "status_filter") else "All"
        records = self.store.search(query, status=status)

        if self._sort_key:
            records = sorted(
                records, key=lambda r: r.get(self._sort_key, "").lower(), reverse=self._sort_desc
            )

        selected_code = self._selected_code()

        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, record in enumerate(records, start=1):
            insert_row(
                self.tree, i - 1, status=record.get("status", "Active"),
                iid=record["vendor_code"], values=[i] + self._row_values(record),
            )
        set_heading_text(self.tree, COLUMNS, WRAPPED_LABELS, self._sort_key, self._sort_desc)

        if selected_code and self.tree.exists(selected_code):
            self.tree.selection_set(selected_code)

        self.count_pill.configure(text=f"  {len(records)} record{'s' if len(records) != 1 else ''}  ")

        # Single pass over all records for every stat, rather than one
        # full pass per status (this ran on every keystroke before the
        # search box was debounced, so it's worth keeping cheap).
        counts = {"Active": 0, "Inactive": 0, "Blocked": 0}
        total = 0
        for r in self.store.all_records():
            total += 1
            status = r.get("status", "Active")
            counts[status] = counts.get(status, 0) + 1
        self.stat_total.configure(text=str(total))
        self.stat_active.configure(text=str(counts["Active"]))
        self.stat_inactive.configure(text=str(counts["Inactive"]))
        self.stat_blocked.configure(text=str(counts["Blocked"]))

        self._update_toggle_label()

    def _selected_code(self):
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _update_toggle_label(self):
        code = self._selected_code()
        record = self.store.get(code) if code else None
        if record and record.get("status") == "Inactive":
            self.toggle_status_btn.configure(text="Reactivate Selected")
        else:
            self.toggle_status_btn.configure(text="Deactivate Selected")

    # ------------------------------------------------------------ actions --
    def add_vendor(self):
        EditVendorDialog(self, self.store, record=None, on_saved=self._after_edit)

    def edit_selected(self):
        code = self._selected_code()
        if not code:
            messagebox.showinfo("Select a Row", "Select a vendor row first (or double-click it).")
            return
        record = self.store.get(code)
        if not record:
            messagebox.showerror("Not Found", "This vendor record no longer exists.")
            self.refresh()
            return
        EditVendorDialog(self, self.store, record, on_saved=self._after_edit)

    def toggle_status_selected(self):
        code = self._selected_code()
        if not code:
            messagebox.showinfo("Select a Row", "Select a vendor row first.")
            return
        record = self.store.get(code)
        if not record:
            return
        new_status = "Active" if record.get("status") == "Inactive" else "Inactive"
        self.store.set_status(code, new_status)
        notify(self, f"Vendor {code} is now {new_status}.", kind="info")
        self._after_edit()

    def delete_selected(self):
        code = self._selected_code()
        if not code:
            messagebox.showinfo("Select a Row", "Select a vendor row first.")
            return
        record = self.store.get(code)
        if not record:
            return
        confirmed = messagebox.askyesno(
            "Delete Permanently",
            f"Permanently delete vendor {code} - {record.get('vendor_name') or '(no name)'}?\n\n"
            "This cannot be undone. Consider Deactivate instead if you may need this record again.",
        )
        if not confirmed:
            return
        self.store.delete(code)
        notify(self, f"Vendor {code} deleted.", kind="error")
        self._after_edit()

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
        notify(self, f"Master data exported to:\n{path}", kind="success")
