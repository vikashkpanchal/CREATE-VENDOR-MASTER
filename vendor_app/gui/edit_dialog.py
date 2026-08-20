"""Modal dialog for adding a new vendor or editing an existing one.

Reused by both the Search tab ("Edit This Vendor Record") and the Master
Data tab ("Edit Selected" / double-click / "+ Add Vendor"). Saves go
through VendorStore.upsert, so the same cell-level merge rules apply
everywhere. Lifecycle status (Active/Inactive/Blocked) is edited here too.
"""

import customtkinter as ctk
from tkinter import messagebox

from vendor_app.config import LABELS, STATUS_VALUES, STATUS_DEFAULT
from vendor_app.validators import ValidationError
from vendor_app.gui import theme
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, divider, primary_button, secondary_button, section_label

SECTIONS = [
    ("VENDOR", ["vendor_code", "vendor_name", "vendor_email"]),
    ("CONTACT PERSON 1", ["vendor_owner_name", "vendor_owner_contact", "vendor_owner_email"]),
    ("CONTACT PERSON 2", ["vendor_supervisor_name", "vendor_supervisor_contact", "vendor_supervisor_email"]),
]


class EditVendorDialog(ctk.CTkToplevel):
    def __init__(self, master, store, record: dict = None, on_saved=None):
        super().__init__(master)
        self.store = store
        self.on_saved = on_saved
        self.record = record or {}
        self.is_new = not bool(record)

        self.configure(fg_color=theme.BG_SURFACE)
        self.title("Add Vendor Record" if self.is_new else "Edit Vendor Record")

        # Fit the dialog to the screen rather than assuming 740px of height is
        # available - on a laptop / scaled display a fixed-height dialog can
        # extend past the bottom of the screen, taking the Save button with it.
        screen_h = self.winfo_screenheight()
        screen_w = self.winfo_screenwidth()
        height = min(740, max(420, screen_h - 120))
        width = min(560, max(420, screen_w - 80))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(420, 380)
        self.transient(master)
        self.grab_set()

        self.vars = {}
        self.status_var = ctk.StringVar(value=self.record.get("status") or STATUS_DEFAULT)
        self._first_entry = None
        self._build_form()
        self.after(50, self._focus_first_field)

    def _build_form(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            header,
            text="Add Vendor Record" if self.is_new else "Edit Vendor Record",
            font=theme.h1_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        hint_text = (
            "Vendor Code is mandatory and numeric. Contact numbers must be digits only. "
            "Separate multiple emails with a semicolon (;)."
            if self.is_new
            else "Blank fields are left unchanged - only fields you edit overwrite the stored record. "
            "Separate multiple emails with a semicolon (;)."
        )
        ctk.CTkLabel(
            header, text=hint_text, font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            wraplength=500, justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # Pack the action bar FIRST, anchored to the bottom edge. Tk gives
        # space to earlier-packed widgets, so reserving it up front means the
        # Save/Cancel buttons stay visible no matter how tall the form grows
        # or how short the window gets; the scrollable body absorbs the rest.
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        primary_button(buttons, "Save", self.save, width=120).pack(side="right", padx=(8, 0))
        secondary_button(buttons, "Cancel", self.destroy, width=120).pack(side="right")

        wrapper = ctk.CTkScrollableFrame(self, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=20, pady=10)

        for title, keys in SECTIONS:
            box = card(wrapper, fg_color=theme.BG_CARD)
            box.pack(fill="x", pady=(0, 14))
            section_label(box, title).pack(anchor="w", padx=18, pady=(14, 4))
            divider(box).pack(fill="x", padx=18, pady=(0, 10))

            for key in keys:
                row = ctk.CTkFrame(box, fg_color="transparent")
                row.pack(fill="x", padx=18, pady=6)
                label_text = LABELS[key] + (" *" if key == "vendor_code" else "")
                ctk.CTkLabel(
                    row, text=label_text, width=210, anchor="w", font=theme.body_font(),
                    text_color=theme.TEXT_SECONDARY,
                ).pack(side="left")

                var = ctk.StringVar(value=self.record.get(key, ""))
                entry = ctk.CTkEntry(
                    row, textvariable=var, height=32,
                    fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
                )
                entry.pack(side="left", fill="x", expand=True)

                if key == "vendor_code" and not self.is_new:
                    # readonly (not disabled): the primary key must never be
                    # edited, but the user still needs to select and copy it.
                    entry.configure(state="readonly", text_color=theme.TEXT_PRIMARY)
                elif self._first_entry is None:
                    self._first_entry = entry

                self.vars[key] = var

            if title == "VENDOR":
                status_row = ctk.CTkFrame(box, fg_color="transparent")
                status_row.pack(fill="x", padx=18, pady=6)
                ctk.CTkLabel(
                    status_row, text="Status", width=210, anchor="w", font=theme.body_font(),
                    text_color=theme.TEXT_SECONDARY,
                ).pack(side="left")
                ctk.CTkOptionMenu(
                    status_row,
                    variable=self.status_var,
                    values=STATUS_VALUES,
                    width=200,
                    height=32,
                    fg_color=theme.BG_INPUT,
                    button_color=theme.BG_CARD_ALT,
                    button_hover_color=theme.BG_HOVER,
                    dropdown_fg_color=theme.BG_CARD_ALT,
                ).pack(side="left")

            ctk.CTkFrame(box, fg_color="transparent", height=6).pack()

    def _focus_first_field(self):
        if self._first_entry is not None:
            self._first_entry.focus_set()

    def save(self):
        raw = {key: self.vars[key].get() for key in self.vars}
        if not self.is_new:
            raw["vendor_code"] = self.record["vendor_code"]

        try:
            result = self.store.upsert(raw, status=self.status_var.get())
        except ValidationError as exc:
            messagebox.showerror("Validation Error", str(exc), parent=self)
            return

        if self.on_saved:
            self.on_saved()
        self.destroy()
        # Toast anchors to the still-open parent window; the dialog itself
        # is already gone by the time it fades in.
        notify(self.master, f"Vendor {raw['vendor_code']} {result}.")
