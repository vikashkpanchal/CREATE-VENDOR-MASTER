"""Full-record modals for one contract item and one frame order item.

Both follow the vendor dialog's shape: the action bar is reserved at the
bottom before the scrolling body, so Save can never be pushed off-screen on
a short or scaled display.

Neither dialog lets you type a rolled-up total. Target Val. (Header) and the
per-item values are ordinary fields, but what a contract has had released
against it, and what one frame order adds up to, are read-outs. A figure
that disagrees with its own detail is the one thing this module exists to
prevent, so no such figure is ever typed.
"""

import customtkinter as ctk
from tkinter import messagebox

from vendor_app.config import (
    ARC_KEYS, ARC_LABELS, FO_KEYS, FO_LABELS,
    RELEASE_INDICATORS, RELEASE_STATUS_LEVELS,
    describe_release_indicator, describe_release_status,
)
from vendor_app.arc import format_amount
from vendor_app.validators import ValidationError, normalize
from vendor_app.gui import theme
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, divider, primary_button, secondary_button, section_label

NOT_STATED = "(not stated)"


def _choices(mapping):
    """A code list rendered as 'CODE - meaning', with a blank first option."""
    return [NOT_STATED] + [f"{code} - {text}" for code, text in mapping.items()]


def _code_of(choice):
    return "" if not choice or choice == NOT_STATED else choice.split(" - ", 1)[0]


class _RecordDialog(ctk.CTkToplevel):
    """Shared scaffolding: sized to the screen, buttons reserved first."""

    KEYS = ()
    LABELS = {}
    SECTIONS = ()
    KEY_FIELDS = ()
    CODE_FIELDS = {}
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
        height = min(820, max(420, screen_h - 120))
        width = min(680, max(440, screen_w - 80))
        self.geometry(
            f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 3)}"
        )
        self.minsize(440, 380)
        self.transient(master)
        self.grab_set()

        self.vars = {}
        self.code_vars = {}
        self._first_entry = None
        self._build()
        self.after(50, self._focus_first)

    def rollup_text(self):
        """Subclass hook: the read-only aggregate lines, or None."""
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
            text_color=theme.TEXT_SECONDARY, wraplength=600, justify="left",
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
                justify="left", anchor="w", wraplength=560,
            ).pack(anchor="w", padx=18, pady=14)

        for title, keys in self.SECTIONS:
            box = card(body, fg_color=theme.BG_CARD)
            box.pack(fill="x", pady=(0, 14))
            section_label(box, title).pack(anchor="w", padx=18, pady=(14, 4))
            divider(box).pack(fill="x", padx=18, pady=(0, 10))
            for key in keys:
                if key in self.CODE_FIELDS:
                    self._code_row(box, key)
                else:
                    self._field_row(box, key)
            ctk.CTkFrame(box, fg_color="transparent", height=6).pack()

    def _field_row(self, parent, key):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        required = key in self.KEY_FIELDS
        ctk.CTkLabel(
            row, text=self.LABELS[key] + (" *" if required else ""), width=210, anchor="w",
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

    def _code_row(self, parent, key):
        """A coded field, offered as its decoded meanings rather than as X's."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(
            row, text=self.LABELS[key], width=210, anchor="w",
            font=theme.body_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(side="left")
        current = normalize(self.record.get(key, "")).upper()
        options = _choices(self.CODE_FIELDS[key])
        value = next((o for o in options if _code_of(o) == current), NOT_STATED)
        var = ctk.StringVar(value=value)
        ctk.CTkOptionMenu(
            row, variable=var, values=options, width=300, height=32,
            fg_color=theme.BG_INPUT, button_color=theme.BG_CARD_ALT,
            button_hover_color=theme.BG_HOVER, dropdown_fg_color=theme.BG_CARD_ALT,
            font=theme.small_font(), dropdown_font=theme.small_font(),
        ).pack(side="left")
        self.code_vars[key] = var

    def _focus_first(self):
        if self._first_entry is not None:
            self._first_entry.focus_set()

    def persist(self, raw):
        raise NotImplementedError

    def title_of(self, raw):
        return " ".join(raw.get(k, "") for k in self.KEY_FIELDS).strip()

    def save(self):
        raw = {key: var.get() for key, var in self.vars.items()}
        for key, var in self.code_vars.items():
            raw[key] = _code_of(var.get())
        if not self.is_new:
            for key in self.KEY_FIELDS:
                raw[key] = self.record.get(key, "")
        try:
            result = self.persist(raw)
        except ValidationError as exc:
            messagebox.showerror("Validation Error", str(exc), parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()
        notify(self.master, f"{self.title_of(raw)} {result}.")


class ArcDialog(_RecordDialog):
    """One row of Table 1: an item of a purchasing document."""

    KEYS = ARC_KEYS
    LABELS = ARC_LABELS
    KEY_FIELDS = ("purchasing_document", "item")
    CODE_FIELDS = {
        "release_indicator": RELEASE_INDICATORS,
        "release_status": RELEASE_STATUS_LEVELS,
    }
    TITLE_NEW = "Add Contract Item"
    TITLE_EDIT = "Edit Contract Item"
    HINT = ("Purchasing Document is the contract every frame order and every "
            "amendment is filed against; Item is the line within it. The header "
            "fields repeat on every item of the same document, and the contract's "
            "Target Val. (Header) is read once rather than summed across them.")
    SECTIONS = (
        ("DOCUMENT", ["purchasing_document", "item", "document_date", "plant",
                      "purchasing_group"]),
        ("VENDOR", ["vendor_supplying_plant"]),
        ("ITEM", ["short_text"]),
        ("VALIDITY", ["validity_start", "validity_end"]),
        ("VALUE", ["target_value"]),
        ("RELEASE", ["release_indicator", "release_status", "po_history"]),
    )

    def rollup_text(self):
        if self.is_new:
            return None
        document = self.record.get("purchasing_document", "")
        items = self.store.items_for_document(document)
        frames = self.store.frames_for_document(document)
        target = self.store.target_value(document)
        released = self.store.released_against(document)
        gap = target - released
        lines = [
            f"Contract {document} - {len(items)} item(s), {len(frames)} frame order(s)",
            f"Target Val. (Header): {format_amount(target)}  (read once, not summed)",
            f"Released against it: {format_amount(released)}",
        ]
        if gap > 0:
            lines.append(f"Balance still to release: {format_amount(gap)}")
        elif gap < 0:
            lines.append(f"OVER-RELEASED by {format_amount(-gap)} against this contract")
        else:
            lines.append("Fully released against.")
        return "\n".join(lines)

    def persist(self, raw):
        return self.store.upsert_arc(raw)

    def title_of(self, raw):
        return f"{ARC_LABELS['purchasing_document']} {raw.get('purchasing_document', '')} " \
               f"item {raw.get('item', '')}".strip()


class FoDialog(_RecordDialog):
    """One row of Table 2: an item of a frame order."""

    KEYS = FO_KEYS
    LABELS = FO_LABELS
    KEY_FIELDS = ("frame_numbers", "item")
    TITLE_NEW = "Add Frame Order Item"
    TITLE_EDIT = "Edit Frame Order Item"
    HINT = ("A frame order is placed against one contract, so Contract No. is "
            "required - it maps from Table 1's Purchasing Document. Contract "
            "Value and the contract validity dates map across too and repeat on "
            "every row; Released, Actual and Opening Value belong to this item.")
    SECTIONS = (
        ("FRAME ORDER", ["frame_numbers", "item", "serial_no", "plant",
                         "frame_pur_group"]),
        ("CONTRACT", ["contract_no", "contract_pur_group", "header_text",
                      "contract_value", "validity_start", "validity_end"]),
        ("VENDOR", ["vendor", "vendor_name"]),
        ("FO VALIDITY", ["fo_validity_start", "fo_validity_end"]),
        ("ITEM", ["description", "requisitioner", "req_tracking_no"]),
        ("VALUE", ["released_value", "actual_value", "opening_value"]),
    )

    def rollup_text(self):
        if self.is_new:
            return None
        frame = self.record.get("frame_numbers", "")
        items = self.store.items_for_frame(frame)
        contract = self.record.get("contract_no", "")
        lines = [
            f"Frame order {frame} - {len(items)} item(s)",
            f"Released: {format_amount(self.store.frame_released(frame))}   "
            f"Actual: {format_amount(self.store.frame_value(frame, 'actual_value'))}   "
            f"Opening: {format_amount(self.store.frame_value(frame, 'opening_value'))}",
        ]
        if contract:
            target = self.store.target_value(contract)
            released = self.store.released_against(contract)
            lines.append(
                f"On contract {contract}: {format_amount(released)} released of "
                f"{format_amount(target)} target"
            )
        return "\n".join(lines)

    def persist(self, raw):
        return self.store.upsert_fo(raw)

    def title_of(self, raw):
        return f"Frame order {raw.get('frame_numbers', '')} item {raw.get('item', '')}".strip()
