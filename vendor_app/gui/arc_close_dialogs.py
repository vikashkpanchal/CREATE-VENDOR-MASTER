"""Closing a contract, and renewing one.

Two small windows behind the ARC Records screen's Close and Renew buttons.
Both act on the whole purchasing document rather than on the line that
happens to be selected: a contract is closed - and renewed - as a whole, and
closing one line of it would mean nothing.

Closing is this app's own mark, not SAP's. It says "this contract is
finished": it drops out of the expiry, risk and release figures, and it is
counted on its own as Closed ARC. Renewing extends the validity to a new
date and, if the contract had been closed, re-opens it - because a contract
somebody is extending is plainly live again.
"""

from datetime import date

import customtkinter as ctk

from vendor_app.arc import format_date
from vendor_app.config import ARC_LABELS
from vendor_app.gui import theme
from vendor_app.gui.util import claim_focus, fit_on_screen, focus_on_click, grow_to_fit
from vendor_app.gui.widgets import card, divider, primary_button, secondary_button, section_label
from vendor_app.validators import ValidationError


class _ContractActionDialog(ctk.CTkToplevel):
    """Shared frame: a headline, the contract it is about, some fields, and
    one action button that cannot be pushed off the bottom."""

    TITLE = ""
    ACTION = ""
    WIDTH, HEIGHT = 560, 420

    def __init__(self, master, store, document, header, on_done=None):
        super().__init__(master)
        self.store = store
        self.document = document
        self.header = header or {}
        self.on_done = on_done
        self.vars = {}
        self._first_entry = None

        self.configure(fg_color=theme.BG_SURFACE)
        self.title(self.TITLE)
        fit_on_screen(self, self.WIDTH, self.HEIGHT, min_w=440, min_h=330, margin_h=120)
        self.transient(master)
        self.grab_set()
        self._build()
        # The fields exist now, so the window can be sized to what they
        # really need rather than to a figure written when it was designed -
        # a window a few pixels short leaves the last field unusable.
        grow_to_fit(self, content=getattr(self, "_content", None))
        self.bind("<Escape>", lambda e: self.destroy())
        if self._first_entry is not None:
            claim_focus(self, self._first_entry)

    # ----------------------------------------------------------- building --
    def _build(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            head, text=self.TITLE, font=theme.h1_font(), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            head, text=self.subtitle(), font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY, anchor="w", justify="left", wraplength=480,
        ).pack(anchor="w", pady=(4, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        primary_button(buttons, self.ACTION, self.submit, width=150).pack(
            side="right", padx=(8, 0)
        )
        secondary_button(buttons, "Cancel", self.destroy, width=110).pack(side="right")

        self.error_label = ctk.CTkLabel(
            self, text="", font=theme.small_font(), text_color=theme.DANGER,
            anchor="w", justify="left", wraplength=480,
        )
        self.error_label.pack(side="bottom", anchor="w", padx=22, pady=(0, 6))

        # The fields scroll. At 150% display scaling on a 14" screen there is
        # not room for four of them plus the headline, and a window that is
        # merely too short does not scroll by itself - Tk stops giving room
        # to whatever is packed last, which arrives as a field one pixel high
        # that cannot be clicked into. Scrolling is what makes every field
        # reachable at any scaling; the buttons, reserved above, never move.
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        box = card(body, fg_color=theme.BG_CARD)
        box.pack(fill="both", expand=True)
        self._content = box
        section_label(box, "CONTRACT").pack(anchor="w", padx=18, pady=(14, 2))
        ctk.CTkLabel(
            box, text=self.contract_line(), font=theme.body_font(),
            text_color=theme.TEXT_PRIMARY, anchor="w", justify="left", wraplength=460,
        ).pack(anchor="w", padx=18, pady=(0, 8))
        divider(box).pack(fill="x", padx=18, pady=(0, 10))
        self.build_fields(box)
        ctk.CTkFrame(box, fg_color="transparent", height=8).pack()

    def field(self, parent, key, label, value="", placeholder=""):
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
        return entry

    def contract_line(self):
        vendor = self.header.get("vendor_supplying_plant", "")
        end = format_date(self.header.get("validity_end", ""))
        line = f"{self.document}"
        if vendor:
            line += f"\n{vendor}"
        if end:
            line += f"\nValidity Period End: {end}"
        closed = format_date(self.header.get("closure_date", ""))
        if closed:
            line += f"\nClosed on {closed}"
        return line

    # ------------------------------------------------------- overridables --
    def subtitle(self):
        return ""

    def build_fields(self, parent):
        raise NotImplementedError

    def apply(self):
        raise NotImplementedError

    # ---------------------------------------------------------- finishing --
    def submit(self):
        try:
            message = self.apply()
        except ValidationError as exc:
            self.error_label.configure(text=str(exc))
            return
        except Exception as exc:                      # a store failure, surfaced
            self.error_label.configure(text=str(exc))
            return
        self.grab_release()
        self.destroy()
        if self.on_done:
            self.on_done(message)


class CloseArcDialog(_ContractActionDialog):
    TITLE = "Close Contract"
    ACTION = "Close Contract"
    HEIGHT = 500

    def subtitle(self):
        return ("A closed contract is finished: it leaves the active, expiring, "
                "at-risk, awaiting-release and without-FO figures, and is counted "
                "on its own as Closed ARC. Its rows stay exactly as they are, and "
                "it can be re-opened or renewed at any time.")

    def build_fields(self, parent):
        self.field(parent, "closure_date", ARC_LABELS["closure_date"],
                   value=format_date(date.today()), placeholder="DD.MM.YYYY")
        self.field(parent, "closure_remarks", ARC_LABELS["closure_remarks"],
                   value=self.header.get("closure_remarks", ""),
                   placeholder="why it is being closed (optional)")

    def apply(self):
        count = self.store.close_document(
            self.document,
            closure_date=self.vars["closure_date"].get(),
            remarks=self.vars["closure_remarks"].get(),
        )
        if not count:
            raise ValidationError("This contract", "is not on file - refresh and try again")
        return f"Contract {self.document} closed ({count} item(s))."


class RenewArcDialog(_ContractActionDialog):
    TITLE = "Renew Contract"
    ACTION = "Renew Contract"
    HEIGHT = 640

    def subtitle(self):
        return ("Extend the contract to a new Validity Period End. The new date "
                "must be after the current one. A new start date and a new target "
                "value are optional. A contract that was closed is re-opened by "
                "renewing it.")

    def build_fields(self, parent):
        self.field(parent, "validity_end", f"New {ARC_LABELS['validity_end']} *",
                   placeholder="DD.MM.YYYY")
        self.field(parent, "validity_start", f"New {ARC_LABELS['validity_start']}",
                   placeholder="optional - leave blank to keep "
                               f"{format_date(self.header.get('validity_start', ''))}")
        self.field(parent, "target_value", f"New {ARC_LABELS['target_value']}",
                   placeholder="optional - leave blank to keep "
                               f"{self.header.get('target_value', '')}")
        self.field(parent, "remarks", "Remarks",
                   placeholder="amendment reference (optional)")

    def apply(self):
        result = self.store.renew_document(
            self.document,
            validity_end=self.vars["validity_end"].get(),
            validity_start=self.vars["validity_start"].get() or None,
            target_value=self.vars["target_value"].get() or None,
            remarks=self.vars["remarks"].get(),
        )
        message = (f"Contract {self.document} renewed to {result['to']} "
                   f"(was {result['from'] or 'no date'}).")
        if result["was_closed"]:
            message += " It was closed, so it has been re-opened."
        return message
