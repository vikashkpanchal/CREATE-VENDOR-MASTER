"""A plain Canvas + inner Frame with both vertical and horizontal
scrollbars. customtkinter's CTkScrollableFrame only scrolls on one axis
at a time, which is not enough for a wide 9-column x 100-row grid - so
the bulk entry grid uses this instead.
"""

import tkinter as tk
from tkinter import ttk

from vendor_app.gui import theme
from vendor_app.gui.style import SCROLL_V_STYLE, SCROLL_H_STYLE, apply_dark_treeview_style


class ScrollCanvas(tk.Frame):
    """`.body` is the frame to place content into; everything else is wiring."""

    def __init__(self, master, frozen_header=False):
        """With `frozen_header`, `.head` is a strip above the scrolling area:
        it scrolls sideways with the body but never up and down, so a
        heading stays in view however far down a long grid is scrolled."""
        super().__init__(master, bg=theme.BG_CARD, highlightthickness=1, highlightbackground=theme.BORDER_SOFT)
        apply_dark_treeview_style()

        body_row = 1 if frozen_header else 0
        self.grid_rowconfigure(body_row, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.head_canvas = None
        self.head = None
        if frozen_header:
            self.head_canvas = tk.Canvas(self, bg=theme.BG_CARD_ALT, highlightthickness=0,
                                         height=30)
            self.head_canvas.grid(row=0, column=0, sticky="ew")
            self.head = tk.Frame(self.head_canvas, bg=theme.BG_CARD)
            self._head_window = self.head_canvas.create_window(
                (0, 0), window=self.head, anchor="nw"
            )

        self.canvas = tk.Canvas(self, bg=theme.BG_CARD, highlightthickness=0)
        self.canvas.grid(row=body_row, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(self, orient="vertical", style=SCROLL_V_STYLE, command=self.canvas.yview)
        vsb.grid(row=body_row, column=1, sticky="ns")
        hsb = ttk.Scrollbar(self, orient="horizontal", style=SCROLL_H_STYLE, command=self._xview)
        hsb.grid(row=body_row + 1, column=0, sticky="ew")
        self._hsb = hsb
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=self._on_xscroll)

        self.body = tk.Frame(self.canvas, bg=theme.BG_CARD)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.bind("<Enter>", lambda e: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda e: self._unbind_wheel())

    # ------------------------------------------------ sideways scrolling --
    def _xview(self, *args):
        self.canvas.xview(*args)

    def _on_xscroll(self, first, last):
        """The body moved sideways: move the scrollbar, and the frozen
        heading with it so every heading stays over its own column."""
        self._hsb.set(first, last)
        if self.head_canvas is not None:
            self.head_canvas.xview_moveto(first)

    def _sync_head_region(self):
        if self.head_canvas is None:
            return
        region = self.canvas.cget("scrollregion").split()
        width = int(float(region[2])) if len(region) == 4 else self.body.winfo_reqwidth()
        height = max(1, self.head.winfo_reqheight())
        self.head_canvas.configure(scrollregion=(0, 0, width, height))
        self.head_canvas.xview_moveto(self.canvas.xview()[0])

    def _on_body_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._sync_head_region()

    def _on_canvas_configure(self, event):
        # Keep the body at least as wide/tall as the visible canvas so short
        # grids don't look pinned to the top-left corner of a huge scroll area.
        bbox = self.canvas.bbox("all") or (0, 0, 0, 0)
        content_w = max(bbox[2], event.width)
        content_h = max(bbox[3], event.height)
        self.canvas.itemconfigure(self._window, width=content_w if bbox[2] < event.width else None)
        self.canvas.configure(scrollregion=(0, 0, content_w, content_h))
        self._sync_head_region()

    def _bind_wheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Shift-MouseWheel>", self._on_mousewheel_shift)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_wheel(self):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Shift-MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _on_mousewheel_shift(self, event):
        self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")

    def _on_mousewheel_linux(self, event):
        self.canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
