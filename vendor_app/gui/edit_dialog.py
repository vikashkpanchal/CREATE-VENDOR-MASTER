"""Modal dialog for adding a new vendor or editing an existing one.

Reused by both the Search tab ("Edit This Vendor Record") and the Master
Data tab ("Edit Selected" / double-click / "+ Add Vendor"). Saves go
through VendorStore.upsert, so the same cell-level merge rules apply
everywhere. Lifecycle status (Active/Inactive/Blocked) is edited here too.
"""

import customtkinter as ctk
from tkinter import messagebox

from vendor_app.config import LABELS, STATUS_VALUES, STATUS_DEFAULT, VENDOR_TYPE_VALUES
from vendor_app.validators import ValidationError
from vendor_app.gui import theme
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, divider, primary_button, secondary_button, section_label
from vendor_app.gui.util import claim_focus, fit_on_screen

# Vendor Type is a choice, not free text, so it is rendered as a dropdown
# rather than an entry - there is no way to type a third value into it.
CHOICE_FIELDS = {"vendor_type": VENDOR_TYPE_VALUES}
NOT_SET = "(not set)"

# (title, fields, how wide the card is). A "half" card takes one of the two
# columns, so the two contact blocks sit side by side instead of one under
# the other - which is what gets the whole record onto one screen.
SECTIONS = [
    # Type sits with Status at the end of the vendor block: both are choices
    # about the vendor rather than parts of its identity, and both come after
    # the mandated fields in the grid and the export too.
    ("VENDOR", ["vendor_code", "vendor_name", "vendor_email", "vendor_type"], "full"),
    ("LOCATION", ["city", "state"], "full"),
    ("CONTACT PERSON 1",
     ["vendor_owner_name", "vendor_owner_contact", "vendor_owner_email"], "half"),
    ("CONTACT PERSON 2",
     ["vendor_supervisor_name", "vendor_supervisor_contact", "vendor_supervisor_email"], "half"),
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

        # Wide enough to read, and laid out two fields to a row (see
        # _build_form). A 560px single column meant twelve fields in a
        # letterbox, five visible at a time with the rest behind a scroll -
        # the whole record is the point of this dialog, so it is sized to
        # show it. Still fitted to the real screen, so Save is never off the
        # bottom edge on a laptop or at 150% display scaling.
        fit_on_screen(self, 980, 860, min_w=720, min_h=520, margin_h=100)
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
            "Vendor Code is mandatory and numeric. Vendor Type is CAD or MARKET. "
            "Contact numbers must be digits only. Separate multiple emails with a "
            "semicolon (;)."
            if self.is_new
            else "Blank fields are left unchanged - only fields you edit overwrite the stored record. "
            "Separate multiple emails with a semicolon (;)."
        )
        ctk.CTkLabel(
            header, text=hint_text, font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            wraplength=900, justify="left",
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
        wrapper.pack(fill="both", expand=True, padx=20, pady=(6, 6))
        for column in range(self.COLUMNS):
            wrapper.grid_columnconfigure(column, weight=1, uniform="section")

        row = column = 0
        for title, keys, width in SECTIONS:
            box = card(wrapper, fg_color=theme.BG_CARD)
            if width == "half":
                box.grid(row=row, column=column, sticky="nsew",
                         padx=(0, 12) if column == 0 else (0, 0), pady=(0, 10))
                column += 1
                if column >= self.COLUMNS:
                    column, row = 0, row + 1
            else:
                if column:                       # finish a part-filled row first
                    column, row = 0, row + 1
                box.grid(row=row, column=0, columnspan=self.COLUMNS,
                         sticky="ew", pady=(0, 10))
                row += 1

            section_label(box, title).pack(anchor="w", padx=18, pady=(12, 2))
            divider(box).pack(fill="x", padx=18, pady=(0, 8))

            grid = ctk.CTkFrame(box, fg_color="transparent")
            grid.pack(fill="x", padx=18, pady=(0, 6))
            # A half-width card holds one field per row; a full-width one two.
            columns = self.COLUMNS if width == "full" else 1
            for index in range(columns):
                grid.grid_columnconfigure(index, weight=1, uniform="field")

            cells = list(keys) + (["status"] if title == "VENDOR" else [])
            for index, key in enumerate(cells):
                self._add_field(grid, key, index // columns, index % columns)

            ctk.CTkFrame(box, fg_color="transparent", height=2).pack()

    # Two fields to a row. The dialog's minimum width keeps both columns
    # readable, so this never needs to reflow - and a fixed arrangement
    # cannot oscillate the way a measured one can.
    COLUMNS = 2

    def _add_field(self, parent, key, row, column):
        """One labelled field - entry, or dropdown for a choice - in a cell."""
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=row, column=column, sticky="ew", padx=(0, 14), pady=5)
        cell.grid_columnconfigure(0, weight=1)

        label_text = ("Status" if key == "status"
                      else LABELS[key] + (" *" if key == "vendor_code" else ""))
        ctk.CTkLabel(
            cell, text=label_text, anchor="w", font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=0, column=0, sticky="w", pady=(0, 3))

        if key == "status":
            ctk.CTkOptionMenu(
                cell, variable=self.status_var, values=STATUS_VALUES, height=34,
                fg_color=theme.BG_INPUT, button_color=theme.BG_CARD_ALT,
                button_hover_color=theme.BG_HOVER, dropdown_fg_color=theme.BG_CARD_ALT,
            ).grid(row=1, column=0, sticky="ew")
            return

        if key in CHOICE_FIELDS:
            current = (self.record.get(key, "") or "").upper()
            var = ctk.StringVar(value=current if current in CHOICE_FIELDS[key] else NOT_SET)
            ctk.CTkOptionMenu(
                cell, variable=var, values=[NOT_SET] + list(CHOICE_FIELDS[key]), height=34,
                fg_color=theme.BG_INPUT, button_color=theme.BG_CARD_ALT,
                button_hover_color=theme.BG_HOVER, dropdown_fg_color=theme.BG_CARD_ALT,
            ).grid(row=1, column=0, sticky="ew")
            self.vars[key] = var
            return

        var = ctk.StringVar(value=self.record.get(key, ""))
        entry = ctk.CTkEntry(
            cell, textvariable=var, height=34,
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
            font=theme.body_font(),
        )
        entry.grid(row=1, column=0, sticky="ew")

        if key == "vendor_code" and not self.is_new:
            # readonly (not disabled): the primary key must never be edited,
            # but the user still needs to select and copy it.
            entry.configure(state="readonly", text_color=theme.TEXT_PRIMARY)
        elif self._first_entry is None:
            self._first_entry = entry

        self.vars[key] = var

    def _focus_first_field(self):
        # claim_focus rather than a single focus_set: on Windows the caret is
        # otherwise lost when CustomTkinter withdraws and re-shows the window
        # to recolour its title bar. See vendor_app/gui/util.py.
        if self._first_entry is not None:
            claim_focus(self, self._first_entry)

    def save(self):
        raw = {key: self.vars[key].get() for key in self.vars}
        for key in CHOICE_FIELDS:
            if raw.get(key) == NOT_SET:
                raw[key] = ""
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
