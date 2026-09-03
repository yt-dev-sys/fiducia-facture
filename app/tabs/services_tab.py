import customtkinter as ctk
from app import database as db
from app.theme import COLORS, body_font
from app.widgets import section_title, primary_button, secondary_button, danger_button, ConfirmDialog, MessageDialog, labeled_entry


class ServiceFormDialog(ctk.CTkToplevel):
    def __init__(self, master, on_saved, service=None):
        super().__init__(master)
        self.title("Modifier service" if service else "Nouveau service")
        self.geometry("400x320")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()

        self.on_saved = on_saved
        self.service = service

        self.name_var = ctk.StringVar(value=service["name"] if service else "")
        self.description_var = ctk.StringVar(value=service["description"] if service else "")

        pad = {"padx": 24, "pady": (10, 0)}
        labeled_entry(self, "Nom du service *", self.name_var)[0].pack(fill="x", **pad)
        labeled_entry(self, "Description", self.description_var)[0].pack(fill="x", **pad)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=24)
        secondary_button(btn_frame, "Annuler", self.destroy, width=120).pack(side="left", padx=8)
        primary_button(btn_frame, "Enregistrer", self.save, width=140).pack(side="left", padx=8)

    def save(self):
        name = self.name_var.get().strip()
        if not name:
            MessageDialog(self, "Erreur", "Le nom du service est obligatoire.", is_error=True)
            return

        if self.service:
            db.update_service(self.service["id"], name, self.description_var.get())
        else:
            db.create_service(name, self.description_var.get())
        self.destroy()
        self.on_saved()


class ServicesTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        self.search_var = ctk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))
        section_title(header, "Services").pack(side="left")
        primary_button(header, "+ Nouveau service", self.open_new_dialog, width=170).pack(side="right")

        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=24, pady=(0, 10))
        search_entry = ctk.CTkEntry(
            search_frame, textvariable=self.search_var, placeholder_text="Rechercher un service...",
            width=320, fg_color=COLORS["bg_soft"], border_color=COLORS["border"], corner_radius=12
        )
        search_entry.pack(side="left")
        search_entry.bind("<KeyRelease>", lambda e: self.refresh())

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        self.list_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.list_frame.grid_columnconfigure(0, weight=3)
        self.list_frame.grid_columnconfigure(1, weight=5)
        self.list_frame.grid_columnconfigure(2, weight=2)

        headers = ["Nom", "Description", ""]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.list_frame, text=h, font=body_font(12, "bold"),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=0, column=i, sticky="w", padx=8, pady=(0, 10))

    def refresh(self):
        for w in self.list_frame.winfo_children()[3:]:
            w.destroy()

        services = db.list_services(self.search_var.get().strip())
        if not services:
            empty = ctk.CTkLabel(self.list_frame, text="Aucun service. Cliquez sur \"+ Nouveau service\" pour commencer.",
                                  font=body_font(13), text_color=COLORS["text_muted"])
            empty.grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=20)
            return

        for idx, s in enumerate(services):
            row = idx + 1
            ctk.CTkLabel(self.list_frame, text=s["name"], font=body_font(13, "bold"),
                         text_color=COLORS["text"], anchor="w").grid(row=row, column=0, sticky="w", padx=8, pady=6)
            ctk.CTkLabel(self.list_frame, text=s["description"] or "-", font=body_font(12),
                         text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=1, sticky="w", padx=8, pady=6)

            actions = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            actions.grid(row=row, column=2, sticky="e", padx=8, pady=4)
            secondary_button(actions, "Modifier", lambda s=s: self.open_edit_dialog(s), width=90).pack(side="left", padx=4)
            danger_button(actions, "Suppr.", lambda s=s: self.confirm_delete(s), width=70).pack(side="left", padx=4)

    def open_new_dialog(self):
        ServiceFormDialog(self, self.refresh)

    def open_edit_dialog(self, service):
        ServiceFormDialog(self, self.refresh, service=service)

    def confirm_delete(self, service):
        def do_delete():
            db.delete_service(service["id"])
            self.refresh()
        ConfirmDialog(self, f"Supprimer le service \"{service['name']}\" ?", do_delete)
