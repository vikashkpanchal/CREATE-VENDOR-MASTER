"""The master-data top-level tabs, each with its own sub-tabs.

Vendor Master      : Records | Search | Change Log
Equipment Master   : Records | Search | De-mob | Dashboard | Change Log
ARC & FO Master    : Dashboard | Structure | ARC Records | FO Records | Change Log

Sub-tabs are built lazily on first visit - each carries a table or chart
canvas most sessions never open.
"""

import customtkinter as ctk

from vendor_app.config import (
    EQUIPMENT_AUDIT_COLUMNS, EQUIPMENT_AUDIT_COLUMN_WIDTHS, EQUIPMENT_AUDIT_WRAPPED_LABELS,
)
from vendor_app.gui import theme


class _SubTabHost(ctk.CTkFrame):
    """A tabview whose panes are constructed on first visit."""

    def __init__(self, master, builders, default=None):
        super().__init__(master, fg_color=theme.BG_SURFACE)
        self._builders = dict(builders)
        self._built = {}
        self._panes = {}

        self.tabs = ctk.CTkTabview(
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
            self.tabs._segmented_button.configure(font=theme.font(12, "bold"), height=34)
        except Exception:
            pass
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        for name in self._builders:
            self._panes[name] = self.tabs.add(name)

        self.tabs.configure(command=self._on_change)
        first = default or next(iter(self._builders))
        self.tabs.set(first)
        self._ensure(first)

    def _on_change(self):
        self._ensure(self.tabs.get())

    def _ensure(self, name):
        if name in self._built or name not in self._builders:
            return
        widget = self._builders[name](self._panes[name])
        widget.pack(fill="both", expand=True)
        self._built[name] = widget

    def built(self, name):
        return self._built.get(name)

    def refresh_built(self):
        for widget in self._built.values():
            if hasattr(widget, "refresh"):
                widget.refresh()


class VendorMasterTab(_SubTabHost):
    def __init__(self, master, store, audit_log, on_data_changed=None):
        from vendor_app.gui.audit_tab import AuditLogTab
        from vendor_app.gui.master_screens import VendorRecordsScreen
        from vendor_app.gui.search_tab import SearchTab

        self.store = store
        self.audit_log = audit_log
        super().__init__(master, {
            "Records": lambda parent: VendorRecordsScreen(
                parent, store, on_data_changed=on_data_changed
            ),
            "Search": lambda parent: SearchTab(
                parent, store, on_data_changed=on_data_changed
            ),
            "Change Log": lambda parent: AuditLogTab(
                parent, audit_log, title="Vendor Change Log",
                subtitle="Every add, edit, status change and delete made to the vendor master.",
            ),
        })


class EquipmentMasterTab(_SubTabHost):
    def __init__(self, master, equipment_store, change_log, on_data_changed=None):
        from vendor_app.gui.audit_tab import AuditLogTab
        from vendor_app.gui.dashboard_tab import DashboardTab
        from vendor_app.gui.demob_tab import DemobTab
        from vendor_app.gui.equipment_tab import EquipmentSearchScreen
        from vendor_app.gui.master_screens import EquipmentRecordsScreen

        self.store = equipment_store
        self.change_log = change_log
        super().__init__(master, {
            "Records": lambda parent: EquipmentRecordsScreen(
                parent, equipment_store, on_data_changed=on_data_changed
            ),
            "Search": lambda parent: EquipmentSearchScreen(parent, equipment_store),
            "De-mob Equipment": lambda parent: DemobTab(
                parent, equipment_store, on_data_changed=on_data_changed
            ),
            "Dashboard": lambda parent: DashboardTab(parent, equipment_store),
            "Change Log": lambda parent: AuditLogTab(
                parent, change_log,
                columns=EQUIPMENT_AUDIT_COLUMNS,
                headers=EQUIPMENT_AUDIT_WRAPPED_LABELS,
                widths=EQUIPMENT_AUDIT_COLUMN_WIDTHS,
                title="Equipment Change Log",
                subtitle="Every add, edit and delete made to the equipment master, "
                         "including vendors it auto-created.",
            ),
        })


class ArcMasterTab(_SubTabHost):
    """Dashboard | Structure | ARC Records | FO Records | Change Log.

    The dashboard comes first deliberately: it answers the questions the data
    is kept for - what is expiring, what has no order against it, where the
    ARC and FO values diverge. Structure shows the hierarchy those figures
    roll up through, and the flat grids are how the underlying rows are
    imported and edited: ARC Records is Table 1 (ME3L), FO Records is Table 2
    (framework tracking), each at the line-item granularity its report uses.
    """

    def __init__(self, master, arc_store, change_log, on_data_changed=None):
        from vendor_app.config import (
            ARC_AUDIT_COLUMNS, ARC_AUDIT_COLUMN_WIDTHS, ARC_AUDIT_WRAPPED_LABELS,
        )
        from vendor_app.gui.audit_tab import AuditLogTab
        from vendor_app.gui.arc_screens import ArcRecordsScreen, FoRecordsScreen
        from vendor_app.gui.arc_dashboard_tab import ArcDashboardTab
        from vendor_app.gui.arc_structure_tab import ArcStructureTab

        self.store = arc_store
        self.change_log = change_log
        super().__init__(master, {
            "Dashboard": lambda parent: ArcDashboardTab(parent, arc_store),
            "Structure": lambda parent: ArcStructureTab(parent, arc_store),
            "ARC Records": lambda parent: ArcRecordsScreen(
                parent, arc_store, on_data_changed=on_data_changed
            ),
            "FO Records": lambda parent: FoRecordsScreen(
                parent, arc_store, on_data_changed=on_data_changed
            ),
            "Change Log": lambda parent: AuditLogTab(
                parent, change_log,
                columns=ARC_AUDIT_COLUMNS,
                headers=ARC_AUDIT_WRAPPED_LABELS,
                widths=ARC_AUDIT_COLUMN_WIDTHS,
                title="ARC & FO Change Log",
                subtitle="Every amendment, add, edit and delete across contracts, "
                         "their items and their frame orders - all filed against "
                         "the purchasing document.",
            ),
        })
