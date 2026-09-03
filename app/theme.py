"""
Shared theme constants: white + baby blue palette.
Import COLORS and FONTS from here so every tab looks consistent.
"""

import customtkinter as ctk

COLORS = {
    "bg": "#FFFFFF",              # main background
    "bg_soft": "#F5F6F9",         # panels / cards / sidebar
    "baby_blue": "#E3F6FC",       # light accent tint (chips, subtle highlights)
    "baby_blue_dark": "#0B8FC4",  # hover / pressed
    "baby_blue_deep": "#12A9E0",  # primary accent - buttons / highlights / active states (sky blue)
    "near_black": "#14171F",      # dark pill / selected-segment background
    "text": "#1F2937",            # main text (dark slate, not pure black)
    "text_muted": "#6B7280",
    "border": "#EAEBEE",
    "success": "#3FBF7F",
    "danger": "#E56B6B",
    "warning": "#F2B84B",
    "white": "#FFFFFF",
    "sidebar_bg": "#F5F6F9",
    "sidebar_active_bg": "#E3F6FC",
}

FONT_FAMILY = "Segoe UI"


def apply_theme():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")


def heading_font(size=20, weight="bold", slant="roman"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight, slant=slant)


def body_font(size=13, weight="normal", slant="roman"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight, slant=slant)
