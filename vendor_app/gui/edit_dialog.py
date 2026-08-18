"""Modal dialog for adding a new vendor or editing an existing one.

Reused by both the Search tab ("Edit This Vendor Record") and the Master
Data tab ("Edit Selected" / double-click). Saves go through
VendorStore.upsert, so the same cell-level merge rules apply everywhere.
"""

import customtkinter as ctk
from tkinter import messagebox

from vendor_app.config import LABELS
from vendor_app.validators import ValidationError
from vendor_app.gui import theme
from vendor_app.gui.widgets import card, divider, primary_button, secondary_button, section_label

SECTIONS = [
    ("VENDOR", ["vendor_code", "vendor_name", "vendor_email"]),
    ("OWNER", ["vendor_owner_name", "vendor_owner_contact", "vendor_owner_email"]),
    ("SUPERVISOR", ["vendor_supervisor_name", "vendor_supervisor_contact", "vendor_supervisor_email"]),
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
        self.geometry("560x680")
        self.minsize(480, 520)
        self.transient(master)
        self.grab_set()

        self.vars = {}
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
                    entry.configure(state="disabled")
                elif self._first_entry is None:
                    self._first_entry = entry

                self.vars[key] = var
            ctk.CTkFrame(box, fg_color="transparent", height=6).pack()

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(0, 20))
        primary_button(buttons, "Save", self.save, width=120).pack(side="right", padx=(8, 0))
        secondary_button(buttons, "Cancel", self.destroy, width=120).pack(side="right")

    def _focus_first_field(self):
        if self._first_entry is not None:
            self._first_entry.focus_set()

    def save(self):
        raw = {key: self.vars[key].get() for key in self.vars}
        if not self.is_new:
            raw["vendor_code"] = self.record["vendor_code"]

        try:
            result = self.store.upsert(raw)
        except ValidationError as exc:
            messagebox.showerror("Validation Error", str(exc), parent=self)
            return

        messagebox.showinfo("Saved", f"Vendor {raw['vendor_code']} {result}.", parent=self)
        if self.on_saved:
            self.on_saved()
        self.destroy()
