"""Top-level application window: branded header + tabbed layout.

Tab order follows day-to-day use: look a vendor up first, browse the
directory second, reach for bulk import when onboarding many vendors,
then the equipment master, the outgoing-email flows, and finally the
audit trail when you need to know who changed what and when.

Every tab after the first two is built lazily on first visit - each one
carries tables or large text areas that most sessions never open.
"""

import customtkinter as ctk

from vendor_app.config import APP_TITLE, AUDIT_FILE, EQUIPMENT_FILE
from vendor_app.audit import AuditLog
from vendor_app.data_manager import VendorStore
from vendor_app.equipment import EquipmentStore
from vendor_app.settings import AppSettings
from vendor_app.gui import theme
from vendor_app.gui.audit_tab import AuditLogTab
from vendor_app.gui.communication_tab import CommunicationTab
from vendor_app.gui.equipment_tab import EquipmentTab
from vendor_app.gui.grid_tab import GridTab
from vendor_app.gui.search_tab import SearchTab
from vendor_app.gui.master_tab import MasterTab

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.configure(fg_color=theme.BG_APP)
        self.title(APP_TITLE)
        self.geometry("1440x860")
        self.minsize(1150, 680)

        self.audit_log = AuditLog(AUDIT_FILE)
        self.store = VendorStore(audit_log=self.audit_log)
        self.equipment_store = EquipmentStore(EQUIPMENT_FILE)
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
            self.tabview._segmented_button.configure(font=theme.font(13, "bold"), height=38)
        except Exception:
            pass  # private attribute name may change across customtkinter versions
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        tab_search = self.tabview.add("Search Vendor Details")
        tab_master = self.tabview.add("Master Data Records")
        self._tab_grid = self.tabview.add("Import & Update Grid")
        self._tab_equipment = self.tabview.add("Equipment Master")
        self._tab_comm = self.tabview.add("Communication")
        tab_audit = self.tabview.add("Audit Log")

        self.search_tab = SearchTab(tab_search, self.store, on_data_changed=self.refresh_all)
        self.search_tab.pack(fill="both", expand=True)

        self.master_tab = MasterTab(tab_master, self.store, on_data_changed=self.refresh_all)
        self.master_tab.pack(fill="both", expand=True)

        # The bulk grid is ~1,000 widgets (100 rows x 9 editable cells).
        # Building it eagerly here would freeze the window before it even
        # appears, for a tab most sessions never open. Build it lazily on
        # first visit instead - see _on_tab_changed.
        # Same lazy treatment for the Equipment Master and Communication
        # tabs: both build tables and large text areas most sessions never touch.
        self.grid_tab = None
        self.equipment_tab = None
        self.communication_tab = None
        for placeholder_parent in (self._tab_grid, self._tab_equipment, self._tab_comm):
            ctk.CTkLabel(placeholder_parent, text="", fg_color="transparent").pack()

        self.audit_tab = AuditLogTab(tab_audit, self.audit_log)
        self.audit_tab.pack(fill="both", expand=True)

        self.tabview.configure(command=self._on_tab_changed)
        self.tabview.set("Search Vendor Details")
        self.refresh_all()

    def _on_tab_changed(self):
        name = self.tabview.get()

        if name == "Import & Update Grid" and self.grid_tab is None:
            self._clear(self._tab_grid)
            self.grid_tab = GridTab(self._tab_grid, self.store, on_data_changed=self.refresh_all)
            self.grid_tab.pack(fill="both", expand=True)

        elif name == "Equipment Master" and self.equipment_tab is None:
            self._clear(self._tab_equipment)
            self.equipment_tab = EquipmentTab(
                self._tab_equipment, self.equipment_store, on_data_changed=self.refresh_all
            )
            self.equipment_tab.pack(fill="both", expand=True)

        elif name == "Communication" and self.communication_tab is None:
            self._clear(self._tab_comm)
            self.communication_tab = CommunicationTab(
                self._tab_comm, self.store, self.equipment_store, self.settings,
                on_data_changed=self.refresh_all,
            )
            self.communication_tab.pack(fill="both", expand=True)

    @staticmethod
    def _clear(parent):
        for widget in parent.winfo_children():
            widget.destroy()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, corner_radius=0, height=64)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        accent_strip = ctk.CTkFrame(header, fg_color=theme.ACCENT, height=3, corner_radius=0)
        accent_strip.pack(fill="x", side="bottom")

        content = ctk.CTkFrame(header, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24)

        mark = ctk.CTkLabel(
            content, text="VM", width=36, height=36, corner_radius=8,
            fg_color=theme.ACCENT, text_color=theme.TEXT_ON_ACCENT, font=theme.font(13, "bold"),
        )
        mark.pack(side="left", pady=14)

        title_col = ctk.CTkFrame(content, fg_color="transparent")
        title_col.pack(side="left", padx=(12, 0), pady=10)
        ctk.CTkLabel(
            title_col, text="Vendor Master", font=theme.font(16, "bold"), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_col, text="Vendor Management System", font=theme.small_font(), text_color=theme.TEXT_SECONDARY
        ).pack(anchor="w")

        self.record_badge = ctk.CTkLabel(
            content, text="0 Active Vendors", font=theme.font(12, "bold"),
            fg_color=theme.ACCENT_SOFT, text_color=theme.ACCENT, corner_radius=999, height=30,
        )
        self.record_badge.pack(side="right", pady=17)

    def refresh_all(self):
        """Called after any write (grid save / edit dialog / status change /
        delete) to keep every tab in sync."""
        self.master_tab.refresh()
        self.audit_tab.refresh()
        if self.equipment_tab is not None:
            self.equipment_tab.refresh()
        active = sum(1 for r in self.store.all_records() if r.get("status") == "Active")
        self.record_badge.configure(text=f"  {active} Active Vendor{'s' if active != 1 else ''}  ")
