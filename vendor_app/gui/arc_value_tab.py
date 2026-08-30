"""ARC Value Calculation: three columns in, a priced annexure out.

The screen is the workflow, in order down the page:

    1. Input      paste Technical ID, Extension Date and Working Shift
                  straight out of Excel, or import a sheet of them
    2. Calculate  every other column is looked up - equipment master for
                  the codes, rates and validity end; ARC & FO master for
                  the vendor and plant; vendor master for the type
    3. Result     the annexure exactly as it will export, with each
                  contract's subtotal, and a list of anything that could
                  not be priced
    4. Export     the .xlsx

Nothing is stored: the calculation is a read of the three masters as they
stand, so re-running it after a correction upstream simply gives the right
answer.
"""

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vendor_app.arc_value import (
    ArcValueCalculator, LINE_ARC_TOTAL, LINE_GRAND_TOTAL, format_number,
)
from vendor_app.config import (
    ARC_VALUE_COLUMNS, ARC_VALUE_COLUMN_WIDTHS, ARC_VALUE_INPUT_KEYS,
    ARC_VALUE_INPUT_LABELS, ARC_VALUE_WRAPPED_LABELS, OT_HOURS_PER_DAY,
    WORKING_DAYS_PER_MONTH, WORKING_SHIFT_VALUES,
)
from vendor_app.export import export_arc_value_to_excel
from vendor_app.importer import _normalize_header, _read_table
from vendor_app.gui import theme
from vendor_app.gui.editable_table import EditableTable
from vendor_app.gui.paste_grid import PasteGrid
from vendor_app.gui.style import ROW_HEIGHT_CHOICES, ROW_HEIGHT_DEFAULT
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import (
    card, danger_button, pill, primary_button, secondary_button, wrap_children,
)

INPUT_ROWS = 200

# The headers a sheet of input rows might carry, beyond our own labels.
INPUT_ALIASES = {
    "technical id": "technical_id",
    "tech id": "technical_id",
    "technical no": "technical_id",
    "equipment technical id": "technical_id",
    "extension date": "extension_date",
    "revised order calculation upto": "extension_date",
    "revised date": "extension_date",
    "working shift": "working_shift",
    "shift": "working_shift",
}


class ArcValueTab(ctk.CTkFrame):
    def __init__(self, master, equipment_store, arc_store, vendor_store):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self.calculator = ArcValueCalculator(equipment_store, arc_store, vendor_store)
        self.lines = []
        self._build()

    # -------------------------------------------------------------- build --
    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew")
        wrap_children(left)
        ctk.CTkLabel(
            left, text="ARC Value Calculation", font=theme.h1_font(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Give it a Technical ID, an Extension Date and a Working Shift. "
                 "Everything else - ARC No, service codes, descriptions, rates, the "
                 "validity end, the vendor and the plant - is looked up from the "
                 "masters.",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
            anchor="w", justify="left",
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        secondary_button(actions, "Import Input...", self.import_input, width=150).pack(
            side="left", padx=(0, 8)
        )
        danger_button(actions, "Clear Input", self.clear_input, width=120).pack(
            side="left", padx=(0, 8)
        )
        primary_button(actions, "Calculate", self.calculate, width=130).pack(side="left")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self._build_input(body)
        self._build_problems(body)
        self._build_output(body)

    def _build_input(self, parent):
        box = card(parent, fg_color=theme.BG_CARD)
        box.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            box, text="1. INPUT", font=theme.label_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            box,
            text=f"Paste all three columns straight out of Excel (Ctrl+V anywhere in "
                 f"the grid). Working Shift is "
                 f"{' or '.join(WORKING_SHIFT_VALUES)} - it decides the overtime hours "
                 f"a month carries "
                 f"({OT_HOURS_PER_DAY['12']}/day on 12, {OT_HOURS_PER_DAY['24']}/day "
                 f"on 24, over {WORKING_DAYS_PER_MONTH} working days).",
            font=theme.small_font(), text_color=theme.TEXT_MUTED,
            anchor="w", justify="left", wraplength=1000,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        self.grid = PasteGrid(
            box,
            [(key, ARC_VALUE_INPUT_LABELS[key]) for key in ARC_VALUE_INPUT_KEYS],
            widths=[24, 20, 16], rows=INPUT_ROWS,
        )
        self.grid.configure(height=240)
        self.grid.pack(fill="x", padx=16, pady=(0, 16))

    def _build_problems(self, parent):
        self.problem_box = card(parent, fg_color=theme.BG_CARD)
        head = ctk.CTkFrame(self.problem_box, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            head, text="NOT PRICED", font=theme.label_font(), text_color=theme.WARNING,
        ).pack(side="left")
        self.problem_count = pill(head, "0", fg=theme.WARNING_SOFT, tc=theme.WARNING)
        self.problem_count.pack(side="left", padx=10)
        self.problem_text = ctk.CTkTextbox(
            self.problem_box, height=110, fg_color=theme.BG_INPUT,
            text_color=theme.TEXT_SECONDARY, font=theme.font(11),
            border_color=theme.BG_INPUT_BORDER, border_width=1, wrap="word",
        )
        self.problem_text.pack(fill="x", padx=16, pady=(0, 16))
        # Hidden until something actually goes wrong - an empty warning panel
        # on every run trains people to ignore the real one.
        self.problem_box.pack_forget()

    def _build_output(self, parent):
        box = card(parent, fg_color=theme.BG_CARD)
        box.pack(fill="both", expand=True)
        # Held so the problem panel can be re-inserted above it when there is
        # something to say, rather than appended below the annexure.
        self._output_box = box
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 8))
        head.grid_columnconfigure(0, weight=1)
        head.grid_columnconfigure(1, weight=0)

        text = ctk.CTkFrame(head, fg_color="transparent")
        text.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            text, text="2. CALCULATED ANNEXURE", font=theme.label_font(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")
        self.summary = ctk.CTkLabel(
            text, text="Paste your input above, then press Calculate.",
            font=theme.small_font(), text_color=theme.TEXT_MUTED,
            anchor="w", justify="left",
        )
        self.summary.pack(anchor="w", pady=(2, 0))

        controls = ctk.CTkFrame(head, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e", padx=(12, 0))
        ctk.CTkLabel(
            controls, text="Row height:", font=theme.font(10), text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))
        self.row_height_var = ctk.StringVar(value=ROW_HEIGHT_DEFAULT)
        ctk.CTkOptionMenu(
            controls, variable=self.row_height_var,
            values=[name for name, _px in ROW_HEIGHT_CHOICES],
            command=lambda *_: self.table.set_row_height(
                dict(ROW_HEIGHT_CHOICES)[self.row_height_var.get()]
            ),
            width=120, height=28,
            fg_color=theme.BG_INPUT, button_color=theme.BG_CARD_ALT,
            button_hover_color=theme.BG_HOVER, dropdown_fg_color=theme.BG_CARD_ALT,
            font=theme.font(10), dropdown_font=theme.font(10),
        ).pack(side="left", padx=(0, 10))
        primary_button(controls, "Export (.xlsx)", self.export, width=150).pack(side="left")

        self.table = EditableTable(
            box, ARC_VALUE_COLUMNS, ARC_VALUE_WRAPPED_LABELS, ARC_VALUE_COLUMN_WIDTHS,
            height=14,
        )
        self.table.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        # Totals read as totals, the way the banded rows do in the workbook.
        self.table.tree.tag_configure(
            "total", background=theme.BG_CARD_ALT,
            font=(theme.FONT_FAMILY, 11, "bold"),
        )

    # ---------------------------------------------------------- actions --
    def clear_input(self):
        if messagebox.askyesno("Clear Input", "Empty the input grid?"):
            self.grid.clear()

    def import_input(self):
        path = filedialog.askopenfilename(
            title="Import Input Rows",
            filetypes=[("Spreadsheet files", "*.xlsx *.xls *.csv *.tsv"),
                       ("All files", "*.*")],
        )
        if not path:
            return
        try:
            rows = self._read_input(path)
        except Exception as exc:
            messagebox.showerror("Import Failed", f"Could not read that file:\n{exc}")
            return
        if not rows:
            messagebox.showwarning(
                "No Rows Found",
                "No Technical ID / Extension Date / Working Shift columns were found.",
            )
            return
        self.grid.clear()
        for index, row in enumerate(rows[:INPUT_ROWS]):
            for column, key in enumerate(ARC_VALUE_INPUT_KEYS):
                cell = self.grid.cells[index][column]
                cell.delete(0, "end")
                cell.insert(0, row.get(key, ""))
        notify(self, f"{min(len(rows), INPUT_ROWS):,} input row(s) loaded.")
        self.calculate()

    @staticmethod
    def _read_input(path):
        frame = _read_table(path)
        label_to_key = {_normalize_header(v): k
                        for k, v in ARC_VALUE_INPUT_LABELS.items()}
        columns = {}
        for column in frame.columns:
            header = _normalize_header(column)
            key = label_to_key.get(header) or INPUT_ALIASES.get(header)
            if key is None and header.replace(" ", "_") in ARC_VALUE_INPUT_KEYS:
                key = header.replace(" ", "_")
            if key and key not in columns:
                columns[key] = column
        rows = []
        for _, row in frame.iterrows():
            record = {k: str(row.get(c, "")).strip() for k, c in columns.items()}
            if any(record.values()):
                rows.append(record)
        return rows

    def calculate(self):
        rows = self.grid.get_rows()
        if not rows:
            messagebox.showinfo(
                "Nothing to Calculate",
                "Paste at least one Technical ID, Extension Date and Working Shift.",
            )
            return
        self.lines, problems = self.calculator.calculate(rows)
        self._show_problems(problems)
        self._fill_table()

        priced = [l for l in self.lines
                  if l["kind"] not in (LINE_ARC_TOTAL, LINE_GRAND_TOTAL)]
        grand = next((l for l in self.lines if l["kind"] == LINE_GRAND_TOTAL), None)
        contracts = len([l for l in self.lines if l["kind"] == LINE_ARC_TOTAL])
        if grand is None:
            self.summary.configure(text="Nothing could be priced - see NOT PRICED above.")
            return
        self.summary.configure(
            text=f"{len(rows):,} input row(s)  •  {int(grand['eqp_qty']):,} machine(s) "
                 f"priced across {contracts:,} contract(s)  •  {len(priced):,} line(s)  "
                 f"•  total value {format_number(grand['value'])}"
        )

    def _show_problems(self, problems):
        self.problem_text.configure(state="normal")
        self.problem_text.delete("1.0", "end")
        if not problems:
            self.problem_box.pack_forget()
            self.problem_text.configure(state="disabled")
            return
        self.problem_text.insert("1.0", "\n".join(str(p) for p in problems))
        self.problem_text.configure(state="disabled")
        self.problem_count.configure(
            text=f"  {len(problems)} row{'s' if len(problems) != 1 else ''}  "
        )
        self.problem_box.pack(fill="x", pady=(0, 12), before=self._output_box)

    def _fill_table(self):
        self.table.clear()
        for index, line in enumerate(self.lines):
            values = []
            for key in ARC_VALUE_COLUMNS:
                value = line.get(key, "")
                values.append(
                    format_number(value)
                    if key in ("eqp_qty", "qty", "monthly_rate", "value")
                    else value
                )
            row_id = self.table.add_row(index, values)
            if line["kind"] in (LINE_ARC_TOTAL, LINE_GRAND_TOTAL):
                self.table.tree.item(row_id, tags=("total",))
        self.table.tree.configure(height=max(6, min(18, len(self.lines))))

    def export(self):
        if not self.lines:
            messagebox.showinfo("Nothing to Export", "Press Calculate first.")
            return
        default = f"ARC_Value_Calculation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return
        export_arc_value_to_excel(
            self.lines, path, title="Contract Amendment Value Calculation"
        )
        notify(self, f"{len(self.lines):,} row(s) exported to:\n{path}")
