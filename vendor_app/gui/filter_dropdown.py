"""Excel-style column filter.

Behaves like a filter dropdown in a spreadsheet:

  * **multi-select** - tick any number of values, not just one
  * **scrollable** with a search box, so a thousand vendors is still usable
  * **cascading** - the options offered are only those still reachable given
    every OTHER filter in force, exactly as Excel narrows its lists
  * (Select All) / Clear, and a summary on the button face

The owner supplies the available values (already narrowed) via set_values();
the widget owns only the selection.
"""

import tkinter as tk

import customtkinter as ctk

from vendor_app.gui import theme

ALL_LABEL = "(All)"


class FilterDropdown(ctk.CTkFrame):
    def __init__(self, master, label, on_change=None, width=190, popup_height=320):
        super().__init__(master, fg_color="transparent")
        self.label_text = label
        self.on_change = on_change
        self.width = width
        self.popup_height = popup_height

        self._values = []          # currently offered (already cascaded)
        self._selected = set()     # empty set == no filter (everything)
        self._popup = None
        self._vars = {}

        ctk.CTkLabel(
            self, text=label, font=theme.font(10), text_color=theme.TEXT_MUTED, anchor="w"
        ).pack(anchor="w")
        self.button = ctk.CTkButton(
            self, text=ALL_LABEL, width=width, height=32, anchor="w",
            fg_color=theme.BG_INPUT, hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY, border_width=1, border_color=theme.BG_INPUT_BORDER,
            font=theme.small_font(), command=self.toggle_popup,
        )
        self.button.pack()

    # ------------------------------------------------------------- state --
    @property
    def selected(self):
        """The chosen values; an empty set means 'no filter applied'."""
        return set(self._selected)

    def matches(self, value):
        return not self._selected or str(value) in self._selected

    def set_values(self, values):
        """Offer `values` (already narrowed by the other filters).

        A selection that is no longer reachable is dropped, which is what
        keeps cascading filters from deadlocking into an empty result.
        """
        self._values = list(values)
        available = set(self._values)
        if self._selected - available:
            self._selected &= available
            self._refresh_button()
            return True          # selection changed as a side effect
        self._refresh_button()
        return False

    def clear(self):
        self._selected = set()
        self._refresh_button()

    def _refresh_button(self):
        count = len(self._selected)
        if count == 0:
            text = ALL_LABEL
        elif count == 1:
            only = next(iter(self._selected))
            text = only if len(only) <= 22 else only[:21] + "…"
        else:
            text = f"{count} selected"
        self.button.configure(
            text=f"  {text}",
            border_color=theme.ACCENT if count else theme.BG_INPUT_BORDER,
            text_color=theme.ACCENT if count else theme.TEXT_PRIMARY,
        )

    # ------------------------------------------------------------- popup --
    def toggle_popup(self):
        if self._popup is not None and self._popup.winfo_exists():
            self._close_popup()
        else:
            self._open_popup()

    def _open_popup(self):
        self._popup = popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)          # a bare dropdown panel
        popup.configure(bg=theme.BORDER)

        x = self.button.winfo_rootx()
        y = self.button.winfo_rooty() + self.button.winfo_height() + 2
        width = max(self.width, 240)
        # Keep the panel on screen when the filter sits near an edge.
        x = min(x, self.winfo_screenwidth() - width - 8)
        y = min(y, max(0, self.winfo_screenheight() - self.popup_height - 8))
        popup.geometry(f"{width}x{self.popup_height}+{x}+{y}")

        frame = tk.Frame(popup, bg=theme.BG_CARD)
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        search_var = tk.StringVar()
        search = tk.Entry(
            frame, textvariable=search_var, bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY,
            insertbackground=theme.TEXT_PRIMARY, relief="flat", highlightthickness=1,
            highlightbackground=theme.BG_INPUT_BORDER, highlightcolor=theme.ACCENT,
            font=(theme.FONT_FAMILY, 10),
        )
        search.pack(fill="x", padx=8, pady=(8, 6), ipady=4)
        search.focus_set()

        # Lightweight placeholder: tk.Entry has none of its own.
        placeholder = "Search values..."
        def show_placeholder():
            if not search_var.get():
                search.configure(fg=theme.TEXT_MUTED)
                search.insert(0, placeholder)
        def clear_placeholder(_event=None):
            if search.get() == placeholder:
                search.delete(0, "end")
                search.configure(fg=theme.TEXT_PRIMARY)
        search.bind("<FocusIn>", clear_placeholder)
        search.bind("<Key>", clear_placeholder)
        show_placeholder()

        actions = tk.Frame(frame, bg=theme.BG_CARD)
        actions.pack(fill="x", padx=8)
        tk.Button(
            actions, text="Select all", command=lambda: self._bulk(True),
            bg=theme.BG_CARD_ALT, fg=theme.TEXT_SECONDARY, relief="flat",
            font=(theme.FONT_FAMILY, 9), bd=0, padx=8, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            actions, text="Clear", command=lambda: self._bulk(False),
            bg=theme.BG_CARD_ALT, fg=theme.TEXT_SECONDARY, relief="flat",
            font=(theme.FONT_FAMILY, 9), bd=0, padx=8, cursor="hand2",
        ).pack(side="left", padx=(6, 0))

        # Buttons reserved before the list so they can never be pushed off.
        footer = tk.Frame(frame, bg=theme.BG_CARD)
        footer.pack(side="bottom", fill="x", padx=8, pady=8)
        tk.Button(
            footer, text="Apply", command=self._apply, bg=theme.ACCENT, fg="#ffffff",
            relief="flat", font=(theme.FONT_FAMILY, 10, "bold"), bd=0, pady=4, cursor="hand2",
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            footer, text="Cancel", command=self._close_popup, bg=theme.BG_CARD_ALT,
            fg=theme.TEXT_SECONDARY, relief="flat", font=(theme.FONT_FAMILY, 10),
            bd=0, pady=4, cursor="hand2",
        ).pack(side="right")

        list_host = tk.Frame(frame, bg=theme.BG_CARD)
        list_host.pack(fill="both", expand=True, padx=8, pady=(6, 0))
        canvas = tk.Canvas(list_host, bg=theme.BG_CARD, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_host, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=theme.BG_CARD)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        for seq, delta in (("<MouseWheel>", None), ("<Button-4>", -1), ("<Button-5>", 1)):
            canvas.bind_all(
                seq,
                lambda e, d=delta: canvas.yview_scroll(
                    d if d is not None else (-1 if e.delta > 0 else 1), "units"
                ),
                add="+",
            )

        self._popup_parts = (canvas, inner, search_var)
        self._vars = {v: tk.BooleanVar(value=(v in self._selected)) for v in self._values}
        self._render_list()
        search_var.trace_add("write", lambda *a: self._render_list())

        popup.bind("<Escape>", lambda e: self._close_popup())
        popup.bind("<Return>", lambda e: self._apply())
        # Clicking anywhere else dismisses the panel, like a real dropdown.
        popup.bind("<FocusOut>", lambda e: None)
        self.winfo_toplevel().bind("<Button-1>", self._maybe_close, add="+")

    def _render_list(self):
        canvas, inner, search_var = self._popup_parts
        for child in inner.winfo_children():
            child.destroy()
        needle = search_var.get().strip().lower()
        if needle == "search values...":
            needle = ""
        for value in self._values:
            if needle and needle not in value.lower():
                continue
            tk.Checkbutton(
                inner, text=(value if len(value) <= 34 else value[:33] + "…"),
                variable=self._vars[value], anchor="w",
                bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, selectcolor=theme.BG_INPUT,
                activebackground=theme.BG_CARD, activeforeground=theme.TEXT_PRIMARY,
                font=(theme.FONT_FAMILY, 10), relief="flat", bd=0, highlightthickness=0,
                cursor="hand2",
            ).pack(fill="x", anchor="w")
        canvas.yview_moveto(0)

    def _bulk(self, state):
        _canvas, _inner, search_var = self._popup_parts
        needle = search_var.get().strip().lower()
        if needle == "search values...":
            needle = ""
        for value, var in self._vars.items():
            if not needle or needle in value.lower():
                var.set(state)

    def _apply(self):
        chosen = {v for v, var in self._vars.items() if var.get()}
        # Everything ticked is the same as no filter - keep it as "(All)" so
        # the other filters are not needlessly narrowed.
        self._selected = set() if chosen == set(self._values) else chosen
        self._refresh_button()
        self._close_popup()
        if self.on_change:
            self.on_change()

    def _maybe_close(self, event):
        if self._popup is None or not self._popup.winfo_exists():
            return
        widget = event.widget
        while widget is not None:
            if widget is self._popup or widget is self.button:
                return
            widget = getattr(widget, "master", None)
        self._close_popup()

    def _close_popup(self):
        if self._popup is not None and self._popup.winfo_exists():
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    self._popup_parts[0].unbind_all(seq)
                except Exception:
                    pass
            self._popup.destroy()
        self._popup = None
