"""Reusable 'paste tab-separated rows' dialog.

Used by the Equipment Master tab (bulk add) and shares the app's dark
styling. The caller supplies the expected column order and a handler that
receives the parsed rows.
"""

import customtkinter as ctk

from vendor_app.gui import theme
from vendor_app.gui.widgets import card, primary_button, secondary_button, section_label


class PasteRowsDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, keys: list, labels: dict, on_submit, note: str = ""):
        super().__init__(master)
        self.keys = keys
        self.labels = labels
        self.on_submit = on_submit

        self.configure(fg_color=theme.BG_SURFACE)
        self.title(title)
        screen_h, screen_w = self.winfo_screenheight(), self.winfo_screenwidth()
        height = min(620, max(400, screen_h - 140))
        width = min(900, max(520, screen_w - 120))
        self.geometry(f"{width}x{height}+{max(0,(screen_w-width)//2)}+{max(0,(screen_h-height)//3)}")
        self.minsize(520, 380)
        self.transient(master)
        self.grab_set()

        self._build(title, note)
        self.after(50, lambda: self.textbox.focus_set())

    def _build(self, title, note):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(header, text=title, font=theme.h1_font(), text_color=theme.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=note or "Paste rows copied from Excel. Columns must be in the order shown below.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            wraplength=760, justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # Action bar reserved first so it can never be pushed off-screen.
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        primary_button(buttons, "Add Rows", self._submit, width=140).pack(side="right", padx=(8, 0))
        secondary_button(buttons, "Cancel", self.destroy, width=120).pack(side="right")

        cols = card(self, fg_color=theme.BG_CARD)
        cols.pack(fill="x", padx=20, pady=(10, 8))
        section_label(cols, "EXPECTED COLUMN ORDER").pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(
            cols,
            text="  →  ".join(self.labels[k] for k in self.keys),
            font=theme.small_font(), text_color=theme.TEXT_PRIMARY,
            wraplength=800, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

        self.textbox = ctk.CTkTextbox(
            self, fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER, border_width=1,
            font=("Consolas", 11),
        )
        self.textbox.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    def _submit(self):
        from vendor_app.communication import parse_pasted_rows

        rows = parse_pasted_rows(self.textbox.get("1.0", "end"), self.keys)
        self.destroy()
        self.on_submit(rows)
