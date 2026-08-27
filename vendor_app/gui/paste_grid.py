"""A small spreadsheet-style paste grid.

Used where the user wants to paste two columns straight out of Excel (for
example an equipment identifier and its breakdown remark) rather than
type into a free-text box. Supports multi-cell Ctrl+V, arrow/Tab/Enter
navigation, and reads back as a list of row dicts.
"""

import tkinter as tk

import customtkinter as ctk

from vendor_app.gui import theme
from vendor_app.gui.scroll_canvas import ScrollCanvas


class PasteGrid(ctk.CTkFrame):
    def __init__(self, master, columns, widths=None, rows=60):
        """`columns` is a list of (key, heading) pairs."""
        super().__init__(master, fg_color=theme.BG_CARD)
        self.columns = list(columns)
        self.widths = widths or [18] * len(self.columns)
        self.row_count = rows
        self.cells = []

        scroll = ScrollCanvas(self)
        scroll.pack(fill="both", expand=True, padx=1, pady=1)
        body = scroll.body

        tk.Label(
            body, text="#", bg=theme.BG_CARD_ALT, fg=theme.TEXT_SECONDARY,
            font=(theme.FONT_FAMILY, 10, "bold"), width=4,
        ).grid(row=0, column=0, sticky="nsew", padx=(0, 1), pady=(0, 1))
        for index, (_key, heading) in enumerate(self.columns):
            tk.Label(
                body, text=heading, bg=theme.BG_CARD_ALT, fg=theme.TEXT_SECONDARY,
                font=(theme.FONT_FAMILY, 10, "bold"), width=self.widths[index],
            ).grid(row=0, column=index + 1, sticky="nsew", padx=(0, 1), pady=(0, 1))

        # One bindtag for this grid's cells, instead of a handler per cell.
        # The tag MUST be unique per instance: bind_class() registers against
        # a class NAME application-wide, so a shared name would let the last
        # grid constructed hijack the handlers of every other grid on screen
        # (paste would land in the wrong table entirely).
        self._cell_tag = f"PasteCell{id(self)}"
        self.bind_class(self._cell_tag, "<Key>", self._on_key)
        self.bind_class(self._cell_tag, "<Control-v>", self._on_paste)
        self.bind_class(self._cell_tag, "<Control-V>", self._on_paste)

        for r in range(1, rows + 1):
            bg = theme.BG_CARD if r % 2 else theme.BG_ROW_ALT
            tk.Label(
                body, text=str(r), bg=bg, fg=theme.TEXT_MUTED,
                font=(theme.FONT_FAMILY, 9), width=4,
            ).grid(row=r, column=0, sticky="nsew", padx=(0, 1), pady=(0, 1))
            row_cells = []
            for c, (_key, _heading) in enumerate(self.columns):
                entry = tk.Entry(
                    body, bg=bg, fg=theme.TEXT_PRIMARY, insertbackground=theme.TEXT_PRIMARY,
                    relief="flat", highlightthickness=1,
                    highlightbackground=theme.BORDER_SOFT, highlightcolor=theme.ACCENT,
                    font=(theme.FONT_FAMILY, 10), width=self.widths[c],
                )
                entry.grid(row=r, column=c + 1, sticky="nsew", padx=(0, 1), pady=(0, 1), ipady=4)
                entry.bindtags((self._cell_tag,) + entry.bindtags())
                entry._pos = (r - 1, c)
                row_cells.append(entry)
            self.cells.append(row_cells)

    # -------------------------------------------------------- navigation --
    def _on_key(self, event):
        row, col = event.widget._pos
        key = event.keysym
        if key == "Down" or key == "Return":
            self._focus(row + 1, col); return "break"
        if key == "Up":
            self._focus(row - 1, col); return "break"
        if key == "Tab":
            self._focus(row, col + 1); return "break"
        if key == "ISO_Left_Tab":
            self._focus(row, col - 1); return "break"
        if key == "Right" and event.widget.index("insert") == len(event.widget.get()):
            self._focus(row, col + 1); return "break"
        if key == "Left" and event.widget.index("insert") == 0:
            self._focus(row, col - 1); return "break"
        return None

    def _focus(self, row, col):
        if 0 <= row < len(self.cells) and 0 <= col < len(self.columns):
            entry = self.cells[row][col]
            entry.focus_set()
            entry.icursor("end")

    # ------------------------------------------------------------- paste --
    def _on_paste(self, event):
        row, col = event.widget._pos
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            return "break"
        lines = clip.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        while lines and lines[-1] == "":
            lines.pop()
        for i, line in enumerate(lines):
            target_row = row + i
            if target_row >= self.row_count:
                break
            for j, value in enumerate(line.split("\t")):
                target_col = col + j
                if target_col >= len(self.columns):
                    break
                cell = self.cells[target_row][target_col]
                cell.delete(0, "end")
                cell.insert(0, value.strip())
        return "break"

    # -------------------------------------------------------------- data --
    def get_rows(self):
        """Non-blank rows as dicts keyed by the column keys."""
        rows = []
        for row_cells in self.cells:
            values = [cell.get().strip() for cell in row_cells]
            if any(values):
                rows.append({key: values[i] for i, (key, _h) in enumerate(self.columns)})
        return rows

    def clear(self):
        for row_cells in self.cells:
            for cell in row_cells:
                cell.delete(0, "end")
