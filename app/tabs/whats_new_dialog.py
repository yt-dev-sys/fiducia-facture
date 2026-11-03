import customtkinter as ctk
from app.theme import COLORS, body_font, heading_font
from app.widgets import primary_button
from app.version import APP_VERSION


class WhatsNewDialog(ctk.CTkToplevel):
    """Read-only "Nouveautés" window with the text from app/assets/whats_new.txt."""

    def __init__(self, master, title, body):
        super().__init__(master)
        self.title("Nouveautés")
        self.geometry("520x540")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text=f"Version {APP_VERSION}", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"], anchor="w").pack(fill="x", padx=28, pady=(24, 0))
        ctk.CTkLabel(self, text=title, font=heading_font(20), text_color=COLORS["text"],
                     anchor="w", justify="left", wraplength=464).pack(fill="x", padx=28, pady=(2, 12))

        box = ctk.CTkTextbox(self, fg_color=COLORS["bg_soft"], text_color=COLORS["text"],
                             font=body_font(13), corner_radius=12, wrap="word", border_width=0)
        box.pack(fill="both", expand=True, padx=28, pady=(0, 14))
        box.insert("1.0", body)
        box.configure(state="disabled")

        primary_button(self, "Compris", self.destroy, width=140).pack(pady=(0, 22))
        self.after(50, self.focus_force)
