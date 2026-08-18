"""Dark-theme ttk styling shared by every table in the app (Master Data
Records, Multi Vendor Search results). customtkinter has no table widget
of its own, so ttk.Treeview is used and re-skinned to match the design
system in theme.py: wrapped two-line headers, tall rows, zebra striping,
and matching dark scrollbars.
"""

from tkinter import ttk

from vendor_app.gui import theme

TREE_STYLE = "Vendor.Treeview"
SCROLL_V_STYLE = "Vendor.Vertical.TScrollbar"
SCROLL_H_STYLE = "Vendor.Horizontal.TScrollbar"

ROW_HEIGHT = 34
HEADER_FONT = (theme.FONT_FAMILY, 10, "bold")
ROW_FONT = (theme.FONT_FAMILY, 11)

_applied = False


def apply_dark_treeview_style() -> ttk.Style:
    global _applied
    style = ttk.Style()
    if _applied:
        return style

    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        TREE_STYLE,
        background=theme.BG_CARD,
        foreground=theme.TEXT_PRIMARY,
        fieldbackground=theme.BG_CARD,
        bordercolor=theme.BORDER_SOFT,
        borderwidth=0,
        rowheight=ROW_HEIGHT,
        font=ROW_FONT,
    )
    style.map(
        TREE_STYLE,
        background=[("selected", theme.ACCENT)],
        foreground=[("selected", theme.TEXT_ON_ACCENT)],
    )

    style.configure(
        f"{TREE_STYLE}.Heading",
        background=theme.BG_CARD_ALT,
        foreground=theme.TEXT_SECONDARY,
        relief="flat",
        font=HEADER_FONT,
        padding=(10, 12, 10, 14),
    )
    style.map(
        f"{TREE_STYLE}.Heading",
        background=[("active", theme.BG_HOVER)],
        foreground=[("active", theme.TEXT_PRIMARY)],
    )

    for scroll_style in (SCROLL_V_STYLE, SCROLL_H_STYLE):
        style.configure(
            scroll_style,
            background=theme.BG_CARD_ALT,
            troughcolor=theme.BG_SURFACE,
            bordercolor=theme.BG_SURFACE,
            arrowcolor=theme.TEXT_SECONDARY,
            relief="flat",
        )
        style.map(scroll_style, background=[("active", theme.ACCENT)])

    _applied = True
    return style


def build_table(parent, columns, key_to_wrapped_label, key_to_width, height=None):
    """Create a themed Treeview with wrapped headers + vertical & horizontal
    scrollbars, wrapped in its own frame. Returns (outer_frame, treeview).

    `columns` is the ordered list of column keys. `key_to_wrapped_label` and
    `key_to_width` map those keys to two-line header text and pixel width.
    """
    apply_dark_treeview_style()

    outer = ttk_frame_with_scrollbars(parent)
    tree_kwargs = {"columns": columns, "show": "headings", "style": TREE_STYLE}
    if height is not None:
        tree_kwargs["height"] = height
    tree = ttk.Treeview(outer["body"], **tree_kwargs)

    for key in columns:
        tree.heading(key, text=key_to_wrapped_label.get(key, key), anchor="center")
        anchor = "center" if key in ("sr_no", "vendor_code") else "w"
        tree.column(key, width=key_to_width.get(key, 150), minwidth=60, anchor=anchor, stretch=False)

    tree.tag_configure("odd", background=theme.BG_CARD)
    tree.tag_configure("even", background=theme.BG_ROW_ALT)

    tree.grid(row=0, column=0, sticky="nsew")
    outer["vsb"].configure(command=tree.yview)
    outer["hsb"].configure(command=tree.xview)
    tree.configure(yscrollcommand=outer["vsb"].set, xscrollcommand=outer["hsb"].set)

    return outer["frame"], tree


def ttk_frame_with_scrollbars(parent):
    """A plain frame hosting a body cell (row 0, col 0) plus a vertical
    scrollbar (col 1) and horizontal scrollbar (row 1) around it, styled
    to match the dark theme. The caller places its own widget into `body`
    and wires the returned scrollbars to it.
    """
    import tkinter as tk

    frame = tk.Frame(parent, bg=theme.BG_CARD, highlightthickness=1, highlightbackground=theme.BORDER_SOFT)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    body = tk.Frame(frame, bg=theme.BG_CARD)
    body.grid(row=0, column=0, sticky="nsew")
    body.grid_rowconfigure(0, weight=1)
    body.grid_columnconfigure(0, weight=1)

    vsb = ttk.Scrollbar(frame, orient="vertical", style=SCROLL_V_STYLE)
    vsb.grid(row=0, column=1, sticky="ns")
    hsb = ttk.Scrollbar(frame, orient="horizontal", style=SCROLL_H_STYLE)
    hsb.grid(row=1, column=0, sticky="ew")

    return {"frame": frame, "body": body, "vsb": vsb, "hsb": hsb}


def stripe_rows(tree):
    """Apply odd/even row tags to every current row for zebra striping."""
    for i, item in enumerate(tree.get_children("")):
        tree.item(item, tags=("even" if i % 2 == 0 else "odd",))
