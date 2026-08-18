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


def build_table(parent, columns, key_to_wrapped_label, key_to_width, height=None, on_sort=None):
    """Create a themed Treeview with wrapped headers + vertical & horizontal
    scrollbars + row hover highlight, wrapped in its own frame. Returns
    (outer_frame, treeview).

    `columns` is the ordered list of column keys. `key_to_wrapped_label` and
    `key_to_width` map those keys to two-line header text and pixel width.
    If `on_sort` is given, it is called with a column key whenever that
    column's header is clicked (the caller owns sort-order state and
    re-populates the tree; see set_heading_text for updating the arrow).
    """
    apply_dark_treeview_style()

    outer = ttk_frame_with_scrollbars(parent)
    tree_kwargs = {"columns": columns, "show": "headings", "style": TREE_STYLE}
    if height is not None:
        tree_kwargs["height"] = height
    tree = ttk.Treeview(outer["body"], **tree_kwargs)

    for key in columns:
        heading_kwargs = {"text": key_to_wrapped_label.get(key, key), "anchor": "center"}
        if on_sort is not None:
            heading_kwargs["command"] = lambda k=key: on_sort(k)
        tree.heading(key, **heading_kwargs)
        anchor = "center" if key in ("sr_no", "vendor_code", "status") else "w"
        tree.column(key, width=key_to_width.get(key, 150), minwidth=60, anchor=anchor, stretch=False)

    # ttk.Treeview resolves overlapping tag options by tag_configure() call
    # order - the FIRST tag configured wins, regardless of the order tags
    # appear in an item's own tags tuple. So highest-priority visual states
    # (hover, then lifecycle status) must be configured before the zebra
    # stripe base tags.
    tree.tag_configure("hover", background=theme.BG_HOVER)
    tree.tag_configure("status-blocked", background=theme.DANGER_SOFT)
    tree.tag_configure("status-inactive", background=theme.BG_CARD_ALT)
    tree.tag_configure("odd", background=theme.BG_CARD)
    tree.tag_configure("even", background=theme.BG_ROW_ALT)
    tree._status_tags = {}

    tree.grid(row=0, column=0, sticky="nsew")
    outer["vsb"].configure(command=tree.yview)
    outer["hsb"].configure(command=tree.xview)
    tree.configure(yscrollcommand=outer["vsb"].set, xscrollcommand=outer["hsb"].set)

    enable_row_hover(tree)

    return outer["frame"], tree


def set_heading_text(tree, columns, key_to_wrapped_label, sort_key=None, sort_desc=False):
    """Refresh every column heading, appending a ▲/▼ sort arrow to whichever
    column is currently sorted."""
    for key in columns:
        text = key_to_wrapped_label.get(key, key)
        if key == sort_key:
            lines = text.split("\n")
            lines[-1] = lines[-1] + (" ▼" if sort_desc else " ▲")
            text = "\n".join(lines)
        tree.heading(key, text=text)


def enable_row_hover(tree):
    """Highlight whichever row the mouse is over, without disturbing zebra
    striping or lifecycle-status tinting on the rest of the table."""
    state = {"row": None}

    def base_tags(row):
        stored = getattr(tree, "_status_tags", {}).get(row)
        if stored:
            return stored
        return ("even" if tree.index(row) % 2 == 0 else "odd",)

    def restore(row):
        if row and tree.exists(row):
            tree.item(row, tags=base_tags(row))

    def on_motion(event):
        row = tree.identify_row(event.y)
        if row == state["row"]:
            return
        restore(state["row"])
        if row:
            tree.item(row, tags=base_tags(row) + ("hover",))
        state["row"] = row

    def on_leave(event):
        restore(state["row"])
        state["row"] = None

    tree.bind("<Motion>", on_motion)
    tree.bind("<Leave>", on_leave)


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


def row_tags(index, status=None):
    """Compute the tag tuple for a table row at 0-based display `index`,
    given its optional lifecycle status (Active/Inactive/Blocked).

    Callers should pass this straight to `tree.insert(..., tags=...)` at
    row-creation time rather than inserting first and retagging after -
    retagging a freshly-inserted batch is one extra paint cycle that can
    occasionally lag a step behind on some Tk/X11 setups, so tagging at
    insert time is both simpler and more robust.
    """
    tags = ["even" if index % 2 == 0 else "odd"]
    if status == "Blocked":
        tags.append("status-blocked")
    elif status == "Inactive":
        tags.append("status-inactive")
    return tuple(tags)


def insert_row(tree, index, status=None, **insert_kwargs):
    """Insert a row into `tree` with the right zebra/status tags already
    applied, and remember those tags for enable_row_hover() to restore."""
    tags = row_tags(index, status)
    iid = tree.insert("", "end", tags=tags, **insert_kwargs)
    tree._status_tags[iid] = tags
    return iid
