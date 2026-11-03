import threading
import customtkinter as ctk
from app import updater
from app.app_logger import log_exception
from app.theme import COLORS, body_font, heading_font
from app.widgets import MessageDialog


def _mb(n):
    return f"{n / (1024 * 1024):.1f}".replace(".", ",")


class UpdateProgressDialog(ctk.CTkToplevel):
    """Shown while a new version is downloaded and verified.

    The download runs in a worker thread that only writes plain values into
    self._state; the window itself polls them from the Tk thread (Tk widgets are
    never touched from the worker). When the installer is ready, on_ready(path)
    is called on the Tk thread."""

    def __init__(self, master, release, on_ready):
        super().__init__(master)
        self.release = release
        self.on_ready = on_ready
        self._state = {"status": "Préparation…", "done": 0, "total": None, "result": None, "error": None}
        self._indeterminate = False

        self.title("Mise à jour")
        self.geometry("460x250")
        self.configure(fg_color=COLORS["white"])
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # cannot be closed mid-download
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text=f"Mise à jour vers la version {release.version}", font=heading_font(17),
                     text_color=COLORS["text"], anchor="w").pack(fill="x", padx=28, pady=(26, 4))
        self.status_label = ctk.CTkLabel(self, text=self._state["status"], font=body_font(13),
                                         text_color=COLORS["text_muted"], anchor="w")
        self.status_label.pack(fill="x", padx=28, pady=(0, 14))

        self.bar = ctk.CTkProgressBar(self, height=14, corner_radius=7,
                                      progress_color=COLORS["baby_blue_deep"], fg_color=COLORS["bg_soft"])
        self.bar.set(0)
        self.bar.pack(fill="x", padx=28)
        self.detail_label = ctk.CTkLabel(self, text="", font=body_font(12), text_color=COLORS["text_muted"], anchor="w")
        self.detail_label.pack(fill="x", padx=28, pady=(8, 0))

        ctk.CTkLabel(self, text="Veuillez patienter. Une fois le téléchargement terminé, l'application "
                                "se fermera et l'assistant d'installation s'ouvrira.",
                     font=body_font(11), text_color=COLORS["text_muted"], wraplength=400,
                     justify="left", anchor="w").pack(fill="x", padx=28, pady=(16, 0))

        threading.Thread(target=self._worker, daemon=True).start()
        self.after(100, self._poll)

    # ---- worker thread (no Tk calls in here) ----
    def _on_progress(self, done, total):
        self._state["done"], self._state["total"] = done, total

    def _on_status(self, text):
        self._state["status"] = text

    def _worker(self):
        try:
            self._state["result"] = updater.prepare_update(self.release, self._on_progress, self._on_status)
        except Exception as exc:
            log_exception("Téléchargement de la mise à jour", exc)
            self._state["error"] = exc

    # ---- Tk thread ----
    def _poll(self):
        st = self._state
        self.status_label.configure(text=st["status"])

        if st["total"]:
            if self._indeterminate:
                self.bar.stop()
                self.bar.configure(mode="determinate")
                self._indeterminate = False
            fraction = min(1.0, st["done"] / st["total"])
            self.bar.set(fraction)
            self.detail_label.configure(
                text=f"{_mb(st['done'])} / {_mb(st['total'])} Mo  —  {int(fraction * 100)} %")
        elif st["done"] and not st["result"]:
            if not self._indeterminate:  # server did not announce a size
                self.bar.configure(mode="indeterminate")
                self.bar.start()
                self._indeterminate = True
            self.detail_label.configure(text=f"{_mb(st['done'])} Mo téléchargés")

        if st["error"] is not None:
            self.destroy()
            MessageDialog(self.master, "Mise à jour",
                          "La mise à jour n'a pas pu être préparée. Votre version actuelle reste intacte.",
                          is_error=True)
            return
        if st["result"] is not None:
            if self._indeterminate:
                self.bar.stop()
                self.bar.configure(mode="determinate")
            self.bar.set(1.0)
            self.status_label.configure(text="Lancement de l'installation…")
            self.detail_label.configure(text="100 %")
            self.after(700, lambda: self._finish(st["result"]))
            return
        self.after(100, self._poll)

    def _finish(self, installer):
        self.destroy()
        self.on_ready(installer)
