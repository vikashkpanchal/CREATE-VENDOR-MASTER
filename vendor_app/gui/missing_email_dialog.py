"""Collect missing vendor email addresses before drafting emails.

Shown when pasted rows reference vendors that have no email on file. For
each one the user can either type an address (written straight back to the
vendor master) or tick Skip to leave that vendor out of this run.
"""

import customtkinter as ctk

from vendor_app.validators import ValidationError, normalize
from vendor_app.gui import theme
from vendor_app.gui.widgets import card, primary_button, secondary_button, section_label


class MissingEmailDialog(ctk.CTkToplevel):
    def __init__(self, master, store, unresolved: list, on_done):
        super().__init__(master)
        self.store = store
        self.unresolved = unresolved
        self.on_done = on_done
        self.rows = {}

        self.configure(fg_color=theme.BG_SURFACE)
        self.title("Missing Vendor Email Addresses")
        screen_h, screen_w = self.winfo_screenheight(), self.winfo_screenwidth()
        height = min(640, max(400, screen_h - 140))
        width = min(820, max(520, screen_w - 120))
        self.geometry(f"{width}x{height}+{max(0,(screen_w-width)//2)}+{max(0,(screen_h-height)//3)}")
        self.minsize(520, 380)
        self.transient(master)
        self.grab_set()
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            header, text="Missing Vendor Email Addresses",
            font=theme.h1_font(), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=f"{len(self.unresolved)} vendor(s) in this batch have no email address on file. "
                 "Enter an address to save it to the vendor master, or tick Skip to leave that "
                 "vendor out of this run. Separate multiple addresses with a semicolon (;).",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            wraplength=740, justify="left",
        ).pack(anchor="w", pady=(4, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        primary_button(buttons, "Continue", self._submit, width=140).pack(side="right", padx=(8, 0))
        secondary_button(buttons, "Cancel", self._cancel, width=120).pack(side="right")
        self.error_label = ctk.CTkLabel(
            buttons, text="", font=theme.small_font(), text_color=theme.DANGER,
            wraplength=460, justify="left",
        )
        self.error_label.pack(side="left")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        for item in self.unresolved:
            box = card(body, fg_color=theme.BG_CARD)
            box.pack(fill="x", pady=(0, 10))

            name = item.get("vendor_name") or "(name not on file)"
            section_label(box, f"{name}  •  {item['vendor_code']}").pack(
                anchor="w", padx=16, pady=(12, 2)
            )
            note = (
                f"{len(item['rows'])} row(s) in this batch"
                if item.get("in_master")
                else f"{len(item['rows'])} row(s) - this vendor code is NOT in the vendor master"
            )
            ctk.CTkLabel(
                box, text=note, font=theme.small_font(), text_color=theme.TEXT_MUTED
            ).pack(anchor="w", padx=16, pady=(0, 8))

            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(0, 14))
            email_var = ctk.StringVar()
            entry = ctk.CTkEntry(
                row, textvariable=email_var, height=32, placeholder_text="vendor@example.com",
                fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
            )
            entry.pack(side="left", fill="x", expand=True)

            skip_var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(
                row, text="Skip", variable=skip_var, width=70,
                fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                text_color=theme.TEXT_SECONDARY, font=theme.small_font(),
            ).pack(side="left", padx=(12, 0))

            self.rows[item["vendor_code"]] = {
                "email": email_var, "skip": skip_var, "item": item,
            }

    def _submit(self):
        skipped, saved, problems = [], 0, []

        for code, entry in self.rows.items():
            if entry["skip"].get():
                skipped.append(code)
                continue
            address = normalize(entry["email"].get())
            if not address:
                problems.append(f"{code}: enter an email address or tick Skip")
                continue
            try:
                # Writes through the normal upsert path, so the address is
                # validated and the change lands in the audit trail.
                self.store.upsert({"vendor_code": code, "vendor_email": address})
                saved += 1
            except ValidationError as exc:
                problems.append(f"{code}: {exc}")

        if problems:
            self.error_label.configure(text="  •  ".join(problems[:3]))
            return

        self.destroy()
        self.on_done({"skipped": skipped, "saved": saved})

    def _cancel(self):
        self.destroy()
        self.on_done(None)
