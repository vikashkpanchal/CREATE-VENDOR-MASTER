"""Full-record modal for one machine in the equipment master.

Double-clicking a row in the equipment grid opens this rather than editing
a single cell, so the whole machine can be reviewed and corrected in one
place - the same way double-click has always worked on a vendor.

A de-mobbed machine opens read-only. Its record is closed: the point of
de-mobbing is that the row stops changing, and if the machine returns it is
entered as a fresh record instead.
"""

import customtkinter as ctk
from tkinter import messagebox

from vendor_app.config import LEASE_TYPE_VALUES, DEMOB_FIELD, EQUIPMENT_KEYS, EQUIPMENT_LABELS
from vendor_app.equipment import is_demobbed
from vendor_app.validators import ValidationError
from vendor_app.gui import theme
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, divider, primary_button, secondary_button, section_label

CHOICE_FIELDS = {"lease_type": LEASE_TYPE_VALUES}
NOT_SET = "(not set)"

SECTIONS = [
    ("MACHINE", ["equipment_description", "uom", "capacity", "ro_rh", "lease_type"]),
    ("IDENTIFIERS", ["rh_ro_number", "technical_id", "reg_no"]),
    ("VENDOR", ["vendor_code", "vendor_name"]),
    ("DEPLOYMENT", ["rh_date", "demob_date", "plant", "plant_code", "shift"]),
    ("CONTRACT", ["validity_end_date", "arc_no", "fo_no"]),
    ("RATES", ["mcm_shift_code", "disc_mcm_shift", "mcm_shift_rate",
               "ot_code", "dic_ot", "ot_rate"]),
]


class EquipmentDialog(ctk.CTkToplevel):
    """Edit one equipment record in full. `record` is the stored dict."""

    def __init__(self, master, store, record=None, on_saved=None):
        super().__init__(master)
        self.store = store
        self.on_saved = on_saved
        self.record = record or {}
        self.is_new = not bool(record)
        self.locked = is_demobbed(self.record)

        self.configure(fg_color=theme.BG_SURFACE)
        self.title("Add Equipment" if self.is_new else "Equipment Record")

        # Sized against the real screen so Save is never off the bottom edge.
        screen_h, screen_w = self.winfo_screenheight(), self.winfo_screenwidth()
        height = min(820, max(440, screen_h - 120))
        width = min(660, max(460, screen_w - 80))
        self.geometry(
            f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 3)}"
        )
        self.minsize(460, 400)
        self.transient(master)
        self.grab_set()

        self.vars = {}
        self._first_entry = None
        self._build()
        self.after(50, self._focus_first)

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            header, text="Add Equipment" if self.is_new else "Equipment Record",
            font=theme.h1_font(), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=(
                "This machine is de-mobbed, so its record is closed and read-only. "
                "If it has returned to site, add it again as a new record."
                if self.locked else
                "Blank fields are left unchanged - only fields you edit overwrite the "
                "stored record. At least one of RH/RO Number, Technical ID or Reg No "
                "is required."
            ),
            font=theme.small_font(),
            text_color=theme.WARNING if self.locked else theme.TEXT_SECONDARY,
            wraplength=580, justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # Reserved before the body so the action bar survives any window height.
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        if self.locked:
            secondary_button(buttons, "Close", self.destroy, width=120).pack(side="right")
        else:
            primary_button(buttons, "Save", self.save, width=120).pack(side="right", padx=(8, 0))
            secondary_button(buttons, "Cancel", self.destroy, width=120).pack(side="right")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        for title, keys in SECTIONS:
            box = card(body, fg_color=theme.BG_CARD)
            box.pack(fill="x", pady=(0, 14))
            section_label(box, title).pack(anchor="w", padx=18, pady=(14, 4))
            divider(box).pack(fill="x", padx=18, pady=(0, 10))
            for key in keys:
                self._field_row(box, key)
            ctk.CTkFrame(box, fg_color="transparent", height=6).pack()

    def _field_row(self, parent, key):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(
            row, text=EQUIPMENT_LABELS[key], width=200, anchor="w",
            font=theme.body_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(side="left")

        if key in CHOICE_FIELDS and not self.locked:
            # Lease Type is dry or wet and nothing else, so it is a list
            # rather than a box a third value can be typed into.
            current = (self.record.get(key, "") or "").upper()
            var = ctk.StringVar(
                value=current if current in CHOICE_FIELDS[key] else NOT_SET
            )
            ctk.CTkOptionMenu(
                row, variable=var, values=[NOT_SET] + list(CHOICE_FIELDS[key]),
                width=200, height=32,
                fg_color=theme.BG_INPUT, button_color=theme.BG_CARD_ALT,
                button_hover_color=theme.BG_HOVER, dropdown_fg_color=theme.BG_CARD_ALT,
            ).pack(side="left")
            self.vars[key] = var
            return

        var = ctk.StringVar(value=self.record.get(key, ""))
        entry = ctk.CTkEntry(
            row, textvariable=var, height=32,
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
        )
        entry.pack(side="left", fill="x", expand=True)
        if self.locked:
            # readonly rather than disabled: a closed record still has to be
            # readable and copyable, it just cannot be changed.
            entry.configure(state="readonly", text_color=theme.TEXT_SECONDARY)
        elif self._first_entry is None:
            self._first_entry = entry
        self.vars[key] = var

    def _focus_first(self):
        if self._first_entry is not None:
            self._first_entry.focus_set()

    def save(self):
        if self.locked:
            return
        raw = {key: var.get() for key, var in self.vars.items()}
        for key in CHOICE_FIELDS:
            if raw.get(key) == NOT_SET:
                raw[key] = ""

        # Setting a De-mob Date here closes the record, so route it through
        # demob() - the one path that logs the closure and releases the
        # machine's identifiers for a future re-arrival.
        new_demob = raw.get(DEMOB_FIELD, "").strip()
        had_demob = bool(self.record.get(DEMOB_FIELD, "").strip())

        try:
            if self.is_new:
                result = self.store.upsert(raw)
            else:
                result = self._save_existing(raw, new_demob, had_demob)
        except ValidationError as exc:
            messagebox.showerror("Validation Error", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Could Not Save", str(exc), parent=self)
            return

        if self.on_saved:
            self.on_saved()
        self.destroy()
        notify(self.master, f"Equipment record {result}.")

    def _save_existing(self, raw, new_demob, had_demob):
        """Apply the edited fields to the stored record, one at a time, so
        every change goes through the store's own validation and change log."""
        changed = 0
        for key in EQUIPMENT_KEYS:
            if key == DEMOB_FIELD:
                continue
            value = raw.get(key, "")
            if value != self.record.get(key, ""):
                self.store.update_field(self.record, key, value)
                changed += 1

        if new_demob and not had_demob:
            identifier = next(
                (self.record.get(k) for k in ("rh_ro_number", "technical_id", "reg_no")
                 if self.record.get(k)), ""
            )
            self.store.demob(identifier, new_demob)
            return "updated and de-mobbed"
        return "updated" if changed else "unchanged"
