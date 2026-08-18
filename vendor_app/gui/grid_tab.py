"""Tab 1: Excel-like bulk import/update grid.

Implemented with plain tk.Entry widgets (styled to match the dark theme)
rather than CTkEntry, since a 100-row x 9-column grid of ~900 entry
widgets needs to stay light to avoid UI lag - CTk's extra draw overhead
per widget is not worth it here.
"""

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from vendor_app.config import KEYS, LABELS, MAX_GRID_ROWS

ENTRY_BG = "#2b2b2b"
ENTRY_FG = "#e8e8e8"
ENTRY_BORDER = "#3f3f3f"
ENTRY_FOCUS_BORDER = "#1f6aa5"
HEADER_BG = "#144870"
HEADER_FG = "#ffffff"
SRNO_BG = "#242424"
SRNO_FG = "#9a9a9a"


class GridTab(ctk.CTkFrame):
    def __init__(self, master, store, on_data_changed=None):
        super().__init__(master, fg_color="transparent")
        self.store = store
        self.on_data_changed = on_data_changed
        self.entries = []  # entries[row][col] -> tk.Entry, col indexes into KEYS

        self._build_toolbar()
        self._build_grid()

    # ------------------------------------------------------------- build --
    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=(10, 4))

        ctk.CTkLabel(
            bar,
            text=f"Bulk Import & Update Grid (max {MAX_GRID_ROWS} rows)",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            bar,
            text="Paste from Excel with Ctrl+V  •  Navigate with Arrow keys / Tab / Enter",
            text_color="#9a9a9a",
        ).pack(side="left", padx=16)

        ctk.CTkButton(bar, text="Save Grid to Master", command=self.save_grid).pack(
            side="right", padx=4
        )
        ctk.CTkButton(
            bar,
            text="Clear Grid",
            fg_color="#8a2d2d",
            hover_color="#6e2323",
            command=self.clear_grid,
        ).pack(side="right", padx=4)

    def _build_grid(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.scroll = ctk.CTkScrollableFrame(container, fg_color="#161616")
        self.scroll.pack(fill="both", expand=True)

        headers = ["Sr. No."] + [LABELS[k] for k in KEYS]
        for col, text in enumerate(headers):
            ctk.CTkLabel(
                self.scroll,
                text=text,
                fg_color=HEADER_BG,
                text_color=HEADER_FG,
                font=ctk.CTkFont(size=11, weight="bold"),
                wraplength=110,
                justify="center",
                width=60 if col == 0 else 130,
                height=46,
                corner_radius=0,
            ).grid(row=0, column=col, sticky="nsew", padx=1, pady=1)

        for r in range(1, MAX_GRID_ROWS + 1):
            row_entries = []
            ctk.CTkLabel(
                self.scroll,
                text=str(r),
                fg_color=SRNO_BG,
                text_color=SRNO_FG,
                width=60,
                height=26,
            ).grid(row=r, column=0, sticky="nsew", padx=1, pady=1)

            for c in range(len(KEYS)):
                entry = tk.Entry(
                    self.scroll,
                    bg=ENTRY_BG,
                    fg=ENTRY_FG,
                    insertbackground=ENTRY_FG,
                    disabledbackground=ENTRY_BG,
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground=ENTRY_BORDER,
                    highlightcolor=ENTRY_FOCUS_BORDER,
                    width=17,
                )
                entry.grid(row=r, column=c + 1, sticky="nsew", padx=1, pady=1, ipady=4)
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
