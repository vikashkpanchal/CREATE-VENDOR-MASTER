"""ARC Structure: the contract -> item / frame order -> item tree.

This is the view that makes the module's rule visible at a glance. Expand a
purchasing document and you see both what it covers (its Table 1 items) and
what has been ordered against it (its frame orders, each with its own
items). A contract shows released against target; a frame order shows what
its items add up to.

The one thing deliberately NOT shown as an addition is the contract's Target
Val. (Header). It repeats on every item of the document, so it is read once
and displayed once - adding the column up is the mistake this whole module
is arranged to prevent.
"""

from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from vendor_app.arc import format_amount, parse_amount
from vendor_app.config import RELEASE_INDICATORS
from vendor_app.export import export_arcs_to_excel
from vendor_app.gui import theme
from vendor_app.gui.style import (
    SCROLL_H_STYLE, SCROLL_V_STYLE, TREE_STYLE, apply_dark_treeview_style,
)
from vendor_app.gui.toast import notify
from vendor_app.gui.util import debounce
from vendor_app.gui.widgets import card, pill, primary_button, secondary_button

# The tree column already carries every identifier - the document, the item
# number, the frame number - so a separate "reference" column only repeated
# it. Its place goes to the release position, which is a contract fact with
# nowhere else to show in this view.
COLUMNS = ["level", "release", "description", "vendor", "dates", "value"]
HEADERS = {
    "#0": "Contract / Item / Frame Order",
    "level": "Level",
    "release": "Release",
    "description": "Description",
    "vendor": "Vendor",
    "dates": "Validity",
    "value": "Released / Target",
}
# Measured against the longest real cell in each column, not guessed. The
# figures and the dates are given whatever they need - a truncated number or
# a half-shown validity period is worse than useless - and the two free-text
# columns absorb what is left, since a clipped description still reads.
WIDTHS = {
    "#0": 205, "level": 88, "release": 195, "description": 180,
    "vendor": 192, "dates": 240, "value": 225,
}


class ArcStructureTab(ctk.CTkFrame):
    def __init__(self, master, store):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = store
        self._build()
        self.refresh()

    # -------------------------------------------------------------- build --
    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 10))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="ARC Structure", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Every purchasing document with the items it covers and the frame "
                 "orders placed against it. A contract shows what has been released "
                 "against its target value.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        secondary_button(actions, "Collapse All", self.collapse_all, width=120).pack(
            side="left", padx=(0, 8)
        )
        secondary_button(actions, "Expand All", self.expand_all, width=120).pack(
            side="left", padx=(0, 8)
        )
        primary_button(actions, "Export ARC Data (.xlsx)", self.export, width=190).pack(
            side="left"
        )

        self._build_kpis()

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(
            toolbar, text="Search:", font=theme.small_font(), text_color=theme.TEXT_SECONDARY
        ).pack(side="left", padx=(0, 8))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add(
            "write", lambda *a: debounce(self, "_arc_search_after", 220, self.refresh)
        )
        ctk.CTkEntry(
            toolbar, textvariable=self.search_var, width=340, height=32,
            placeholder_text="Purchasing document, frame number, vendor, text...",
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
        ).pack(side="left")
        self.count_pill = pill(toolbar, "0 contracts")
        self.count_pill.pack(side="left", padx=12)

        wrap = card(self, fg_color=theme.BG_CARD)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        apply_dark_treeview_style()
        body = ctk.CTkFrame(wrap, fg_color=theme.BG_CARD)
        body.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # show="tree headings": unlike every other table in the app this one
        # needs the tree column, since the hierarchy IS the content.
        self.tree = ttk.Treeview(
            body, columns=COLUMNS, show="tree headings", style=TREE_STYLE
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.heading("#0", text=HEADERS["#0"], anchor="w")
        self.tree.column("#0", width=WIDTHS["#0"], minwidth=180, stretch=False)
        for key in COLUMNS:
            self.tree.heading(key, text=HEADERS[key], anchor="w")
            anchor = "e" if key == "value" else "w"
            self.tree.column(key, width=WIDTHS[key], minwidth=70, anchor=anchor, stretch=False)

        vsb = ttk.Scrollbar(body, orient="vertical", style=SCROLL_V_STYLE, command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(body, orient="horizontal", style=SCROLL_H_STYLE,
                            command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.tag_configure("contract", background=theme.BG_CARD_ALT,
                                font=(theme.FONT_FAMILY, 11, "bold"))
        self.tree.tag_configure("orphan", background=theme.DANGER_SOFT)
        self.tree.tag_configure("frame", background=theme.BG_CARD)
        self.tree.tag_configure("item", background=theme.BG_ROW_ALT)
        self.tree.bind("<Double-1>", self._on_double_click)

    def _build_kpis(self):
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", padx=20, pady=(0, 10))
        self.kpi = {}
        for key, label in (
            ("arcs", "Contracts"), ("arc_items", "Contract Items"),
            ("fos", "Frame Orders"), ("target_value", "Total Target Value"),
            ("value", "Released Against"), ("orphan_fos", "FOs Without a Contract"),
        ):
            box = card(strip, fg_color=theme.BG_CARD)
            box.pack(side="left", fill="x", expand=True, padx=(0, 10))
            ctk.CTkLabel(
                box, text=label, font=theme.small_font(), text_color=theme.TEXT_SECONDARY
            ).pack(anchor="w", padx=16, pady=(14, 0))
            value = ctk.CTkLabel(
                box, text="0", font=theme.display_font(), text_color=theme.TEXT_PRIMARY
            )
            value.pack(anchor="w", padx=16, pady=(0, 14))
            self.kpi[key] = value

    # ------------------------------------------------------------ refresh --
    def _matches(self, node, needle):
        """A contract stays when it, any item, any frame order or any of its
        items matches."""
        if not needle:
            return True
        blobs = [" ".join(str(v) for v in node["header"].values())]
        blobs += [" ".join(str(v) for v in item.values()) for item in node["items"]]
        for frame in node["frames"]:
            blobs += [" ".join(str(v) for v in row.values()) for row in frame["items"]]
        return any(needle in b.lower() for b in blobs)

    def refresh(self):
        if not hasattr(self, "tree"):
            return
        needle = self.search_var.get().strip().lower()
        tree = [n for n in self.store.structure() if self._matches(n, needle)]

        for item in self.tree.get_children():
            self.tree.delete(item)

        for node in tree:
            header = node["header"]
            tags = ("orphan",) if node.get("orphan") else ("contract",)
            contract_id = self.tree.insert(
                "", "end", text=f"  {node['document']}", open=False, tags=tags,
                values=[
                    "Contract",
                    RELEASE_INDICATORS.get(
                        (header.get("release_indicator", "") or "").strip().upper(), ""),
                    self._contract_text(node),
                    header.get("vendor_supplying_plant", ""),
                    self._dates(header.get("validity_start", ""),
                                header.get("validity_end", "")),
                    self._contract_value(node),
                ],
            )
            for item in node["items"]:
                self.tree.insert(
                    contract_id, "end",
                    text=f"      Item {item.get('item', '')}", tags=("item",),
                    values=[
                        "Item", "", item.get("short_text", ""),
                        # A contract item carries no vendor, period or value of
                        # its own - all three are the document's, so they stay
                        # empty rather than repeating something they are not.
                        "", "", "",
                    ],
                )
            for frame in node["frames"]:
                first = frame["header"]
                frame_id = self.tree.insert(
                    contract_id, "end",
                    text=f"      {frame['frame']}", tags=("frame",),
                    values=[
                        "FO", "",
                        first.get("header_text", "") or first.get("description", ""),
                        self._vendor(first),
                        self._dates(first.get("fo_validity_start", ""),
                                    first.get("fo_validity_end", "")),
                        format_amount(frame["released"]),
                    ],
                )
                for row in frame["items"]:
                    self.tree.insert(
                        frame_id, "end",
                        text=f"            Item {row.get('item', '')}", tags=("item",),
                        values=[
                            "FO Item", "", self._item_text(row), "", "",
                            format_amount(parse_amount(row.get("released_value", ""))),
                        ],
                    )

        summary = self.store.summary()
        for key in ("arcs", "arc_items", "fos", "orphan_fos"):
            self.kpi[key].configure(text=f"{summary[key]:,}")
        self.kpi["target_value"].configure(text=format_amount(summary["target_value"]))
        self.kpi["value"].configure(text=format_amount(summary["value"]))
        contracts = sum(1 for n in tree if not n.get("orphan"))
        text = f"{contracts} contract{'s' if contracts != 1 else ''} shown"
        if any(n.get("orphan") for n in tree):
            # The unmatched group is a row in the tree but not a contract, so
            # it is named rather than quietly inflating the count.
            text += " + unmatched frame orders"
        self.count_pill.configure(text=f"  {text}  ")

    @staticmethod
    def _contract_text(node):
        """The contract's own text: the first item that carries one."""
        for item in node["items"]:
            if item.get("short_text"):
                return item["short_text"]
        return node["header"].get("short_text", "")

    @staticmethod
    def _contract_value(node):
        """Released against the contract, and the target it was released for.

        Both belong in one cell: the released figure alone says nothing about
        whether the contract is under- or over-used, which is the question
        this column is read for.
        """
        released = format_amount(node["released"])
        target = node.get("target") or 0.0
        return f"{released} / {format_amount(target)}" if target else released

    @staticmethod
    def _item_text(row):
        """An FO item's description, with its requisition tracking number when
        it has one - that is how the item is traced back upstream."""
        text = row.get("description", "")
        tracking = row.get("req_tracking_no", "")
        return f"{text}  ({tracking})".strip() if tracking else text

    @staticmethod
    def _vendor(record):
        code = record.get("vendor", "")
        name = record.get("vendor_name", "")
        if code and name:
            return f"{code} - {name}"
        return code or name

    @staticmethod
    def _dates(start, end):
        if start and end:
            return f"{start} to {end}"
        return start or end

    # ------------------------------------------------------------ actions --
    def expand_all(self):
        for item in self.tree.get_children():
            self.tree.item(item, open=True)
            for child in self.tree.get_children(item):
                self.tree.item(child, open=True)

    def collapse_all(self):
        for item in self.tree.get_children():
            self.tree.item(item, open=False)

    def _on_double_click(self, event):
        """Double-click a contract or frame order row to open a record."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        values = self.tree.item(item, "values")
        level = values[0] if values else ""
        key = self.tree.item(item, "text").strip()
        if level == "Contract":
            rows = self.store.items_for_document(key)
            if rows:
                from vendor_app.gui.arc_dialogs import ArcDialog
                ArcDialog(self, self.store, rows[0], on_saved=self.refresh)
        elif level == "Frame Order":
            rows = self.store.items_for_frame(key)
            if rows:
                from vendor_app.gui.arc_dialogs import FoDialog
                FoDialog(self, self.store, rows[0], on_saved=self.refresh)

    def export(self):
        records = [self.store.arc_row(a) for a in self.store.all_arcs()]
        if not records:
            messagebox.showwarning("No Data", "There is no ARC data to export.")
            return
        default = f"ARC_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return
        export_arcs_to_excel(records, path)
        notify(self, f"{len(records):,} row(s) exported to:\n{path}")
