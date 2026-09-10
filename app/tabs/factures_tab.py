from tkinter import filedialog
from datetime import date
import customtkinter as ctk
from PIL import Image
from app import database as db
from app.theme import COLORS, body_font, heading_font
from app.format_utils import format_price_dh, MONTHS_FR
from app.widgets import (
    section_title, primary_button, secondary_button, danger_button, MessageDialog, labeled_entry,
    SegmentedToggle, status_pill, avatar_badge, ConfirmDialog
)
from app import pdf_export
from app.app_logger import log_exception
from app.app_paths import get_asset_path

DEADLINE_OPTIONS = ["Immédiat", "30j", "60j", "90j", "120j"]


class InvoiceFormDialog(ctk.CTkToplevel):
    def __init__(self, master, on_saved, invoice=None):
        super().__init__(master)
        self.invoice = invoice
        self.title("Modifier la facture" if invoice else "Nouvelle facture")
        self.geometry("640x680")
        self.configure(fg_color=COLORS["white"])
        self.grab_set()

        self.on_saved = on_saved
        self.clients = db.list_clients()
        profile = db.get_company_profile() or {}

        if not self.clients:
            self.destroy()
            return

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        scroll.pack(fill="both", expand=True, padx=20, pady=(20, 0))

        section_title(scroll, "Modifier la facture" if invoice else "Nouvelle facture").pack(anchor="w", pady=(0, 12))

        name_counts = {}
        for c in self.clients:
            name_counts[c["name"]] = name_counts.get(c["name"], 0) + 1
        self.client_display_by_id = {
            c["id"]: (c["name"] if name_counts[c["name"]] == 1 else f'{c["name"]} (#{c["id"]})')
            for c in self.clients
        }
        self.client_by_display = {display: c for c, display in
                                   ((c, self.client_display_by_id[c["id"]]) for c in self.clients)}
        client_names = [self.client_display_by_id[c["id"]] for c in self.clients]
        default_client_name = client_names[0]
        if invoice and invoice["client_id"] in self.client_display_by_id:
            default_client_name = self.client_display_by_id[invoice["client_id"]]
        self.client_var = ctk.StringVar(value=default_client_name)
        ctk.CTkLabel(scroll, text="Client *", font=body_font(12, "bold"), text_color=COLORS["text_muted"]).pack(anchor="w")
        ctk.CTkOptionMenu(scroll, values=client_names, variable=self.client_var,
                          command=self._on_client_change, fg_color=COLORS["bg_soft"],
                          button_color=COLORS["baby_blue_deep"],
                          button_hover_color=COLORS["baby_blue_dark"], text_color=COLORS["text"],
                          dropdown_fg_color=COLORS["white"]).pack(anchor="w", pady=(4, 14), fill="x")

        ctk.CTkLabel(scroll, text="Date de la facture", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))
        if invoice:
            ctk.CTkLabel(scroll, text=f"{invoice['invoice_date']} (non modifiable)",
                         font=body_font(13), text_color=COLORS["text"], anchor="w").pack(anchor="w", pady=(0, 14), fill="x")
            self.invoice_date_var = None
        else:
            self.invoice_date_var = ctk.StringVar(value=date.today().isoformat())
            ctk.CTkEntry(scroll, textvariable=self.invoice_date_var, placeholder_text="AAAA-MM-JJ",
                         fg_color=COLORS["bg_soft"], border_color=COLORS["border"],
                         text_color=COLORS["text"], corner_radius=12).pack(anchor="w", pady=(0, 14), fill="x")

        type_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        type_frame.pack(anchor="w", fill="x", pady=(0, 14))
        ctk.CTkLabel(type_frame, text="Type de facturation", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        default_business_type = invoice["business_type"] if invoice else "company"
        self.business_type_var = ctk.StringVar(value=default_business_type)
        toggle_row = ctk.CTkFrame(type_frame, fg_color="transparent")
        toggle_row.pack(anchor="w", pady=(4, 0))
        ctk.CTkRadioButton(toggle_row, text="Sans TVA", variable=self.business_type_var,
                           value="auto", command=self._on_type_change, fg_color=COLORS["baby_blue_deep"]).pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(toggle_row, text="Avec TVA", variable=self.business_type_var,
                           value="company", command=self._on_type_change, fg_color=COLORS["baby_blue_deep"]).pack(side="left")

        default_tva_rate = invoice["tva_rate"] if invoice and invoice.get("tva_rate") else profile.get("default_tva_rate", 20.0)
        self.tva_rate_var = ctk.StringVar(value=str(default_tva_rate))
        self.tva_frame, self.tva_entry = labeled_entry(scroll, "Taux de TVA (%)", self.tva_rate_var, width=100)

        ctk.CTkLabel(scroll, text="Deadline", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(14, 4))
        self.deadline_var = ctk.StringVar(value=invoice["deadline"] if invoice and invoice.get("deadline") else DEADLINE_OPTIONS[0])
        ctk.CTkOptionMenu(scroll, values=DEADLINE_OPTIONS, variable=self.deadline_var,
                          fg_color=COLORS["bg_soft"], button_color=COLORS["baby_blue_deep"],
                          button_hover_color=COLORS["baby_blue_dark"], text_color=COLORS["text"],
                          dropdown_fg_color=COLORS["white"]).pack(anchor="w", pady=(0, 14), fill="x")

        ctk.CTkLabel(scroll, text="Services", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))
        self.services_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_soft"], corner_radius=12)
        self.services_frame.pack(fill="x", pady=(0, 14))
        self.service_checks = []

        self.notes_var = ctk.StringVar(value=invoice["notes"] if invoice and invoice.get("notes") else "")
        labeled_entry(scroll, "Notes (optionnel)", self.notes_var)[0].pack(fill="x", pady=(0, 14))

        self._on_type_change()
        self._on_client_change(self.client_var.get())

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=16)
        secondary_button(btn_frame, "Annuler", self.destroy, width=140).pack(side="left", padx=8)
        primary_button(btn_frame, "Enregistrer les modifications" if invoice else "Créer la facture",
                       self.save, width=200 if invoice else 180).pack(side="left", padx=8)

    def _on_type_change(self):
        if self.business_type_var.get() == "company":
            self.tva_frame.pack(anchor="w", pady=(0, 4))
        else:
            self.tva_frame.pack_forget()

    def _on_client_change(self, client_display_name):
        for w in self.services_frame.winfo_children():
            w.destroy()
        self.service_checks = []

        client = self.client_by_display.get(client_display_name)
        if not client:
            return

        rows = db.get_client_service_prices(client["id"])
        if not rows:
            ctk.CTkLabel(self.services_frame, text="Aucun service assigné à ce client.",
                         font=body_font(12), text_color=COLORS["text_muted"]).pack(
                 anchor="w", padx=12, pady=10)
            return

        preselected_ids = None
        if self.invoice and client["id"] == self.invoice["client_id"]:
            existing_items = db.get_invoice_items(self.invoice["id"])
            if existing_items:
                preselected_ids = {i["source_price_id"] for i in existing_items if i.get("source_price_id")}

        for row in rows:
            checked = True if preselected_ids is None else (row["id"] in preselected_ids)
            var = ctk.BooleanVar(value=checked)
            ctk.CTkCheckBox(
                self.services_frame, text=f"{row['description']} — {format_price_dh(row['price'])}",
                variable=var, fg_color=COLORS["baby_blue_deep"], hover_color=COLORS["baby_blue_dark"],
                text_color=COLORS["text"], font=body_font(12)
            ).pack(anchor="w", padx=12, pady=(10 if row is rows[0] else 4, 4 if row is not rows[-1] else 10))
            self.service_checks.append((row, var))

    def save(self):
        client = self.client_by_display.get(self.client_var.get())
        if not client:
            MessageDialog(self, "Erreur", "Veuillez sélectionner un client.", is_error=True)
            return

        invoice_date = None
        if self.invoice_date_var is not None:
            invoice_date = self.invoice_date_var.get().strip()
            try:
                date.fromisoformat(invoice_date)
            except ValueError:
                MessageDialog(self, "Erreur", "Date invalide. Format attendu : AAAA-MM-JJ.", is_error=True)
                return

        business_type = self.business_type_var.get()
        if business_type == "company":
            try:
                tva_rate = float(self.tva_rate_var.get().replace(",", "."))
            except ValueError:
                MessageDialog(self, "Erreur", "Taux de TVA invalide.", is_error=True)
                return
        else:
            tva_rate = 0.0

        selected_items = [
            {"description": row["description"], "price": row["price"],
             "service_id": row.get("service_id"), "source_price_id": row["id"]}
            for row, var in self.service_checks if var.get()
        ]
        if not selected_items:
            MessageDialog(self, "Erreur", "Veuillez sélectionner au moins un service.", is_error=True)
            return

        try:
            if self.invoice:
                db.update_invoice(
                    self.invoice["id"], client_id=client["id"], business_type=business_type,
                    tva_rate=tva_rate, deadline=self.deadline_var.get(), notes=self.notes_var.get(),
                    selected_items=selected_items
                )
            else:
                db.create_invoice(
                    client_id=client["id"], business_type=business_type, tva_rate=tva_rate,
                    deadline=self.deadline_var.get(), invoice_date=invoice_date,
                    notes=self.notes_var.get(), selected_items=selected_items
                )
        except Exception as e:
            log_exception("Enregistrement facture", e)
            MessageDialog(self, "Erreur", f"Impossible d'enregistrer la facture: {e}", is_error=True)
            return

        self.destroy()
        self.on_saved()


class InvoiceDetailDialog(ctk.CTkToplevel):
    def __init__(self, master, invoice_id, on_change):
        super().__init__(master)
        self.on_change = on_change
        self.invoice = db.get_invoice(invoice_id)
        is_draft = not self.invoice.get("numero")
        self.title("Brouillon" if is_draft else f"F° {self.invoice['numero']}")
        self.geometry("500x600")
        self.configure(fg_color=COLORS["white"])
        self.grab_set()

        inv = self.invoice
        profile = db.get_company_profile() or {}

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(scroll, text=inv["numero"] if not is_draft else "Brouillon (pas encore facturé)",
                     font=heading_font(20), text_color=COLORS["text"]).pack(anchor="w")
        ctk.CTkLabel(scroll, text=f"Date: {inv['invoice_date']}", font=body_font(12), text_color=COLORS["text_muted"]).pack(anchor="w", pady=(2, 12))

        emitter_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_soft"], corner_radius=12)
        emitter_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(emitter_frame, text="Émetteur", font=body_font(12, "bold"), text_color=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(emitter_frame, text=profile.get("name") or "(nom non configuré)", font=body_font(13, "bold")).pack(anchor="w", padx=12)
        ice_line = f"ICE: {profile.get('ice') or '-'}   IF: {profile.get('if_number') or '-'}"
        ctk.CTkLabel(emitter_frame, text=ice_line, font=body_font(11), text_color=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=(0, 10))

        client_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_soft"], corner_radius=12)
        client_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(client_frame, text="Client", font=body_font(12, "bold"), text_color=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(client_frame, text=inv["client_name"], font=body_font(13, "bold")).pack(anchor="w", padx=12)
        ctk.CTkLabel(client_frame, text=f"ICE: {inv['client_ice'] or '-'}", font=body_font(11), text_color=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkLabel(scroll, text="Deadline", font=body_font(12, "bold"), text_color=COLORS["text_muted"]).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(scroll, text=inv.get("deadline") or "Immédiat", font=body_font(13, "bold"), text_color=COLORS["text"]).pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(scroll, text="Services", font=body_font(12, "bold"), text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))
        services_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_soft"], corner_radius=12)
        services_frame.pack(fill="x", pady=(0, 14))
        service_rows = db.get_client_service_prices(inv["client_id"])
        if service_rows:
            text = "\n".join(f"{r['description']} — {format_price_dh(r['price'])}" for r in service_rows)
        else:
            text = "Aucun service assigné à ce client."
        ctk.CTkLabel(services_frame, text=text, font=body_font(12), text_color=COLORS["text"],
                     justify="left", anchor="w").pack(fill="x", padx=12, pady=10)

        is_paid = inv["status"] == "paid"
        status_pill(scroll, "Payée ✓" if is_paid else "Non payée", "success" if is_paid else "danger").pack(
            anchor="w", pady=(0, 10))

        if inv["notes"]:
            ctk.CTkLabel(scroll, text=f"Notes: {inv['notes']}", font=body_font(12), text_color=COLORS["text_muted"], wraplength=440, justify="left").pack(anchor="w", pady=(0, 10))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, 16))
        secondary_button(btn_frame, "Modifier", self.open_edit, width=100).pack(side="left", padx=6)
        if not is_draft:
            primary_button(btn_frame, "Print", self.print_pdf, width=100).pack(side="left", padx=6)

    def open_edit(self):
        self.destroy()
        InvoiceFormDialog(self.master, self.on_change, invoice=self.invoice)

    def print_pdf(self):
        default_name = f"{self.invoice['numero']}.pdf"
        save_path = filedialog.asksaveasfilename(
            parent=self,
            title="Enregistrer la facture PDF",
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("Fichier PDF", "*.pdf")],
        )
        if not save_path:
            return
        try:
            pdf_export.generate_invoice_pdf(self.invoice["id"], save_path)
        except Exception as e:
            log_exception("Génération PDF facture", e)
            MessageDialog(self, "Erreur PDF", f"Impossible de générer le PDF : {e}", is_error=True)


class FacturesTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        today = date.today()
        self.search_var = ctk.StringVar()
        self.status_filter = ctk.StringVar(value="Non payées")
        self.year_filter = ctk.StringVar(value=str(today.year))
        self.sort_column = None
        self.sort_descending = True
        self.month_filter = ctk.StringVar(value=MONTHS_FR[today.month - 1])
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
        section_title(header, "Factures").pack(side="left")

        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=24, pady=(0, 4))
        search_entry = ctk.CTkEntry(
            filter_frame, textvariable=self.search_var, placeholder_text="Rechercher (numéro, client)...",
            width=240, fg_color=COLORS["bg_soft"], border_color=COLORS["border"], corner_radius=12
        )
        search_entry.pack(side="left", padx=(0, 10))
        search_entry.bind("<KeyRelease>", lambda e: self.refresh())

        self.status_toggle = SegmentedToggle(
            filter_frame, ["Toutes", "Payées", "Non payées"], self.status_filter.get(),
            on_change=self._on_status_change
        )
        self.status_toggle.pack(side="left", padx=(0, 10))

        year_entry = ctk.CTkEntry(
            filter_frame, textvariable=self.year_filter, placeholder_text="Année", width=90,
            fg_color=COLORS["bg_soft"], border_color=COLORS["border"], corner_radius=12
        )
        year_entry.pack(side="left", padx=(0, 10))
        year_entry.bind("<KeyRelease>", lambda e: self.refresh())

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
            self.sort_headers = [
                ("numero", "F°"),
                ("client_name", "Client"),
                ("invoice_date", "Date"),
                ("deadline", "Deadline"),
                ("status", "Statut"),
            ]
            col_weights = [1, 2, 3, 2, 2, 2, 1]
            header_offset = 1
        else:
            self.sort_headers = [
                ("numero", "F°"),
                ("client_name", "Client"),
                ("invoice_date", "Date"),
                ("deadline", "Deadline"),
                ("status", "Statut"),
            ]
            col_weights = [2, 3, 2, 2, 2, 1]
            header_offset = 0

        for i, w in enumerate(col_weights):
            self.list_frame.grid_columnconfigure(i, weight=w)

        self.header_labels = {}
        for i, (key, label) in enumerate(self.sort_headers):
            header = ctk.CTkLabel(
                self.list_frame, text=label, font=body_font(12, "bold"),
                text_color=COLORS["text_muted"], anchor="w", cursor="hand2"
            )
            header.grid(row=0, column=i + header_offset, sticky="w", padx=8, pady=(0, 10))
            header.bind("<Button-1>", lambda e, key=key: self._sort_by(key))
            self.header_labels[key] = header

        if self.show_checkboxes:
            select_all_cb = ctk.CTkCheckBox(
                self.list_frame, text="", variable=self.select_all_var,
                command=self._toggle_select_all, width=28, height=28,
                fg_color=COLORS["baby_blue_deep"], hover_color=COLORS["baby_blue_dark"],
                checkbox_width=20, checkbox_height=20, corner_radius=4
            )
            select_all_cb.grid(row=0, column=0, sticky="w", padx=8, pady=(0, 10))

        ctk.CTkLabel(self.list_frame, text="", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"], anchor="w").grid(
            row=0, column=len(self.sort_headers) + header_offset, sticky="w", padx=8, pady=(0, 10)
        )

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

    def _sort_by(self, column):
        if self.sort_column == column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            self.sort_descending = True
        self._update_sort_headers()
        self.refresh()

    def _update_sort_headers(self):
        for key, label in self.sort_headers:
            indicator = " ↓" if self.sort_column == key and self.sort_descending else (" ↑" if self.sort_column == key else "")
            self.header_labels[key].configure(text=label + indicator)

    @staticmethod
    def _sort_value(invoice, column):
        value = invoice.get(column)
        if value is None:
            return ""
        if column == "status":
            return {"paid": 1, "unpaid": 0}.get(value, -1)
        if column == "deadline":
            order = {"Immédiat": 0, "30j": 30, "60j": 60, "90j": 90, "120j": 120}
            return order.get(value, 999)
        if column == "numero":
            digits = "".join(ch for ch in str(value) if ch.isdigit())
            return (int(digits) if digits else -1)
        if column in ("client_name",):
            return str(value).casefold()
        return str(value)

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
        if not hasattr(self, 'current_invoices') or not self.current_invoices:
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

        danger_button(
            self.bulk_action_frame, "Supprimer", self.bulk_delete, width=100
        ).pack(side="left", padx=(0, 6))
        primary_button(
            self.bulk_action_frame, "Défacturer", self.bulk_unfinalize, width=100
        ).pack(side="left")

    def _rebuild_rows(self):
        for w in self.list_frame.winfo_children():
            if w.grid_info().get("row", 0) > 0:
                w.destroy()

        if not self.current_invoices:
            empty = ctk.CTkLabel(self.list_frame, text="Aucune facture trouvée.",
                                  font=body_font(13), text_color=COLORS["text_muted"])
            col_span = 7 if self.show_checkboxes else 6
            empty.grid(row=1, column=0, columnspan=col_span, sticky="w", padx=8, pady=20)
            return

        for idx, inv in enumerate(self.current_invoices):
            row = idx + 1
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

            ctk.CTkLabel(self.list_frame, text=inv["numero"], font=body_font(13, "bold"),
                         text_color=COLORS["text"], anchor="w").grid(row=row, column=col_offset, sticky="w", padx=8, pady=6)

            client_cell = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            client_cell.grid(row=row, column=col_offset + 1, sticky="w", padx=8, pady=6)
            avatar_badge(client_cell, inv["client_name"], size=28, font_size=11).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(client_cell, text=inv["client_name"], font=body_font(12),
                         text_color=COLORS["text"]).pack(side="left")

            ctk.CTkLabel(self.list_frame, text=inv["invoice_date"], font=body_font(12),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=col_offset + 2, sticky="w", padx=8, pady=6)
            ctk.CTkLabel(self.list_frame, text=inv.get("deadline") or "Immédiat", font=body_font(12),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=col_offset + 3, sticky="w", padx=8, pady=6)

            is_paid = inv["status"] == "paid"
            status_pill(self.list_frame, "Payée" if is_paid else "Non payée",
                        "success" if is_paid else "danger").grid(row=row, column=col_offset + 4, sticky="w", padx=8, pady=6)

            secondary_button(self.list_frame, "Voir", lambda inv=inv: self.open_detail(inv), width=70).grid(row=row, column=col_offset + 5, sticky="e", padx=8, pady=4)

    def refresh(self):
        self.selected_invoice_ids.clear()
        self.checkbox_vars.clear()
        self.select_all_var.set(False)

        status_map = {"Toutes": None, "Payées": "paid", "Non payées": "unpaid"}
        year_value = self.year_filter.get().strip()
        year = int(year_value) if year_value.isdigit() else None
        month_value = self.month_filter.get()
        month = None if month_value == "Tous mois" else int(month_value.split(" - ")[0])

        invoices = db.list_invoices(
            self.search_var.get().strip(), status_map[self.status_filter.get()],
            year=year, month=month
        )
        if self.sort_column:
            invoices.sort(
                key=lambda invoice: self._sort_value(invoice, self.sort_column),
                reverse=self.sort_descending,
            )

        self.current_invoices = invoices
        self._build_headers()
        self._rebuild_rows()
        self._update_bulk_actions_visibility()

    def open_detail(self, invoice):
        InvoiceDetailDialog(self, invoice["id"], self.refresh)

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

    def bulk_unfinalize(self):
        if not self.selected_invoice_ids:
            return
        count = len(self.selected_invoice_ids)
        ConfirmDialog(
            self, f"Défacturer {count} facture(s) sélectionnée(s) ?\n\n"
                  "Elles redeviendront des brouillons (sans numéro) et seront déplacées vers l'onglet List SF.",
            self._do_bulk_unfinalize
        )

    def _do_bulk_unfinalize(self):
        for inv_id in list(self.selected_invoice_ids):
            try:
                db.unfinalize_invoice(inv_id)
            except Exception as e:
                log_exception("Défacturation groupée", e)
                MessageDialog(self, "Erreur", f"Impossible de défacturer une facture : {e}", is_error=True)
        self.refresh()
