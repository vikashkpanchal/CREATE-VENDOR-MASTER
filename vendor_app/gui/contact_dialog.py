"""Who a vendor should contact about a breakdown letter.

A name, an email and a contact number, printed at the foot of every
breakdown email under "For any clarification or reply regarding the above
breakdown equipment, please contact:". Entered once and remembered, so the
same person is not typed in on every run; any of the three may be left
blank, and only what is given is printed.
"""

import re

import customtkinter as ctk

from vendor_app.gui import theme
from vendor_app.gui.cc_dialog import _check_address
from vendor_app.gui.util import claim_focus, fit_on_screen, focus_on_click, grow_to_fit
from vendor_app.gui.widgets import (
    card, danger_button, divider, primary_button, secondary_button, section_label,
)

# Digits plus the separators people actually write a number with:
# "+91 98250 12345", "0288-2345678", "(0288) 234 5678".
_PHONE_CHARS = re.compile(r"^[0-9+()\-./ ]+$")


def validate_contact(name: str, email: str, phone: str):
    """Returns ((name, email, phone), error_or_None). All three may be blank."""
    name = " ".join((name or "").split())
    email = (email or "").strip()
    phone = " ".join((phone or "").split())

    if email:
        if "@" not in email:
            return None, f"'{email}' is not an email address - it needs an @."
        cleaned, error = _check_address(email)
        if error:
            return None, error
        email = cleaned
    if phone:
        digits = sum(ch.isdigit() for ch in phone)
        if not _PHONE_CHARS.match(phone):
            return None, (f"'{phone}' is not a phone number - use digits, spaces, "
                          "+ and - only.")
        if digits < 6 or digits > 15:
            return None, (f"'{phone}' has {digits} digits - a phone number has "
                          "between 6 and 15.")
    return (name, email, phone), None


class BreakdownContactDialog(ctk.CTkToplevel):
    """Edit the breakdown contact person. Calls on_saved(contact_dict)."""

    WIDTH, HEIGHT = 540, 520

    def __init__(self, master, settings, on_saved=None):
        super().__init__(master)
        self.settings = settings
        self.on_saved = on_saved
        self.vars = {}
        self._first_entry = None

        self.configure(fg_color=theme.BG_SURFACE)
        self.title("Breakdown Contact Person")
        fit_on_screen(self, self.WIDTH, self.HEIGHT, min_w=440, min_h=380, margin_h=120)
        self.transient(master)
        self.grab_set()
        self._build()
        grow_to_fit(self, content=self._content)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._save())
        claim_focus(self, self._first_entry)

    def _build(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            head, text="Contact Person for Replies", font=theme.h1_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            head,
            text="Printed at the foot of every breakdown email, so the vendor knows "
                 "whom to reply to or call. Any field may be left blank - only what "
                 "you fill in is printed.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            anchor="w", justify="left", wraplength=470,
        ).pack(anchor="w", pady=(4, 0))

        # Buttons and the error line are reserved before the fields, so no
        # window height can push them out of reach.
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        primary_button(buttons, "Save", self._save, width=120).pack(side="right", padx=(8, 0))
        secondary_button(buttons, "Cancel", self.destroy, width=100).pack(side="right")
        danger_button(buttons, "Clear All", self._clear, width=110).pack(side="left")

        self.error_label = ctk.CTkLabel(
            self, text="", font=theme.small_font(), text_color=theme.DANGER,
            anchor="w", justify="left", wraplength=470,
        )
        self.error_label.pack(side="bottom", anchor="w", padx=22, pady=(0, 6))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=10)
        box = card(body, fg_color=theme.BG_CARD)
        box.pack(fill="both", expand=True)
        self._content = box
        section_label(box, "CONTACT").pack(anchor="w", padx=18, pady=(14, 2))
        divider(box).pack(fill="x", padx=18, pady=(0, 6))

        current = self.settings.breakdown_contact()
        self._field(box, "name", "Contact Person Name", current["name"], "e.g. Vikash Panchal")
        self._field(box, "email", "Email", current["email"], "name@ril.com")
        self._field(box, "phone", "Contact Number", current["phone"], "+91 98250 12345")
        ctk.CTkFrame(box, fg_color="transparent", height=8).pack()

    def _field(self, parent, key, label, value, placeholder):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(
            row, text=label, anchor="w", font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 3))
        var = ctk.StringVar(value=value)
        entry = ctk.CTkEntry(
            row, textvariable=var, height=34, placeholder_text=placeholder,
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
            font=theme.body_font(),
        )
        entry.pack(fill="x")
        focus_on_click(entry, entry._entry, getattr(entry, "_canvas", None))
        self.vars[key] = var
        if self._first_entry is None:
            self._first_entry = entry

    def _clear(self):
        for var in self.vars.values():
            var.set("")
        self.error_label.configure(text="")

    def _save(self):
        cleaned, error = validate_contact(
            self.vars["name"].get(), self.vars["email"].get(), self.vars["phone"].get()
        )
        if error:
            self.error_label.configure(text=error)
            return
        name, email, phone = cleaned
        self.settings.set_breakdown_contact(name, email, phone)
        contact = self.settings.breakdown_contact()
        self.grab_release()
        self.destroy()
        if self.on_saved:
            self.on_saved(contact)
