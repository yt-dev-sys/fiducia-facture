import threading
from datetime import datetime
import customtkinter as ctk
from app.theme import COLORS, body_font
from app.widgets import section_title, primary_button, secondary_button, MessageDialog, ConfirmDialog
import app.telegram_backup as telegram_backup
from app.format_utils import format_date_fr
from app.version import APP_VERSION
from app import updater
from app.app_logger import log_exception


class AppSettingsDialog(ctk.CTkToplevel):
    """App-level settings: Telegram backup and application version / updates."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Paramètres")
        self.geometry("460x480")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.grab_set()

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["white"])
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        # ---------- Telegram backup ----------
        section_title(scroll, "Sauvegarde Telegram").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            scroll,
            text="Sauvegarde automatique quotidienne de la base de données.\n"
                 "Telegram est optionnel : l'application continue de fonctionner même sans connexion.",
            font=body_font(12), text_color=COLORS["text_muted"], justify="left"
        ).pack(anchor="w", pady=(0, 10))

        self.telegram_status_label = ctk.CTkLabel(scroll, text="", font=body_font(12, "bold"),
                                                text_color=COLORS["text"], anchor="w")
        self.telegram_status_label.pack(anchor="w", pady=(0, 10))
        self._refresh_telegram_status()

        telegram_btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        telegram_btn_frame.pack(anchor="w", pady=(0, 6))
        secondary_button(telegram_btn_frame, "Connecter Telegram", self.connect_telegram, width=220).pack(
            side="left", padx=(0, 8))
        primary_button(telegram_btn_frame, "Sauvegarder maintenant", self.backup_now, width=190).pack(side="left")

        # ---------- Application updates ----------
        divider = ctk.CTkFrame(scroll, fg_color=COLORS["border"], height=1)
        divider.pack(fill="x", pady=(16, 16))
        section_title(scroll, "Application").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(scroll, text=f"Version installée : {APP_VERSION}", font=body_font(12),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 10))
        secondary_button(scroll, "Rechercher une mise à jour", self.check_for_updates, width=220).pack(anchor="w", pady=(0, 10))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=16)
        secondary_button(btn_frame, "Fermer", self.destroy, width=140).pack(side="left", padx=8)

    def _refresh_telegram_status(self):
        if telegram_backup.is_connected():
            last = telegram_backup.get_last_backup_at()
            if last:
                dt = datetime.fromisoformat(last)
                text = f"✅ Connecté — dernière sauvegarde : {format_date_fr(dt.strftime('%Y-%m-%d'))} à {dt.strftime('%H:%M')}"
            else:
                text = "✅ Connecté — aucune sauvegarde effectuée pour l'instant"
            color = COLORS["success"]
        elif telegram_backup.token_present():
            text = "⚠ Token Telegram trouvé, mais chat non connecté"
            color = COLORS["warning"]
        else:
            text = "⚠ Telegram non connecté — les factures continuent de fonctionner normalement"
            color = COLORS["text_muted"]
        self.telegram_status_label.configure(text=text, text_color=color)

    def connect_telegram(self):
        def worker():
            try:
                telegram_backup.connect()
                self.after(0, self._on_telegram_success, "Telegram est connecté.")
            except Exception as e:
                self.after(0, self._on_telegram_error, f"Connexion échouée : {e}")
        threading.Thread(target=worker, daemon=True).start()

    def backup_now(self):
        def worker():
            try:
                name = telegram_backup.backup_now(interactive=True)
                self.after(0, self._on_telegram_success, f"Sauvegarde Telegram envoyée : {name}")
            except Exception as e:
                self.after(0, self._on_telegram_error, f"Sauvegarde échouée : {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _on_telegram_success(self, message):
        self._refresh_telegram_status()
        MessageDialog(self, "Telegram", message)

    def _on_telegram_error(self, message):
        self._refresh_telegram_status()
        MessageDialog(self, "Telegram", message, is_error=True)

    def check_for_updates(self):
        def worker():
            try:
                release = updater.fetch_latest_release()
                if not release:
                    self.after(0, lambda: MessageDialog(self, "Mise à jour", "Vous utilisez déjà la dernière version disponible."))
                    return
                self.after(0, lambda r=release: self._offer_update(r))
            except Exception as e:
                self.after(0, lambda: MessageDialog(self, "Mise à jour", "Impossible de vérifier les mises à jour pour le moment.", is_error=True))
        threading.Thread(target=worker, daemon=True).start()

    def _offer_update(self, release):
        ConfirmDialog(self, f"Une nouvelle version ({release.version}) est disponible.\n\nInstaller maintenant ?",
                      lambda: self._download_update(release))

    def _download_update(self, release):
        def worker():
            try:
                installer = updater.prepare_update(release)
                self.after(0, lambda: updater.launch_installer(installer))
                self.after(1000, self.master.destroy)
            except Exception as e:
                log_exception("Téléchargement de la mise à jour", e)
                self.after(0, lambda: MessageDialog(self, "Mise à jour", "La mise à jour n'a pas pu être préparée. Votre version actuelle reste intacte.", is_error=True))
        threading.Thread(target=worker, daemon=True).start()
