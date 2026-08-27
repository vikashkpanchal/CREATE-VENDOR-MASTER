"""ARC Structure: the ARC -> FO -> line item tree, with values rolling up.

This is the view that makes the module's rule visible at a glance. Expand an
ARC and you see the FOs it carries; expand an FO and you see the line items
its value is made of. Every parent shows the total of its children, so the
ARC figure can always be traced down to the references it came from.
"""

from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from vendor_app.arc import format_amount
from vendor_app.export import export_arcs_to_excel
from vendor_app.gui import theme
from vendor_app.gui.style import (
    SCROLL_H_STYLE, SCROLL_V_STYLE, TREE_STYLE, apply_dark_treeview_style,
)
from vendor_app.gui.toast import notify
from vendor_app.gui.util import debounce
from vendor_app.gui.widgets import card, pill, primary_button, secondary_button

COLUMNS = ["level", "reference", "description", "vendor", "dates", "value"]
HEADERS = {
    "#0": "ARC / FO / Line",
    "level": "Level",
    "reference": "Reference",
    "description": "Description",
    "vendor": "Vendor",
    "dates": "Dates",
    "value": "Value (Ordered / Target)",
}
# Sized so the Value column - the number this whole view exists to show -
# lands inside the panel without anyone having to scroll right for it.
WIDTHS = {
    "#0": 235, "level": 74, "reference": 128, "description": 250,
    "vendor": 180, "dates": 158, "value": 190,
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
            text="Every ARC with the FOs beneath it and the line items behind each FO. "
                 "A parent's value is always the sum of its children, shown against "
                 "the ARC's own target value.",
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
        primary_button(actions, "Export ARCs (.xlsx)", self.export, width=180).pack(side="left")

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
            toolbar, textvariable=self.search_var, width=320, height=32,
            placeholder_text="ARC No, FO No, vendor, description...",
            fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
        ).pack(side="left")
        self.count_pill = pill(toolbar, "0 ARCs")
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

        self.tree.tag_configure("arc", background=theme.BG_CARD_ALT,
                                font=(theme.FONT_FAMILY, 11, "bold"))
        self.tree.tag_configure("orphan", background=theme.DANGER_SOFT)
        self.tree.tag_configure("fo", background=theme.BG_CARD)
        self.tree.tag_configure("line", background=theme.BG_ROW_ALT)
        self.tree.bind("<Double-1>", self._on_double_click)

    def _build_kpis(self):
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", padx=20, pady=(0, 10))
        self.kpi = {}
        for key, label in (
            ("arcs", "ARCs"), ("fos", "FOs"), ("lines", "Line Items"),
            ("target_value", "Total ARC Value"), ("value", "Ordered on FOs"),
            ("orphan_fos", "FOs Without an ARC"),
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
        """An ARC stays when it, any of its FOs, or any line matches."""
        if not needle:
            return True
        blobs = [" ".join(str(v) for v in node["record"].values())]
        for fo in node["fos"]:
            blobs.append(" ".join(str(v) for v in fo["record"].values()))
            blobs.extend(" ".join(str(v) for v in l["record"].values()) for l in fo["lines"])
        return any(needle in b.lower() for b in blobs)

    def refresh(self):
        if not hasattr(self, "tree"):
            return
        needle = self.search_var.get().strip().lower()
        tree = [n for n in self.store.structure() if self._matches(n, needle)]

        for item in self.tree.get_children():
            self.tree.delete(item)

        for node in tree:
            arc = node["record"]
            tags = ("orphan",) if node.get("orphan") else ("arc",)
            arc_id = self.tree.insert(
                "", "end", text=f"  {arc.get('arc_no', '')}", open=False, tags=tags,
                values=[
                    "ARC",
                    arc.get("amendment_no", "") and f"Amd {arc.get('amendment_no')}" or "",
                    arc.get("arc_description", ""),
                    self._vendor(arc),
                    self._dates(arc.get("arc_start_date", ""), arc.get("arc_end_date", "")),
                    self._arc_value(node),
                ],
            )
            for fo in node["fos"]:
                record = fo["record"]
                fo_id = self.tree.insert(
                    arc_id, "end", text=f"      {record.get('fo_no', '')}", tags=("fo",),
                    values=[
                        "FO",
                        record.get("fo_no", ""),
                        record.get("fo_description", ""),
                        self._vendor(record),
                        self._dates(record.get("fo_date", ""),
                                    record.get("validity_end_date", "")),
                        format_amount(fo["total"]),
                    ],
                )
                for line in fo["lines"]:
                    item = line["record"]
                    self.tree.insert(
                        fo_id, "end",
                        text=f"            Line {item.get('line_no', '')}", tags=("line",),
                        values=[
                            "Line",
                            item.get("item_code", "") or item.get("reference", ""),
                            self._line_description(item),
                            # A line item has no vendor and no period of its
                            # own, so those columns stay empty rather than
                            # being filled with something they are not.
                            "", "",
                            format_amount(line["value"]),
                        ],
                    )

        summary = self.store.summary()
        self.kpi["arcs"].configure(text=f"{summary['arcs']:,}")
        self.kpi["fos"].configure(text=f"{summary['fos']:,}")
        self.kpi["lines"].configure(text=f"{summary['lines']:,}")
        self.kpi["target_value"].configure(text=format_amount(summary["target_value"]))
        self.kpi["value"].configure(text=format_amount(summary["value"]))
        self.kpi["orphan_fos"].configure(text=f"{summary['orphan_fos']:,}")
        self.count_pill.configure(
            text=f"  {len(tree)} ARC{'s' if len(tree) != 1 else ''} shown  "
        )

    @staticmethod
    def _vendor(record):
        code = record.get("vendor_code", "")
        name = record.get("vendor_name", "")
        if code and name:
            return f"{code} - {name}"
        return code or name

    @staticmethod
    def _arc_value(node):
        """Ordered against the ARC, and the target it was released for.

        Both figures belong in the same cell: the roll-up on its own says
        nothing about whether the contract is under- or over-used, which is
        the question this column is read for.
        """
        ordered = format_amount(node["total"])
        target = node.get("target") or 0.0
        return f"{ordered} / {format_amount(target)}" if target else ordered

    @staticmethod
    def _dates(start, end):
        if start and end:
            return f"{start} to {end}"
        return start or end

    @staticmethod
    def _line_description(item):
        """The item, with its quantity x rate appended when it has one - that
        is the arithmetic behind the line's value, so it belongs next to it."""
        text = item.get("item_description", "") or item.get("reference", "")
        qty, rate = item.get("quantity", ""), item.get("rate", "")
        if qty and rate:
            return f"{text}  ({qty} x {rate})".strip()
        return text

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
        """Double-click an ARC or FO row to open its full record."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        values = self.tree.item(item, "values")
        level = values[0] if values else ""
        key = self.tree.item(item, "text").strip()
        if level == "ARC":
            record = self.store.arcs.find(key)
            if record is not None:
                from vendor_app.gui.arc_dialogs import ArcDialog
                ArcDialog(self, self.store, record, on_saved=self.refresh)
        elif level == "FO":
            record = self.store.fos.find(key)
            if record is not None:
                from vendor_app.gui.arc_dialogs import FoDialog
                FoDialog(self, self.store, record, on_saved=self.refresh)

    def export(self):
        records = [self.store.arc_row(a) for a in self.store.all_arcs()]
        if not records:
            messagebox.showwarning("No Data", "There are no ARCs to export.")
            return
        default = f"ARC_Master_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return
        export_arcs_to_excel(records, path)
        notify(self, f"{len(records):,} ARC(s) exported to:\n{path}")
