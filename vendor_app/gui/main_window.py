"""Top-level application window: branded header + three top-level tabs.

The whole application is three things, and the navigation now says so:

    Vendor Master     Records | Search | Change Log
    Equipment Master  Records | Search | Dashboard | Change Log
    Communication     Defective Invoice | Equipment Breakdown

Everything else is a sub-tab inside one of those three, so the top bar
never grows past what a person can scan in one glance. Each top tab (and
each sub-tab inside it) is built lazily on first visit, so start-up stays
fast no matter how much the app grows.
"""

import customtkinter as ctk

from vendor_app.audit import AuditLog, ChangeLog
from vendor_app.config import (
    APP_TITLE, AUDIT_FILE, EQUIPMENT_AUDIT_COLUMNS, EQUIPMENT_AUDIT_FILE, EQUIPMENT_FILE,
)
from vendor_app.data_manager import VendorStore
from vendor_app.equipment import EquipmentStore
from vendor_app.settings import AppSettings
from vendor_app.gui import theme

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

VENDOR_TAB = "Vendor Master"
EQUIPMENT_TAB = "Equipment Master"
COMMUNICATION_TAB = "Communication"


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.configure(fg_color=theme.BG_APP)
        self.title(APP_TITLE)
        self.geometry("1480x900")
        self.minsize(1150, 700)

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
                       for name in (VENDOR_TAB, EQUIPMENT_TAB, COMMUNICATION_TAB)}
        self.vendor_tab = None
        self.equipment_tab = None
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
            content, text="VM", width=36, height=36, corner_radius=8,
            fg_color=theme.ACCENT, text_color=theme.TEXT_ON_ACCENT, font=theme.font(13, "bold"),
        ).pack(side="left", pady=14)

        title_col = ctk.CTkFrame(content, fg_color="transparent")
        title_col.pack(side="left", padx=(12, 0), pady=10)
        ctk.CTkLabel(
            title_col, text="Vendor Master", font=theme.font(16, "bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_col, text="Vendor & Equipment Management System",
            font=theme.small_font(), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")

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

        for tab in (self.vendor_tab, self.equipment_tab):
            if tab is not None:
                tab.refresh_built()
