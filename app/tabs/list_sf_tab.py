from datetime import date
import customtkinter as ctk
from app import database as db
from app.theme import COLORS, body_font
from app.format_utils import format_price_dh, MONTHS_FR
from app.widgets import (
    section_title, primary_button, secondary_button, danger_button, MessageDialog,
    ConfirmDialog, SegmentedToggle, status_pill, avatar_badge, icon_button
)
from app.tabs.factures_tab import InvoiceDetailDialog, InvoiceFormDialog
from app.app_logger import log_exception
from tkinter import filedialog
from app import pdf_export


class ListSFTab(ctk.CTkFrame):
    """List SF: draft factures (no number yet). Creation happens here; a draft only
    becomes an official, numbered facture (and moves to the Factures tab) once the
    user clicks "Facturer"."""

    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        today = date.today()
        self.search_var = ctk.StringVar()
        self.status_filter = ctk.StringVar(value="Toutes")
        self.year_filter = ctk.StringVar(value=str(today.year))
        self.month_filter = ctk.StringVar(value=MONTHS_FR[today.month - 1])
        self.current_invoices = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))
        section_title(header, "List SF").pack(side="left")
        icon_button(header, "🖨", self.print_list_pdf, size=40).pack(side="right", padx=(8, 0))
        primary_button(header, "+ Nouvelle facture", self.open_new_dialog, width=180).pack(side="right")

        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=24, pady=(0, 14))
        search_entry = ctk.CTkEntry(
            filter_frame, textvariable=self.search_var, placeholder_text="Rechercher (client)...",
            width=240, fg_color=COLORS["bg_soft"], border_color=COLORS["border"], corner_radius=12
        )
        search_entry.pack(side="left", padx=(0, 10))
        search_entry.bind("<KeyRelease>", lambda e: self.refresh())

        self.status_toggle = SegmentedToggle(
            filter_frame, ["Toutes", "Payées", "À facturer"], self.status_filter.get(),
            on_change=self._on_status_change
        )
        self.status_toggle.pack(side="left", padx=(0, 10))

        year_entry = ctk.CTkEntry(
            filter_frame, textvariable=self.year_filter, placeholder_text="Année", width=90,
            fg_color=COLORS["bg_soft"], border_color=COLORS["border"], corner_radius=12
        )
        year_entry.pack(side="left", padx=(0, 10))
        year_entry.bind("<KeyRelease>", lambda e: self.refresh())

        ctk.CTkOptionMenu(
            filter_frame, values=["Tous mois"] + MONTHS_FR, variable=self.month_filter,
            command=lambda _: self.refresh(), fg_color=COLORS["bg_soft"],
            button_color=COLORS["baby_blue_deep"], button_hover_color=COLORS["baby_blue_dark"],
            text_color=COLORS["text"], dropdown_fg_color=COLORS["white"], width=150, corner_radius=12
        ).pack(side="left")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"], corner_radius=16)
        self.list_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        for i, w in enumerate([3, 2, 2, 2, 1, 1, 1]):
            self.list_frame.grid_columnconfigure(i, weight=w)

        headers = ["Client", "Date", "Deadline", "Montant", "", "", ""]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.list_frame, text=h, font=body_font(12, "bold"),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=0, column=i, sticky="w", padx=8, pady=(0, 10))

    def _on_status_change(self, value):
        self.status_filter.set(value)
        self.refresh()

    def refresh(self):
        for w in self.list_frame.winfo_children()[7:]:
            w.destroy()

        status_map = {"Toutes": None, "Payées": "paid", "À facturer": "unpaid"}
        year_value = self.year_filter.get().strip()
        year = int(year_value) if year_value.isdigit() else None
        month_value = self.month_filter.get()
        month = None if month_value == "Tous mois" else int(month_value.split(" - ")[0])

        invoices = db.list_invoices(
            self.search_var.get().strip(), status_map[self.status_filter.get()],
            year=year, month=month, drafts_only=True
        )
        # Keep exactly the rows currently displayed so the PDF mirrors the active filters.
        self.current_invoices = invoices

        if not invoices:
            empty = ctk.CTkLabel(self.list_frame, text="Aucune facture dans List SF.",
                                  font=body_font(13), text_color=COLORS["text_muted"])
            empty.grid(row=1, column=0, columnspan=7, sticky="w", padx=8, pady=20)
            return

        for idx, inv in enumerate(invoices):
            row = idx + 1

            client_cell = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            client_cell.grid(row=row, column=0, sticky="w", padx=8, pady=6)
            avatar_badge(client_cell, inv["client_name"], size=28, font_size=11).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(client_cell, text=inv["client_name"], font=body_font(12),
                         text_color=COLORS["text"]).pack(side="left")

            ctk.CTkLabel(self.list_frame, text=inv["invoice_date"], font=body_font(12),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=1, sticky="w", padx=8, pady=6)
            ctk.CTkLabel(self.list_frame, text=inv.get("deadline") or "Immédiat", font=body_font(12),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=2, sticky="w", padx=8, pady=6)

            montant = db.compute_invoice_totals(inv)[0]
            ctk.CTkLabel(self.list_frame, text=format_price_dh(montant), font=body_font(12, "bold"),
                         text_color=COLORS["text"], anchor="w").grid(row=row, column=3, sticky="w", padx=8, pady=6)

            secondary_button(self.list_frame, "Voir", lambda inv=inv: self.open_detail(inv), width=64).grid(row=row, column=4, sticky="e", padx=6, pady=4)
            primary_button(self.list_frame, "Facturer", lambda inv=inv: self.confirm_finalize(inv), width=90).grid(row=row, column=5, sticky="e", padx=6, pady=4)
            danger_button(self.list_frame, "Suppr.", lambda inv=inv: self.confirm_delete(inv), width=70).grid(row=row, column=6, sticky="e", padx=6, pady=4)


    def print_list_pdf(self):
        """Export all currently displayed List SF rows to a PDF."""
        if not self.current_invoices:
            MessageDialog(self, "Liste SF vide", "Aucune facture à imprimer dans la liste actuellement affichée.", is_error=True)
            return

        save_path = filedialog.asksaveasfilename(
            parent=self,
            title="Enregistrer la liste SF en PDF",
            initialfile="Liste SF.pdf",
            defaultextension=".pdf",
            filetypes=[("Fichier PDF", "*.pdf")],
        )
        if not save_path:
            return

        try:
            pdf_export.generate_list_sf_pdf(self.current_invoices, save_path)
        except Exception as e:
            log_exception("Génération PDF List SF", e)
            MessageDialog(self, "Erreur PDF", f"Impossible de générer le PDF : {e}", is_error=True)

    def confirm_finalize(self, invoice):
        ConfirmDialog(
            self, f"Facturer cette facture pour \"{invoice['client_name']}\" ?\n\n"
                  "Elle recevra son numéro définitif et sera déplacée vers l'onglet Factures.",
            lambda: self.finalize(invoice)
        )

    def finalize(self, invoice):
        try:
            db.finalize_invoice(invoice["id"])
        except Exception as e:
            log_exception("Facturation depuis List SF", e)
            MessageDialog(self, "Erreur", f"Impossible de facturer : {e}", is_error=True)
            return
        self.refresh()

    def confirm_delete(self, invoice):
        ConfirmDialog(self, f"Supprimer cette facture pour \"{invoice['client_name']}\" ?", lambda: self.delete(invoice))

    def delete(self, invoice):
        db.delete_invoice(invoice["id"])
        self.refresh()

    def open_new_dialog(self):
        if not db.list_clients():
            MessageDialog(self, "Aucun client", "Créez d'abord un client dans l'onglet Clients.", is_error=True)
            return
        InvoiceFormDialog(self, self.refresh)

    def open_detail(self, invoice):
        InvoiceDetailDialog(self, invoice["id"], self.refresh)
