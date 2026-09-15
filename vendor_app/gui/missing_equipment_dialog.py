"""The pop-up that says which machines are not in the Equipment Master.

A breakdown run is driven by identifiers typed or pasted from site, and some
of them will not be on file - a machine that was never entered, a Reg No
with a digit wrong. Those rows cannot produce an email, and a line of small
text under the toolbar was too easy to miss: the run looked like it had
worked, minus a few vendors nobody noticed.

So it is said out loud, in a window that has to be closed. The identifiers
are listed in full and can be copied straight out, because the next step is
either adding those machines to the master or correcting what was pasted.
"""

import customtkinter as ctk

from vendor_app.gui import theme
from vendor_app.gui.toast import notify
from vendor_app.gui.util import fit_on_screen
from vendor_app.gui.widgets import card, primary_button, secondary_button, section_label


class MissingEquipmentDialog(ctk.CTkToplevel):
    """Lists identifiers that are not in the Equipment Master.

    `found` is how many machines DID resolve, so the window can say whether
    the run continues without them or has nothing left to send at all.
    """

    def __init__(self, master, missing: list, found: int = 0):
        super().__init__(master)
        self.missing = [str(m) for m in missing]
        self.found = found

        self.configure(fg_color=theme.BG_SURFACE)
        self.title("Equipment Not in the Master")
        fit_on_screen(self, 640, 560, min_w=460, min_h=340,
                      margin_w=120, margin_h=140)
        self.transient(master)
        self.grab_set()
        self._build()
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(60, lambda: self.close_button.focus_set())

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            header, text="Equipment Not in the Master", font=theme.h1_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        count = len(self.missing)
        if self.found:
            note = (f"{count} identifier(s) are not in the Equipment Master, so those "
                    f"machines are left out of this run. The other {self.found} "
                    "machine(s) are prepared as usual.")
        else:
            note = (f"None of the {count} identifier(s) are in the Equipment Master, "
                    "so there is nothing to prepare. Add the machines from the "
                    "Equipment Master tab, or check the identifiers below.")
        ctk.CTkLabel(
            header, text=note, font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY, anchor="w", justify="left",
            wraplength=580,
        ).pack(anchor="w", pady=(4, 0))

        # Reserved before the list, so a long list can never push them out.
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        self.close_button = primary_button(buttons, "Close", self.destroy, width=120)
        self.close_button.pack(side="right")
        secondary_button(buttons, "Copy List", self.copy_list, width=130).pack(
            side="right", padx=(0, 8)
        )

        box = card(self, fg_color=theme.BG_CARD)
        box.pack(fill="both", expand=True, padx=20, pady=10)
        section_label(box, f"NOT FOUND ({count})").pack(anchor="w", padx=18, pady=(14, 6))

        listing = ctk.CTkScrollableFrame(box, fg_color="transparent")
        listing.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        for identifier in self.missing:
            ctk.CTkLabel(
                listing, text=identifier or "(blank)", font=theme.body_font(),
                text_color=theme.TEXT_PRIMARY, anchor="w",
            ).pack(anchor="w", padx=6, pady=2)

    def copy_list(self):
        """Put the identifiers on the clipboard, one per line, ready to paste
        back into the grid once the machines are on the master."""
        self.clipboard_clear()
        self.clipboard_append("\n".join(self.missing))
        notify(self.master, f"{len(self.missing)} identifier(s) copied.")
