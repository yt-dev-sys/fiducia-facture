from datetime import date
import customtkinter as ctk
from PIL import Image
from app import database as db
from app.theme import COLORS, body_font
from app.format_utils import format_price_dh, MONTHS_FR
from app.widgets import (
    section_title, primary_button, secondary_button, danger_button, MessageDialog,
    ConfirmDialog, SegmentedToggle, status_pill, avatar_badge, icon_button, bind_search_debounce
)
from app.tabs.factures_tab import InvoiceDetailDialog, InvoiceFormDialog
from app.app_logger import log_exception
from app.app_paths import get_asset_path
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
        self.month_filter = ctk.StringVar(value="Tous mois")
        self.current_invoices = []
        self.selected_invoice_ids = set()
        self.select_all_var = ctk.BooleanVar(value=False)
        self.checkbox_vars = {}
        self.bulk_action_frame = None
        self.show_checkboxes = False

        off_img = Image.open(get_asset_path("select-mode-off.png"))
        on_img = Image.open(get_asset_path("select-mode-on.png"))
        self.select_off_icon = ctk.CTkImage(light_image=off_img, dark_image=off_img, size=(22, 22))
        self.select_on_icon = ctk.CTkImage(light_image=on_img, dark_image=on_img, size=(22, 22))

        self._build_ui()
        self.refresh()
        self.bind("<Control-a>", self._on_select_all)
        self.bind("<Escape>", self._on_escape)
        self.focus_set()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))
        section_title(header, "List SF").pack(side="left")
        icon_button(header, "🖨", self.print_list_pdf, size=40).pack(side="right", padx=(8, 0))
        primary_button(header, "+ Nouvelle facture", self.open_new_dialog, width=180).pack(side="right")

        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=24, pady=(0, 4))
        search_entry = ctk.CTkEntry(
            filter_frame, textvariable=self.search_var, placeholder_text="Rechercher (client)...",
            width=240, fg_color=COLORS["bg_soft"], border_color=COLORS["border"], corner_radius=12
        )
        search_entry.pack(side="left", padx=(0, 10))
        bind_search_debounce(search_entry, self.refresh)

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
        bind_search_debounce(year_entry, self.refresh, delay_ms=500)

        month_menu = ctk.CTkOptionMenu(
            filter_frame, values=["Tous mois"] + MONTHS_FR, variable=self.month_filter,
            command=lambda _: self.refresh(), fg_color=COLORS["bg_soft"],
            button_color=COLORS["baby_blue_deep"], button_hover_color=COLORS["baby_blue_dark"],
            text_color=COLORS["text"], dropdown_fg_color=COLORS["white"], width=150, corner_radius=12
        )
        month_menu.pack(side="left")

        self.select_mode_btn = ctk.CTkButton(
            filter_frame, text="", image=self.select_off_icon, command=self._toggle_select_mode,
            width=36, height=36, fg_color="transparent", hover_color=COLORS["bg_soft"],
            corner_radius=10
        )
        self.select_mode_btn.pack(side="left", padx=(10, 0))

        self.bulk_action_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        self.bulk_action_frame.pack(side="left", padx=(10, 0))
        self._update_bulk_actions_visibility()

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"], corner_radius=16)
        self.list_frame.pack(fill="both", expand=True, padx=24, pady=(4, 20))
        self._build_headers()

    def _build_headers(self):
        for w in self.list_frame.winfo_children():
            if w.grid_info().get("row") == 0:
                w.destroy()

        if self.show_checkboxes:
            headers = ["", "Client", "Date", "Deadline", "Montant", "", "", ""]
            col_weights = [1, 3, 2, 2, 2, 1, 1, 1]
        else:
            headers = ["Client", "Date", "Deadline", "Montant", "", "", ""]
            col_weights = [3, 2, 2, 2, 1, 1, 1]

        for i, w in enumerate(col_weights):
            self.list_frame.grid_columnconfigure(i, weight=w)

        for i, h in enumerate(headers):
            if self.show_checkboxes and i == 0:
                select_all_cb = ctk.CTkCheckBox(
                    self.list_frame, text="", variable=self.select_all_var,
                    command=self._toggle_select_all, width=28, height=28,
                    fg_color=COLORS["baby_blue_deep"], hover_color=COLORS["baby_blue_dark"],
                    checkbox_width=20, checkbox_height=20, corner_radius=4
                )
                select_all_cb.grid(row=0, column=0, sticky="w", padx=8, pady=(0, 10))
            else:
                ctk.CTkLabel(self.list_frame, text=h, font=body_font(12, "bold"),
                             text_color=COLORS["text_muted"], anchor="w").grid(row=0, column=i, sticky="w", padx=8, pady=(0, 10))

    def _toggle_select_mode(self):
        self.show_checkboxes = not self.show_checkboxes
        if self.show_checkboxes:
            self.select_mode_btn.configure(image=self.select_on_icon)
        else:
            self.select_mode_btn.configure(image=self.select_off_icon)
            self.selected_invoice_ids.clear()
            self.checkbox_vars.clear()
            self.select_all_var.set(False)
            self._update_bulk_actions_visibility()
        self._build_headers()
        self._rebuild_rows()

    def _on_status_change(self, value):
        self.status_filter.set(value)
        self.refresh()

    def _toggle_select_all(self):
        if self.select_all_var.get():
            for inv in self.current_invoices:
                self.selected_invoice_ids.add(inv["id"])
                if inv["id"] in self.checkbox_vars:
                    self.checkbox_vars[inv["id"]].set(True)
        else:
            self.selected_invoice_ids.clear()
            for var in self.checkbox_vars.values():
                var.set(False)
        self._update_bulk_actions_visibility()
        self._update_select_all_state()

    def _on_select_all(self, event):
        if self.show_checkboxes:
            self.select_all_var.set(not self.select_all_var.get())
            self._toggle_select_all()

    def _on_escape(self, event):
        if self.selected_invoice_ids:
            self.select_all_var.set(False)
            self.selected_invoice_ids.clear()
            for var in self.checkbox_vars.values():
                var.set(False)
            self._update_bulk_actions_visibility()
            self._update_select_all_state()

    def _on_checkbox_change(self, invoice_id, var):
        if var.get():
            self.selected_invoice_ids.add(invoice_id)
        else:
            self.selected_invoice_ids.discard(invoice_id)
        self._update_bulk_actions_visibility()
        self._update_select_all_state()

    def _update_select_all_state(self):
        if not self.current_invoices:
            self.select_all_var.set(False)
        elif len(self.selected_invoice_ids) == len(self.current_invoices):
            self.select_all_var.set(True)
        else:
            self.select_all_var.set(False)

    def _update_bulk_actions_visibility(self):
        for w in self.bulk_action_frame.winfo_children():
            w.destroy()

        if not self.selected_invoice_ids:
            return

        count = len(self.selected_invoice_ids)
        ctk.CTkLabel(
            self.bulk_action_frame, text=f"{count} sélectionnée(s)",
            font=body_font(12, "bold"), text_color=COLORS["baby_blue_deep"]
        ).pack(side="left", padx=(0, 10))

        primary_button(
            self.bulk_action_frame, "Facturer", self.bulk_finalize, width=100
        ).pack(side="left", padx=(0, 6))
        danger_button(
            self.bulk_action_frame, "Supprimer", self.bulk_delete, width=100
        ).pack(side="left")

    def _render_one_row(self, inv, row):
        """Render a single draft invoice row into the list grid."""
        col_offset = 0
        if self.show_checkboxes:
            var = ctk.BooleanVar(value=False)
            self.checkbox_vars[inv["id"]] = var
            cb = ctk.CTkCheckBox(
                self.list_frame, text="", variable=var,
                command=lambda inv_id=inv["id"], v=var: self._on_checkbox_change(inv_id, v),
                width=28, height=28, fg_color=COLORS["baby_blue_deep"],
                hover_color=COLORS["baby_blue_dark"], checkbox_width=20,
                checkbox_height=20, corner_radius=4
            )
            cb.grid(row=row, column=0, sticky="w", padx=8, pady=6)
            col_offset = 1

        client_cell = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        client_cell.grid(row=row, column=col_offset, sticky="w", padx=8, pady=6)
        avatar_badge(client_cell, inv["client_name"], size=28, font_size=11).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(client_cell, text=inv["client_name"], font=body_font(12),
                     text_color=COLORS["text"]).pack(side="left")

        ctk.CTkLabel(self.list_frame, text=inv["invoice_date"], font=body_font(12),
                     text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=col_offset + 1, sticky="w", padx=8, pady=6)
        ctk.CTkLabel(self.list_frame, text=inv.get("deadline") or "Immédiat", font=body_font(12),
                     text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=col_offset + 2, sticky="w", padx=8, pady=6)

        montant = db.compute_invoice_totals(inv)[0]
        ctk.CTkLabel(self.list_frame, text=format_price_dh(montant), font=body_font(12, "bold"),
                     text_color=COLORS["text"], anchor="w").grid(row=row, column=col_offset + 3, sticky="w", padx=8, pady=6)

        secondary_button(self.list_frame, "Voir", lambda inv=inv: self.open_detail(inv), width=64).grid(
            row=row, column=col_offset + 4, sticky="e", padx=6, pady=4)

        if not self.selected_invoice_ids:
            primary_button(self.list_frame, "Facturer", lambda inv=inv: self.confirm_finalize(inv), width=90).grid(
                row=row, column=col_offset + 5, sticky="e", padx=6, pady=4)
            danger_button(self.list_frame, "Suppr.", lambda inv=inv: self.confirm_delete(inv), width=70).grid(
                row=row, column=col_offset + 6, sticky="e", padx=6, pady=4)

    def _rebuild_rows(self):
        for w in self.list_frame.winfo_children():
            if w.grid_info().get("row", 0) > 0:
                w.destroy()

        if not self.current_invoices:
            empty = ctk.CTkLabel(self.list_frame, text="Aucune facture dans List SF.",
                                  font=body_font(13), text_color=COLORS["text_muted"])
            col_span = 8 if self.show_checkboxes else 7
            empty.grid(row=1, column=0, columnspan=col_span, sticky="w", padx=8, pady=20)
            return

        CHUNK = 25
        invoices = self.current_invoices

        def render_chunk(start):
            for idx in range(start, min(start + CHUNK, len(invoices))):
                self._render_one_row(invoices[idx], idx + 1)
            if start + CHUNK < len(invoices):
                self.after(0, lambda: render_chunk(start + CHUNK))

        render_chunk(0)

    def refresh(self):
        self.selected_invoice_ids.clear()
        self.checkbox_vars.clear()
        self.select_all_var.set(False)

        status_map = {"Toutes": None, "Payées": "paid", "À facturer": "unpaid"}
        year_value = self.year_filter.get().strip()
        year = int(year_value) if year_value.isdigit() else None
        month_value = self.month_filter.get()
        month = None if month_value == "Tous mois" else int(month_value.split(" - ")[0])

        invoices = db.list_invoices(
            self.search_var.get().strip(), status_map[self.status_filter.get()],
            year=year, month=month, drafts_only=True
        )
        self.current_invoices = invoices

        self._build_headers()
        self._rebuild_rows()
        self._update_bulk_actions_visibility()

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

    def bulk_finalize(self):
        if not self.selected_invoice_ids:
            return
        count = len(self.selected_invoice_ids)
        ConfirmDialog(
            self, f"Facturer {count} facture(s) sélectionnée(s) ?\n\n"
                  "Elles recevront leurs numéros définitifs et seront déplacées vers l'onglet Factures.",
            self._do_bulk_finalize
        )

    def _do_bulk_finalize(self):
        for inv_id in list(self.selected_invoice_ids):
            try:
                db.finalize_invoice(inv_id)
            except Exception as e:
                log_exception("Facturation groupée", e)
                MessageDialog(self, "Erreur", f"Impossible de facturer une facture : {e}", is_error=True)
        self.refresh()

    def bulk_delete(self):
        if not self.selected_invoice_ids:
            return
        count = len(self.selected_invoice_ids)
        ConfirmDialog(
            self, f"Supprimer {count} facture(s) sélectionnée(s) ?\n\nCette action est irréversible.",
            self._do_bulk_delete
        )

    def _do_bulk_delete(self):
        for inv_id in list(self.selected_invoice_ids):
            try:
                db.delete_invoice(inv_id)
            except Exception as e:
                log_exception("Suppression groupée", e)
                MessageDialog(self, "Erreur", f"Impossible de supprimer une facture : {e}", is_error=True)
        self.refresh()

    def open_new_dialog(self):
        if not db.list_clients():
            MessageDialog(self, "Aucun client", "Créez d'abord un client dans l'onglet Clients.", is_error=True)
            return
        InvoiceFormDialog(self, self.refresh)

    def open_detail(self, invoice):
        InvoiceDetailDialog(self, invoice["id"], self.refresh)
