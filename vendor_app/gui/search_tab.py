"""Tab 2: Search Vendor Details - Single Vendor Search and Multi Vendor Search."""

from datetime import datetime
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk

from vendor_app.config import KEYS, LABELS
from vendor_app.export import export_records_to_excel
from vendor_app.validators import split_emails, normalize
from vendor_app.gui.edit_dialog import EditVendorDialog
from vendor_app.gui.style import apply_dark_treeview_style


class SearchTab(ctk.CTkFrame):
    def __init__(self, master, store, on_data_changed=None):
        super().__init__(master, fg_color="transparent")
        self.store = store
        self.on_data_changed = on_data_changed
        self.multi_results = []

        self._build_mode_switch()
        self.single_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.multi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._build_single()
        self._build_multi()
        self.single_frame.pack(fill="both", expand=True)

    # --------------------------------------------------------- mode switch --
    def _build_mode_switch(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(
            bar, text="Search Vendor Details", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        seg = ctk.CTkSegmentedButton(
            bar,
            values=["Single Vendor Search", "Multi Vendor Search"],
            command=self._on_mode_change,
        )
        seg.set("Single Vendor Search")
        seg.pack(side="right")

    def _on_mode_change(self, value):
        if value.startswith("Single"):
            self.multi_frame.pack_forget()
            self.single_frame.pack(fill="both", expand=True)
        else:
            self.single_frame.pack_forget()
            self.multi_frame.pack(fill="both", expand=True)

    # -------------------------------------------------------- single mode --
    def _build_single(self):
        top = ctk.CTkFrame(self.single_frame, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(top, text="Vendor Code:").pack(side="left", padx=(0, 6))
        self.single_code_entry = ctk.CTkEntry(top, width=220, placeholder_text="Enter Vendor Code")
        self.single_code_entry.pack(side="left", padx=(0, 6))
        self.single_code_entry.bind("<Return>", lambda e: self.do_single_search())
        ctk.CTkButton(top, text="Search", command=self.do_single_search).pack(side="left", padx=4)

        self.card_frame = ctk.CTkScrollableFrame(self.single_frame, fg_color="#161616")
        self.card_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        ctk.CTkLabel(
            self.card_frame,
            text="Enter a Vendor Code and click Search to view the profile.",
            text_color="#9a9a9a",
        ).pack(pady=40)

    def do_single_search(self):
        code = normalize(self.single_code_entry.get())
        for widget in self.card_frame.winfo_children():
            widget.destroy()

        if not code:
            ctk.CTkLabel(self.card_frame, text="Please enter a Vendor Code.", text_color="#e08a8a").pack(
                pady=20
            )
            return

        record = self.store.get(code)
        if not record:
            ctk.CTkLabel(
                self.card_frame, text=f"No vendor found with code '{code}'.", text_color="#e08a8a"
            ).pack(pady=20)
            return

        self._render_card(record)

    def _render_card(self, record):
        header = ctk.CTkFrame(self.card_frame, fg_color="#1f6aa5", corner_radius=8)
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            header,
            text=f"{record.get('vendor_name') or '(no name)'}   •   Code: {record.get('vendor_code')}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffffff",
        ).pack(anchor="w", padx=16, pady=12)

        body = ctk.CTkFrame(self.card_frame, fg_color="#232323", corner_radius=8)
        body.pack(fill="x", pady=(0, 10))

        def add_row(label, value):
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(row, text=label, width=270, anchor="w", text_color="#9a9a9a").pack(
                side="left"
            )
            ctk.CTkLabel(row, text=value or "—", anchor="w", justify="left", wraplength=480).pack(
                side="left", fill="x", expand=True
            )

        add_row("Vendor Code", record.get("vendor_code"))
        add_row("Vendor Name", record.get("vendor_name"))

        emails = split_emails(record.get("vendor_email", ""))
        if emails:
            for i, email in enumerate(emails, start=1):
                add_row(f"Vendor Email ID {i}", email)
        else:
            add_row("Vendor Email ID", "")

        add_row("Vendor Owner Name", record.get("vendor_owner_name"))
        add_row("Vendor Owner Contact Number", record.get("vendor_owner_contact"))
        add_row("Vendor Owner Email ID", record.get("vendor_owner_email"))
        add_row("Vendor Supervisor Contact Name", record.get("vendor_supervisor_name"))
        add_row("Vendor Supervisor Contact Number", record.get("vendor_supervisor_contact"))
        add_row("Vendor Supervisor Email ID", record.get("vendor_supervisor_email"))

        ctk.CTkButton(
            self.card_frame, text="Edit This Vendor Record", command=lambda: self._edit(record)
        ).pack(anchor="w", pady=(0, 20))

    def _edit(self, record):
        EditVendorDialog(self, self.store, record, on_saved=self._after_edit)

    def _after_edit(self):
        if self.on_data_changed:
            self.on_data_changed()
        self.do_single_search()

    # --------------------------------------------------------- multi mode --
    def _build_multi(self):
        split = ctk.CTkFrame(self.multi_frame, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=10, pady=10)

        left = ctk.CTkFrame(split, fg_color="#161616", width=260)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)
        ctk.CTkLabel(left, text="Vendor Codes\n(one per line, or paste a list)", justify="left").pack(
            anchor="w", padx=10, pady=(10, 4)
        )
        self.multi_text = ctk.CTkTextbox(left, width=240, height=420)
        self.multi_text.pack(fill="both", expand=True, padx=10, pady=4)
        ctk.CTkButton(left, text="Search", command=self.do_multi_search).pack(
            fill="x", padx=10, pady=(4, 10)
        )

        right = ctk.CTkFrame(split, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        toolbar = ctk.CTkFrame(right, fg_color="transparent")
        toolbar.pack(fill="x")
        self.multi_status = ctk.CTkLabel(toolbar, text="No search performed yet.", text_color="#9a9a9a")
        self.multi_status.pack(side="left")
        ctk.CTkButton(
            toolbar, text="Export Search Results (.xlsx)", command=self.export_multi_results
        ).pack(side="right")

        apply_dark_treeview_style()
        table_frame = ctk.CTkFrame(right, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, pady=(6, 0))

        self.multi_tree = ttk.Treeview(table_frame, columns=KEYS, show="headings", style="Dark.Treeview")
        for key in KEYS:
            self.multi_tree.heading(key, text=LABELS[key])
            self.multi_tree.column(key, width=140, anchor="w")
        self.multi_tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.multi_tree.yview)
        self.multi_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

    def do_multi_search(self):
        raw = self.multi_text.get("1.0", "end")
        candidates = [c.strip() for chunk in raw.splitlines() for c in chunk.replace(",", "\n").split("\n")]
        codes, seen = [], set()
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                codes.append(c)

        found, missing = self.store.get_many(codes)
        self.multi_results = found

        for row in self.multi_tree.get_children():
            self.multi_tree.delete(row)
        for record in found:
            self.multi_tree.insert("", "end", values=[record.get(k, "") for k in KEYS])

        status = f"Found {len(found)} of {len(codes)} vendor code(s)."
        if missing:
            shown = ", ".join(missing[:10])
            status += f"  Missing: {shown}" + (" ..." if len(missing) > 10 else "")
        self.multi_status.configure(text=status)

    def export_multi_results(self):
        if not self.multi_results:
            messagebox.showwarning("No Data", "Run a search with results before exporting.")
            return
        default_name = f"Vendor_Search_Results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default_name, filetypes=[("Excel Workbook", "*.xlsx")]
        )
        if not path:
            return
        export_records_to_excel(self.multi_results, path)
        messagebox.showinfo("Exported", f"Search results exported to:\n{path}")
