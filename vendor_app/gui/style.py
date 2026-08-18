"""Dark-theme styling for ttk.Treeview, shared by the Master and Search tabs.

customtkinter does not ship its own table widget, so Treeview is used for
tabular views and manually re-skinned to match the app's dark theme.
"""

from tkinter import ttk

_applied = False


def apply_dark_treeview_style() -> ttk.Style:
    global _applied
    style = ttk.Style()
    if not _applied:
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Dark.Treeview",
            background="#1f1f1f",
            foreground="#e5e5e5",
            fieldbackground="#1f1f1f",
            bordercolor="#1f1f1f",
            borderwidth=0,
            rowheight=26,
        )
        style.map(
            "Dark.Treeview",
            background=[("selected", "#1f6aa5")],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Dark.Treeview.Heading",
            background="#144870",
            foreground="#ffffff",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Dark.Treeview.Heading", background=[("active", "#1f6aa5")])
        _applied = True
    return style
