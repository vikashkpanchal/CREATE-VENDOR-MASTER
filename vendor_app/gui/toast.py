"""Lightweight, non-blocking toast notifications.

Used for routine confirmations (saved, status changed, exported) so the
user isn't interrupted by a modal dialog for every successful action.
Modal messagebox popups are still used for destructive confirmations and
validation errors, where an explicit acknowledgement is appropriate.
"""

import customtkinter as ctk

from vendor_app.gui import theme

_KIND_COLORS = {
    "success": (theme.SUCCESS_SOFT, theme.SUCCESS),
    "error": (theme.DANGER_SOFT, theme.DANGER),
    "info": (theme.ACCENT_SOFT, theme.ACCENT),
}


class _Toast(ctk.CTkFrame):
    def __init__(self, master, text, kind="success"):
        bg, fg = _KIND_COLORS.get(kind, _KIND_COLORS["info"])
        super().__init__(master, fg_color=bg, corner_radius=8, border_width=1, border_color=fg)
        ctk.CTkLabel(
            self, text=text, text_color=fg, font=theme.font(12, "bold"),
            wraplength=360, justify="left",
        ).pack(padx=16, pady=12)


def show_toast(root, text: str, kind: str = "success", duration_ms: int = 2800):
    """Place a self-dismissing toast in the bottom-right corner of `root`."""
    toast = _Toast(root, text, kind)
    toast.place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")
    toast.lift()
    root.after(duration_ms, toast.destroy)
    return toast


def notify(widget, text: str, kind: str = "success", duration_ms: int = 2800):
    """Convenience wrapper: show a toast anchored to `widget`'s top-level window."""
    root = widget.winfo_toplevel()
    return show_toast(root, text, kind, duration_ms)
