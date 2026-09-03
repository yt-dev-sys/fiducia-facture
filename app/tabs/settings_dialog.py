import customtkinter as ctk
from app import database as db
from app.theme import COLORS, body_font
from app.widgets import section_title, primary_button, secondary_button, labeled_entry, MessageDialog, bind_digits_only


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.title("Profil de l'entreprise")
        self.geometry("460x560")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()
        self.on_saved = on_saved

        profile = db.get_company_profile() or {}

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        section_title(scroll, "Profil de l'entreprise").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(scroll, text="Ces informations apparaissent sur toutes les factures.",
                     font=body_font(12), text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 14))

        self.name_var = ctk.StringVar(value=profile.get("name", ""))
        self.address_var = ctk.StringVar(value=profile.get("address", ""))
        self.ice_var = ctk.StringVar(value=profile.get("ice", ""))
        bind_digits_only(self.ice_var, max_len=15)
        self.if_var = ctk.StringVar(value=profile.get("if_number", ""))
        self.rc_var = ctk.StringVar(value=profile.get("rc", ""))
        self.patente_var = ctk.StringVar(value=profile.get("patente", ""))
        self.phone_var = ctk.StringVar(value=profile.get("phone", ""))
        self.email_var = ctk.StringVar(value=profile.get("email", ""))
        self.tva_var = ctk.StringVar(value=str(profile.get("default_tva_rate", 20.0)))
        self.cnss_var = ctk.StringVar(value=profile.get("cnss", ""))
        self.bank_details_var = ctk.StringVar(value=profile.get("bank_details", ""))

        pad = {"pady": (0, 10)}
        labeled_entry(scroll, "Nom / Raison sociale", self.name_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Adresse", self.address_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "ICE (15 chiffres)", self.ice_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Identifiant Fiscal (IF)", self.if_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Registre de Commerce (RC)", self.rc_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "N° Taxe Professionnelle (Patente)", self.patente_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Téléphone", self.phone_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Email", self.email_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Taux de TVA par défaut (%)", self.tva_var, width=100)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "CNSS", self.cnss_var)[0].pack(fill="x", **pad)
        labeled_entry(scroll, "Coordonnées bancaires (banque + RIB)", self.bank_details_var)[0].pack(fill="x", **pad)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=16)
        secondary_button(btn_frame, "Annuler", self.destroy, width=120).pack(side="left", padx=8)
        primary_button(btn_frame, "Enregistrer", self.save, width=140).pack(side="left", padx=8)

    def save(self):
        try:
            tva_rate = float(self.tva_var.get().replace(",", "."))
        except ValueError:
            MessageDialog(self, "Erreur", "Taux de TVA invalide.", is_error=True)
            return

        db.update_company_profile({
            "business_type": "company",
            "name": self.name_var.get(),
            "address": self.address_var.get(),
            "ice": self.ice_var.get(),
            "if_number": self.if_var.get(),
            "rc": self.rc_var.get(),
            "patente": self.patente_var.get(),
            "phone": self.phone_var.get(),
            "email": self.email_var.get(),
            "default_tva_rate": tva_rate,
            "cnss": self.cnss_var.get(),
            "bank_details": self.bank_details_var.get(),
        })
        self.destroy()
        if self.on_saved:
            self.on_saved()
