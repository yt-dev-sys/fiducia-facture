import customtkinter as ctk
from app import database as db
from app.theme import COLORS, body_font
from app.widgets import section_title, primary_button, secondary_button, danger_button, ConfirmDialog, MessageDialog, labeled_entry, bind_digits_only, avatar_badge, bind_search_debounce
from app.format_utils import format_price_dh, parse_price
from app.app_logger import log_exception


class ServicePriceRow(ctk.CTkFrame):
    """One row: pick one of your existing services (from the Services tab) + its price for this client."""

    def __init__(self, master, services, on_remove, existing=None):
        super().__init__(master, fg_color=COLORS["bg_soft"], corner_radius=12)
        self.services = services
        self.on_remove = on_remove

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_columnconfigure(3, weight=0)

        service_names = [s["name"] for s in services]
        existing_service = None
        if existing and existing.get("service_id"):
            existing_service = next((s for s in services if s["id"] == existing["service_id"]), None)

        default_name = existing_service["name"] if existing_service else (service_names[0] if service_names else "")
        self.service_var = ctk.StringVar(value=default_name)
        self.service_menu = ctk.CTkOptionMenu(
            self, values=service_names, variable=self.service_var,
            fg_color=COLORS["white"], button_color=COLORS["baby_blue_deep"],
            button_hover_color=COLORS["baby_blue_dark"], text_color=COLORS["text"],
            dropdown_fg_color=COLORS["white"]
        )
        self.service_menu.grid(row=0, column=0, padx=6, pady=8, sticky="ew")

        self.price_var = ctk.StringVar(value=str(existing["price"]) if existing else "")
        price_entry = ctk.CTkEntry(self, textvariable=self.price_var, width=100, placeholder_text="Prix",
                                    fg_color=COLORS["white"], border_color=COLORS["border"])
        price_entry.grid(row=0, column=1, padx=(6, 0), pady=8)

        ctk.CTkLabel(self, text="DH", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"]).grid(row=0, column=2, padx=(4, 6), pady=8)

        remove_btn = ctk.CTkButton(self, text="✕", width=28, height=28, fg_color="transparent",
                                    text_color=COLORS["danger"], hover_color="#FDEAEA",
                                    command=lambda: self.on_remove(self))
        remove_btn.grid(row=0, column=3, padx=6, pady=8)

    def get_data(self):
        choice = self.service_var.get()
        svc = next((s for s in self.services if s["name"] == choice), None)
        if not svc:
            return None
        try:
            price = parse_price(self.price_var.get())
        except ValueError:
            price = 0.0
        return {"service_id": svc["id"], "description": svc["name"], "price": price}


class ClientFormDialog(ctk.CTkToplevel):
    def __init__(self, master, on_saved, client=None):
        super().__init__(master)
        self.title("Modifier client" if client else "Nouveau client")
        self.geometry("460x700")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()

        self.on_saved = on_saved
        self.client = client
        self.services = db.list_services()
        self.service_price_rows = []
        existing_rows = db.get_client_service_prices(client["id"]) if client else []

        self.name_var = ctk.StringVar(value=client["name"] if client else "")
        self.ice_var = ctk.StringVar(value=client["ice"] if client else "")
        bind_digits_only(self.ice_var, max_len=15)
        self.if_var = ctk.StringVar(value=client["if_number"] if client and client.get("if_number") else "")
        self.address_var = ctk.StringVar(value=client["address"] if client else "")
        self.phone_var = ctk.StringVar(value=client["phone"] if client else "")
        self.email_var = ctk.StringVar(value=client["email"] if client else "")

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        scroll.pack(fill="both", expand=True, padx=4, pady=(4, 0))

        pad = {"padx": 20, "pady": (10, 0)}
        labeled_entry(scroll, "Nom du client *", self.name_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "ICE (15 chiffres)", self.ice_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "IF", self.if_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Adresse", self.address_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Téléphone", self.phone_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Email", self.email_var)[0].pack(fill="x", **pad)

        ctk.CTkLabel(scroll, text="Services", font=body_font(12, "bold"),
                     text_color=COLORS["text_muted"], anchor="w").pack(anchor="w", padx=20, pady=(14, 4))
        self.rows_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.rows_container.pack(fill="x", padx=20)

        if self.services:
            self.add_service_button = secondary_button(scroll, "+ Ajouter un service", self.add_service_row, width=190)
            self.add_service_button.pack(anchor="w", padx=20, pady=(8, 14))

            if existing_rows:
                for row in existing_rows:
                    self.add_service_row(existing=row)
            else:
                self.add_service_row()
        else:
            ctk.CTkLabel(
                scroll, text="Aucun service disponible. Ajoutez-en dans l'onglet Services.",
                font=body_font(12), text_color=COLORS["text_muted"]
            ).pack(anchor="w", padx=20, pady=(0, 14))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=16)
        secondary_button(btn_frame, "Annuler", self.destroy, width=120).pack(side="left", padx=8)
        primary_button(btn_frame, "Enregistrer", self.save, width=140).pack(side="left", padx=8)

    def add_service_row(self, existing=None):
        row = ServicePriceRow(self.rows_container, self.services, self.remove_service_row, existing=existing)
        row.pack(fill="x", pady=4)
        self.service_price_rows.append(row)

    def remove_service_row(self, row):
        if len(self.service_price_rows) <= 1:
            return
        row.destroy()
        self.service_price_rows.remove(row)

    def save(self):
        name = self.name_var.get().strip()
        if not name:
            MessageDialog(self, "Erreur", "Le nom du client est obligatoire.", is_error=True)
            return

        service_price_rows = []
        for row in self.service_price_rows:
            data = row.get_data()
            if data:
                service_price_rows.append(data)

        try:
            if self.client:
                db.update_client(
                    self.client["id"], name,
                    address=self.address_var.get(), ice=self.ice_var.get(), if_number=self.if_var.get(),
                    phone=self.phone_var.get(), email=self.email_var.get(),
                    service_price_rows=service_price_rows
                )
            else:
                db.create_client(
                    name,
                    address=self.address_var.get(), ice=self.ice_var.get(), if_number=self.if_var.get(),
                    phone=self.phone_var.get(), email=self.email_var.get(),
                    service_price_rows=service_price_rows
                )
            self.destroy()
            self.on_saved()
        except Exception as e:
            log_exception("Enregistrement client", e)
            MessageDialog(self, "Erreur", str(e), is_error=True)


class ClientsTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        self.search_var = ctk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))

        section_title(header, "Clients").pack(side="left")
        primary_button(header, "+ Nouveau client", self.open_new_dialog, width=170).pack(side="right")

        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=24, pady=(0, 10))
        search_entry = ctk.CTkEntry(
            search_frame, textvariable=self.search_var, placeholder_text="Rechercher un client...",
            width=320, fg_color=COLORS["bg_soft"], border_color=COLORS["border"], corner_radius=12
        )
        search_entry.pack(side="left")
        bind_search_debounce(search_entry, self.refresh)

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        self.list_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.list_frame.grid_columnconfigure(0, weight=2)  # Nom
        self.list_frame.grid_columnconfigure(1, weight=2)  # ICE
        self.list_frame.grid_columnconfigure(2, weight=3)  # Adresse
        self.list_frame.grid_columnconfigure(3, weight=3)  # Service
        self.list_frame.grid_columnconfigure(4, weight=2)  # Prix
        self.list_frame.grid_columnconfigure(5, weight=2)  # actions

        headers = ["Nom", "ICE", "Adresse", "Service", "Montant", ""]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.list_frame, text=h, font=body_font(12, "bold"),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=0, column=i, sticky="w", padx=8, pady=(0, 10))

    def _render_one_client(self, c, row):
        """Render a single client row into the list grid."""
        name_cell = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        name_cell.grid(row=row, column=0, sticky="w", padx=8, pady=6)
        avatar_badge(name_cell, c["name"], size=28, font_size=11).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(name_cell, text=c["name"], font=body_font(13, "bold"),
                     text_color=COLORS["text"]).pack(side="left")

        ctk.CTkLabel(self.list_frame, text=c["ice"] or "-", font=body_font(12),
                     text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=1, sticky="w", padx=8, pady=6)
        ctk.CTkLabel(self.list_frame, text=c["address"] or "-", font=body_font(12),
                     text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=2, sticky="w", padx=8, pady=6)
        ctk.CTkLabel(self.list_frame, text=c.get("service_names") or "-", font=body_font(12),
                     text_color=COLORS["text_muted"], anchor="w", wraplength=200, justify="left").grid(row=row, column=3, sticky="w", padx=8, pady=6)
        ctk.CTkLabel(self.list_frame, text=format_price_dh(c.get("total_price", 0)), font=body_font(12, "bold"),
                     text_color=COLORS["text"], anchor="w").grid(row=row, column=4, sticky="w", padx=8, pady=6)

        actions = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        actions.grid(row=row, column=5, sticky="e", padx=8, pady=4)
        secondary_button(actions, "Modifier", lambda c=c: self.open_edit_dialog(c), width=90).pack(side="left", padx=4)
        danger_button(actions, "Suppr.", lambda c=c: self.confirm_delete(c), width=70).pack(side="left", padx=4)

    def refresh(self):
        for w in self.list_frame.winfo_children()[6:]:
            w.destroy()

        clients = db.list_clients(self.search_var.get().strip())
        if not clients:
            empty = ctk.CTkLabel(self.list_frame, text="Aucun client. Cliquez sur \"+ Nouveau client\" pour commencer.",
                                  font=body_font(13), text_color=COLORS["text_muted"])
            empty.grid(row=1, column=0, columnspan=6, sticky="w", padx=8, pady=20)
            return

        CHUNK = 25

        def render_chunk(start):
            for idx in range(start, min(start + CHUNK, len(clients))):
                self._render_one_client(clients[idx], idx + 1)
            if start + CHUNK < len(clients):
                self.list_frame.after(0, lambda: render_chunk(start + CHUNK))

        render_chunk(0)

    def open_new_dialog(self):
        ClientFormDialog(self, self.refresh)

    def open_edit_dialog(self, client):
        ClientFormDialog(self, self.refresh, client=client)

    def confirm_delete(self, client):
        def do_delete():
            try:
                db.delete_client(client["id"])
                self.refresh()
            except ValueError as e:
                MessageDialog(self, "Suppression impossible", str(e), is_error=True)
        ConfirmDialog(self, f"Supprimer le client \"{client['name']}\" ?", do_delete)
