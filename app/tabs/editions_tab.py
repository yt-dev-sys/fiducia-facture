"""
Editions tab: 3 printable statements (Etat des ventes, Etat des paiements, Etat des créances).
"""

from datetime import date
from tkinter import filedialog
import customtkinter as ctk
from app import database as db
from app.theme import COLORS, body_font
from app.widgets import section_title, primary_button, secondary_button, MessageDialog, StatCard
from app.format_utils import MONTHS_FR, format_price_dh
from app import reports
from app.app_logger import log_exception


class YearMonthDialog(ctk.CTkToplevel):
    """Small dialog asking for a year + month, then triggers a save-as PDF export."""

    def __init__(self, master, title, on_confirm):
        super().__init__(master)
        self.title(title)
        self.geometry("320x260")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()
        self.on_confirm = on_confirm

        today = date.today()

        ctk.CTkLabel(self, text=title, font=body_font(14, "bold"),
                     text_color=COLORS["text"]).pack(pady=(20, 16))

        ctk.CTkLabel(self, text="Année", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"], anchor="w").pack(fill="x", padx=24)
        self.year_var = ctk.StringVar(value=str(today.year))
        ctk.CTkEntry(self, textvariable=self.year_var, width=120,
                     fg_color=COLORS["bg_soft"], border_color=COLORS["border"],
                     text_color=COLORS["text"], corner_radius=12).pack(padx=24, pady=(4, 12), anchor="w")

        ctk.CTkLabel(self, text="Mois", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"], anchor="w").pack(fill="x", padx=24)
        self.month_var = ctk.StringVar(value=MONTHS_FR[today.month - 1])
        ctk.CTkOptionMenu(self, values=MONTHS_FR, variable=self.month_var, width=220,
                          fg_color=COLORS["bg_soft"], button_color=COLORS["baby_blue_deep"],
                          button_hover_color=COLORS["baby_blue_dark"], text_color=COLORS["text"],
                          corner_radius=12).pack(padx=24, pady=(4, 20), anchor="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack()
        secondary_button(btn_frame, "Annuler", self.destroy, width=100).pack(side="left", padx=6)
        primary_button(btn_frame, "Imprimer", self._confirm, width=120).pack(side="left", padx=6)

    def _confirm(self):
        try:
            year = int(self.year_var.get().strip())
            if year < 2000 or year > 2100:
                raise ValueError
        except ValueError:
            MessageDialog(self, "Erreur", "Veuillez entrer une année valide (ex: 2026).", is_error=True)
            return
        month = int(self.month_var.get().split(" - ")[0])
        self.destroy()
        self.on_confirm(year, month)


class EditionsTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])

        section_title(self, "Editions").pack(anchor="w", padx=24, pady=(24, 16))

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=24, pady=(0, 24), anchor="n")
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_columnconfigure(1, weight=1)
        cards_frame.grid_columnconfigure(2, weight=1)

        self.ventes_card = StatCard(cards_frame, "Etat des ventes", COLORS["baby_blue_deep"],
                                     command=self.open_etat_des_ventes, value_font_size=20)
        self.ventes_card.grid(row=0, column=0, sticky="ew", padx=(0, 16))

        self.paiement_card = StatCard(cards_frame, "Etat des paiement", COLORS["success"],
                                       command=self.open_etat_des_paiements, value_font_size=20)
        self.paiement_card.grid(row=0, column=1, sticky="ew", padx=16)

        self.creances_card = StatCard(cards_frame, "Etat des creances", COLORS["danger"],
                                       command=self.open_etat_des_creances, value_font_size=20)
        self.creances_card.grid(row=0, column=2, sticky="ew", padx=(16, 0))

        self.refresh()

    def refresh(self):
        self.ventes_card.set_value(format_price_dh(reports.sum_all_ventes()))
        self.paiement_card.set_value(format_price_dh(reports.sum_all_paiements()))
        self.creances_card.set_value(format_price_dh(reports.sum_all_creances()))

    # ---------------- Etat des ventes ----------------
    def open_etat_des_ventes(self):
        YearMonthDialog(self, "Etat des ventes", self._export_etat_des_ventes)

    def _export_etat_des_ventes(self, year, month):
        save_path = self._ask_save_path(f"Etat_des_ventes_{year}-{month:02d}.pdf")
        if not save_path:
            return
        try:
            reports.generate_etat_des_ventes(year, month, save_path)
        except Exception as e:
            log_exception("Génération PDF Etat des ventes", e)
            MessageDialog(self, "Erreur PDF", f"Impossible de générer le PDF : {e}", is_error=True)

    # ---------------- Etat des paiements ----------------
    def open_etat_des_paiements(self):
        YearMonthDialog(self, "Etat des paiement", self._export_etat_des_paiements)

    def _export_etat_des_paiements(self, year, month):
        save_path = self._ask_save_path(f"Etat_des_paiements_{year}-{month:02d}.pdf")
        if not save_path:
            return
        try:
            reports.generate_etat_des_paiements(year, month, save_path)
        except Exception as e:
            log_exception("Génération PDF Etat des paiements", e)
            MessageDialog(self, "Erreur PDF", f"Impossible de générer le PDF : {e}", is_error=True)

    # ---------------- Etat des creances ----------------
    def open_etat_des_creances(self):
        save_path = self._ask_save_path("Etat_des_creances.pdf")
        if not save_path:
            return
        try:
            reports.generate_etat_des_creances(save_path)
        except Exception as e:
            log_exception("Génération PDF Etat des créances", e)
            MessageDialog(self, "Erreur PDF", f"Impossible de générer le PDF : {e}", is_error=True)

    def _ask_save_path(self, default_name):
        return filedialog.asksaveasfilename(
            parent=self,
            title="Enregistrer le PDF",
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("Fichier PDF", "*.pdf")],
        )
