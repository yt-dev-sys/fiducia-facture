from tkinter import filedialog
from datetime import date
import customtkinter as ctk
from app import database as db
from app.theme import COLORS, body_font, heading_font
from app.format_utils import format_price_dh, MONTHS_FR
from app.widgets import (
    section_title, primary_button, secondary_button, MessageDialog, labeled_entry,
    SegmentedToggle, status_pill, avatar_badge
)
from app import pdf_export
from app.app_logger import log_exception

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
            # Safety net only - FacturesTab.open_new_dialog() already checks for
            # this before ever constructing this dialog, so this shouldn't normally run.
            self.destroy()
            return

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        scroll.pack(fill="both", expand=True, padx=20, pady=(20, 0))

        section_title(scroll, "Modifier la facture" if invoice else "Nouvelle facture").pack(anchor="w", pady=(0, 12))

        # Client picker. Clients are looked up by their unique id, never by name,
        # so two clients that happen to share the same name are never confused
        # with each other. When a name collision exists, the dropdown label is
        # disambiguated with the client's id.
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

        # Invoice date - editable only when creating (never changed once issued, to
        # preserve the legally-required sequential numbering).
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

        # Business type / VAT toggle - defaults to "Avec TVA" for new invoices
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

        # Deadline
        ctk.CTkLabel(scroll, text="Deadline", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(14, 4))
        self.deadline_var = ctk.StringVar(value=invoice["deadline"] if invoice and invoice.get("deadline") else DEADLINE_OPTIONS[0])
        ctk.CTkOptionMenu(scroll, values=DEADLINE_OPTIONS, variable=self.deadline_var,
                          fg_color=COLORS["bg_soft"], button_color=COLORS["baby_blue_deep"],
                          button_hover_color=COLORS["baby_blue_dark"], text_color=COLORS["text"],
                          dropdown_fg_color=COLORS["white"]).pack(anchor="w", pady=(0, 14), fill="x")

        # Services checklist (from the selected client's service+price rows) - the
        # checked ones are snapshotted onto this invoice permanently at save time.
        ctk.CTkLabel(scroll, text="Services", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))
        self.services_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_soft"], corner_radius=12)
        self.services_frame.pack(fill="x", pady=(0, 14))
        self.service_checks = []  # list of (row_dict, BooleanVar)

        # Notes
        self.notes_var = ctk.StringVar(value=invoice["notes"] if invoice and invoice.get("notes") else "")
        labeled_entry(scroll, "Notes (optionnel)", self.notes_var)[0].pack(fill="x", pady=(0, 14))

        self._on_type_change()
        self._on_client_change(self.client_var.get())

        # Buttons
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

        # When editing, pre-check whichever rows this invoice was originally snapshotted
        # from (matched via source_price_id). New invoices default to everything checked.
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

        # Emitter
        emitter_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_soft"], corner_radius=12)
        emitter_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(emitter_frame, text="Émetteur", font=body_font(12, "bold"), text_color=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(emitter_frame, text=profile.get("name") or "(nom non configuré)", font=body_font(13, "bold")).pack(anchor="w", padx=12)
        ice_line = f"ICE: {profile.get('ice') or '-'}   IF: {profile.get('if_number') or '-'}"
        ctk.CTkLabel(emitter_frame, text=ice_line, font=body_font(11), text_color=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=(0, 10))

        # Client
        client_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_soft"], corner_radius=12)
        client_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(client_frame, text="Client", font=body_font(12, "bold"), text_color=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(client_frame, text=inv["client_name"], font=body_font(13, "bold")).pack(anchor="w", padx=12)
        ctk.CTkLabel(client_frame, text=f"ICE: {inv['client_ice'] or '-'}", font=body_font(11), text_color=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=(0, 10))

        # Deadline
        ctk.CTkLabel(scroll, text="Deadline", font=body_font(12, "bold"), text_color=COLORS["text_muted"]).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(scroll, text=inv.get("deadline") or "Immédiat", font=body_font(13, "bold"), text_color=COLORS["text"]).pack(anchor="w", pady=(0, 12))

        # Services (read-only, from the client's service+price rows)
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
        """Generates the invoice PDF and lets the user choose where to save it."""
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
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))
        section_title(header, "Factures").pack(side="left")

        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=24, pady=(0, 14))
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

        ctk.CTkOptionMenu(
            filter_frame, values=["Tous mois"] + MONTHS_FR, variable=self.month_filter,
            command=lambda _: self.refresh(), fg_color=COLORS["bg_soft"],
            button_color=COLORS["baby_blue_deep"], button_hover_color=COLORS["baby_blue_dark"],
            text_color=COLORS["text"], dropdown_fg_color=COLORS["white"], width=150, corner_radius=12
        ).pack(side="left")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"], corner_radius=16)
        self.list_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        for i, w in enumerate([2, 3, 2, 2, 2, 1]):
            self.list_frame.grid_columnconfigure(i, weight=w)

        self.sort_headers = [
            ("numero", "F°"),
            ("client_name", "Client"),
            ("invoice_date", "Date"),
            ("deadline", "Deadline"),
            ("status", "Statut"),
        ]
        self.header_labels = {}
        for i, (key, label) in enumerate(self.sort_headers):
            header = ctk.CTkLabel(
                self.list_frame, text=label, font=body_font(12, "bold"),
                text_color=COLORS["text_muted"], anchor="w", cursor="hand2"
            )
            header.grid(row=0, column=i, sticky="w", padx=8, pady=(0, 10))
            header.bind("<Button-1>", lambda e, key=key: self._sort_by(key))
            self.header_labels[key] = header

        ctk.CTkLabel(self.list_frame, text="", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"], anchor="w").grid(
            row=0, column=5, sticky="w", padx=8, pady=(0, 10)
        )

    def _sort_by(self, column):
        if self.sort_column == column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            # First click sorts descending, as requested (e.g. F°: largest -> smallest).
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
            # Invoice numbers may contain a prefix; compare their numeric part when possible.
            digits = "".join(ch for ch in str(value) if ch.isdigit())
            return (int(digits) if digits else -1)
        if column in ("client_name",):
            return str(value).casefold()
        return str(value)

    def _on_status_change(self, value):
        self.status_filter.set(value)
        self.refresh()

    def refresh(self):
        for w in self.list_frame.winfo_children()[6:]:
            w.destroy()

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

        self._update_sort_headers()

        if not invoices:
            empty = ctk.CTkLabel(self.list_frame, text="Aucune facture trouvée.",
                                  font=body_font(13), text_color=COLORS["text_muted"])
            empty.grid(row=1, column=0, columnspan=6, sticky="w", padx=8, pady=20)
            return

        for idx, inv in enumerate(invoices):
            row = idx + 1
            ctk.CTkLabel(self.list_frame, text=inv["numero"], font=body_font(13, "bold"),
                         text_color=COLORS["text"], anchor="w").grid(row=row, column=0, sticky="w", padx=8, pady=6)

            client_cell = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            client_cell.grid(row=row, column=1, sticky="w", padx=8, pady=6)
            avatar_badge(client_cell, inv["client_name"], size=28, font_size=11).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(client_cell, text=inv["client_name"], font=body_font(12),
                         text_color=COLORS["text"]).pack(side="left")

            ctk.CTkLabel(self.list_frame, text=inv["invoice_date"], font=body_font(12),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=2, sticky="w", padx=8, pady=6)
            ctk.CTkLabel(self.list_frame, text=inv.get("deadline") or "Immédiat", font=body_font(12),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=3, sticky="w", padx=8, pady=6)

            is_paid = inv["status"] == "paid"
            status_pill(self.list_frame, "Payée" if is_paid else "Non payée",
                        "success" if is_paid else "danger").grid(row=row, column=4, sticky="w", padx=8, pady=6)

            secondary_button(self.list_frame, "Voir", lambda inv=inv: self.open_detail(inv), width=70).grid(row=row, column=5, sticky="e", padx=8, pady=4)

    def open_detail(self, invoice):
        InvoiceDetailDialog(self, invoice["id"], self.refresh)
