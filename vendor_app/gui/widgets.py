"""Small reusable, theme-consistent widget factories.

Keeping button/badge styling in one place means every tab picks up the
same primary/secondary/danger look instead of re-declaring colors.
"""

import customtkinter as ctk

from vendor_app.gui import theme


def primary_button(master, text, command, height=34, width=170, **kwargs):
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        width=width,
        height=height,
        corner_radius=6,
        fg_color=theme.ACCENT,
        hover_color=theme.ACCENT_HOVER,
        text_color=theme.TEXT_ON_ACCENT,
        font=theme.font(12, "bold"),
        **kwargs,
    )


def secondary_button(master, text, command, height=34, width=140, **kwargs):
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        width=width,
        height=height,
        corner_radius=6,
        fg_color=theme.BG_CARD_ALT,
        hover_color=theme.BG_HOVER,
        text_color=theme.TEXT_PRIMARY,
        border_width=1,
        border_color=theme.BORDER,
        font=theme.font(12, "bold"),
        **kwargs,
    )


def danger_button(master, text, command, height=34, width=140, **kwargs):
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        width=width,
        height=height,
        corner_radius=6,
        fg_color=theme.DANGER,
        hover_color=theme.DANGER_HOVER,
        text_color=theme.TEXT_ON_ACCENT,
        font=theme.font(12, "bold"),
        **kwargs,
    )


def section_label(master, text, **kwargs):
    """Small uppercase-style section heading used to group form fields."""
    return ctk.CTkLabel(
        master,
        text=text,
        font=theme.label_font(),
        text_color=theme.TEXT_SECONDARY,
        anchor="w",
        **kwargs,
    )


def pill(master, text, fg=theme.ACCENT_SOFT, tc=theme.ACCENT, **kwargs):
    """A rounded status/count badge, e.g. '4 Records' or 'Missing: 2'."""
    return ctk.CTkLabel(
        master,
        text=f"  {text}  ",
        font=theme.font(11, "bold"),
        fg_color=fg,
        text_color=tc,
        corner_radius=999,
        height=26,
        **kwargs,
    )


def divider(master, **kwargs):
    return ctk.CTkFrame(master, fg_color=theme.BORDER, height=1, **kwargs)


def card(master, **kwargs):
    defaults = dict(fg_color=theme.BG_CARD, corner_radius=10, border_width=1, border_color=theme.BORDER_SOFT)
    defaults.update(kwargs)
    return ctk.CTkFrame(master, **defaults)


def wrap_children(frame, reserve=0):
    """Keep a header's text wrapping inside the room it actually has.

    A title block sitting next to action buttons must give way to them, so
    its labels wrap onto a second line instead of demanding width they will
    not get - and instead of being clipped mid-sentence on a small screen.
    """
    def _apply(event):
        width = max(200, event.width - reserve)
        for child in frame.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                child.configure(wraplength=width, justify="left", anchor="w")

    frame.bind("<Configure>", _apply)
    return frame
