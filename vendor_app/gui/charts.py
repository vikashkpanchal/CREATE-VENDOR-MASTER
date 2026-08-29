"""Small chart widgets drawn on a Tk canvas.

Deliberately dependency-free (no matplotlib): ranked magnitude bars, a
composition bar, a status donut and a two-series comparison cover every
chart the dashboards ask for.

Design follows the house data-viz rules: one hue for a single-measure
ranking (colour encodes nothing there, so it must not vary by rank),
categorical hues only where colour carries identity and always with a
named legend, direct value labels instead of a value axis, recessive
tracks, and a hover tooltip on every ranked bar.
"""

import tkinter as tk

from vendor_app.gui import theme

# Validated dark-surface series steps.
BAR_COLOR = "#3987e5"
BAR_HOVER = "#5b9dee"
BAR_TRACK = "#1f2530"


class BarChart(tk.Frame):
    """Horizontal ranked bar chart. `data` is a list of (label, value)."""

    BAR_H = 22
    GAP = 10
    PAD_TOP = 10
    LABEL_W = 200
    VALUE_W = 64

    def __init__(self, master, title="", empty_text="No data for the current filters."):
        super().__init__(master, bg=theme.BG_CARD, highlightthickness=0)
        self.title_text = title
        self.empty_text = empty_text
        self.data = []
        self._bars = {}

        if title:
            tk.Label(
                self, text=title, bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY,
                font=(theme.FONT_FAMILY, 12, "bold"), anchor="w",
            ).pack(anchor="w", padx=16, pady=(14, 2))

        self.canvas = tk.Canvas(self, bg=theme.BG_CARD, highlightthickness=0, height=200)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(4, 12))
        self.canvas.bind("<Configure>", lambda e: self._draw())
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._hide_tip())

        self._tip = None

    def set_data(self, data):
        self.data = list(data)
        self._draw()

    # -------------------------------------------------------------- draw --
    def _rounded_bar(self, x0, y0, x1, y1, radius, fill, tags):
        """A bar with rounded ends; falls back to a plain rect when short."""
        radius = max(0, min(radius, (y1 - y0) // 2, max(0, (x1 - x0) // 2)))
        if radius <= 1 or x1 - x0 < 3:
            return self.canvas.create_rectangle(
                x0, y0, max(x1, x0 + 2), y1, fill=fill, outline="", tags=tags
            )
        self.canvas.create_rectangle(x0 + radius, y0, x1 - radius, y1, fill=fill, outline="", tags=tags)
        self.canvas.create_oval(x0, y0, x0 + 2 * radius, y1, fill=fill, outline="", tags=tags)
        self.canvas.create_oval(x1 - 2 * radius, y0, x1, y1, fill=fill, outline="", tags=tags)

    def _fit(self, text, max_px):
        """Shorten `text` with an ellipsis until it fits `max_px`."""
        font = ("TkDefaultFont", 10)
        try:
            import tkinter.font as tkfont
            measurer = tkfont.Font(family=theme.FONT_FAMILY, size=10)
        except Exception:
            # Fall back to a character estimate if font metrics are unavailable.
            limit = max(4, int(max_px / 7))
            return text if len(text) <= limit else text[: limit - 1] + "\u2026"

        if measurer.measure(text) <= max_px:
            return text
        shortened = text
        while shortened and measurer.measure(shortened + "\u2026") > max_px:
            shortened = shortened[:-1]
        return (shortened + "\u2026") if shortened else text[:1]

    def _draw(self):
        self.canvas.delete("all")
        self._bars = {}
        width = self.canvas.winfo_width()
        if width <= 1:
            return

        if not self.data:
            self.canvas.create_text(
                width // 2, 60, text=self.empty_text, fill=theme.TEXT_MUTED,
                font=(theme.FONT_FAMILY, 10),
            )
            self.canvas.configure(height=120)
            return

        rows = self.data
        height = self.PAD_TOP * 2 + len(rows) * (self.BAR_H + self.GAP)
        self.canvas.configure(height=max(120, height))

        plot_x0 = self.LABEL_W + 12
        plot_x1 = max(plot_x0 + 40, width - self.VALUE_W - 16)
        largest = max(value for _, value in rows) or 1

        for index, (label, value) in enumerate(rows):
            y0 = self.PAD_TOP + index * (self.BAR_H + self.GAP)
            y1 = y0 + self.BAR_H
            tag = f"bar{index}"

            # Truncate to what actually fits: the label is right-anchored at
            # LABEL_W, so an over-long name would otherwise run off the left
            # edge of the canvas instead of being clipped politely.
            text = self._fit(str(label), self.LABEL_W - 10)
            self.canvas.create_text(
                self.LABEL_W, y0 + self.BAR_H / 2, text=text, anchor="e",
                fill=theme.TEXT_SECONDARY, font=(theme.FONT_FAMILY, 10),
            )
            # Recessive track shows each bar's share of the leader at a glance.
            self._rounded_bar(plot_x0, y0, plot_x1, y1, 4, BAR_TRACK, ("track",))
            bar_x1 = plot_x0 + (plot_x1 - plot_x0) * (value / largest)
            self._rounded_bar(plot_x0, y0, bar_x1, y1, 4, BAR_COLOR, (tag, "bar"))
            self.canvas.create_text(
                plot_x1 + 10, y0 + self.BAR_H / 2, text=f"{value:,}", anchor="w",
                fill=theme.TEXT_PRIMARY, font=(theme.FONT_FAMILY, 10, "bold"),
            )
            self._bars[tag] = (y0, y1, label, value)

    # ------------------------------------------------------------- hover --
    def _on_motion(self, event):
        for tag, (y0, y1, label, value) in self._bars.items():
            if y0 <= event.y <= y1:
                self._show_tip(event, f"{label}: {value:,}")
                return
        self._hide_tip()

    def _show_tip(self, event, text):
        if self._tip is None:
            self._tip = tk.Label(
                self.canvas, bg=theme.BG_CARD_ALT, fg=theme.TEXT_PRIMARY,
                font=(theme.FONT_FAMILY, 9), bd=0, padx=8, pady=4,
                highlightthickness=1, highlightbackground=theme.BORDER,
            )
        self._tip.configure(text=text)
        self._tip.place(x=min(event.x + 14, max(0, self.canvas.winfo_width() - 220)), y=event.y + 12)

    def _hide_tip(self):
        if self._tip is not None:
            self._tip.place_forget()


class SplitBar(tk.Frame):
    """A single composition bar (e.g. RO vs RH) with a legend beneath it.

    Two categories only - identity matters here, so the two validated
    categorical hues are used, and both are labelled in the legend so
    identity is never carried by colour alone.
    """

    COLORS = ["#3987e5", "#d95926"]

    def __init__(self, master, title=""):
        super().__init__(master, bg=theme.BG_CARD, highlightthickness=0)
        if title:
            tk.Label(
                self, text=title, bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY,
                font=(theme.FONT_FAMILY, 12, "bold"), anchor="w",
            ).pack(anchor="w", padx=16, pady=(14, 6))
        self.canvas = tk.Canvas(self, bg=theme.BG_CARD, highlightthickness=0, height=34)
        self.canvas.pack(fill="x", padx=16)
        self.legend = tk.Frame(self, bg=theme.BG_CARD)
        self.legend.pack(anchor="w", padx=16, pady=(10, 14))
        self.data = []
        self.canvas.bind("<Configure>", lambda e: self._draw())

    def set_data(self, data):
        self.data = [(k, v) for k, v in data if v]
        self._draw()

    def _draw(self):
        self.canvas.delete("all")
        for child in self.legend.winfo_children():
            child.destroy()

        width = self.canvas.winfo_width()
        if width <= 1:
            return
        total = sum(v for _, v in self.data)
        if not total:
            self.canvas.create_text(
                width // 2, 17, text="No data", fill=theme.TEXT_MUTED,
                font=(theme.FONT_FAMILY, 10),
            )
            return

        x = 0
        for index, (label, value) in enumerate(self.data):
            segment = (width) * (value / total)
            color = self.COLORS[index % len(self.COLORS)]
            # 2px surface gap between segments keeps them visually separate.
            self.canvas.create_rectangle(
                x, 4, max(x + 2, x + segment - 2), 30, fill=color, outline="",
            )
            if segment > 44:
                self.canvas.create_text(
                    x + segment / 2, 17, text=f"{value:,}", fill="#ffffff",
                    font=(theme.FONT_FAMILY, 10, "bold"),
                )
            x += segment

            item = tk.Frame(self.legend, bg=theme.BG_CARD)
            item.pack(side="left", padx=(0, 18))
            tk.Canvas(item, width=10, height=10, bg=color, highlightthickness=0).pack(
                side="left", padx=(0, 6)
            )
            share = value / total * 100
            tk.Label(
                item, text=f"{label}  {value:,}  ({share:.0f}%)", bg=theme.BG_CARD,
                fg=theme.TEXT_SECONDARY, font=(theme.FONT_FAMILY, 10),
            ).pack(side="left")


class PieChart(tk.Frame):
    """A donut of a small categorical breakdown, with a labelled legend.

    Used for status splits, where the categories are few and named. Every
    slice is also written out in the legend with its count and share, so the
    reading never depends on telling two colours apart.
    """

    SIZE = 168
    THICKNESS = 34
    # How wide a legend entry may run before it wraps onto a second line.
    # Sized for the narrowest column a donut sits in - three charts across a
    # dashboard - so an entry never demands more width than the legend has.
    # A fixed wrap is deliberate: re-arranging the legend on resize made the
    # two layouts flip each other back and forth without ever settling.
    LEGEND_TEXT_W = 160
    DEFAULT_COLORS = ["#3987e5", "#d95926", "#8a94a6", "#34b871", "#e0ac48"]

    def __init__(self, master, title="", colors=None,
                 empty_text="No data to chart yet."):
        super().__init__(master, bg=theme.BG_CARD, highlightthickness=0)
        self.colors = colors or {}
        self.empty_text = empty_text
        self.data = []

        if title:
            tk.Label(
                self, text=title, bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY,
                font=(theme.FONT_FAMILY, 12, "bold"), anchor="w",
            ).pack(anchor="w", padx=16, pady=(14, 6))

        body = tk.Frame(self, bg=theme.BG_CARD)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.canvas = tk.Canvas(
            body, bg=theme.BG_CARD, highlightthickness=0,
            width=self.SIZE, height=self.SIZE,
        )
        self.canvas.pack(side="left")
        self.legend = tk.Frame(body, bg=theme.BG_CARD)
        self.legend.pack(side="left", fill="both", expand=True, padx=(16, 0))

    def set_data(self, data):
        self.data = [(str(k), v) for k, v in data if v]
        self._draw()

    def _color(self, index, label):
        return self.colors.get(label, self.DEFAULT_COLORS[index % len(self.DEFAULT_COLORS)])

    def _draw(self):
        self.canvas.delete("all")
        for child in self.legend.winfo_children():
            child.destroy()

        total = sum(v for _, v in self.data)
        size, thick = self.SIZE, self.THICKNESS
        if not total:
            self.canvas.create_oval(4, 4, size - 4, size - 4, outline=BAR_TRACK, width=thick)
            tk.Label(
                self.legend, text=self.empty_text, bg=theme.BG_CARD,
                fg=theme.TEXT_MUTED, font=(theme.FONT_FAMILY, 10), justify="left",
            ).pack(anchor="w")
            return

        start = 90.0
        for index, (label, value) in enumerate(self.data):
            extent = -360.0 * value / total
            # A single-category donut needs a full ring: Tk draws nothing at
            # all for an extent of exactly 360, so it is nudged just under.
            drawn = extent if abs(extent) < 359.99 else -359.99
            self.canvas.create_arc(
                thick / 2 + 4, thick / 2 + 4, size - thick / 2 - 4, size - thick / 2 - 4,
                start=start, extent=drawn, style="arc",
                outline=self._color(index, label), width=thick,
            )
            start += extent

        self.canvas.create_text(
            size / 2, size / 2 - 8, text=f"{total:,}", fill=theme.TEXT_PRIMARY,
            font=(theme.FONT_FAMILY, 17, "bold"),
        )
        self.canvas.create_text(
            size / 2, size / 2 + 12, text="total", fill=theme.TEXT_MUTED,
            font=(theme.FONT_FAMILY, 9),
        )

        for index, (label, value) in enumerate(self.data):
            row = tk.Frame(self.legend, bg=theme.BG_CARD)
            row.pack(anchor="w", pady=3)
            tk.Canvas(
                row, width=10, height=10, bg=self._color(index, label), highlightthickness=0,
            ).pack(side="left", padx=(0, 8))
            tk.Label(
                row, text=f"{label}  {value:,}  ({value / total * 100:.0f}%)",
                bg=theme.BG_CARD, fg=theme.TEXT_SECONDARY, font=(theme.FONT_FAMILY, 10),
                wraplength=self.LEGEND_TEXT_W, justify="left", anchor="w",
            ).pack(side="left")


class GroupedBarChart(tk.Frame):
    """Two measures compared per category, e.g. ARC value against FO value.

    Both series are drawn as paired bars on a shared scale, so the gap
    between them is the length difference and needs no arithmetic. Colour
    carries series identity only, and both series are named in the legend.
    """

    BAR_H = 13
    PAIR_GAP = 3
    GROUP_GAP = 14
    PAD_TOP = 10
    LABEL_W = 170
    VALUE_W = 108
    COLORS = ["#3987e5", "#d95926"]

    def __init__(self, master, title="", series=("A", "B"), formatter=None,
                 empty_text="No data to chart yet."):
        super().__init__(master, bg=theme.BG_CARD, highlightthickness=0)
        self.series = series
        self.formatter = formatter or (lambda v: f"{v:,.0f}")
        self.empty_text = empty_text
        self.data = []

        if title:
            tk.Label(
                self, text=title, bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY,
                font=(theme.FONT_FAMILY, 12, "bold"), anchor="w",
            ).pack(anchor="w", padx=16, pady=(14, 2))

        legend = tk.Frame(self, bg=theme.BG_CARD)
        legend.pack(anchor="w", padx=16, pady=(2, 4))
        for index, name in enumerate(series):
            item = tk.Frame(legend, bg=theme.BG_CARD)
            item.pack(side="left", padx=(0, 16))
            tk.Canvas(
                item, width=10, height=10, bg=self.COLORS[index % len(self.COLORS)],
                highlightthickness=0,
            ).pack(side="left", padx=(0, 6))
            tk.Label(
                item, text=name, bg=theme.BG_CARD, fg=theme.TEXT_SECONDARY,
                font=(theme.FONT_FAMILY, 10),
            ).pack(side="left")

        self.canvas = tk.Canvas(self, bg=theme.BG_CARD, highlightthickness=0, height=200)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(4, 12))
        self.canvas.bind("<Configure>", lambda e: self._draw())

    def set_data(self, data):
        """`data` is a list of (label, value_a, value_b)."""
        self.data = list(data)
        self._draw()

    def _fit(self, text, max_px):
        try:
            import tkinter.font as tkfont
            measurer = tkfont.Font(family=theme.FONT_FAMILY, size=10)
        except Exception:
            limit = max(4, int(max_px / 7))
            return text if len(text) <= limit else text[: limit - 1] + "…"
        if measurer.measure(text) <= max_px:
            return text
        shortened = text
        while shortened and measurer.measure(shortened + "…") > max_px:
            shortened = shortened[:-1]
        return (shortened + "…") if shortened else text[:1]

    def _draw(self):
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        if width <= 1:
            return
        if not self.data:
            self.canvas.create_text(
                width // 2, 60, text=self.empty_text, fill=theme.TEXT_MUTED,
                font=(theme.FONT_FAMILY, 10),
            )
            self.canvas.configure(height=120)
            return

        group_h = self.BAR_H * 2 + self.PAIR_GAP
        height = self.PAD_TOP * 2 + len(self.data) * (group_h + self.GROUP_GAP)
        self.canvas.configure(height=max(120, height))

        plot_x0 = self.LABEL_W + 12
        plot_x1 = max(plot_x0 + 40, width - self.VALUE_W - 16)
        largest = max(max(a, b) for _, a, b in self.data) or 1

        for index, (label, first, second) in enumerate(self.data):
            top = self.PAD_TOP + index * (group_h + self.GROUP_GAP)
            self.canvas.create_text(
                self.LABEL_W, top + group_h / 2, anchor="e",
                text=self._fit(str(label), self.LABEL_W - 10),
                fill=theme.TEXT_SECONDARY, font=(theme.FONT_FAMILY, 10),
            )
            for offset, (value, color) in enumerate(
                ((first, self.COLORS[0]), (second, self.COLORS[1]))
            ):
                y0 = top + offset * (self.BAR_H + self.PAIR_GAP)
                y1 = y0 + self.BAR_H
                self.canvas.create_rectangle(
                    plot_x0, y0, plot_x1, y1, fill=BAR_TRACK, outline="",
                )
                bar_x1 = plot_x0 + (plot_x1 - plot_x0) * (max(value, 0) / largest)
                self.canvas.create_rectangle(
                    plot_x0, y0, max(plot_x0 + 2, bar_x1), y1, fill=color, outline="",
                )
                self.canvas.create_text(
                    plot_x1 + 10, (y0 + y1) / 2, anchor="w", text=self.formatter(value),
                    fill=theme.TEXT_PRIMARY if offset == 0 else theme.TEXT_SECONDARY,
                    font=(theme.FONT_FAMILY, 9, "bold" if offset == 0 else "normal"),
                )
