"""A small spreadsheet-style paste grid.

Used where the user wants to paste two columns straight out of Excel (for
example an equipment identifier and its breakdown remark) rather than
type into a free-text box. Supports multi-cell Ctrl+V, arrow/Tab/Enter
navigation, and reads back as a list of row dicts.

A grid can be large - the ARC value calculation takes 1,000 rows, which is
4,000 Tk widgets. Built in one go that freezes the window for several
seconds before it is even drawn. So the first rows are built at once and
the rest in small batches while the event loop is idle; anything that
needs a row further down - a paste, an import, the arrow keys - builds up
to it on the spot. To the person using it, all the rows are simply there.
"""

import tkinter as tk

import customtkinter as ctk

from vendor_app.gui import theme
from vendor_app.gui.scroll_canvas import ScrollCanvas


class PasteGrid(ctk.CTkFrame):
    # Rows built before the grid is first shown, then per turn of the event
    # loop. A row costs ~5ms to build and lay out, so a batch of 16 keeps
    # each pause under a tenth of a second - typing and scrolling stay
    # smooth while the rest of a large grid fills in behind them.
    FIRST_BATCH = 60
    BATCH = 16

    def __init__(self, master, columns, widths=None, rows=60):
        """`columns` is a list of (key, heading) pairs; `rows` is how many
        rows the grid holds."""
        super().__init__(master, fg_color=theme.BG_CARD)
        self.columns = list(columns)
        self.widths = widths or [18] * len(self.columns)
        self.row_count = rows
        self.cells = []
        self._pending = None

        # The headings live in a frozen strip above the rows: they follow the
        # grid sideways but never scroll up out of sight, so row 900 still
        # sits under a visible "Technical ID".
        self._scroll = scroll = ScrollCanvas(self, frozen_header=True)
        scroll.pack(fill="both", expand=True, padx=1, pady=1)
        self._body = body = scroll.body
        self._headings = []
        for text in ["#"] + [heading for _key, heading in self.columns]:
            self._headings.append(tk.Label(
                scroll.head, text=text, bg=theme.BG_CARD_ALT, fg=theme.TEXT_SECONDARY,
                font=(theme.FONT_FAMILY, 10, "bold"), justify="center",
            ))
        body.bind("<Configure>", lambda e: self._align_headings(), add="+")

        # One bindtag for this grid's cells, instead of a handler per cell.
        # The tag MUST be unique per instance: bind_class() registers against
        # a class NAME application-wide, so a shared name would let the last
        # grid constructed hijack the handlers of every other grid on screen
        # (paste would land in the wrong table entirely).
        self._cell_tag = f"PasteCell{id(self)}"
        self.bind_class(self._cell_tag, "<Key>", self._on_key)
        self.bind_class(self._cell_tag, "<Control-v>", self._on_paste)
        self.bind_class(self._cell_tag, "<Control-V>", self._on_paste)

        self.ensure_rows(self.FIRST_BATCH)
        self._schedule_more()

    def _align_headings(self):
        """Lay each heading exactly over its column, wrapping it onto a second
        line rather than cutting it off when the column is narrower."""
        if not self.cells:
            return
        head = self._scroll.head
        spans = []
        for column in range(len(self._headings)):
            x, _y, width, _h = self._body.grid_bbox(column, 1)
            spans.append((x, width))
        if not any(width for _x, width in spans):
            return                                  # not laid out yet
        tallest = 0
        for label, (_x, width) in zip(self._headings, spans):
            label.configure(wraplength=max(20, width - 8))
            tallest = max(tallest, label.winfo_reqheight())
        height = tallest + 8
        for label, (x, width) in zip(self._headings, spans):
            label.place(x=x, y=0, width=max(1, width - 1), height=height - 1)
        total = sum(spans[-1]) if spans else 0
        head.configure(width=max(total, self._body.winfo_reqwidth()), height=height)
        self._scroll.head_canvas.configure(height=height)
        self._scroll._sync_head_region()

    # ------------------------------------------------------------ rows --
    def ensure_rows(self, count):
        """Build rows until at least `count` exist (never past the grid's
        size). Cheap when they already do."""
        target = min(count, self.row_count)
        body = self._body
        for r in range(len(self.cells) + 1, target + 1):
            bg = theme.BG_CARD if r % 2 else theme.BG_ROW_ALT
            tk.Label(
                body, text=str(r), bg=bg, fg=theme.TEXT_MUTED,
                font=(theme.FONT_FAMILY, 9), width=5,
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

    def _schedule_more(self):
        if len(self.cells) < self.row_count:
            self._pending = self.after(10, self._build_more)
        else:
            self._pending = None

    def _build_more(self):
        self._pending = None
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.ensure_rows(len(self.cells) + self.BATCH)
        self._schedule_more()

    def destroy(self):
        if self._pending is not None:
            try:
                self.after_cancel(self._pending)
            except tk.TclError:
                pass
            self._pending = None
        super().destroy()

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
        if 0 <= row < self.row_count:
            self.ensure_rows(row + 1)
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
        self.ensure_rows(row + len(lines))
        placed = 0
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
            placed += 1
        if placed < len(lines):
            self._say_overflow(len(lines), placed)
        return "break"

    def _say_overflow(self, given, placed):
        """Rows that did not fit are never dropped in silence."""
        from vendor_app.gui.toast import notify
        notify(self, f"{given:,} rows pasted but the grid holds {self.row_count:,}: "
                     f"the last {given - placed:,} did not fit. Paste them in a "
                     f"second run, or import the file instead.",
               kind="error", duration_ms=6000)

    # -------------------------------------------------------------- data --
    def get_rows(self):
        """Non-blank rows as dicts keyed by the column keys."""
        rows = []
        for row_cells in self.cells:
            values = [cell.get().strip() for cell in row_cells]
            if any(values):
                rows.append({key: values[i] for i, (key, _h) in enumerate(self.columns)})
        return rows

    def set_rows(self, records):
        """Fill the grid from row dicts keyed by the column keys, replacing
        what is there. Returns how many rows were placed - fewer than given
        when there are more records than the grid holds."""
        self.clear()
        records = list(records)[: self.row_count]
        self.ensure_rows(len(records))
        for index, record in enumerate(records):
            for column, (key, _h) in enumerate(self.columns):
                cell = self.cells[index][column]
                cell.insert(0, str(record.get(key, "") or ""))
        return len(records)

    def clear(self):
        for row_cells in self.cells:
            for cell in row_cells:
                cell.delete(0, "end")
