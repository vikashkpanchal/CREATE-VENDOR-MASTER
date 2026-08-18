"""Search Vendor Details: Single Vendor Search and Multi Vendor Search."""

from datetime import datetime
from tkinter import messagebox, filedialog

import customtkinter as ctk

from vendor_app.config import KEYS, WRAPPED_LABELS, COLUMN_WIDTHS
from vendor_app.export import export_records_to_excel
from vendor_app.validators import split_emails, normalize
from vendor_app.gui import theme
from vendor_app.gui.edit_dialog import EditVendorDialog
from vendor_app.gui.style import build_table, stripe_rows
from vendor_app.gui.widgets import card, divider, pill, primary_button, section_label


class SearchTab(ctk.CTkFrame):
    def __init__(self, master, store, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
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
        bar.pack(fill="x", padx=20, pady=(20, 12))

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Search Vendor Details", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Look up one vendor's full profile, or check many vendor codes at once.",
            font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        seg = ctk.CTkSegmentedButton(
            bar,
            values=["Single Vendor Search", "Multi Vendor Search"],
            command=self._on_mode_change,
            selected_color=theme.ACCENT,
            selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.BG_CARD_ALT,
            unselected_hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.font(12, "bold"),
            height=36,
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
        top = card(self.single_frame, fg_color=theme.BG_CARD)
        top.pack(fill="x", padx=20, pady=(0, 14))
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=16)
        ctk.CTkLabel(row, text="Vendor Code", font=theme.label_font(), text_color=theme.TEXT_SECONDARY).pack(
            side="left", padx=(0, 10)
        )
        self.single_code_entry = ctk.CTkEntry(
            row,
            width=240,
            height=34,
            placeholder_text="e.g. 1001",
            fg_color=theme.BG_INPUT,
            border_color=theme.BG_INPUT_BORDER,
        )
        self.single_code_entry.pack(side="left", padx=(0, 10))
        self.single_code_entry.bind("<Return>", lambda e: self.do_single_search())
        primary_button(row, "Search", self.do_single_search, width=120).pack(side="left")

        self.card_frame = ctk.CTkScrollableFrame(self.single_frame, fg_color=theme.BG_SURFACE)
        self.card_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self._empty_state(self.card_frame, "Enter a Vendor Code and click Search to view the profile.")

    def _empty_state(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=theme.body_font(), text_color=theme.TEXT_MUTED).pack(pady=48)

    def do_single_search(self):
        code = normalize(self.single_code_entry.get())
        for widget in self.card_frame.winfo_children():
            widget.destroy()

        if not code:
            self._empty_state(self.card_frame, "Please enter a Vendor Code.")
            return

        record = self.store.get(code)
        if not record:
            self._empty_state(self.card_frame, f"No vendor found with code '{code}'.")
            return

        self._render_card(record)

    def _render_card(self, record):
        header = card(self.card_frame, fg_color=theme.ACCENT_SOFT, border_color=theme.ACCENT_BORDER)
        header.pack(fill="x", pady=(0, 14))
        head_row = ctk.CTkFrame(header, fg_color="transparent")
        head_row.pack(fill="x", padx=20, pady=18)

        initials = "".join(w[0] for w in (record.get("vendor_name") or "?").split()[:2]).upper() or "?"
        ctk.CTkLabel(
            head_row,
            text=initials,
            width=52,
            height=52,
            corner_radius=26,
            fg_color=theme.ACCENT,
            text_color=theme.TEXT_ON_ACCENT,
            font=theme.font(16, "bold"),
        ).pack(side="left", padx=(0, 16))

        text_col = ctk.CTkFrame(head_row, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            text_col,
            text=record.get("vendor_name") or "(no name on file)",
            font=theme.h1_font(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")
        pill(text_col, f"Code: {record.get('vendor_code')}").pack(anchor="w", pady=(6, 0))

        self._info_section(self.card_frame, "Vendor", [
            ("Vendor Code", record.get("vendor_code")),
            ("Vendor Name", record.get("vendor_name")),
        ] + self._email_rows("Vendor Email ID", record.get("vendor_email", "")))

        self._info_section(self.card_frame, "Owner", [
            ("Vendor Owner Name", record.get("vendor_owner_name")),
            ("Vendor Owner Contact Number", record.get("vendor_owner_contact")),
            ("Vendor Owner Email ID", record.get("vendor_owner_email")),
        ])

        self._info_section(self.card_frame, "Supervisor", [
            ("Vendor Supervisor Contact Name", record.get("vendor_supervisor_name")),
            ("Vendor Supervisor Contact Number", record.get("vendor_supervisor_contact")),
            ("Vendor Supervisor Email ID", record.get("vendor_supervisor_email")),
        ])

        primary_button(
            self.card_frame, "Edit This Vendor Record", lambda: self._edit(record), width=210
        ).pack(anchor="w", pady=(4, 20))

    def _email_rows(self, label, value):
        emails = split_emails(value)
        if not emails:
            return [(label, "")]
        if len(emails) == 1:
            return [(label, emails[0])]
        return [(f"{label} {i}", email) for i, email in enumerate(emails, start=1)]

    def _info_section(self, parent, title, rows):
        box = card(parent, fg_color=theme.BG_CARD)
        box.pack(fill="x", pady=(0, 14))
        section_label(box, title.upper()).pack(anchor="w", padx=20, pady=(16, 4))
        divider(box).pack(fill="x", padx=20, pady=(0, 6))
        for label, value in rows:
            r = ctk.CTkFrame(box, fg_color="transparent")
            r.pack(fill="x", padx=20, pady=6)
            ctk.CTkLabel(
                r, text=label, width=270, anchor="w", font=theme.small_font(), text_color=theme.TEXT_SECONDARY
            ).pack(side="left")
            ctk.CTkLabel(
                r,
                text=value or "—",
                anchor="w",
                justify="left",
                wraplength=480,
                font=theme.body_font(),
                text_color=theme.TEXT_PRIMARY,
            ).pack(side="left", fill="x", expand=True)
        ctk.CTkFrame(box, fg_color="transparent", height=6).pack()

    def _edit(self, record):
        EditVendorDialog(self, self.store, record, on_saved=self._after_edit)

    def _after_edit(self):
        if self.on_data_changed:
            self.on_data_changed()
        self.do_single_search()

    # --------------------------------------------------------- multi mode --
    def _build_multi(self):
        split = ctk.CTkFrame(self.multi_frame, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        left = card(split, fg_color=theme.BG_CARD, width=280)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)
        section_label(left, "VENDOR CODES").pack(anchor="w", padx=16, pady=(16, 0))
        ctk.CTkLabel(
            left, text="One per line, or paste a list", font=theme.small_font(), text_color=theme.TEXT_MUTED
        ).pack(anchor="w", padx=16, pady=(0, 8))
        self.multi_text = ctk.CTkTextbox(
            left, width=240, height=420, fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER, border_width=1
        )
        self.multi_text.pack(fill="both", expand=True, padx=16, pady=4)
        primary_button(left, "Search", self.do_multi_search, width=248).pack(padx=16, pady=(10, 16))

        right = ctk.CTkFrame(split, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(right, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.multi_status = pill(toolbar, "No search performed yet.", fg=theme.BG_CARD_ALT, tc=theme.TEXT_SECONDARY)
        self.multi_status.pack(side="left")
        primary_button(toolbar, "Export Search Results (.xlsx)", self.export_multi_results, width=230).pack(
            side="right"
        )

        outer, self.multi_tree = build_table(right, KEYS, WRAPPED_LABELS, COLUMN_WIDTHS)
        outer.grid(row=1, column=0, sticky="nsew")

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
        stripe_rows(self.multi_tree)

        status = f"Found {len(found)} of {len(codes)} vendor code(s)"
        if missing:
            shown = ", ".join(missing[:10])
            status += f"  •  Missing: {shown}" + (" ..." if len(missing) > 10 else "")
        self.multi_status.configure(text=f"  {status}  ")

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
