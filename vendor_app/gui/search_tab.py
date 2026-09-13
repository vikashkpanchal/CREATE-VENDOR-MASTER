"""Search Vendor Details: Single Vendor Search and Multi Vendor Search."""

from datetime import datetime
from tkinter import messagebox, filedialog

import customtkinter as ctk

from vendor_app.config import DISPLAY_COLUMNS, WRAPPED_LABELS, COLUMN_WIDTHS, LABELS
from vendor_app.export import export_records_to_excel
from vendor_app.validators import split_emails, normalize
from vendor_app.gui import theme
from vendor_app.gui.edit_dialog import EditVendorDialog
from vendor_app.gui.style import build_table, insert_row, set_heading_text
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, divider, pill, primary_button, secondary_button, section_label, wrap_children

SINGLE_MODE = "Single Vendor Search"
MULTI_MODE = "Multi Vendor Search"


class SearchTab(ctk.CTkFrame):
    def __init__(self, master, store, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = store
        self.on_data_changed = on_data_changed
        self.multi_results = []
        self._multi_sort_key = None
        self._multi_sort_desc = False

        self._build_mode_switch()
        self.single_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.multi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._build_single()
        self._build_multi()
        self.single_frame.pack(fill="both", expand=True)

    # --------------------------------------------------------- mode switch --
    def _build_mode_switch(self):
        """Title, then the two searches as their own row of buttons.

        The switch used to sit in the far top-right corner of the header. On
        a Windows laptop at 125% or 150% display scaling that corner was off
        the edge of the screen entirely, so Multi Vendor Search could not be
        seen, let alone clicked. It now has its own full-width row directly
        under the title, left-aligned with the search controls it drives -
        the first place anybody looks, and nowhere near an edge.
        """
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(20, 8))
        wrap_children(bar)
        ctk.CTkLabel(
            bar, text="Search Vendor Details", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            bar,
            text="Look up one vendor's full profile, or check many vendor codes at once.",
            font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        switch_row = ctk.CTkFrame(self, fg_color="transparent")
        switch_row.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(
            switch_row, text="SEARCH", font=theme.label_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 10))
        self.mode_switch = ctk.CTkSegmentedButton(
            switch_row,
            values=[SINGLE_MODE, MULTI_MODE],
            command=self._on_mode_change,
            selected_color=theme.ACCENT,
            selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.BG_CARD_ALT,
            unselected_hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.font(12, "bold"),
            height=36,
        )
        self.mode_switch.set(SINGLE_MODE)
        self.mode_switch.pack(side="left")
        self.mode_hint = ctk.CTkLabel(
            switch_row, text="One vendor code at a time.",
            font=theme.small_font(), text_color=theme.TEXT_MUTED,
        )
        self.mode_hint.pack(side="left", padx=14)

    def show_mode(self, value):
        """Switch modes from anywhere - the segmented button follows."""
        self.mode_switch.set(value)
        self._on_mode_change(value)

    def _on_mode_change(self, value):
        if value == SINGLE_MODE:
            self.multi_frame.pack_forget()
            self.single_frame.pack(fill="both", expand=True)
            self.mode_hint.configure(text="One vendor code at a time.")
        else:
            self.single_frame.pack_forget()
            self.multi_frame.pack(fill="both", expand=True)
            self.mode_hint.configure(
                text="Paste or type many vendor codes - one per line, or comma separated."
            )

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

        badge_row = ctk.CTkFrame(text_col, fg_color="transparent")
        badge_row.pack(anchor="w", pady=(6, 0))
        pill(badge_row, f"Code: {record.get('vendor_code')}").pack(side="left")
        status = record.get("status", "Active")
        bg, fg = theme.status_colors(status)
        pill(badge_row, theme.format_status(status), fg=bg, tc=fg).pack(side="left", padx=(8, 0))

        self._info_section(self.card_frame, "Vendor", [
            (LABELS["vendor_code"], record.get("vendor_code")),
            (LABELS["vendor_name"], record.get("vendor_name")),
            (LABELS["vendor_type"], record.get("vendor_type")),
        ] + self._email_rows(LABELS["vendor_email"], record.get("vendor_email", "")))

        self._info_section(self.card_frame, "Contact Person 1", [
            (LABELS["vendor_owner_name"], record.get("vendor_owner_name")),
            (LABELS["vendor_owner_contact"], record.get("vendor_owner_contact")),
            (LABELS["vendor_owner_email"], record.get("vendor_owner_email")),
        ])

        self._info_section(self.card_frame, "Contact Person 2", [
            (LABELS["vendor_supervisor_name"], record.get("vendor_supervisor_name")),
            (LABELS["vendor_supervisor_contact"], record.get("vendor_supervisor_contact")),
            (LABELS["vendor_supervisor_email"], record.get("vendor_supervisor_email")),
        ])

        actions = ctk.CTkFrame(self.card_frame, fg_color="transparent")
        actions.pack(anchor="w", pady=(4, 20))
        primary_button(actions, "Edit This Vendor Record", lambda: self._edit(record), width=210).pack(
            side="left", padx=(0, 8)
        )
        toggle_label = "Reactivate" if record.get("status") == "Inactive" else "Deactivate"
        secondary_button(actions, toggle_label, lambda: self._toggle_status(record), width=140).pack(side="left")

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

    def _toggle_status(self, record):
        new_status = "Active" if record.get("status") == "Inactive" else "Inactive"
        self.store.set_status(record["vendor_code"], new_status)
        notify(self, f"Vendor {record['vendor_code']} is now {new_status}.", kind="info")
        self._after_edit()

    def _after_edit(self):
        if self.on_data_changed:
            self.on_data_changed()
        self.do_single_search()

    # --------------------------------------------------------- multi mode --
    def _build_multi(self):
        """Codes in at the top, results underneath.

        This used to be a tall fixed-size card down the left-hand side with
        the Search button below the text box. The card does not grow to fit
        its contents, so on a short panel - a laptop at 150% display
        scaling leaves this screen about 130 pixels tall - the text box took
        every pixel and the Search button was never drawn at all. There was
        then no way to run a multi-vendor search.

        An input bar across the top cannot fail that way: it asks for a
        fixed height, the results table takes whatever is left, and the
        button sits next to the box it belongs to at any size.
        """
        holder = ctk.CTkFrame(self.multi_frame, fg_color="transparent")
        holder.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        holder.grid_rowconfigure(1, weight=1)
        holder.grid_columnconfigure(0, weight=1)

        box = card(holder, fg_color=theme.BG_CARD)
        box.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        # The actions get their own column, reserved before the text box, so
        # a wide input can never push them out of the card.
        box.grid_columnconfigure(0, weight=1)
        box.grid_columnconfigure(1, weight=0)

        entry_side = ctk.CTkFrame(box, fg_color="transparent")
        entry_side.grid(row=0, column=0, sticky="ew", padx=(16, 12), pady=14)
        section_label(entry_side, "VENDOR CODES").pack(anchor="w")
        ctk.CTkLabel(
            entry_side, text="One per line, or separated by commas - paste a whole list.",
            font=theme.small_font(), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 6))
        self.multi_text = ctk.CTkTextbox(
            entry_side, height=84, fg_color=theme.BG_INPUT,
            border_color=theme.BG_INPUT_BORDER, border_width=1,
        )
        self.multi_text.pack(fill="x")

        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(0, 16), pady=14)
        primary_button(actions, "Search", self.do_multi_search, width=190).pack(
            anchor="e", pady=(0, 8)
        )
        secondary_button(actions, "Clear", self.clear_multi, width=190).pack(anchor="e")

        right = ctk.CTkFrame(holder, fg_color="transparent")
        right.grid(row=1, column=0, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(right, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.multi_status = pill(toolbar, "No search performed yet.", fg=theme.BG_CARD_ALT, tc=theme.TEXT_SECONDARY)
        self.multi_status.pack(side="left")
        primary_button(toolbar, "Export Search Results (.xlsx)", self.export_multi_results, width=230).pack(
            side="right"
        )

        outer, self.multi_tree = build_table(
            right, DISPLAY_COLUMNS, WRAPPED_LABELS, COLUMN_WIDTHS, on_sort=self._on_multi_sort
        )
        outer.grid(row=1, column=0, sticky="nsew")

    def clear_multi(self):
        self.multi_text.delete("1.0", "end")
        self.multi_results = []
        self._populate_multi_tree()
        self.multi_status.configure(text="No search performed yet.")

    def _multi_row_values(self, record):
        values = []
        for key in DISPLAY_COLUMNS:
            if key == "status":
                values.append(theme.format_status(record.get("status", "Active")))
            else:
                values.append(record.get(key, ""))
        return values

    def _on_multi_sort(self, key):
        if self._multi_sort_key == key:
            self._multi_sort_desc = not self._multi_sort_desc
        else:
            self._multi_sort_key = key
            self._multi_sort_desc = False
        self._populate_multi_tree()

    def _populate_multi_tree(self):
        records = self.multi_results
        if self._multi_sort_key:
            records = sorted(
                records, key=lambda r: r.get(self._multi_sort_key, "").lower(), reverse=self._multi_sort_desc
            )
        for row in self.multi_tree.get_children():
            self.multi_tree.delete(row)
        for i, record in enumerate(records):
            insert_row(
                self.multi_tree, i, status=record.get("status", "Active"),
                iid=record["vendor_code"], values=self._multi_row_values(record),
            )
        set_heading_text(
            self.multi_tree, DISPLAY_COLUMNS, WRAPPED_LABELS, self._multi_sort_key, self._multi_sort_desc
        )

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
        self._populate_multi_tree()

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
        notify(self, f"Search results exported to:\n{path}", kind="success")
