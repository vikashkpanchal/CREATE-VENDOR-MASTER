"""Import & Update Grid: Excel-like bulk entry, capped at 100 rows.

Built with plain tk.Entry widgets (styled to match the dark theme) rather
than CTkEntry - a 100-row x 9-column grid is ~900 entry widgets, and
CTkEntry's extra per-widget draw overhead is not worth it at that count.
"""

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from vendor_app.config import KEYS, LABELS, MAX_GRID_ROWS
from vendor_app.gui import theme
from vendor_app.gui.scroll_canvas import ScrollCanvas
from vendor_app.gui.widgets import card, danger_button, primary_button

CELL_WIDTH = {
    "vendor_code": 14,
    "vendor_name": 24,
    "vendor_email": 28,
    "vendor_owner_name": 18,
    "vendor_owner_contact": 18,
    "vendor_owner_email": 22,
    "vendor_supervisor_name": 20,
    "vendor_supervisor_contact": 20,
    "vendor_supervisor_email": 22,
}


class GridTab(ctk.CTkFrame):
    def __init__(self, master, store, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = store
        self.on_data_changed = on_data_changed
        self.entries = []  # entries[row][col] -> tk.Entry, col indexes into KEYS

        self._build_toolbar()
        self._build_grid()

    # ------------------------------------------------------------- build --
    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(20, 10))

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Import & Update Grid", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text=f"Bulk add or update up to {MAX_GRID_ROWS} vendors at once  •  "
            "Paste directly from Excel with Ctrl+V  •  Navigate with Arrow keys / Tab / Enter",
            font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.pack(side="right")
        danger_button(actions, "Clear Grid", self.clear_grid).pack(side="left", padx=(0, 8))
        primary_button(actions, "Save Grid to Master", self.save_grid, width=190).pack(side="left")

    def _build_grid(self):
        wrapper = card(self, fg_color=theme.BG_CARD)
        wrapper.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        wrapper.grid_rowconfigure(0, weight=1)
        wrapper.grid_columnconfigure(0, weight=1)

        scroll = ScrollCanvas(wrapper)
        scroll.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.scroll = scroll.body

        headers = ["Sr. No."] + [LABELS[k] for k in KEYS]
        for col, text in enumerate(headers):
            width_chars = 6 if col == 0 else CELL_WIDTH[KEYS[col - 1]]
            ctk.CTkLabel(
                self.scroll,
                text=text,
                fg_color=theme.BG_CARD_ALT,
                text_color=theme.TEXT_SECONDARY,
                font=theme.font(11, "bold"),
                wraplength=max(60, width_chars * 7),
                justify="center",
                width=width_chars * 8,
                height=48,
                corner_radius=0,
            ).grid(row=0, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))

        for r in range(1, MAX_GRID_ROWS + 1):
            row_entries = []
            row_bg = theme.BG_CARD if r % 2 else theme.BG_ROW_ALT
            ctk.CTkLabel(
                self.scroll,
                text=str(r),
                fg_color=row_bg,
                text_color=theme.TEXT_MUTED,
                font=theme.small_font(),
                width=48,
                height=30,
            ).grid(row=r, column=0, sticky="nsew", padx=(0, 1), pady=(0, 1))

            for c in range(len(KEYS)):
                entry = tk.Entry(
                    self.scroll,
                    bg=row_bg,
                    fg=theme.TEXT_PRIMARY,
                    insertbackground=theme.TEXT_PRIMARY,
                    disabledbackground=row_bg,
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground=theme.BORDER_SOFT,
                    highlightcolor=theme.ACCENT,
                    font=(theme.FONT_FAMILY, 10),
                    width=CELL_WIDTH[KEYS[c]],
                )
                entry.grid(row=r, column=c + 1, sticky="nsew", padx=(0, 1), pady=(0, 1), ipady=5)
                entry.bind("<Key>", lambda ev, rr=r - 1, cc=c: self._on_key(ev, rr, cc))
                entry.bind("<Control-v>", lambda ev, rr=r - 1, cc=c: self._on_paste(ev, rr, cc))
                entry.bind("<Control-V>", lambda ev, rr=r - 1, cc=c: self._on_paste(ev, rr, cc))
                row_entries.append(entry)
            self.entries.append(row_entries)

    # --------------------------------------------------------- navigation --
    def _on_key(self, event, row, col):
        key = event.keysym
        widget = event.widget
        if key == "Down":
            self._focus_cell(row + 1, col)
            return "break"
        if key == "Up":
            self._focus_cell(row - 1, col)
            return "break"
        if key == "Right" and widget.index("insert") == len(widget.get()):
            self._focus_cell(row, col + 1)
            return "break"
        if key == "Left" and widget.index("insert") == 0:
            self._focus_cell(row, col - 1)
            return "break"
        if key == "Return":
            self._focus_cell(row + 1, col)
            return "break"
        if key == "Tab":
            self._focus_cell(row, col + 1)
            return "break"
        if key == "ISO_Left_Tab":  # Shift+Tab
            self._focus_cell(row, col - 1)
            return "break"
        return None

    def _focus_cell(self, row, col):
        if 0 <= row < len(self.entries) and 0 <= col < len(KEYS):
            entry = self.entries[row][col]
            entry.focus_set()
            entry.icursor("end")

    # -------------------------------------------------------------- paste --
    def _on_paste(self, event, row, col):
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            return "break"

        lines = clip.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        while lines and lines[-1] == "":
            lines.pop()

        for i, line in enumerate(lines):
            target_row = row + i
            if target_row >= MAX_GRID_ROWS:
                break
            cells = line.split("\t")
            for j, value in enumerate(cells):
                target_col = col + j
                if target_col >= len(KEYS):
                    break
                cell_entry = self.entries[target_row][target_col]
                cell_entry.delete(0, "end")
                cell_entry.insert(0, value)
        return "break"

    # -------------------------------------------------------------- actions --
    def clear_grid(self):
        if not messagebox.askyesno("Clear Grid", "Clear all cells in the grid?"):
            return
        for row in self.entries:
            for entry in row:
                entry.delete(0, "end")

    def save_grid(self):
        raw_records = []
        for row in self.entries:
            record = {KEYS[c]: row[c].get() for c in range(len(KEYS))}
            raw_records.append(record)

        result = self.store.bulk_upsert(raw_records)
        message = f"Added: {result['added']}\nUpdated: {result['updated']}"

        if result["errors"]:
            error_lines = "\n".join(f"Row {i}: {err}" for i, err in result["errors"][:15])
            more = len(result["errors"]) - 15
            if more > 0:
                error_lines += f"\n...and {more} more"
            message += f"\n\nRows with errors ({len(result['errors'])}) were skipped:\n{error_lines}"
            messagebox.showwarning("Grid Saved with Errors", message)
        else:
            messagebox.showinfo("Grid Saved", message)

        if self.on_data_changed:
            self.on_data_changed()
