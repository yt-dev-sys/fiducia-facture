import threading
import customtkinter as ctk
from app import database as db
from app.theme import COLORS, apply_theme, heading_font, body_font
from app.tabs.dashboard_tab import DashboardTab
from app.tabs.clients_tab import ClientsTab
from app.tabs.services_tab import ServicesTab
from app.tabs.list_sf_tab import ListSFTab
from app.tabs.factures_tab import FacturesTab
from app.tabs.payment_tab import PaymentTab
from app.tabs.editions_tab import EditionsTab
from app.tabs.settings_dialog import SettingsDialog
from app.tabs.app_settings_dialog import AppSettingsDialog
from app.widgets import ConfirmDialog, MessageDialog
from app import updater
from app import telegram_backup
from app.app_logger import log_exception, log_info

NAV_ITEMS = [
    ("Dashboard", "🏠"),
    ("Clients", "👥"),
    ("Services", "🧰"),
    ("List SF", "📝"),
    ("Factures", "🧾"),
    ("Payment", "💳"),
    ("Editions", "📑"),
]


class FactureApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        apply_theme()
        db.init_db()

        self.title("Fiducia Facture")
        self.geometry("1150x720")
        self.minsize(950, 600)
        self.resizable(True, True)
        self.configure(fg_color=COLORS["bg"])

        self.nav_buttons = {}
        self.nav_indicators = {}
        self.tab_frames = {}
        self.current_tab = "Dashboard"

        root = ctk.CTkFrame(self, fg_color=COLORS["bg"])
        root.pack(fill="both", expand=True)

        self._build_sidebar(root)
        self._build_content(root)
        self.select_tab("Dashboard")
        self._setup_text_selection()
        self.after(1200, self._check_updates_automatically)
        self.after(1500, self._start_daily_telegram_backup)

    def _build_sidebar(self, root):
        sidebar = ctk.CTkFrame(root, fg_color=COLORS["sidebar_bg"], width=210, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = ctk.CTkLabel(sidebar, text="🧾 Fiducia Facture", font=heading_font(16),
                              text_color=COLORS["text"], anchor="w")
        brand.pack(fill="x", padx=20, pady=(24, 24))

        ctk.CTkLabel(sidebar, text="GENERAL", font=body_font(11, "bold"),
                     text_color=COLORS["text_muted"], anchor="w").pack(fill="x", padx=20, pady=(0, 8))

        for name, icon in NAV_ITEMS:
            self._build_nav_row(sidebar, name, icon)

        divider = ctk.CTkFrame(sidebar, fg_color=COLORS["border"], height=1)
        divider.pack(fill="x", padx=20, pady=16)

        self._build_nav_row(sidebar, "Profil entreprise", "⚙", on_click=self.open_settings)
        self._build_nav_row(sidebar, "Paramètres", "🛠", on_click=self.open_app_settings)

    def _build_nav_row(self, sidebar, name, icon, on_click=None):
        row = ctk.CTkFrame(sidebar, fg_color="transparent", height=40)
        row.pack(fill="x", padx=(0, 12), pady=2)
        row.pack_propagate(False)

        indicator = ctk.CTkFrame(row, fg_color="transparent", width=4)
        indicator.pack(side="left", fill="y")
        self.nav_indicators[name] = indicator

        command = on_click if on_click else (lambda n=name: self.select_tab(n))
        btn = ctk.CTkButton(
            row, text=f"  {icon}   {name}", command=command, anchor="w",
            fg_color="transparent", hover_color=COLORS["sidebar_active_bg"],
            text_color=COLORS["text_muted"], corner_radius=8, font=body_font(13),
            height=36
        )
        btn.pack(side="left", fill="both", expand=True, padx=(8, 0))
        if not on_click:
            self.nav_buttons[name] = btn

    def _build_content(self, root):
        content = ctk.CTkFrame(root, fg_color=COLORS["bg"], corner_radius=0)
        content.pack(side="left", fill="both", expand=True)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.dashboard_tab = DashboardTab(content)
        self.clients_tab = ClientsTab(content)
        self.services_tab = ServicesTab(content)
        self.list_sf_tab = ListSFTab(content)
        self.factures_tab = FacturesTab(content)
        self.payment_tab = PaymentTab(content)
        self.editions_tab = EditionsTab(content)

        self.tab_frames = {
            "Dashboard": self.dashboard_tab,
            "Clients": self.clients_tab,
            "Services": self.services_tab,
            "List SF": self.list_sf_tab,
            "Factures": self.factures_tab,
            "Payment": self.payment_tab,
            "Editions": self.editions_tab,
        }
        for frame in self.tab_frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

    def _setup_text_selection(self):
        """Enable text copying via right-click context menu on any widget."""
        import tkinter as tk

        self._copy_menu = tk.Menu(self, tearoff=0)
        self._copy_menu.add_command(label="Copier", command=self._copy_widget_text)
        self._last_clicked_widget = None

        def on_right_click(event):
            widget = event.widget
            self._last_clicked_widget = widget
            try:
                self._copy_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._copy_menu.grab_release()

        def on_left_click(event):
            self._last_clicked_widget = event.widget

        self.bind_all("<Button-3>", on_right_click)
        self.bind_all("<Button-1>", on_left_click)

    def _copy_widget_text(self):
        """Copy text from the last right-clicked widget to clipboard."""
        widget = self._last_clicked_widget
        if widget is None:
            return
        text = None
        try:
            # CTkLabel / CTkButton / CTkEntry
            if hasattr(widget, "cget"):
                try:
                    text = widget.cget("text")
                except Exception:
                    pass
            # tk.Text / tk.Entry
            if not text:
                try:
                    text = widget.selection_get()
                except Exception:
                    pass
            if not text:
                try:
                    text = widget.get("1.0", "end-1c")
                except Exception:
                    pass
            if not text:
                try:
                    text = widget.get()
                except Exception:
                    pass
        except Exception:
            pass
        if text and text.strip():
            self.clipboard_clear()
            self.clipboard_append(text.strip())

    def select_tab(self, name):
        # Reset client search when leaving Clients tab — just clear the var,
        # no DB refresh here; the next time Clients is visited, refresh() loads the full list.
        if name != "Clients" and hasattr(self, "clients_tab"):
            self.clients_tab.search_var.set("")

        self.current_tab = name
        for item_name, btn in self.nav_buttons.items():
            active = item_name == name
            btn.configure(
                fg_color=COLORS["sidebar_active_bg"] if active else "transparent",
                text_color=COLORS["baby_blue_deep"] if active else COLORS["text_muted"],
                font=body_font(13, "bold" if active else "normal"),
            )
            self.nav_indicators[item_name].configure(
                fg_color=COLORS["baby_blue_deep"] if active else "transparent"
            )

        self.tab_frames[name].tkraise()

        # Defer data loading until after the frame is painted — the UI
        # shows the new tab instantly while the DB query runs right after.
        def _do_refresh():
            if name == "Dashboard":
                self.dashboard_tab.refresh()
            elif name == "Payment":
                self.payment_tab.refresh()
            elif name == "Factures":
                self.factures_tab.refresh()
            elif name == "List SF":
                self.list_sf_tab.refresh()
            elif name == "Editions":
                self.editions_tab.refresh()
            elif name == "Clients":
                self.clients_tab.refresh()

        self.after_idle(_do_refresh)

    def _start_daily_telegram_backup(self):
        """Initialize Telegram (if configured) and attempt one daily backup.

        This runs in a daemon thread so a slow/unavailable network never blocks
        the user interface or application startup.
        """
        def worker():
            try:
                if not telegram_backup.token_present():
                    telegram_backup.ensure_token_file()
                    return
                if not telegram_backup.is_connected():
                    # The user has to send /start once. If they already did,
                    # this discovers and stores the private chat ID.
                    telegram_backup.connect()
                telegram_backup.maybe_backup_daily()
            except Exception as exc:
                log_exception("Initialisation/sauvegarde Telegram quotidienne", exc)
        threading.Thread(target=worker, daemon=True).start()

    def _check_updates_automatically(self):
        def worker():
            try:
                updater.check_in_background(lambda release: self.after(0, lambda r=release: self._offer_update(r)))
            except Exception as exc:
                log_exception("Vérification automatique des mises à jour", exc)
        threading.Thread(target=worker, daemon=True).start()

    def _offer_update(self, release):
        if not self.winfo_exists():
            return
        ConfirmDialog(
            self,
            f"Une nouvelle version ({release.version}) de Fiducia Facture est disponible.\n\n"
            "Vous pouvez continuer à utiliser l'application si vous préférez mettre à jour plus tard.\n\n"
            "Installer maintenant ?",
            lambda: self._download_and_install_update(release),
        )

    def _download_and_install_update(self, release):
        def worker():
            try:
                installer = updater.prepare_update(release)
                log_info(f"Lancement de l'installateur {release.version}.")
                updater.launch_installer(installer)
                self.after(500, self.destroy)
            except Exception as exc:
                log_exception("Installation de la mise à jour", exc)
                self.after(0, lambda: MessageDialog(
                    self, "Mise à jour",
                    "La mise à jour n'a pas pu être préparée. Votre version actuelle reste intacte.",
                    is_error=True,
                ))
        threading.Thread(target=worker, daemon=True).start()

    def open_settings(self):
        SettingsDialog(self, on_saved=self._on_settings_saved)

    def _on_settings_saved(self):
        # Business type default may have changed; nothing else to refresh live.
        pass

    def open_app_settings(self):
        AppSettingsDialog(self)


def run_app():
    app = FactureApp()
    app.mainloop()
