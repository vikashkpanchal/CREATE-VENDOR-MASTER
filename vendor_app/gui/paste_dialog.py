"""Excel-like 'paste rows' dialog.

Opens a real grid with one column per field of the target master, so the
user can paste a block copied straight out of Excel and see it land in the
right columns before committing. Ctrl+V pastes a whole multi-row,
multi-column block from wherever the cursor sits; individual cells can
also be typed into and corrected first.
"""

import customtkinter as ctk

from vendor_app.gui import theme
from vendor_app.gui.paste_grid import PasteGrid
from vendor_app.gui.widgets import card, primary_button, secondary_button, section_label

DEFAULT_ROWS = 200


class PasteRowsDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, keys: list, labels: dict, on_submit,
                 note: str = "", rows: int = DEFAULT_ROWS):
        super().__init__(master)
        self.keys = list(keys)
        self.labels = labels
        self.on_submit = on_submit

        self.configure(fg_color=theme.BG_SURFACE)
        self.title(title)
        screen_h, screen_w = self.winfo_screenheight(), self.winfo_screenwidth()
        height = min(720, max(420, screen_h - 100))
        width = min(1500, max(700, screen_w - 80))
        self.geometry(
            f"{width}x{height}+{max(0,(screen_w-width)//2)}+{max(0,(screen_h-height)//4)}"
        )
        self.minsize(700, 420)
        self.transient(master)

        self._build(title, note, rows)
        self.after(80, self._activate)

    def _activate(self):
        try:
            self.grab_set()
            self.lift()
        except Exception:
            pass
        # Land the caret in the first cell so Ctrl+V works immediately.
        if self.grid.cells:
            self.grid.cells[0][0].focus_force()

    def _column_width(self, key):
        """Roughly fit the header, within sane bounds."""
        return max(12, min(30, len(self.labels.get(key, key)) + 2))

    def _build(self, title, note, rows):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 6))
        ctk.CTkLabel(
            header, text=title, font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=note or "Paste rows copied from Excel straight into the grid.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            wraplength=1300, justify="left",
        ).pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(
            header,
            text="Click the cell where the block should start, then press Ctrl+V - a "
                 "multi-column, multi-row paste fills across and down from there. "
                 "Arrow keys / Tab / Enter move between cells; scroll sideways for "
                 "more columns.",
            font=theme.font(10), text_color=theme.TEXT_MUTED,
            wraplength=1300, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        # Action bar reserved first so it can never be pushed off-screen.
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", side="bottom", padx=20, pady=(0, 16))
        primary_button(buttons, "Add Rows", self._submit, width=150).pack(side="right", padx=(8, 0))
        secondary_button(buttons, "Cancel", self.destroy, width=120).pack(side="right")
        secondary_button(buttons, "Clear Grid", self._clear, width=130).pack(side="left")
        self.status = ctk.CTkLabel(
            buttons, text="", font=theme.small_font(), text_color=theme.TEXT_MUTED
        )
        self.status.pack(side="left", padx=14)

        wrap = card(self, fg_color=theme.BG_CARD)
        wrap.pack(fill="both", expand=True, padx=20, pady=(10, 10))
        section_label(wrap, "PASTE HERE").pack(anchor="w", padx=14, pady=(12, 6))

        self.grid = PasteGrid(
            wrap,
            columns=[(key, self.labels.get(key, key)) for key in self.keys],
            widths=[self._column_width(key) for key in self.keys],
            rows=rows,
        )
        self.grid.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def _clear(self):
        self.grid.clear()
        self.status.configure(text="")

    def _submit(self):
        rows = self.grid.get_rows()
        if not rows:
            self.status.configure(text="Nothing pasted yet.")
            return
        self.destroy()
        self.on_submit(rows)
