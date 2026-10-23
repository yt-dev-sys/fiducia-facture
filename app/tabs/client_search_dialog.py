import customtkinter as ctk
from app import database as db
from app.theme import COLORS, body_font
from app.widgets import (section_title, secondary_button, primary_button, status_pill,
                         ConfirmDialog, MessageDialog, bind_search_debounce)
from app.format_utils import format_date_fr, format_price_dh


class ClientDetailDialog(ctk.CTkToplevel):
    """Read-only: every invoice this client ever had, by date of making and date of payment."""

    def __init__(self, master, client):
        super().__init__(master)
        self.title(f"Détail — {client['name']}")
        self.geometry("640x460")
        self.configure(fg_color=COLORS["white"])
        self.grab_set()

        invoices = db.list_client_invoices(client["id"])
        paid = sum(1 for i in invoices if i["status"] == "paid")

        section_title(self, client["name"]).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(
            self, text=f"{len(invoices)} facture(s) au total — {paid} payée(s), {len(invoices) - paid} non payée(s)",
            font=body_font(12), text_color=COLORS["text_muted"]
        ).pack(anchor="w", padx=20, pady=(0, 10))

        frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        for col in range(4):
            frame.grid_columnconfigure(col, weight=1)
        for col, title in enumerate(["Date de facture", "Date de paiement", "Montant", "Statut"]):
            ctk.CTkLabel(frame, text=title, font=body_font(12, "bold"),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=0, column=col, sticky="w", padx=8, pady=4)

        if not invoices:
            ctk.CTkLabel(frame, text="Aucune facture pour ce client.", font=body_font(13),
                         text_color=COLORS["text_muted"]).grid(row=1, column=0, columnspan=4, pady=30)
        for r, inv in enumerate(invoices, start=1):
            is_paid = inv["status"] == "paid"
            is_draft = inv["numero"] is None
            ctk.CTkLabel(frame, text=format_date_fr(inv["invoice_date"]), font=body_font(13),
                         text_color=COLORS["text"], anchor="w").grid(row=r, column=0, sticky="w", padx=8, pady=4)
            ctk.CTkLabel(frame, text=format_date_fr(inv["payment_date"]) if is_paid and inv["payment_date"] else "—",
                         font=body_font(13), text_color=COLORS["text"], anchor="w").grid(row=r, column=1, sticky="w", padx=8, pady=4)
            ctk.CTkLabel(frame, text=format_price_dh(inv["total_ttc"]), font=body_font(13),
                         text_color=COLORS["text"], anchor="w").grid(row=r, column=2, sticky="w", padx=8, pady=4)
            if is_paid:
                pill = status_pill(frame, "Payée", "success")
            elif is_draft:
                pill = status_pill(frame, "Brouillon", "neutral")
            else:
                pill = status_pill(frame, "Impayée", "danger")
            pill.grid(row=r, column=3, sticky="w", padx=8, pady=4)

        secondary_button(self, "Fermer", self.destroy, width=140).pack(pady=(0, 16))


class ClientSearchDialog(ctk.CTkToplevel):
    """Search utility: all clients, including hidden ones (deleted by the user or auto-hidden)."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Recherche")
        self.geometry("780x520")
        self.configure(fg_color=COLORS["white"])
        self.grab_set()
        self.search_var = ctk.StringVar()

        section_title(self, "Recherche de clients").pack(anchor="w", padx=20, pady=(18, 8))
        entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Nom, ICE...", width=320,
                             fg_color=COLORS["bg_soft"], border_color=COLORS["border"], corner_radius=12)
        entry.pack(anchor="w", padx=20, pady=(0, 10))
        bind_search_debounce(entry, self.refresh)

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=3)
        self.list_frame.grid_columnconfigure(1, weight=2)
        self.list_frame.grid_columnconfigure(2, weight=1)
        self.list_frame.grid_columnconfigure(3, weight=2)
        self.list_frame.grid_columnconfigure(4, weight=0)
        for col, title in enumerate(["Nom", "ICE", "Type", "Statut", ""]):
            ctk.CTkLabel(self.list_frame, text=title, font=body_font(12, "bold"),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=0, column=col, sticky="w", padx=8, pady=4)

        secondary_button(self, "Fermer", self.destroy, width=140).pack(pady=(0, 16))
        self.refresh()

    def refresh(self):
        for w in self.list_frame.winfo_children()[5:]:
            w.destroy()
        clients = db.search_all_clients(self.search_var.get().strip())
        if not clients:
            ctk.CTkLabel(self.list_frame, text="Aucun client trouvé.", font=body_font(13),
                         text_color=COLORS["text_muted"]).grid(row=1, column=0, columnspan=5, pady=30)
            return
        # Capped so very large databases stay responsive; narrow the search to see the rest.
        for r, c in enumerate(clients[:200], start=1):
            ctk.CTkLabel(self.list_frame, text=c["name"], font=body_font(13, "bold"),
                         text_color=COLORS["text"], anchor="w").grid(row=r, column=0, sticky="w", padx=8, pady=4)
            ctk.CTkLabel(self.list_frame, text=c["ice"] or "—", font=body_font(13),
                         text_color=COLORS["text"], anchor="w").grid(row=r, column=1, sticky="w", padx=8, pady=4)
            ctk.CTkLabel(self.list_frame, text="Temp" if c["client_type"] == "temp" else "Client",
                         font=body_font(13), text_color=COLORS["text_muted"], anchor="w").grid(
                row=r, column=2, sticky="w", padx=8, pady=4)
            if not c["is_hidden"]:
                pill = status_pill(self.list_frame, "Actif", "success")
            elif c["hidden_reason"] == "user":
                pill = status_pill(self.list_frame, "Supprimé", "danger")
            else:
                pill = status_pill(self.list_frame, "Auto (payé)", "neutral")
            pill.grid(row=r, column=3, sticky="w", padx=8, pady=4)

            actions = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            actions.grid(row=r, column=4, sticky="e", padx=8, pady=4)
            secondary_button(actions, "Détail", lambda c=c: ClientDetailDialog(self, c), width=80).pack(side="left", padx=4)
            if c["is_hidden"]:
                primary_button(actions, "Restaurer", lambda c=c: self.confirm_restore(c), width=100).pack(side="left", padx=4)

    def confirm_restore(self, client):
        def do_restore():
            db.restore_client(client["id"])
            self.refresh()
        ConfirmDialog(self, f"Restaurer le client \"{client['name']}\" ?", do_restore)
