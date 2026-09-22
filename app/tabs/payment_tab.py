from datetime import date
from tkinter import filedialog
import customtkinter as ctk
from app import database as db
from app.theme import COLORS, body_font, heading_font
from app.widgets import section_title, primary_button, secondary_button, MessageDialog
from app.format_utils import format_price_dh
from app import receipt_export
from app.app_logger import log_exception

PAYMENT_TYPE_OPTIONS = ["Espèces", "Chèque", "Virement bancaire"]


class InvoicePickerDialog(ctk.CTkToplevel):
    """Shown when a client has more than one unpaid invoice, so the user can pick which one to settle."""

    def __init__(self, master, client_name, invoices, on_select):
        super().__init__(master)
        self.title(f"Choisir une facture - {client_name}")
        self.geometry("380x420")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()
        self.on_select = on_select

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        scroll.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(scroll, text=f"{client_name} a plusieurs factures impayées :",
                     font=body_font(13, "bold"), text_color=COLORS["text"], wraplength=320,
                     justify="left").pack(anchor="w", pady=(0, 12))

        for inv in invoices:
            row = ctk.CTkFrame(scroll, fg_color=COLORS["bg_soft"], corner_radius=12)
            row.pack(fill="x", pady=4)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(info, text=inv["numero"], font=body_font(13, "bold"), text_color=COLORS["text"]).pack(anchor="w")
            ctk.CTkLabel(info, text=inv["invoice_date"], font=body_font(11), text_color=COLORS["text_muted"]).pack(anchor="w")
            secondary_button(row, "Sélectionner", lambda inv=inv: self._choose(inv), width=100).pack(side="right", padx=12)

    def _choose(self, invoice):
        self.destroy()
        self.on_select(invoice)


class PaymentDialog(ctk.CTkToplevel):
    """Payment dialog for a single invoice: payment type + payment date."""

    def __init__(self, master, invoice, on_change):
        super().__init__(master)
        self.title(f"Paiement - {invoice['numero']}")
        self.geometry("420x420")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()

        self.invoice = invoice
        self.on_change = on_change

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=20)

        section_title(body, "Confirmer le paiement").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(body, text=f"{invoice['numero']}  ·  {invoice['client_name']}",
                     font=body_font(12), text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(body, text="Type de paiement", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self.payment_type_var = ctk.StringVar(value=PAYMENT_TYPE_OPTIONS[0])
        ctk.CTkOptionMenu(
            body, values=PAYMENT_TYPE_OPTIONS, variable=self.payment_type_var,
            fg_color=COLORS["bg_soft"], button_color=COLORS["baby_blue_deep"],
            button_hover_color=COLORS["baby_blue_dark"], text_color=COLORS["text"],
            dropdown_fg_color=COLORS["white"]
        ).pack(anchor="w", fill="x", pady=(4, 16))

        ctk.CTkLabel(body, text="Date de paiement (AAAA-MM-JJ)", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self.payment_date_var = ctk.StringVar(value=date.today().isoformat())
        ctk.CTkEntry(
            body, textvariable=self.payment_date_var, fg_color=COLORS["bg_soft"],
            border_color=COLORS["border"], corner_radius=12
        ).pack(anchor="w", fill="x", pady=(4, 20))

        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.pack(anchor="w")
        secondary_button(btn_frame, "Annuler", self.destroy, width=120).pack(side="left", padx=(0, 8))
        primary_button(btn_frame, "Confirmer le paiement", self.confirm, width=200).pack(side="left")

    def confirm(self):
        payment_date = self.payment_date_var.get().strip()
        if not payment_date:
            MessageDialog(self, "Erreur", "Veuillez indiquer une date de paiement.", is_error=True)
            return
        db.set_invoice_paid(self.invoice["id"], self.payment_type_var.get(), payment_date)
        self._export_receipt(payment_date)
        self.destroy()
        self.on_change()

    def _export_receipt(self, payment_date):
        """Generates the payment receipt PDF and lets the user choose where to save it."""
        default_name = f"Recu_{self.invoice['numero']}.pdf"
        save_path = filedialog.asksaveasfilename(
            parent=self,
            title="Enregistrer le reçu PDF",
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("Fichier PDF", "*.pdf")],
        )
        if not save_path:
            return
        try:
            receipt_export.generate_receipt_pdf(self.invoice["id"], payment_date, save_path)
        except Exception as e:
            log_exception("Génération reçu PDF", e)
            MessageDialog(self, "Erreur PDF", f"Impossible de générer le reçu PDF : {e}", is_error=True)


class PaymentTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))
        section_title(header, "Payment").pack(side="left")

        self.summary_label = ctk.CTkLabel(self, text="", font=body_font(13), text_color=COLORS["text_muted"])
        self.summary_label.pack(anchor="w", padx=24, pady=(0, 10))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        self.list_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        for i, w in enumerate([3, 2, 2, 2]):
            self.list_frame.grid_columnconfigure(i, weight=w)

        headers = ["Client", "Factures impayées", "Montant", ""]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.list_frame, text=h, font=body_font(12, "bold"),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=0, column=i, sticky="w", padx=8, pady=(0, 10))

    def refresh(self):
        for w in self.list_frame.winfo_children()[4:]:
            w.destroy()

        clients = db.list_clients_with_unpaid_invoices()
        self.summary_label.configure(
            text=f"{len(clients)} client(s) avec des factures impayées"
        )

        if not clients:
            empty = ctk.CTkLabel(self.list_frame, text="Aucune facture impayée. Tous les clients sont à jour.",
                                  font=body_font(13), text_color=COLORS["text_muted"])
            empty.grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=20)
            return

        for idx, c in enumerate(clients):
            row = idx + 1
            ctk.CTkLabel(self.list_frame, text=c["client_name"], font=body_font(13, "bold"),
                         text_color=COLORS["text"], anchor="w").grid(row=row, column=0, sticky="w", padx=8, pady=6)
            ctk.CTkLabel(self.list_frame, text=str(c["unpaid_count"]), font=body_font(12),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=1, sticky="w", padx=8, pady=6)
            ctk.CTkLabel(self.list_frame, text=format_price_dh(c.get("montant", 0)), font=body_font(12, "bold"),
                         text_color=COLORS["text"], anchor="w").grid(row=row, column=2, sticky="w", padx=8, pady=6)

            primary_button(self.list_frame, "Payé", lambda c=c: self.start_payment(c), width=90).grid(
                row=row, column=3, sticky="e", padx=8, pady=4
            )

    def start_payment(self, client):
        unpaid = db.list_unpaid_invoices_for_client(client["client_id"])
        if not unpaid:
            self.refresh()
            return
        if len(unpaid) == 1:
            self.open_payment_dialog(unpaid[0])
        else:
            InvoicePickerDialog(self, client["client_name"], unpaid, self.open_payment_dialog)

    def open_payment_dialog(self, invoice):
        # invoice from list_unpaid_invoices_for_client doesn't include client_name - fetch full record
        full_invoice = db.get_invoice(invoice["id"])
        PaymentDialog(self, full_invoice, self.refresh)
