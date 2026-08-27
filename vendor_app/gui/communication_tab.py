"""Communication: draft vendor emails from pasted data.

Two flows, sharing the same shape and the same one-email-per-vendor rule:

  * Defective Invoice Communication - paste invoice rows, every defective
    invoice for a vendor lands in ONE email to that vendor.
  * Equipment Breakdown Communication - paste RH/RO Numbers or Technical
    IDs, every broken-down machine for a vendor lands in ONE email.

Emails are saved as Outlook DRAFTS in their own sub-folder so the user
reviews them before sending. Each flow keeps its OWN CC row - the people
copied on an invoice chase are rarely the people copied on a breakdown -
asked for once and reused from then on.
"""

import webbrowser
import tempfile
import os
from tkinter import messagebox

import customtkinter as ctk

from vendor_app.config import (
    CC_BREAKDOWN_KEY,
    CC_DEFECTIVE_KEY,
    CC_FLOW_LABELS,
    DEFECTIVE_INVOICE_KEYS,
    DEFECTIVE_INVOICE_LABELS,
    OUTLOOK_BREAKDOWN_FOLDER,
    OUTLOOK_DEFECTIVE_FOLDER,
)
from vendor_app.communication import (
    build_breakdown_messages,
    build_defective_invoice_messages,
    parse_identifiers,
    parse_pasted_rows,
    resolve_breakdown_rows,
)
from vendor_app import outlook
from vendor_app.gui import theme
from vendor_app.gui.cc_dialog import CCAddressDialog
from vendor_app.gui.paste_grid import PasteGrid
from vendor_app.gui.missing_email_dialog import MissingEmailDialog
from vendor_app.gui.style import build_table, insert_row
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, pill, primary_button, secondary_button, section_label

PREVIEW_COLUMNS = ["vendor_code", "vendor_name", "rows", "to"]
PREVIEW_LABELS = {
    "vendor_code": "Vendor\nCode",
    "vendor_name": "Vendor\nName",
    "rows": "Rows in\nEmail",
    "to": "Recipient(s)",
}
PREVIEW_WIDTHS = {"vendor_code": 110, "vendor_name": 250, "rows": 100, "to": 420}


class _EmailFlow(ctk.CTkFrame):
    """Shared UI for both communication flows.

    Subclasses supply the input hint, how to turn pasted text into messages,
    and which Outlook folder the drafts belong in.
    """

    INPUT_TITLE = "PASTE DATA"
    INPUT_HINT = ""
    FOLDER = ""
    EMPTY_HINT = "Paste data, then Prepare Emails."
    # Which CC row this flow uses. Each flow has its own; they never share.
    CC_KEY = CC_DEFECTIVE_KEY

    def __init__(self, master, store, settings, on_data_changed=None, **kwargs):
        super().__init__(master, fg_color="transparent")
        self.store = store
        self.settings = settings
        self.on_data_changed = on_data_changed
        self.messages = []
        self._skip_codes = set()
        self._build()

    # ---------------------------------------------------------------- UI --
    def _build(self):
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        left = card(split, fg_color=theme.BG_CARD, width=getattr(self, "INPUT_WIDTH", 340))
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)
        section_label(left, self.INPUT_TITLE).pack(anchor="w", padx=16, pady=(16, 0))
        ctk.CTkLabel(
            left, text=self.INPUT_HINT, font=theme.small_font(),
            text_color=theme.TEXT_MUTED, justify="left", wraplength=300,
        ).pack(anchor="w", padx=16, pady=(0, 8))
        # Buttons reserved at the bottom BEFORE the expanding input, so the
        # input can never grow far enough to push them out of view.
        button_width = getattr(self, "INPUT_WIDTH", 340) - 32
        secondary_button(left, "Clear", self.clear_input, width=button_width).pack(
            side="bottom", padx=16, pady=(0, 16)
        )
        primary_button(left, "Prepare Emails", self.prepare, width=button_width).pack(
            side="bottom", padx=16, pady=(10, 6)
        )
        self.build_input(left)

        right = ctk.CTkFrame(split, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # This row is laid out with grid, NOT pack. With pack, a long status
        # message packed to the left claims its full requested width first and
        # the action buttons packed after it get whatever is left - which on a
        # narrow window was nothing, pushing Preview/Create Drafts off the
        # right edge where they could not be clicked. grid gives the buttons a
        # column of their own that the status text cannot encroach on.
        toolbar = ctk.CTkFrame(right, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.grid_columnconfigure(0, weight=1)
        toolbar.grid_columnconfigure(1, weight=0)

        actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")
        secondary_button(actions, "Preview Selected", self.preview_selected, width=160).pack(
            side="left", padx=(0, 8)
        )
        primary_button(
            actions, "Create Outlook Drafts", self.create_drafts, width=200
        ).pack(side="left")

        # This flow's own CC row, directly above its results.
        cc_row = ctk.CTkFrame(right, fg_color="transparent")
        cc_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        # Just "CC:" - the sub-tab above already says which flow this is, and
        # spelling it out again here cost the address pill the room to show
        # the address itself.
        ctk.CTkLabel(
            cc_row, text="CC:", font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))
        self.cc_pill = pill(cc_row, "", fg=theme.BG_CARD_ALT, tc=theme.TEXT_SECONDARY)
        self.cc_pill.pack(side="left")
        self.cc_pill.configure(cursor="hand2")
        self.cc_pill.bind("<Button-1>", lambda e: self.change_cc())
        secondary_button(cc_row, "Change CC", self.change_cc, width=115).pack(
            side="left", padx=(8, 0)
        )
        self._refresh_cc_pill()

        # The status line gets a row to itself, so however long the message
        # runs it can never squeeze the buttons or the CC controls.
        self.status_pill = pill(
            right, self.EMPTY_HINT, fg=theme.BG_CARD_ALT, tc=theme.TEXT_SECONDARY
        )
        self.status_pill.grid(row=2, column=0, sticky="w", pady=(0, 8))

        wrap = card(right, fg_color=theme.BG_CARD)
        wrap.grid(row=3, column=0, sticky="nsew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        outer, self.tree = build_table(wrap, PREVIEW_COLUMNS, PREVIEW_LABELS, PREVIEW_WIDTHS)
        outer.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.tree.bind("<Double-1>", lambda e: self.preview_selected())

    def build_input(self, parent):
        """Default input: a free-text paste box. Subclasses may replace it."""
        self.input_text = ctk.CTkTextbox(
            parent, width=300, height=300, fg_color=theme.BG_INPUT,
            border_color=theme.BG_INPUT_BORDER, border_width=1, font=("Consolas", 10),
        )
        self.input_text.pack(fill="both", expand=True, padx=16, pady=4)

    def read_input(self):
        return self.input_text.get("1.0", "end")

    def has_input(self):
        return bool(self.read_input().strip())

    def clear_input(self):
        self.input_text.delete("1.0", "end")
        self.messages = []
        self._skip_codes = set()
        self._render_preview()

    # ------------------------------------------------------------ prepare --
    def _build_messages(self, text, skip_codes):
        """Subclass hook. Returns the dict from build_*_messages()."""
        raise NotImplementedError

    def prepare(self):
        if not self.has_input():
            messagebox.showinfo("Nothing Pasted", "Paste some data first.")
            return

        try:
            result = self._build_messages(self.read_input(), self._skip_codes)
        except Exception as exc:
            messagebox.showerror("Could Not Read Input", str(exc))
            return

        if result is None:
            return

        unresolved = result.get("unresolved", [])
        if unresolved:
            # Ask for the missing addresses (or let the user skip those
            # vendors), then rebuild so the preview reflects the answers.
            MissingEmailDialog(self, self.store, unresolved, self._on_missing_resolved)
            return

        self._finish_prepare(result)

    def _on_missing_resolved(self, outcome):
        if outcome is None:
            return
        self._skip_codes.update(outcome.get("skipped", []))
        if self.on_data_changed and outcome.get("saved"):
            self.on_data_changed()
        try:
            result = self._build_messages(self.read_input(), self._skip_codes)
        except Exception as exc:
            messagebox.showerror("Could Not Read Input", str(exc))
            return
        if result is None:
            return
        if result.get("unresolved"):
            MissingEmailDialog(self, self.store, result["unresolved"], self._on_missing_resolved)
            return
        self._finish_prepare(result)

    def _finish_prepare(self, result):
        self.messages = result.get("messages", [])
        skipped = result.get("skipped", [])
        self._render_preview()

        status = f"{len(self.messages)} email(s) ready - one per vendor"
        if skipped:
            status += f"  •  {len(skipped)} vendor(s) skipped"
        extra = result.get("note")
        if extra:
            status += f"  •  {extra}"
        # Cap the status text: it shares its row with the action buttons, and
        # an unbounded message is what used to squeeze them off the screen.
        if len(status) > 110:
            status = status[:107] + "..."
        self.status_pill.configure(text=f"  {status}  ")

    def _render_preview(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, message in enumerate(self.messages):
            insert_row(
                self.tree, i, iid=message["vendor_code"],
                values=[
                    message["vendor_code"],
                    message["vendor_name"],
                    message["row_count"],
                    message["to"],
                ],
            )

    # ------------------------------------------------------------ preview --
    def preview_selected(self):
        if not self.messages:
            messagebox.showinfo("Nothing to Preview", "Prepare the emails first.")
            return
        selection = self.tree.selection()
        message = None
        if selection:
            message = next((m for m in self.messages if m["vendor_code"] == selection[0]), None)
        message = message or self.messages[0]

        cc = self.cc_address
        html = (
            f'<div style="font-family:Calibri,Arial,sans-serif; font-size:11pt;">'
            f'<p style="background:#eee; padding:8px; border:1px solid #ccc;">'
            f'<b>To:</b> {message["to"]}<br>'
            f'<b>Cc:</b> {cc or "(none)"}<br>'
            f'<b>Subject:</b> {message["subject"]}'
            f"</p></div>" + message["body_html"]
        )
        path = os.path.join(tempfile.gettempdir(), f"vm_preview_{message['vendor_code']}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        webbrowser.open(f"file://{path}")

    # ----------------------------------------------------------------- CC --
    @property
    def cc_address(self):
        """This flow's CC address - never the other flow's."""
        return self.settings.cc_for(self.CC_KEY)

    def _refresh_cc_pill(self):
        self.cc_pill.configure(text=f"  {self.cc_address or '(not set)'}  ")

    def change_cc(self):
        CCAddressDialog(
            self, self.settings, on_saved=self._on_cc_saved,
            cc_key=self.CC_KEY, flow_label=CC_FLOW_LABELS[self.CC_KEY],
        )

    def _on_cc_saved(self, value):
        self._refresh_cc_pill()
        notify(self, f"{CC_FLOW_LABELS[self.CC_KEY]} set to: {value or '(none)'}")

    # ------------------------------------------------------------- drafts --
    def _ensure_cc(self):
        """Ask for THIS flow's CC address exactly once, then reuse it."""
        if self.settings.cc_prompted_for(self.CC_KEY):
            return True

        dialog = CCAddressDialog(
            self, self.settings, first_run=True,
            cc_key=self.CC_KEY, flow_label=CC_FLOW_LABELS[self.CC_KEY],
        )
        value = dialog.wait_for_result()
        if value is None:
            # Cancelled: leave it unprompted so we ask again next time rather
            # than silently drafting with no CC.
            return False
        self._refresh_cc_pill()
        return True

    def create_drafts(self):
        if not self.messages:
            messagebox.showinfo("Nothing to Send", "Prepare the emails first.")
            return

        if not outlook.OUTLOOK_AVAILABLE:
            messagebox.showerror(
                "Outlook Not Available",
                "Outlook drafts can only be created on Windows with Microsoft "
                "Outlook installed and the 'pywin32' package present.\n\n"
                "Install it with:\n    pip install pywin32\n\n"
                "You can still use 'Preview Selected' to check each email.",
            )
            return

        if not self._ensure_cc():
            return

        confirmed = messagebox.askyesno(
            "Create Outlook Drafts",
            f"Create {len(self.messages)} draft email(s) in the Outlook folder "
            f"'{self.FOLDER}'?\n\nOne email per vendor. Nothing is sent - every "
            "message is saved as a draft for you to review.",
        )
        if not confirmed:
            return

        try:
            result = outlook.create_drafts(
                self.messages, self.FOLDER, cc_addresses=self.cc_address
            )
        except outlook.OutlookError as exc:
            messagebox.showerror("Outlook Error", str(exc))
            return

        if result["errors"]:
            lines = "\n".join(f"{label}: {err}" for label, err in result["errors"][:10])
            messagebox.showwarning(
                "Drafts Created with Errors",
                f"Created: {result['created']} of {len(self.messages)}\n\n"
                f"Failed ({len(result['errors'])}):\n{lines}",
            )
        else:
            notify(
                self,
                f"{result['created']} draft(s) created in Outlook folder '{self.FOLDER}'.",
            )


class DefectiveInvoiceFlow(_EmailFlow):
    INPUT_TITLE = "DEFECTIVE INVOICE ROWS"
    INPUT_HINT = (
        "Paste from Excel, one invoice per line, columns in this order:\n"
        "Vendor Code, Vendor Name, PO Number, Scroll No, Invoice No, "
        "Invoice Date, Invoice Amount, Remarks\n\n"
        "A header row is detected and skipped automatically."
    )
    FOLDER = OUTLOOK_DEFECTIVE_FOLDER
    CC_KEY = CC_DEFECTIVE_KEY

    def _build_messages(self, text, skip_codes):
        rows = parse_pasted_rows(text, DEFECTIVE_INVOICE_KEYS)
        if not rows:
            messagebox.showwarning("No Rows Found", "No invoice rows were recognized.")
            return None
        result = build_defective_invoice_messages(self.store, rows, skip_codes=skip_codes)
        result["note"] = f"{len(rows)} invoice row(s)"
        return result


class EquipmentBreakdownFlow(_EmailFlow):
    INPUT_TITLE = "BREAKDOWN EQUIPMENT"
    INPUT_HINT = (
        "Paste straight from Excel into the grid: the identifier in the first "
        "column (RH/RO Number, Technical ID or Reg No) and that machine's "
        "remark in the second.\n\n"
        "Everything else - equipment, capacity, UOM, Reg No, vendor - is "
        "fetched from the Equipment Master, since these identifiers are unique."
    )
    FOLDER = OUTLOOK_BREAKDOWN_FOLDER
    CC_KEY = CC_BREAKDOWN_KEY
    INPUT_WIDTH = 470

    def __init__(self, master, store, settings, equipment_store, on_data_changed=None):
        self.equipment_store = equipment_store
        super().__init__(master, store, settings, on_data_changed=on_data_changed)

    def build_input(self, parent):
        """A two-column grid, so remarks can be pasted alongside the IDs."""
        self.grid = PasteGrid(
            parent,
            columns=[("identifier", "RH / Technical ID / Reg No"), ("remarks", "Remarks")],
            widths=[20, 24],
            rows=80,
        )
        self.grid.pack(fill="both", expand=True, padx=16, pady=4)

    def read_input(self):
        return self.grid.get_rows()

    def has_input(self):
        return bool(self.grid.get_rows())

    def clear_input(self):
        self.grid.clear()
        self.messages = []
        self._skip_codes = set()
        self._render_preview()

    def _build_messages(self, rows, skip_codes):
        pairs = [(r.get("identifier", ""), r.get("remarks", "")) for r in rows
                 if str(r.get("identifier", "")).strip()]
        if not pairs:
            messagebox.showwarning(
                "No Identifiers Found",
                "Enter at least one RH/RO Number, Technical ID or Reg No in the first column.",
            )
            return None

        resolved = resolve_breakdown_rows(self.equipment_store, pairs)
        if not resolved["records"]:
            messagebox.showwarning(
                "Not Found",
                "None of those identifiers are in the Equipment Master.\n\n"
                "Add the equipment first from the Equipment Master tab.",
            )
            return None

        result = build_breakdown_messages(self.store, resolved["records"], skip_codes=skip_codes)
        note = f"{len(resolved['records'])} machine(s)"
        if resolved["missing"]:
            shown = ", ".join(resolved["missing"][:5])
            note += f"  •  not in Equipment Master: {shown}"
            if len(resolved["missing"]) > 5:
                note += " ..."
        result["note"] = note
        return result


class CommunicationTab(ctk.CTkFrame):
    """Host tab: header (with the shared CC setting) plus the two flows."""

    def __init__(self, master, store, equipment_store, settings, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = store
        self.equipment_store = equipment_store
        self.settings = settings
        self.on_data_changed = on_data_changed
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 12))

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Communication", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Draft vendor emails from pasted data - one email per vendor, saved as "
                 "Outlook drafts for review before sending. Each flow keeps its own CC row.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))


        self.subtabs = ctk.CTkTabview(
            self,
            fg_color=theme.BG_SURFACE,
            segmented_button_fg_color=theme.BG_CARD_ALT,
            segmented_button_selected_color=theme.ACCENT,
            segmented_button_selected_hover_color=theme.ACCENT_HOVER,
            segmented_button_unselected_color=theme.BG_CARD_ALT,
            segmented_button_unselected_hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=10,
        )
        try:
            self.subtabs._segmented_button.configure(font=theme.font(12, "bold"), height=34)
        except Exception:
            pass
        self.subtabs.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tab_invoice = self.subtabs.add("Defective Invoice Communication")
        tab_breakdown = self.subtabs.add("Equipment Breakdown Communication")

        self.invoice_flow = DefectiveInvoiceFlow(
            tab_invoice, self.store, self.settings, on_data_changed=self.on_data_changed
        )
        self.invoice_flow.pack(fill="both", expand=True)

        self.breakdown_flow = EquipmentBreakdownFlow(
            tab_breakdown, self.store, self.settings, self.equipment_store,
            on_data_changed=self.on_data_changed,
        )
        self.breakdown_flow.pack(fill="both", expand=True)

    def refresh(self):
        """Keep both flows' CC pills in step after a change made elsewhere."""
        for flow in (getattr(self, "invoice_flow", None), getattr(self, "breakdown_flow", None)):
            if flow is not None:
                flow._refresh_cc_pill()
