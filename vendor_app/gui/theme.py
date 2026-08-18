"""Central design system: color tokens, typography and spacing.

A single source of truth so every tab/dialog reads as one consistent,
data-forward, dark analytical UI (cobalt accent on charcoal surfaces,
clear typographic hierarchy, generous whitespace) rather than a pile of
ad-hoc widget colors.
"""

import customtkinter as ctk

# ---------------------------------------------------------------- surfaces --
BG_APP = "#0c0f14"          # window background
BG_SURFACE = "#12161d"      # tab body background
BG_CARD = "#181d26"         # cards / table containers
BG_CARD_ALT = "#1f2530"     # nested cards, table headers
BG_INPUT = "#212733"        # entry/textbox fields
BG_INPUT_BORDER = "#333c4a"
BG_ROW_ALT = "#1b212b"      # zebra stripe on tables
BG_HOVER = "#262d3a"

# -------------------------------------------------------------------- brand --
ACCENT = "#3273f6"          # primary cobalt blue
ACCENT_HOVER = "#255ed1"
ACCENT_SOFT = "#182a4d"     # accent tint background for badges/pills
ACCENT_BORDER = "#2c4a86"

# ---------------------------------------------------------------- semantic --
SUCCESS = "#34b871"
SUCCESS_SOFT = "#132a1e"
WARNING = "#e0ac48"
WARNING_SOFT = "#302108"
DANGER = "#e5626c"
DANGER_HOVER = "#c94a54"
DANGER_SOFT = "#331419"

# ---------------------------------------------------------------------- text --
TEXT_PRIMARY = "#f2f4f8"
TEXT_SECONDARY = "#9aa7ba"
TEXT_MUTED = "#69748a"
TEXT_ON_ACCENT = "#ffffff"

# ------------------------------------------------------------------ borders --
BORDER = "#293040"
BORDER_SOFT = "#1e2430"

# ------------------------------------------------------------------- fonts --
FONT_FAMILY = "Segoe UI"


def font(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


# Named typographic scale, created lazily (needs a Tk root to exist first).
def display_font():
    return font(22, "bold")


def h1_font():
    return font(17, "bold")


def h2_font():
    return font(14, "bold")


def body_font():
    return font(12, "normal")


def small_font():
    return font(11, "normal")


def label_font():
    return font(11, "bold")


def mono_font(size: int = 12):
    return ctk.CTkFont(family="Consolas", size=size)
