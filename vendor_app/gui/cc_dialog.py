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

import re

import customtkinter as ctk

from vendor_app.gui import theme
from vendor_app.gui.widgets import card, danger_button, divider, primary_button, secondary_button, section_label
from vendor_app.gui.util import claim_focus, fit_on_screen, focus_on_click


# An entry with no "@" at all - a distribution list or a name out of the
# address book ("P&M Cell", "RIL-PM-CELL"). Outlook resolves these against
# the GAL, so they are accepted; anything with a character an address book
# entry would never carry is not.
_ALIAS_RE = re.compile(r"^[\w.&'\- ]+$", re.UNICODE)
# "Vikash Panchal <vikash.panchal@ril.com>" - what you get when a recipient
# is copied out of Outlook.
_DISPLAY_RE = re.compile(r"^(?P<name>[^<>]*)<(?P<addr>[^<>]+)>$")


def _check_address(address: str):
    """One CC entry. Returns (cleaned, error_or_None).

    Deliberately permissive, because Outlook - not this app - resolves
    recipients, and being stricter than Outlook only blocks addresses that
    would have worked. A plant address book is full of entries this used to
    reject: internal domains with no dot in them (name@ril), distribution
    lists with no "@" at all, and the "Name <address>" form that comes from
    copying a recipient out of Outlook itself.
    """
    text = address.strip().strip(",").strip()
    if not text:
        return "", None

    match = _DISPLAY_RE.match(text)
    if match:
        inner = match.group("addr").strip()
        if inner.count("@") != 1 or " " in inner:
            return None, f"'{text}' is not a valid email address."
        return text, None

    if "<" in text or ">" in text:
        return None, (f"'{text}' has a stray < or > - write it as "
                      "Name <address@company.com>.")

    if "@" not in text:
        if _ALIAS_RE.match(text):
            return text, None          # a distribution list or address-book name
        return None, f"'{text}' is not an email address or an address-book name."

    if text.count("@") != 1:
        return None, f"'{text}' has more than one @."
    local, _, domain = text.partition("@")
    if not local or not domain or " " in text:
        return None, f"'{text}' is not a valid email address."
    if domain.startswith(".") or domain.endswith("."):
        return None, f"'{text}' has a misplaced dot in its domain."
    return text, None


def validate_cc(value: str):
    """Validate a CC list. Returns (cleaned, error_or_None).

    Entries may be separated by a semicolon, a comma or a newline - pasting
    a column straight out of Excel is the normal way this field gets
    filled - and the cleaned result is always semicolon-separated, which is
    what Outlook expects.

    Blank is valid and means "no CC".
    """
    text = (value or "").strip()
    if not text:
        return "", None

    parts = [p for p in re.split(r"[;\n\r]+", text.replace(",", ";")) if p.strip()]
    addresses = []
    for part in parts:
        cleaned, error = _check_address(part)
        if error:
            return None, error
        if cleaned and cleaned not in addresses:
            addresses.append(cleaned)

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
        fit_on_screen(self, 620, 330, min_w=440, min_h=300, margin_w=120)
        self.resizable(True, False)
        self.transient(master)

        self._build()

        # Grab only once the window actually exists, otherwise the grab can
        # land before the entry is mapped and swallow its first clicks.
        self.after(80, self._activate)
        # ...and claim the caret repeatedly while the window settles, because
        # on Windows a fixed delay is not enough on its own. See claim_focus.
        claim_focus(self, self.entry)

    def _activate(self):
        try:
            self.grab_set()
        except Exception:
            pass
        # Select the whole address so typing replaces it - but only while it
        # is still untouched. Selecting text the user has already started
        # typing would wipe it on their next keystroke.
        if self.value_var.get() == self._initial_value:
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

        self._initial_value = self.settings.cc_for(self.cc_key)
        self.value_var = ctk.StringVar(value=self._initial_value)
        self.entry = ctk.CTkEntry(
            box, textvariable=self.value_var, height=36,
            placeholder_text="name@company.com",
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
            font=theme.body_font(),
        )
        self.entry.pack(fill="x", padx=18, pady=(0, 6))
        self.entry.bind("<Return>", lambda e: self._save())
        self.entry.bind("<Escape>", lambda e: self._cancel())
        # Any click on the field - text, border or padding - takes the caret.
        focus_on_click(self.entry, self.entry._entry,
                       getattr(self.entry, "_canvas", None), box)

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
