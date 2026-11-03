import customtkinter as ctk
from app import database as db
from app.theme import COLORS, body_font
from app.widgets import section_title, primary_button, secondary_button, danger_button, ConfirmDialog, MessageDialog, labeled_entry, bind_digits_only, avatar_badge, bind_search_debounce
from app.app_logger import log_exception


class ClientFormDialog(ctk.CTkToplevel):
    def __init__(self, master, on_saved, client=None, client_type="normal"):
        super().__init__(master)
        self.client_type = client_type
        self.title("Modifier client" if client else ("Nouveau client temporaire" if client_type == "temp" else "Nouveau client"))
        self.geometry("460x520")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()

        self.on_saved = on_saved
        self.client = client

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

        ctk.CTkFrame(scroll, fg_color="transparent", height=8).pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=16)
        secondary_button(btn_frame, "Annuler", self.destroy, width=120).pack(side="left", padx=8)
        primary_button(btn_frame, "Enregistrer", self.save, width=140).pack(side="left", padx=8)

    def save(self):
        name = self.name_var.get().strip()
        if not name:
            MessageDialog(self, "Erreur", "Le nom du client est obligatoire.", is_error=True)
            return

        try:
            if self.client:
                db.update_client(
                    self.client["id"], name,
                    address=self.address_var.get(), ice=self.ice_var.get(), if_number=self.if_var.get(),
                    phone=self.phone_var.get(), email=self.email_var.get()
                )
            else:
                db.create_client(
                    name,
                    address=self.address_var.get(), ice=self.ice_var.get(), if_number=self.if_var.get(),
                    phone=self.phone_var.get(), email=self.email_var.get(),
                    client_type=self.client_type
                )
            self.destroy()
            self.on_saved()
        except Exception as e:
            log_exception("Enregistrement client", e)
            MessageDialog(self, "Erreur", str(e), is_error=True)


class ClientsTab(ctk.CTkFrame):
    """Clients list. client_type 'normal' = the Clients tab, 'temp' = the Temp Client tab
    (identical, except temp clients are hidden automatically once all their invoices are paid)."""

    def __init__(self, master, client_type="normal"):
        super().__init__(master, fg_color=COLORS["bg"])
        self.client_type = client_type
        self.search_var = ctk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))

        section_title(header, "Temp Client" if self.client_type == "temp" else "Clients").pack(side="left")
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
        self.list_frame.grid_columnconfigure(0, weight=3)  # Nom
        self.list_frame.grid_columnconfigure(1, weight=3)  # ICE
        self.list_frame.grid_columnconfigure(2, weight=4)  # Adresse
        self.list_frame.grid_columnconfigure(3, weight=2)  # actions

        headers = ["Nom", "ICE", "Adresse", ""]
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

        actions = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        actions.grid(row=row, column=3, sticky="e", padx=8, pady=4)
        secondary_button(actions, "Modifier", lambda c=c: self.open_edit_dialog(c), width=90).pack(side="left", padx=4)
        danger_button(actions, "Suppr.", lambda c=c: self.confirm_delete(c), width=70).pack(side="left", padx=4)

    def refresh(self):
        for w in self.list_frame.winfo_children()[4:]:
            w.destroy()

        clients = db.list_clients(self.search_var.get().strip(), client_type=self.client_type)
        if not clients:
            empty_text = ("Aucun client temporaire. Cliquez sur \"+ Nouveau client\" pour commencer."
                          if self.client_type == "temp"
                          else "Aucun client. Cliquez sur \"+ Nouveau client\" pour commencer.")
            empty = ctk.CTkLabel(self.list_frame, text=empty_text,
                                  font=body_font(13), text_color=COLORS["text_muted"])
            empty.grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=20)
            return

        CHUNK = 25

        def render_chunk(start):
            for idx in range(start, min(start + CHUNK, len(clients))):
                self._render_one_client(clients[idx], idx + 1)
            if start + CHUNK < len(clients):
                self.list_frame.after(0, lambda: render_chunk(start + CHUNK))

        render_chunk(0)

    def open_new_dialog(self):
        ClientFormDialog(self, self.refresh, client_type=self.client_type)

    def open_edit_dialog(self, client):
        ClientFormDialog(self, self.refresh, client=client)

    def confirm_delete(self, client):
        def do_delete():
            try:
                db.hide_client(client["id"])
                self.refresh()
            except ValueError as e:
                MessageDialog(self, "Suppression impossible", str(e), is_error=True)
        ConfirmDialog(self, f"Supprimer le client \"{client['name']}\" ?\n\nIl sera masqué (recherche normale) mais "
                          "reste retrouvable dans Paramètres > Recherche.", do_delete)
