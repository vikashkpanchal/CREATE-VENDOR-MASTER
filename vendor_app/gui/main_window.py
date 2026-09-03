"""Top-level application window: branded header + the top-level tabs.

The whole application is five things, and the navigation says so:

    Vendor Master     Records | Search | Change Log
    Equipment Master  Records | Search | De-mob | Dashboard | Change Log
    ARC & FO Master   Dashboard | Structure | ARC Records | FO Records | Change Log
    ARC Value Calc.   three input columns priced into a contract annexure
    Communication     Defective Invoice | Equipment Breakdown

Everything else is a sub-tab inside one of those, so the top bar
never grows past what a person can scan in one glance. Each top tab (and
each sub-tab inside it) is built lazily on first visit, so start-up stays
fast no matter how much the app grows.
"""

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vendor_app import workbook
from vendor_app.arc import ArcStore
from vendor_app.audit import AuditLog, ChangeLog
from vendor_app.config import (
    APP_TITLE, ARC_AUDIT_COLUMNS, ARC_AUDIT_FILE, AUDIT_FILE, EQUIPMENT_AUDIT_COLUMNS,
    EQUIPMENT_AUDIT_FILE, EQUIPMENT_FILE,
)
from vendor_app.data_manager import VendorStore
from vendor_app.equipment import EquipmentStore
from vendor_app.settings import AppSettings
from vendor_app.gui import theme
from vendor_app.gui.loading import run_with_loading
from vendor_app.gui.toast import notify
from vendor_app.gui.widgets import primary_button, secondary_button

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

VENDOR_TAB = "Vendor Master"
EQUIPMENT_TAB = "Equipment Master"
ARC_TAB = "ARC & FO Master"
ARC_VALUE_TAB = "ARC Value Calculation"
COMMUNICATION_TAB = "Communication"


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.configure(fg_color=theme.BG_APP)
        self.title(APP_TITLE)

        # Never open larger than the screen it is opening on. A fixed
        # 1480x900 window is bigger than a 14" laptop's 1366x768 display, so
        # everything on the right of it - the action buttons, the last filter
        # column - would sit off the edge with no way to reach it. The
        # minimum size is clamped for the same reason: a minsize the screen
        # cannot satisfy is a window that can never be made to fit.
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = min(1480, max(900, screen_w - 80))
        height = min(900, max(620, screen_h - 90))
        self.geometry(
            f"{width}x{height}+{max(0, (screen_w - width) // 2)}"
            f"+{max(0, (screen_h - height) // 3)}"
        )
        self.minsize(min(1150, width), min(700, height))

        # --- stores -------------------------------------------------------
        self.audit_log = AuditLog(AUDIT_FILE)
        self.store = VendorStore(audit_log=self.audit_log)
        self.equipment_log = ChangeLog(EQUIPMENT_AUDIT_FILE, EQUIPMENT_AUDIT_COLUMNS)
        # The equipment store holds a reference to the vendor store so that a
        # vendor referenced by an equipment row is created in the vendor
        # master automatically (code + name).
        self.equipment_store = EquipmentStore(
            EQUIPMENT_FILE, change_log=self.equipment_log, vendor_store=self.store
        )
        # The reverse link, so a vendor cannot be closed while machines are
        # still running under it. Set after construction because the two
        # stores refer to each other.
        self.store.equipment_store = self.equipment_store
        self.arc_log = ChangeLog(ARC_AUDIT_FILE, ARC_AUDIT_COLUMNS)
        # ARCs and FOs name vendors too, so the ARC store seeds the vendor
        # master exactly the way the equipment store does.
        self.arc_store = ArcStore(
            change_log=self.arc_log, vendor_store=self.store
        )
        # A machine's ARC No is read from the contract its FO belongs to, and
        # its Plant Code from that contract's header. Set after construction
        # because the ARC store is built after the equipment store.
        self.equipment_store.arc_store = self.arc_store
        self.settings = AppSettings()

        self._build_header()

        self.tabview = ctk.CTkTabview(
            self,
            fg_color=theme.BG_SURFACE,
            segmented_button_fg_color=theme.BG_CARD_ALT,
            segmented_button_selected_color=theme.ACCENT,
            segmented_button_selected_hover_color=theme.ACCENT_HOVER,
            segmented_button_unselected_color=theme.BG_CARD_ALT,
            segmented_button_unselected_hover_color=theme.BG_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=10,
        )
        try:
            self.tabview._segmented_button.configure(font=theme.font(14, "bold"), height=42)
        except Exception:
            pass  # private attribute name may change across customtkinter versions
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._panes = {name: self.tabview.add(name)
                       for name in (VENDOR_TAB, EQUIPMENT_TAB, ARC_TAB,
                                    ARC_VALUE_TAB, COMMUNICATION_TAB)}
        self.vendor_tab = None
        self.equipment_tab = None
        self.arc_tab = None
        self.arc_value_tab = None
        self.communication_tab = None

        self.tabview.configure(command=self._on_tab_changed)
        self.tabview.set(VENDOR_TAB)
        self._ensure(VENDOR_TAB)
        self.refresh_all()

    # --------------------------------------------------------- lazy tabs --
    def _on_tab_changed(self):
        self._ensure(self.tabview.get())

    def _ensure(self, name):
        if name == VENDOR_TAB and self.vendor_tab is None:
            from vendor_app.gui.master_tabs import VendorMasterTab
            self.vendor_tab = VendorMasterTab(
                self._panes[name], self.store, self.audit_log,
                on_data_changed=self.refresh_all,
            )
            self.vendor_tab.pack(fill="both", expand=True)

        elif name == EQUIPMENT_TAB and self.equipment_tab is None:
            from vendor_app.gui.master_tabs import EquipmentMasterTab
            self.equipment_tab = EquipmentMasterTab(
                self._panes[name], self.equipment_store, self.equipment_log,
                on_data_changed=self.refresh_all,
            )
            self.equipment_tab.pack(fill="both", expand=True)

        elif name == ARC_TAB and self.arc_tab is None:
            from vendor_app.gui.master_tabs import ArcMasterTab
            self.arc_tab = ArcMasterTab(
                self._panes[name], self.arc_store, self.arc_log,
                on_data_changed=self.refresh_all,
            )
            self.arc_tab.pack(fill="both", expand=True)

        elif name == ARC_VALUE_TAB and self.arc_value_tab is None:
            from vendor_app.gui.arc_value_tab import ArcValueTab
            self.arc_value_tab = ArcValueTab(
                self._panes[name], self.equipment_store, self.arc_store, self.store,
            )
            self.arc_value_tab.pack(fill="both", expand=True)

        elif name == COMMUNICATION_TAB and self.communication_tab is None:
            from vendor_app.gui.communication_tab import CommunicationTab
            self.communication_tab = CommunicationTab(
                self._panes[name], self.store, self.equipment_store, self.settings,
                on_data_changed=self.refresh_all,
            )
            self.communication_tab.pack(fill="both", expand=True)

    # ------------------------------------------------------------ header --
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=0, height=64)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkFrame(header, fg_color=theme.ACCENT, height=3, corner_radius=0).pack(
            fill="x", side="bottom"
        )

        content = ctk.CTkFrame(header, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24)

        ctk.CTkLabel(
            content, text="P&M", width=48, height=36, corner_radius=8,
            fg_color=theme.ACCENT, text_color=theme.TEXT_ON_ACCENT, font=theme.font(13, "bold"),
        ).pack(side="left", pady=14)

        title_col = ctk.CTkFrame(content, fg_color="transparent")
        title_col.pack(side="left", padx=(12, 0), pady=10)
        ctk.CTkLabel(
            title_col, text="P&M Master", font=theme.font(16, "bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_col, text="Vendor, Equipment & Contract Management System",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")

        # One click out, one click in - for every master at once. They live in
        # the header rather than on a tab because they are about the whole
        # dataset, not any one master, and the header is on screen from the
        # moment the app opens.
        backup = ctk.CTkFrame(content, fg_color="transparent")
        backup.pack(side="right", padx=(16, 0), pady=15)
        secondary_button(
            backup, "Import All Data...", self.import_all_data, width=160, height=32,
        ).pack(side="left", padx=(0, 8))
        primary_button(
            backup, "Export All Data", self.export_all_data, width=150, height=32,
        ).pack(side="left")

        badges = ctk.CTkFrame(content, fg_color="transparent")
        badges.pack(side="right", pady=17)
        self.equipment_badge = ctk.CTkLabel(
            badges, text="", font=theme.font(12, "bold"),
            fg_color=theme.BG_CARD_ALT, text_color=theme.TEXT_SECONDARY,
            corner_radius=999, height=30,
        )
        self.equipment_badge.pack(side="right", padx=(8, 0))
        self.record_badge = ctk.CTkLabel(
            badges, text="", font=theme.font(12, "bold"),
            fg_color=theme.ACCENT_SOFT, text_color=theme.ACCENT, corner_radius=999, height=30,
        )
        self.record_badge.pack(side="right")
        self.arc_badge = ctk.CTkLabel(
            badges, text="", font=theme.font(12, "bold"),
            fg_color=theme.BG_CARD_ALT, text_color=theme.TEXT_SECONDARY,
            corner_radius=999, height=30,
        )
        self.arc_badge.pack(side="right", padx=(8, 0))

    # ------------------------------------------------- all-master backup --
    def export_all_data(self):
        """Every master into one workbook - a sheet each, arrangement as is."""
        default = f"PM_Master_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not path:
            return

        def work(report):
            report(message="Writing every master...")
            return workbook.export_all(
                self.store, self.equipment_store, self.arc_store, path
            )

        def done(counts, error):
            if error is not None:
                messagebox.showerror("Export Failed", f"Could not write that file:\n{error}")
                return
            notify(self, "Exported to:\n" + path + "\n\n" + "\n".join(
                f"{sheet}: {rows:,} row(s)" for sheet, rows in counts.items()
            ))

        run_with_loading(
            self, "Exporting all data", work, on_done=done,
            subtitle="Vendor, Equipment, ARC and FO masters into a single workbook.",
        )

    def import_all_data(self):
        """Read a workbook of masters back in - one sheet per master."""
        path = filedialog.askopenfilename(
            title="Import All Data",
            filetypes=[("Excel Workbook", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Import All Data",
            "Load every master sheet this file carries?\n\n"
            "Rows are merged by their keys the same way a single-master import "
            "is: a blank cell never overwrites what is already stored, and "
            "nothing is deleted.",
        ):
            return

        def work(report):
            return workbook.import_all(
                path, self.store, self.equipment_store, self.arc_store,
                progress=lambda done, total, message="": report(done, total, message),
            )

        def done(results, error):
            if error is not None:
                messagebox.showerror("Import Failed", f"Could not read that file:\n{error}")
                return
            self.refresh_all()
            summary = workbook.summarise(results)
            problems = [
                f"{workbook.LABELS[kind]} row {row}: {message}"
                for kind in workbook.IMPORT_ORDER
                for row, message in (results.get(kind) or {}).get("errors", [])[:10]
            ]
            if problems:
                messagebox.showwarning(
                    "Imported with Errors",
                    summary + "\n\nRows skipped:\n" + "\n".join(problems[:20]),
                )
            else:
                notify(self, summary)

        run_with_loading(
            self, "Importing all data", work, on_done=done,
            subtitle="Vendor, Equipment, ARC and FO masters from a single workbook.",
        )

    # ----------------------------------------------------------- refresh --
    def refresh_all(self):
        """Keep every built view in step after any write, wherever it came from -
        an equipment import can create vendors, so both masters can move at once."""
        active = sum(1 for r in self.store.all_records() if r.get("status") == "Active")
        self.record_badge.configure(
            text=f"  {active:,} Active Vendor{'s' if active != 1 else ''}  "
        )
        running = len(self.equipment_store.running_records())
        self.equipment_badge.configure(text=f"  {running:,} Running Equipment  ")
        # Contracts, not rows: Table 1 carries one row per item, so counting
        # records would report a five-item contract as five ARCs.
        arcs = len(self.arc_store.documents())
        self.arc_badge.configure(text=f"  {arcs:,} ARC{'s' if arcs != 1 else ''}  ")

        for tab in (self.vendor_tab, self.equipment_tab, self.arc_tab):
            if tab is not None:
                tab.refresh_built()
