"""Equipment Master: rental/hired equipment supplied by vendors.

Three modes, mirroring the vendor master's shape:
  * Equipment Records - the full list, live filter, import/paste, export
  * Single Search     - one identifier (RH/RO Number, Technical ID or Reg
                        No) returns that machine's full profile card
  * Multi Search      - paste a list of identifiers, get all matches in a
                        table (capped at MAX_EQUIPMENT_SEARCH_RESULTS)
"""

from datetime import datetime
from tkinter import messagebox, filedialog

import customtkinter as ctk

from vendor_app.config import (
    EQUIPMENT_COLUMN_WIDTHS,
    EQUIPMENT_KEYS,
    EQUIPMENT_LABELS,
    EQUIPMENT_LOOKUP_KEYS,
    EQUIPMENT_WRAPPED_LABELS,
    MAX_EQUIPMENT_SEARCH_RESULTS,
)
from vendor_app.communication import parse_identifiers
from vendor_app.export import export_equipment_to_excel
from vendor_app.importer import _read_table, _normalize_header  # reuse tolerant file reading
from vendor_app.validators import normalize
from vendor_app.gui import theme
from vendor_app.gui.style import build_table, insert_row
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import card, divider, pill, primary_button, section_label, wrap_children

COLUMNS = ["sr_no"] + EQUIPMENT_KEYS
_EQUIPMENT_LABEL_TO_KEY = {label.lower(): key for key, label in EQUIPMENT_LABELS.items()}


def load_equipment_from_file(path: str) -> list:
    """Parse an .xlsx/.csv/.tsv of equipment rows, matching headers by name."""
    df = _read_table(path)
    field_columns = {}
    for col in df.columns:
        header = _normalize_header(col)
        if header in _EQUIPMENT_LABEL_TO_KEY:
            field_columns[_EQUIPMENT_LABEL_TO_KEY[header]] = col
        elif header.replace(" ", "_") in EQUIPMENT_KEYS:
            field_columns[header.replace(" ", "_")] = col

    return [
        {key: str(row.get(col, "")).strip() for key, col in field_columns.items()}
        for _, row in df.iterrows()
    ]


class EquipmentSearchScreen(ctk.CTkFrame):
    """Look one machine up, or resolve a whole list of identifiers at once."""

    def __init__(self, master, equipment_store, on_data_changed=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.store = equipment_store
        self.on_data_changed = on_data_changed
        self.multi_results = []

        self._build_header()
        self.single_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.multi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._build_single()
        self._build_multi()
        self.single_frame.pack(fill="both", expand=True)

    def refresh(self):
        """Re-run the last multi search so results follow the master."""
        if self.multi_results:
            self.do_multi_search()

    # -------------------------------------------------------------- header --
    def _build_header(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(20, 12))

        left = ctk.CTkFrame(bar, fg_color="transparent")
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=0)
        left.grid(row=0, column=0, sticky="ew")
        wrap_children(left)
        ctk.CTkLabel(
            left, text="Search Equipment", font=theme.h1_font(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Find a machine by RH/RO Number, Technical ID or Reg No - "
                 "any one of the three works.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        seg = ctk.CTkSegmentedButton(
            bar,
            values=["Single Search", "Multi Search"],
            command=self._on_mode_change,
            selected_color=theme.ACCENT,
            selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.BG_CARD_ALT,
            unselected_hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.font(12, "bold"),
            height=36,
        )
        seg.set("Single Search")
        seg.grid(row=0, column=1, sticky="e", padx=(12, 0))

    def _on_mode_change(self, value):
        for frame in (self.single_frame, self.multi_frame):
            frame.pack_forget()
        if value == "Single Search":
            self.single_frame.pack(fill="both", expand=True)
        else:
            self.multi_frame.pack(fill="both", expand=True)

    # -------------------------------------------------------- single search --
    def _build_single(self):
        top = card(self.single_frame, fg_color=theme.BG_CARD)
        top.pack(fill="x", padx=20, pady=(0, 14))
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=16)
        ctk.CTkLabel(
            row, text="Identifier", font=theme.label_font(), text_color=theme.TEXT_SECONDARY
        ).pack(side="left", padx=(0, 10))
        self.single_entry = ctk.CTkEntry(
            row, width=260, height=34, fg_color=theme.BG_INPUT, border_color=theme.BG_INPUT_BORDER,
            placeholder_text="RH/RO Number, Technical ID or Reg No",
        )
        self.single_entry.pack(side="left", padx=(0, 10))
        self.single_entry.bind("<Return>", lambda e: self.do_single_search())
        primary_button(row, "Search", self.do_single_search, width=120).pack(side="left")

        self.card_frame = ctk.CTkScrollableFrame(self.single_frame, fg_color=theme.BG_SURFACE)
        self.card_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self._empty(self.card_frame, "Enter any one identifier and click Search.")

    def _empty(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=theme.body_font(), text_color=theme.TEXT_MUTED).pack(pady=48)

    def do_single_search(self):
        value = normalize(self.single_entry.get())
        for w in self.card_frame.winfo_children():
            w.destroy()
        if not value:
            self._empty(self.card_frame, "Please enter an identifier.")
            return
        record = self.store.lookup(value)
        if not record:
            self._empty(self.card_frame, f"No equipment found for '{value}'.")
            return

        header = card(self.card_frame, fg_color=theme.ACCENT_SOFT, border_color=theme.ACCENT_BORDER)
        header.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=18)
        ctk.CTkLabel(
            inner, text=record.get("equipment_description") or "(no description)",
            font=theme.h1_font(), text_color=theme.TEXT_PRIMARY, anchor="w",
        ).pack(anchor="w")
        badges = ctk.CTkFrame(inner, fg_color="transparent")
        badges.pack(anchor="w", pady=(6, 0))
        for key in EQUIPMENT_LOOKUP_KEYS:
            if record.get(key):
                pill(badges, f"{EQUIPMENT_LABELS[key]}: {record[key]}").pack(side="left", padx=(0, 8))

        box = card(self.card_frame, fg_color=theme.BG_CARD)
        box.pack(fill="x", pady=(0, 14))
        section_label(box, "EQUIPMENT DETAILS").pack(anchor="w", padx=20, pady=(16, 4))
        divider(box).pack(fill="x", padx=20, pady=(0, 6))
        for key in EQUIPMENT_KEYS:
            r = ctk.CTkFrame(box, fg_color="transparent")
            r.pack(fill="x", padx=20, pady=6)
            ctk.CTkLabel(
                r, text=EQUIPMENT_LABELS[key], width=240, anchor="w",
                font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            ).pack(side="left")
            ctk.CTkLabel(
                r, text=record.get(key) or "—", anchor="w", justify="left", wraplength=480,
                font=theme.body_font(), text_color=theme.TEXT_PRIMARY,
            ).pack(side="left", fill="x", expand=True)
        ctk.CTkFrame(box, fg_color="transparent", height=6).pack()

    # --------------------------------------------------------- multi search --
    def _build_multi(self):
        split = ctk.CTkFrame(self.multi_frame, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        left = card(split, fg_color=theme.BG_CARD, width=290)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)
        section_label(left, "IDENTIFIERS").pack(anchor="w", padx=16, pady=(16, 0))
        ctk.CTkLabel(
            left,
            text=f"RH/RO Number, Technical ID or Reg No\nOne per line  •  max "
                 f"{MAX_EQUIPMENT_SEARCH_RESULTS} results",
            font=theme.small_font(), text_color=theme.TEXT_MUTED, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))
        # Same bottom-anchored button as the Communication tab: reserved
        # before the expanding textbox so it stays on screen.
        primary_button(left, "Search", self.do_multi_search, width=258).pack(
            side="bottom", padx=16, pady=(10, 16)
        )
        self.multi_text = ctk.CTkTextbox(
            left, width=250, height=320, fg_color=theme.BG_INPUT,
            border_color=theme.BG_INPUT_BORDER, border_width=1,
        )
        self.multi_text.pack(fill="both", expand=True, padx=16, pady=4)

        right = ctk.CTkFrame(split, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(right, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.multi_status = pill(
            toolbar, "No search performed yet.", fg=theme.BG_CARD_ALT, tc=theme.TEXT_SECONDARY
        )
        self.multi_status.pack(side="left")
        primary_button(
            toolbar, "Export Results (.xlsx)", self.export_multi_results, width=200
        ).pack(side="right")

        outer, self.multi_tree = build_table(
            right, COLUMNS, EQUIPMENT_WRAPPED_LABELS, EQUIPMENT_COLUMN_WIDTHS
        )
        outer.grid(row=1, column=0, sticky="nsew")

    def do_multi_search(self):
        identifiers = parse_identifiers(self.multi_text.get("1.0", "end"))
        found, missing = self.store.lookup_many(identifiers)

        capped = len(found) > MAX_EQUIPMENT_SEARCH_RESULTS
        found = found[:MAX_EQUIPMENT_SEARCH_RESULTS]
        self.multi_results = found

        for row in self.multi_tree.get_children():
            self.multi_tree.delete(row)
        for i, record in enumerate(found, start=1):
            insert_row(
                self.multi_tree, i - 1,
                values=[i] + [record.get(k, "") for k in EQUIPMENT_KEYS],
            )

        status = f"Found {len(found)} of {len(identifiers)} identifier(s)"
        if capped:
            status += f"  •  capped at {MAX_EQUIPMENT_SEARCH_RESULTS}"
        if missing:
            shown = ", ".join(missing[:8])
            status += f"  •  Not found: {shown}" + (" ..." if len(missing) > 8 else "")
        self.multi_status.configure(text=f"  {status}  ")

    def export_multi_results(self):
        if not self.multi_results:
            messagebox.showwarning("No Data", "Run a search with results before exporting.")
            return
        default = f"Equipment_Search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return
        export_equipment_to_excel(self.multi_results, path)
        notify(self, f"Search results exported to:\n{path}")
