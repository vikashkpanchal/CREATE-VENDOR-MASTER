"""Dialog for viewing and editing the CC address used by one email flow.

Each communication flow owns its own CC row, so the dialog is told which
one it is editing (`cc_key`) and names that flow throughout - there is no
single app-wide CC to confuse it with.

customtkinter's CTkInputDialog cannot be pre-filled, so it could only ever
ask for a brand-new value - the existing CC address was impossible to edit
(and an accidental blank submit silently cleared it). This dialog loads the
current address into an editable field instead, and separates "save what I
typed" from "clear the CC entirely".
"""

import customtkinter as ctk

from vendor_app.gui import theme
from vendor_app.gui.widgets import card, danger_button, divider, primary_button, secondary_button, section_label


def validate_cc(value: str):
    """Validate a ';'-separated CC list. Returns (cleaned, error_or_None).

    Blank is valid and means "no CC". Kept deliberately permissive - this
    only catches obvious typos, Outlook does the real resolving.
    """
    text = (value or "").strip().strip(";").strip()
    if not text:
        return "", None

    addresses = [a.strip() for a in text.replace(",", ";").split(";") if a.strip()]
    for address in addresses:
        if address.count("@") != 1 or " " in address:
            return None, f"'{address}' is not a valid email address."
        local, _, domain = address.partition("@")
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            return None, f"'{address}' is not a valid email address."

    return "; ".join(addresses), None


class CCAddressDialog(ctk.CTkToplevel):
    """Edit the CC address. Calls on_saved(new_value) only if it changed."""

    def __init__(self, master, settings, on_saved=None, first_run: bool = False,
                 cc_key=None, flow_label=None):
        super().__init__(master)
        self.settings = settings
        self.on_saved = on_saved
        self.first_run = first_run
        from vendor_app.config import CC_DEFECTIVE_KEY, CC_FLOW_LABELS
        self.cc_key = cc_key or CC_DEFECTIVE_KEY
        self.flow_label = flow_label or CC_FLOW_LABELS.get(self.cc_key, "CC")
        self.result = None

        self.configure(fg_color=theme.BG_SURFACE)
        self.title(self.flow_label)
        screen_h, screen_w = self.winfo_screenheight(), self.winfo_screenwidth()
        width, height = min(620, max(460, screen_w - 120)), 330
        self.geometry(f"{width}x{height}+{max(0,(screen_w-width)//2)}+{max(0,(screen_h-height)//3)}")
        self.minsize(440, 300)
        self.resizable(True, False)
        self.transient(master)

        self._build()

        # Grab only once the window actually exists, otherwise the grab can
        # land before the entry is mapped and swallow its first clicks.
        self.after(80, self._activate)

    def _activate(self):
        try:
            self.grab_set()
        except Exception:
            pass
        self.entry.focus_force()
        # Select the whole address so typing replaces it, while a click or
        # arrow key still drops the caret in for an ordinary edit.
        self.entry.select_range(0, "end")
        self.entry.icursor("end")

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            header, text=self.flow_label, font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=(
                f"This address is kept in CC on every {self.flow_label.lower()} email, "
                "and on no other flow. You are asked once; it is saved and reused "
                "from then on."
                if self.first_run else
                f"This address is kept in CC on every {self.flow_label.lower()} email. "
                "Each communication flow has its own, so changing this one leaves "
                "the other untouched."
            ),
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            wraplength=540, justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # Buttons reserved at the bottom first so they cannot be pushed off.
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        primary_button(buttons, "Save", self._save, width=120).pack(side="right", padx=(8, 0))
        secondary_button(buttons, "Cancel", self._cancel, width=110).pack(side="right")
        danger_button(buttons, "Clear CC", self._clear, width=120).pack(side="left")

        box = card(self, fg_color=theme.BG_CARD)
        box.pack(fill="x", padx=20, pady=10)
        section_label(box, "EMAIL ADDRESS").pack(anchor="w", padx=18, pady=(14, 4))
        divider(box).pack(fill="x", padx=18, pady=(0, 10))

        self.value_var = ctk.StringVar(value=self.settings.cc_for(self.cc_key))
        self.entry = ctk.CTkEntry(
            box, textvariable=self.value_var, height=36,
            placeholder_text="name@company.com",
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
            font=theme.body_font(),
        )
        self.entry.pack(fill="x", padx=18, pady=(0, 6))
        self.entry.bind("<Return>", lambda e: self._save())
        self.entry.bind("<Escape>", lambda e: self._cancel())

        ctk.CTkLabel(
            box,
            text="Separate multiple addresses with a semicolon (;). "
                 "Leave blank, or use Clear CC, for no CC at all.",
            font=theme.small_font(), text_color=theme.TEXT_MUTED,
            wraplength=520, justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 14))

        self.error_label = ctk.CTkLabel(
            self, text="", font=theme.small_font(), text_color=theme.DANGER,
            wraplength=540, justify="left",
        )
        self.error_label.pack(anchor="w", padx=22)

    # ------------------------------------------------------------ actions --
    def _save(self):
        cleaned, error = validate_cc(self.value_var.get())
        if error:
            self.error_label.configure(text=error)
            return
        self._finish(cleaned)

    def _clear(self):
        self._finish("")

    def _finish(self, value):
        self.settings.set_cc_for(self.cc_key, value)
        self.result = value
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        if self.on_saved:
            self.on_saved(value)

    def _cancel(self):
        self.result = None
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def wait_for_result(self):
        """Block until the dialog closes; returns the saved value or None."""
        self.wait_window()
        return self.result
