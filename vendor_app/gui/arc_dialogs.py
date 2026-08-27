"""Full-record modals for an ARC and for an FO.

Both follow the vendor dialog's shape: the action bar is reserved at the
bottom before the scrolling body, so Save can never be pushed off-screen on
a short or scaled display.

Neither dialog lets you type a rolled-up total. An ARC carries the target
value released in SAP as an ordinary field, but what has actually been
ordered against it - the sum of its FOs - is a read-out, as is an FO's
line-item total. A figure that disagrees with its own detail is the one
thing this module exists to prevent, so no such figure is ever typed.
"""

import customtkinter as ctk
from tkinter import messagebox

from vendor_app.config import (
    ARC_KEYS, ARC_LABELS, ARC_STATUS_DEFAULT, ARC_STATUS_VALUES,
    FO_KEYS, FO_LABELS, FO_STATUS_DEFAULT, FO_STATUS_VALUES,
)
from vendor_app.arc import format_amount
from vendor_app.validators import ValidationError
from vendor_app.gui import theme
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, divider, primary_button, secondary_button, section_label


class _RecordDialog(ctk.CTkToplevel):
    """Shared scaffolding: sized to the screen, buttons reserved first."""

    KEYS = ()
    LABELS = {}
    SECTIONS = ()
    STATUS_KEY = "status"
    STATUS_VALUES = ()
    STATUS_DEFAULT = ""
    PRIMARY_KEY = ""
    TITLE_NEW = "Add Record"
    TITLE_EDIT = "Edit Record"
    HINT = ""

    def __init__(self, master, store, record=None, on_saved=None):
        super().__init__(master)
        self.store = store
        self.on_saved = on_saved
        self.record = record or {}
        self.is_new = not bool(record)

        self.configure(fg_color=theme.BG_SURFACE)
        self.title(self.TITLE_NEW if self.is_new else self.TITLE_EDIT)

        screen_h, screen_w = self.winfo_screenheight(), self.winfo_screenwidth()
        height = min(780, max(420, screen_h - 120))
        width = min(640, max(440, screen_w - 80))
        self.geometry(
            f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 3)}"
        )
        self.minsize(440, 380)
        self.transient(master)
        self.grab_set()

        self.vars = {}
        self.status_var = ctk.StringVar(
            value=self.record.get(self.STATUS_KEY) or self.STATUS_DEFAULT
        )
        self._first_entry = None
        self._build()
        self.after(50, self._focus_first)

    def rollup_text(self):
        """Subclass hook: the read-only aggregate line, or None."""
        return None

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            header, text=self.TITLE_NEW if self.is_new else self.TITLE_EDIT,
            font=theme.h1_font(), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header, text=self.HINT, font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY, wraplength=560, justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # Reserved before the body, so the buttons survive any window height.
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        primary_button(buttons, "Save", self.save, width=120).pack(side="right", padx=(8, 0))
        secondary_button(buttons, "Cancel", self.destroy, width=120).pack(side="right")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        rollup = self.rollup_text()
        if rollup:
            banner = card(body, fg_color=theme.ACCENT_SOFT)
            banner.pack(fill="x", pady=(0, 12))
            ctk.CTkLabel(
                banner, text=rollup, font=theme.font(13, "bold"), text_color=theme.ACCENT,
                justify="left", anchor="w", wraplength=520,
            ).pack(anchor="w", padx=18, pady=14)

        for title, keys in self.SECTIONS:
            box = card(body, fg_color=theme.BG_CARD)
            box.pack(fill="x", pady=(0, 14))
            section_label(box, title).pack(anchor="w", padx=18, pady=(14, 4))
            divider(box).pack(fill="x", padx=18, pady=(0, 10))
            for key in keys:
                if key == self.STATUS_KEY:
                    self._status_row(box)
                else:
                    self._field_row(box, key)
            ctk.CTkFrame(box, fg_color="transparent", height=6).pack()

    def _field_row(self, parent, key):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        required = key == self.PRIMARY_KEY
        ctk.CTkLabel(
            row, text=self.LABELS[key] + (" *" if required else ""), width=190, anchor="w",
            font=theme.body_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(side="left")

        var = ctk.StringVar(value=self.record.get(key, ""))
        entry = ctk.CTkEntry(
            row, textvariable=var, height=32,
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
        )
        entry.pack(side="left", fill="x", expand=True)
        if required and not self.is_new:
            # readonly, not disabled: the key must not change, but it still
            # has to be selectable so it can be copied out.
            entry.configure(state="readonly", text_color=theme.TEXT_PRIMARY)
        elif self._first_entry is None:
            self._first_entry = entry
        self.vars[key] = var

    def _status_row(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(
            row, text=self.LABELS[self.STATUS_KEY], width=190, anchor="w",
            font=theme.body_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(side="left")
        ctk.CTkOptionMenu(
            row, variable=self.status_var, values=list(self.STATUS_VALUES), width=220, height=32,
            fg_color=theme.BG_INPUT, button_color=theme.BG_CARD_ALT,
            button_hover_color=theme.BG_HOVER, dropdown_fg_color=theme.BG_CARD_ALT,
        ).pack(side="left")

    def _focus_first(self):
        if self._first_entry is not None:
            self._first_entry.focus_set()

    def persist(self, raw):
        raise NotImplementedError

    def save(self):
        raw = {key: var.get() for key, var in self.vars.items()}
        raw[self.STATUS_KEY] = self.status_var.get()
        if not self.is_new:
            raw[self.PRIMARY_KEY] = self.record[self.PRIMARY_KEY]
        try:
            result = self.persist(raw)
        except ValidationError as exc:
            messagebox.showerror("Validation Error", str(exc), parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()
        notify(self.master, f"{self.LABELS[self.PRIMARY_KEY]} {raw[self.PRIMARY_KEY]} {result}.")


class ArcDialog(_RecordDialog):
    KEYS = ARC_KEYS
    LABELS = ARC_LABELS
    PRIMARY_KEY = "arc_no"
    STATUS_VALUES = ARC_STATUS_VALUES
    STATUS_DEFAULT = ARC_STATUS_DEFAULT
    TITLE_NEW = "Add ARC"
    TITLE_EDIT = "Edit ARC"
    HINT = ("ARC No is the master key - every FO and every amendment is filed "
            "against it. ARC Value is the target released in SAP; what has "
            "actually been ordered against it is shown above, not typed in.")
    SECTIONS = (
        ("CONTRACT", ["arc_no", "arc_description", "plant", "purchasing_group",
                      "release_status", "status"]),
        ("VENDOR", ["vendor_code", "vendor_name"]),
        ("VALIDITY", ["arc_start_date", "arc_end_date"]),
        ("VALUE", ["arc_value"]),
        ("AMENDMENT", ["amendment_no", "amendment_date", "remarks"]),
    )

    def rollup_text(self):
        if self.is_new:
            return None
        arc_no = self.record.get("arc_no", "")
        fos = self.store.fos_for_arc(arc_no)
        ordered = self.store.fo_value_for_arc(arc_no)
        target = self.store.arc_target_value(arc_no)
        gap = target - ordered
        lines = [
            f"ARC Value (target): {format_amount(target)}",
            f"Ordered on {len(fos)} FO(s): {format_amount(ordered)}",
        ]
        if gap > 0:
            lines.append(f"Balance still to order: {format_amount(gap)}")
        elif gap < 0:
            lines.append(f"OVER-ORDERED by {format_amount(-gap)} against this ARC")
        else:
            lines.append("Fully ordered against.")
        return "\n".join(lines)

    def persist(self, raw):
        return self.store.upsert_arc(raw)


class FoDialog(_RecordDialog):
    KEYS = FO_KEYS
    LABELS = FO_LABELS
    PRIMARY_KEY = "fo_no"
    STATUS_VALUES = FO_STATUS_VALUES
    STATUS_DEFAULT = FO_STATUS_DEFAULT
    TITLE_NEW = "Add FO"
    TITLE_EDIT = "Edit FO"
    HINT = ("An FO is a sub-part of one ARC, so ARC No is required. Once the FO "
            "has line items they become its value; the figure below is only used "
            "while it has none.")
    SECTIONS = (
        ("ORDER", ["fo_no", "arc_no", "fo_description", "plant", "purchasing_group",
                   "status"]),
        ("VENDOR", ["vendor_code", "vendor_name"]),
        ("VALIDITY", ["fo_date", "validity_end_date"]),
        ("VALUE", ["fo_value", "released_value", "open_value", "remarks"]),
    )

    def rollup_text(self):
        if self.is_new:
            return None
        fo_no = self.record.get("fo_no", "")
        lines = self.store.lines_for_fo(fo_no)
        total = self.store.fo_total(fo_no)
        if lines:
            return (f"FO Total: {format_amount(total)}\n"
                    f"Summed from {len(lines)} line item(s) - the entered FO Value "
                    "below is ignored while lines exist.")
        return (f"FO Total: {format_amount(total)}\n"
                "Taken from the entered FO Value - this FO has no line items yet.")

    def persist(self, raw):
        return self.store.upsert_fo(raw)
