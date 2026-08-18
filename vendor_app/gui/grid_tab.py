"""Import & Update Grid: Excel-like bulk entry, capped at 100 rows.

Built with plain tk.Entry widgets (styled to match the dark theme) rather
than CTkEntry - a 100-row x 9-column grid is ~900 entry widgets, and
CTkEntry's extra per-widget draw overhead is not worth it at that count.
"""

import tkinter as tk
from tkinter import messagebox, filedialog

import customtkinter as ctk

from vendor_app.config import KEYS, LABELS, MAX_GRID_ROWS
from vendor_app.importer import load_records_from_file
from vendor_app.gui import theme
from vendor_app.gui.scroll_canvas import ScrollCanvas
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, danger_button, primary_button, secondary_button

def _wrap_header(text, max_chars):
    """Greedy word-wrap `text` so every line is <= max_chars.

    Used instead of Tk's own wraplength auto-wrap for the grid header: a
    tk.Label mixing an explicit "\\n" with a width constraint that still
    forces a *further* auto-wrap of one segment can miscompute its own
    required height, clipping the last line. Pre-wrapping every line to
    fit removes the ambiguity entirely - no segment ever needs a second,
    Tk-computed wrap.
    """
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


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
        secondary_button(actions, "Import from File...", self.import_from_file, width=170).pack(
            side="left", padx=(0, 8)
        )
        primary_button(actions, "Save Grid to Master", self.save_grid, width=190).pack(side="left")

    def _build_grid(self):
        wrapper = card(self, fg_color=theme.BG_CARD)
        wrapper.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        wrapper.grid_rowconfigure(0, weight=1)
        wrapper.grid_columnconfigure(0, weight=1)

        scroll = ScrollCanvas(wrapper)
        scroll.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.scroll = scroll.body

        # Plain tk widgets throughout (not CTkLabel/CTkEntry): at ~1,000
        # cells, customtkinter's per-widget canvas-drawing overhead adds up
        # to a real, noticeable construction delay. Key/paste handlers are
        # bound ONCE via bind_class + a shared bindtag, not once per cell
        # (900 cells x 3 binds = 2,700 individual Tcl bind calls otherwise)
        # - event.widget carries its (row, col) directly as an attribute.
        headers = ["Sr. No."] + [LABELS[k] for k in KEYS]
        for col, text in enumerate(headers):
            width_chars = 6 if col == 0 else CELL_WIDTH[KEYS[col - 1]]
            tk.Label(
                self.scroll,
                text=_wrap_header(text, max(6, width_chars - 3)),
                bg=theme.BG_CARD_ALT,
                fg=theme.TEXT_SECONDARY,
                font=(theme.FONT_FAMILY, 11, "bold"),
                justify="center",
                width=width_chars,
            ).grid(row=0, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))

        self.bind_class("GridEntry", "<Key>", self._on_key_event)
        self.bind_class("GridEntry", "<Control-v>", self._on_paste_event)
        self.bind_class("GridEntry", "<Control-V>", self._on_paste_event)

        for r in range(1, MAX_GRID_ROWS + 1):
            row_entries = []
            row_bg = theme.BG_CARD if r % 2 else theme.BG_ROW_ALT
            tk.Label(
                self.scroll,
                text=str(r),
                bg=row_bg,
                fg=theme.TEXT_MUTED,
                font=(theme.FONT_FAMILY, 11),
                width=6,
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
                entry.bindtags(("GridEntry",) + entry.bindtags())
                entry._grid_pos = (r - 1, c)
                row_entries.append(entry)
            self.entries.append(row_entries)

    def _on_key_event(self, event):
        row, col = event.widget._grid_pos
        return self._on_key(event, row, col)

    def _on_paste_event(self, event):
        row, col = event.widget._grid_pos
        return self._on_paste(event, row, col)

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

        if result["errors"]:
            message = f"Added: {result['added']}  •  Updated: {result['updated']}"
            error_lines = "\n".join(f"Row {i}: {err}" for i, err in result["errors"][:15])
            more = len(result["errors"]) - 15
            if more > 0:
                error_lines += f"\n...and {more} more"
            message += f"\n\nRows with errors ({len(result['errors'])}) were skipped:\n{error_lines}"
            messagebox.showwarning("Grid Saved with Errors", message)
        else:
            notify(self, f"Grid saved - Added: {result['added']}  •  Updated: {result['updated']}")

        if self.on_data_changed:
            self.on_data_changed()

    def import_from_file(self):
        path = filedialog.askopenfilename(
            title="Import Vendors from File",
            filetypes=[("Spreadsheet files", "*.xlsx *.xls *.csv *.tsv"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            records = load_records_from_file(path)
        except Exception as exc:
            messagebox.showerror("Import Failed", f"Could not read that file:\n{exc}")
            return

        if not records:
            messagebox.showwarning("No Rows Found", "That file has no recognizable vendor rows.")
            return

        truncated = len(records) > MAX_GRID_ROWS
        records = records[:MAX_GRID_ROWS]

        for row in self.entries:
            for entry in row:
                entry.delete(0, "end")

        for r, record in enumerate(records):
            for c, key in enumerate(KEYS):
                value = record.get(key, "")
                if value:
                    self.entries[r][c].insert(0, value)

        message = f"Loaded {len(records)} row(s) into the grid. Review, then click Save Grid to Master."
        if truncated:
            message += f"\n\nThe file had more than {MAX_GRID_ROWS} rows - only the first {MAX_GRID_ROWS} were loaded."
            messagebox.showwarning("Import Truncated", message)
        else:
            notify(self, message, kind="info")
