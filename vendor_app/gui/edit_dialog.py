"""Modal dialog for adding a new vendor or editing an existing one.

Reused by both the Search tab ("Edit This Vendor Record") and the Master
Data tab ("Edit Selected" / double-click). Saves go through
VendorStore.upsert, so the same cell-level merge rules apply everywhere.
"""

import customtkinter as ctk
from tkinter import messagebox

from vendor_app.config import KEYS, LABELS
from vendor_app.validators import ValidationError


class EditVendorDialog(ctk.CTkToplevel):
    def __init__(self, master, store, record: dict = None, on_saved=None):
        super().__init__(master)
        self.store = store
        self.on_saved = on_saved
        self.record = record or {}
        self.is_new = not bool(record)

        self.title("Add Vendor Record" if self.is_new else "Edit Vendor Record")
        self.geometry("540x640")
        self.minsize(480, 520)
        self.transient(master)
        self.grab_set()

        self.vars = {}
        self._build_form()
        self.after(50, self._focus_first_field)

    def _build_form(self):
        wrapper = ctk.CTkScrollableFrame(self, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        self._first_entry = None
        for key in KEYS:
            row = ctk.CTkFrame(wrapper, fg_color="transparent")
            row.pack(fill="x", pady=6)
            label_text = LABELS[key] + (" *" if key == "vendor_code" else "")
            ctk.CTkLabel(row, text=label_text, width=230, anchor="w").pack(side="left")

            var = ctk.StringVar(value=self.record.get(key, ""))
            entry = ctk.CTkEntry(row, textvariable=var)
            entry.pack(side="left", fill="x", expand=True)

            if key == "vendor_code" and not self.is_new:
                # Vendor Code is the primary key: locked once a record exists.
                entry.configure(state="disabled")
            elif self._first_entry is None:
                self._first_entry = entry

            self.vars[key] = var

        hint_text = (
            "Vendor Code is mandatory and numeric. Contact numbers must be digits only. "
            "Separate multiple emails with a semicolon (;)."
            if self.is_new
            else "Blank fields are left unchanged; only fields you edit will overwrite the "
            "stored record. Separate multiple emails with a semicolon (;)."
        )
        ctk.CTkLabel(
            wrapper, text=hint_text, text_color="#9a9a9a", wraplength=470, justify="left"
        ).pack(fill="x", pady=(10, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(buttons, text="Save", command=self.save).pack(side="right", padx=4)
        ctk.CTkButton(
            buttons, text="Cancel", fg_color="#4a4a4a", hover_color="#3a3a3a", command=self.destroy
        ).pack(side="right", padx=4)

    def _focus_first_field(self):
        if self._first_entry is not None:
            self._first_entry.focus_set()

    def save(self):
        raw = {key: self.vars[key].get() for key in KEYS}
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
