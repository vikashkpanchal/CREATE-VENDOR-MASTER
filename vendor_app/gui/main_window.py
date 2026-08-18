"""Top-level application window: dark theme + 3-tab layout."""

import customtkinter as ctk

from vendor_app.config import APP_TITLE
from vendor_app.data_manager import VendorStore
from vendor_app.gui.grid_tab import GridTab
from vendor_app.gui.search_tab import SearchTab
from vendor_app.gui.master_tab import MasterTab

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1400x820")
        self.minsize(1100, 650)

        self.store = VendorStore()

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        tab_grid = self.tabview.add("Import & Update Grid")
        tab_search = self.tabview.add("Search Vendor Details")
        tab_master = self.tabview.add("Master Data Records")

        self.grid_tab = GridTab(tab_grid, self.store, on_data_changed=self.refresh_all)
        self.grid_tab.pack(fill="both", expand=True)

        self.search_tab = SearchTab(tab_search, self.store, on_data_changed=self.refresh_all)
        self.search_tab.pack(fill="both", expand=True)

        self.master_tab = MasterTab(tab_master, self.store, on_data_changed=self.refresh_all)
        self.master_tab.pack(fill="both", expand=True)

    def refresh_all(self):
        """Called after any write (grid save / edit dialog) to keep views in sync."""
        self.master_tab.refresh()
