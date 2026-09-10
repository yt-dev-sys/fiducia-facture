"""Centralized application/user-data paths for Fiducia Facture."""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "FiduciaFacture"
USER_DATA_NAME = "Fiducia Facture"


def get_documents_dir() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"


def get_user_data_dir() -> Path:
    path = get_documents_dir() / USER_DATA_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_app_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local")
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_dir() -> Path:
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_update_dir() -> Path:
    path = get_app_data_dir() / "update"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir() -> Path:
    path = get_app_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_state_dir() -> Path:
    path = get_app_data_dir() / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_database_path() -> Path:
    return get_user_data_dir() / "facture_app.db"


def get_backup_dir() -> Path:
    path = get_user_data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_daily_backup_dir() -> Path:
    path = get_backup_dir() / "daily"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_manual_backup_dir() -> Path:
    path = get_backup_dir() / "manual"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_exports_dir() -> Path:
    path = get_user_data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_telegram_config_dir() -> Path:
    path = get_app_data_dir() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_telegram_token_path() -> Path:
    return get_telegram_config_dir() / "telegram_bot_token.txt"


def get_telegram_chat_id_path() -> Path:
    return get_telegram_config_dir() / "telegram_chat_id.txt"


def get_credentials_path() -> Path:
    # Legacy compatibility only; Google Drive is no longer used.
    return get_user_data_dir() / "credentials.json"


def get_token_path() -> Path:
    # Legacy compatibility only; Google Drive is no longer used.
    return get_user_data_dir() / "token.json"


def get_backup_state_path() -> Path:
    return get_state_dir() / "backup_state.json"


def get_legacy_data_dir() -> Path:
    """Legacy source-tree data directory used by pre-installer versions."""
    return Path(__file__).resolve().parent.parent / "data"


def migrate_legacy_user_files() -> None:
    """Copy legacy user files to Documents once, never deleting the source."""
    import shutil
    legacy = get_legacy_data_dir()
    if not legacy.exists():
        return
    target = get_user_data_dir()
    names = ("facture_app.db",)
    for name in names:
        src, dst = legacy / name, target / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)


def get_asset_path(filename: str) -> Path:
    """Get path to an asset file in the assets directory."""
    return Path(__file__).resolve().parent.parent / "assets" / filename
