"""
Reusable UI building blocks shared across tabs.
"""

import customtkinter as ctk
from app.theme import COLORS, heading_font, body_font


class Table(ctk.CTkScrollableFrame):
    """A simple scrollable table: header row + data rows with per-row action buttons."""

    def __init__(self, master, columns, on_row_select=None, **kwargs):
        super().__init__(master, fg_color=COLORS["white"], **kwargs)
        self.columns = columns  # list of (key, label, weight)
        self.on_row_select = on_row_select
        self.rows_data = []
        self.row_widgets = []

        for i, (_, _, weight) in enumerate(self.columns):
            self.grid_columnconfigure(i, weight=weight)

        self._build_header()

    def _build_header(self):
        for i, (_, label, _) in enumerate(self.columns):
            lbl = ctk.CTkLabel(
                self, text=label, font=body_font(13, "bold"),
                text_color=COLORS["text"], anchor="w"
            )
            lbl.grid(row=0, column=i, sticky="w", padx=10, pady=(4, 8))

    def set_rows(self, rows, row_builder):
        """rows: list of dicts. row_builder(frame_row_index, row_dict, row_index) builds cell widgets."""
        for w in self.row_widgets:
            w.destroy()
        self.row_widgets = []
        self.rows_data = rows

        for idx, row in enumerate(rows):
            grid_row = idx + 1
            bg = COLORS["bg_soft"] if idx % 2 == 0 else COLORS["white"]
            row_frame_widgets = row_builder(self, grid_row, row, idx)
            self.row_widgets.extend(row_frame_widgets)


def labeled_entry(master, label_text, textvariable=None, width=280, show=None):
    frame = ctk.CTkFrame(master, fg_color="transparent")
    lbl = ctk.CTkLabel(frame, text=label_text, font=body_font(12, "bold"), text_color=COLORS["text_muted"], anchor="w")
    lbl.pack(anchor="w", pady=(0, 2))
    entry = ctk.CTkEntry(
        frame, textvariable=textvariable, width=width, show=show,
        fg_color=COLORS["bg_soft"], border_color=COLORS["border"],
        text_color=COLORS["text"], corner_radius=12
    )
    entry.pack(anchor="w", fill="x")
    return frame, entry


def bind_digits_only(var, max_len=15):
    """Restricts a StringVar to digits only, capped at max_len characters.
    Used for ICE fields (Moroccan ICE is always exactly 15 digits)."""
    def _sanitize(*_args):
        current = var.get()
        filtered = "".join(ch for ch in current if ch.isdigit())[:max_len]
        if filtered != current:
            var.set(filtered)
    var.trace_add("write", _sanitize)
    return var


def section_title(master, text):
    return ctk.CTkLabel(master, text=text, font=heading_font(18), text_color=COLORS["text"], anchor="w")


class StatCard(ctk.CTkFrame):
    """A single stat card: solid colored background, label top-left, big centered white number.
    Fixed medium height, stretches to fill available horizontal space. Optionally clickable."""

    def __init__(self, master, label, bg_color, command=None, value_font_size=32):
        super().__init__(master, fg_color=bg_color, corner_radius=20, height=140,
                          cursor="hand2" if command else "arrow")
        self.pack_propagate(False)
        self.grid_propagate(False)

        self.label_widget = ctk.CTkLabel(self, text=label, font=body_font(13, "bold"),
                                          text_color=COLORS["white"], anchor="w")
        self.label_widget.pack(anchor="w", padx=18, pady=(16, 0))

        self.value_label = ctk.CTkLabel(self, text="0", font=heading_font(value_font_size, "bold"),
                                         text_color=COLORS["white"])
        self.value_label.pack(expand=True, pady=(4, 18))

        if command:
            for widget in (self, self.label_widget, self.value_label):
                widget.bind("<Button-1>", lambda e: command())

    def set_value(self, value):
        self.value_label.configure(text=str(value))


def avatar_badge(master, text, bg_color=None, size=36, font_size=13):
    """A small circular badge with an initial/short text centered in it — e.g. a
    client's first initial. Returns the CTkFrame (place/pack it like any widget)."""
    bg_color = bg_color or COLORS["baby_blue_deep"]
    circle = ctk.CTkFrame(master, width=size, height=size, corner_radius=size // 2, fg_color=bg_color)
    circle.pack_propagate(False)
    ctk.CTkLabel(circle, text=text[:1].upper() if text else "?", font=body_font(font_size, "bold"),
                 text_color=COLORS["white"]).pack(expand=True)
    return circle


def status_pill(master, text, kind="neutral"):
    """A small rounded status chip — kind: 'success' (green), 'danger' (red/amber), or 'neutral' (gray)."""
    palette = {
        "success": (COLORS["success"], COLORS["white"]),
        "danger": (COLORS["danger"], COLORS["white"]),
        "neutral": (COLORS["bg_soft"], COLORS["text_muted"]),
    }
    bg, fg = palette.get(kind, palette["neutral"])
    pill = ctk.CTkFrame(master, fg_color=bg, corner_radius=999, height=26)
    pill.pack_propagate(False)
    ctk.CTkLabel(pill, text=text, font=body_font(11, "bold"), text_color=fg).pack(
        padx=12, pady=2)
    return pill


class SegmentedToggle(ctk.CTkFrame):
    """A pill-shaped segmented control: dark selected segment, light unselected ones,
    sharing one underlying value. Mirrors a native mobile-style filter toggle."""

    def __init__(self, master, options, value, on_change=None):
        super().__init__(master, fg_color=COLORS["bg_soft"], corner_radius=999)
        self.options = options
        self.value = value
        self.on_change = on_change
        self.buttons = {}
        self._build()

    def _build(self):
        for w in self.winfo_children():
            w.destroy()
        self.buttons = {}
        for opt in self.options:
            selected = opt == self.value
            btn = ctk.CTkButton(
                self, text=opt, width=1, height=30, corner_radius=999,
                fg_color=COLORS["near_black"] if selected else "transparent",
                hover_color=COLORS["near_black"] if selected else COLORS["border"],
                text_color=COLORS["white"] if selected else COLORS["text_muted"],
                font=body_font(12, "bold" if selected else "normal"),
                command=lambda o=opt: self._select(o)
            )
            btn.pack(side="left", padx=3, pady=3)
            self.buttons[opt] = btn

    def _select(self, opt):
        if opt == self.value:
            return
        self.value = opt
        self._build()
        if self.on_change:
            self.on_change(opt)

    def get(self):
        return self.value


def primary_button(master, text, command, width=160):
    return ctk.CTkButton(
        master, text=text, command=command, width=width,
        fg_color=COLORS["baby_blue_deep"], hover_color=COLORS["baby_blue_dark"],
        text_color=COLORS["white"], corner_radius=14, font=body_font(13, "bold")
    )


def secondary_button(master, text, command, width=120):
    return ctk.CTkButton(
        master, text=text, command=command, width=width,
        fg_color=COLORS["white"], hover_color=COLORS["bg_soft"],
        text_color=COLORS["text"], corner_radius=14, font=body_font(13),
        border_width=1, border_color=COLORS["border"]
    )


def icon_button(master, icon, command, active=False, size=32):
    """A small square icon-only button - used for the star/watchlist toggle."""
    return ctk.CTkButton(
        master, text=icon, command=command, width=size, height=size,
        fg_color=COLORS["baby_blue"] if active else "transparent",
        hover_color=COLORS["bg_soft"],
        text_color=COLORS["warning"] if active else COLORS["text_muted"],
        corner_radius=10, font=body_font(15),
        border_width=1 if active else 0, border_color=COLORS["border"]
    )


def danger_button(master, text, command, width=100):
    return ctk.CTkButton(
        master, text=text, command=command, width=width,
        fg_color=COLORS["danger"], hover_color="#C94F4F",
        text_color=COLORS["white"], corner_radius=14, font=body_font(12),
        border_width=0
    )


class ConfirmDialog(ctk.CTkToplevel):
    def __init__(self, master, message, on_confirm):
        super().__init__(master)
        self.title("Confirmer")
        self.geometry("360x160")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()

        lbl = ctk.CTkLabel(self, text=message, font=body_font(13), text_color=COLORS["text"], wraplength=320, justify="left")
        lbl.pack(padx=20, pady=(24, 16), fill="x")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, 16))

        def confirm_and_close():
            self.destroy()
            on_confirm()

        secondary_button(btn_frame, "Annuler", self.destroy, width=110).pack(side="left", padx=8)
        danger_button(btn_frame, "Confirmer", confirm_and_close, width=110).pack(side="left", padx=8)


def bind_search_debounce(entry_widget, callback, delay_ms=300):
    """Bind a search entry so the callback fires only after the user stops typing
    for `delay_ms` milliseconds. Prevents a DB query on every single keystroke."""
    _after_id = [None]

    def on_key(_event=None):
        if _after_id[0] is not None:
            entry_widget.after_cancel(_after_id[0])
        _after_id[0] = entry_widget.after(delay_ms, callback)

    entry_widget.bind("<KeyRelease>", on_key)


class MessageDialog(ctk.CTkToplevel):
    def __init__(self, master, title, message, is_error=False):
        super().__init__(master)
        self.title(title)
        self.geometry("380x160")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()

        color = COLORS["danger"] if is_error else COLORS["text"]
        lbl = ctk.CTkLabel(self, text=message, font=body_font(13), text_color=color, wraplength=340, justify="left")
        lbl.pack(padx=20, pady=(24, 16), fill="both", expand=True)

        primary_button(self, "OK", self.destroy, width=100).pack(pady=(0, 16))
