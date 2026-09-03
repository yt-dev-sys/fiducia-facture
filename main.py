#!/usr/bin/env python3
"""Fiducia Facture desktop application entry point."""

import threading

from app.app_logger import install_global_exception_hook, log_info
from app.main_window import run_app


def _startup_services():
    # Secondary services are deliberately isolated from application startup.
    try:
        from app import telegram_backup
        telegram_backup.ensure_token_file()
        telegram_backup.maybe_backup_daily()
    except Exception as exc:
        from app.app_logger import log_exception
        log_exception("Service de sauvegarde au démarrage", exc)



if __name__ == "__main__":
    install_global_exception_hook()
    log_info("Application démarrée")
    threading.Thread(target=_startup_services, daemon=True).start()
    run_app()
