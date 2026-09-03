"""Safe local + Telegram backups for Fiducia Facture.

The bot token is deliberately stored outside the installation directory so an
application update never replaces it. No Telegram credentials are committed
in the public source tree.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import ssl
import certifi
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.app_logger import log_info, log_exception
from app.app_paths import (
    get_database_path,
    get_daily_backup_dir,
    get_manual_backup_dir,
    get_backup_state_path,
    get_telegram_token_path,
    get_telegram_chat_id_path,
)

DB_PATH = get_database_path()
STATE_PATH = get_backup_state_path()
TOKEN_PATH = get_telegram_token_path()
CHAT_ID_PATH = get_telegram_chat_id_path()
BACKUP_INTERVAL_DAYS = 1
DAILY_RETENTION = 7
TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024
API_BASE = "https://api.telegram.org"
SSL_CONTEXT = ssl.create_default_context(
    cafile=certifi.where()
)


def token_present() -> bool:
    return bool(_read_token())


def is_connected() -> bool:
    return token_present() and _read_chat_id() is not None


def _read_token() -> str:
    try:
        return TOKEN_PATH.read_text(encoding="utf-8").strip() if TOKEN_PATH.exists() else ""
    except OSError:
        return ""


def _read_chat_id() -> Optional[int]:
    try:
        raw = CHAT_ID_PATH.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except (OSError, ValueError):
        return None


def _write_chat_id(chat_id: int) -> None:
    CHAT_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHAT_ID_PATH.write_text(str(chat_id), encoding="utf-8")


def ensure_token_file() -> Path:
    """Create the blank developer-managed token file without overwriting it."""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TOKEN_PATH.exists():
        TOKEN_PATH.write_text("", encoding="utf-8")
    return TOKEN_PATH


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_last_backup_at():
    return _load_state().get("last_backup_at")


def _set_last_backup_at(iso_dt: str) -> None:
    state = _load_state()
    state["last_backup_at"] = iso_dt
    state["last_successful_backup"] = iso_dt
    _save_state(state)


def _api(method: str, params: Optional[dict] = None, timeout: int = 20) -> dict:
    token = _read_token()
    if not token:
        raise RuntimeError(f"Token Telegram vide. Ajoutez votre token dans : {TOKEN_PATH}")

    url = f"{API_BASE}/bot{token}/{method}"
    data = None
    headers = {"User-Agent": "FiduciaFacture/1.0"}

    if params:
        encoded = urllib.parse.urlencode(params).encode("utf-8")
        data = encoded
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
            context=SSL_CONTEXT,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Telegram HTTP {exc.code}: {body[:300]}"
        ) from exc

    except urllib.error.URLError as exc:
        reason = exc.reason

        if isinstance(reason, ssl.SSLError):
            raise RuntimeError(
                f"Erreur SSL Telegram upload : {reason!r} | "
                f"reason={getattr(reason, 'reason', None)!r} | "
                f"verify_code={getattr(reason, 'verify_code', None)!r} | "
                f"verify_message={getattr(reason, 'verify_message', None)!r}"
            ) from exc

        raise RuntimeError(
            f"Envoi Telegram impossible : {reason!r}"
        ) from exc

    if not payload.get("ok"):
        raise RuntimeError(
            payload.get("description", "Telegram a refusé la requête.")
        )

    return payload


def _api_upload_document(chat_id: int, path: Path, caption: str) -> dict:
    token = _read_token()
    if not token:
        raise RuntimeError(f"Token Telegram vide. Ajoutez votre token dans : {TOKEN_PATH}")
    boundary = "----FiduciaFactureBoundary"
    body = bytearray()

    def field(name: str, value: str):
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    field("chat_id", str(chat_id))
    field("disable_notification", "true")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="document"; filename="{path.name}"\r\n'
        "Content-Type: application/zip\r\n\r\n".encode()
    )
    body.extend(path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    url = f"{API_BASE}/bot{token}/sendDocument"
    request = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "User-Agent": "FiduciaFacture/1.0",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=90,
            context=SSL_CONTEXT,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Envoi Telegram impossible : {exc.reason}") from exc
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "Telegram a refusé le fichier."))
    return payload


def get_bot_info() -> dict:
    return _api("getMe").get("result", {})


def discover_chat() -> int:
    """Find the first private chat that sent /start to this bot.

    The app uses short polling instead of a webhook, so the father does not
    need a public server or any router configuration.
    """
    current = _load_state()
    offset = int(current.get("telegram_update_offset", 0))
    result = _api("getUpdates", {"offset": offset, "timeout": 1, "allowed_updates": json.dumps(["message"])}, timeout=5)
    updates = result.get("result", [])
    latest_offset = offset
    for update in updates:
        latest_offset = max(latest_offset, int(update.get("update_id", 0)) + 1)
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") == "private":
            text = (message.get("text") or "").strip().lower()
            if text.startswith("/start"):
                chat_id = int(chat["id"])
                _write_chat_id(chat_id)
                current["telegram_update_offset"] = latest_offset
                _save_state(current)
                return chat_id
    if latest_offset != offset:
        current["telegram_update_offset"] = latest_offset
        _save_state(current)
    raise RuntimeError("Aucun /start reçu. Ouvrez le bot Telegram et envoyez-lui /start, puis réessayez.")


def connect() -> str:
    """Validate the token and discover the father's private chat."""
    ensure_token_file()
    bot = get_bot_info()
    try:
        chat_id = discover_chat()
    except RuntimeError as exc:
        # A valid token with no /start yet is a normal setup state.
        if "Aucun /start" in str(exc):
            return f"Bot @{bot.get('username', 'inconnu')} reconnu. Envoyez /start au bot puis cliquez à nouveau sur Connecter."
        raise
    _api("sendMessage", {"chat_id": chat_id, "text": "✅ Fiducia Facture est connecté. Les sauvegardes automatiques seront envoyées ici."})
    log_info(f"Connexion Telegram réussie avec le chat {chat_id}.")
    return f"Telegram connecté avec @{bot.get('username', 'bot')} ."


def _safe_sqlite_snapshot(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    temp.unlink(missing_ok=True)
    # timeout: back off and retry instead of immediately raising "database is
    # locked" if this runs at the same moment as a UI write.
    source = sqlite3.connect(str(DB_PATH), timeout=10)
    target = sqlite3.connect(str(temp), timeout=10)
    try:
        source.backup(target)
        result = target.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"Vérification SQLite échouée : {result}")
        target.close()
        source.close()
        temp.replace(destination)
    except Exception:
        try:
            target.close()
        except Exception:
            pass
        try:
            source.close()
        except Exception:
            pass
        temp.unlink(missing_ok=True)
        raise


def _retain_daily_backups() -> None:
    files = sorted(get_daily_backup_dir().glob("facture_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[DAILY_RETENTION:]:
        try:
            old.unlink()
        except OSError:
            pass


def create_local_backup(manual: bool = False) -> Path:
    if not DB_PATH.exists():
        raise FileNotFoundError("Base de données introuvable, rien à sauvegarder.")
    folder = get_manual_backup_dir() if manual else get_daily_backup_dir()
    stamp = datetime.now().strftime("%Y-%m-%d_%Hh%M%S")
    path = folder / f"facture_{stamp}.db"
    _safe_sqlite_snapshot(path)
    if not manual:
        _retain_daily_backups()
    return path


def _make_backup_archive(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%Hh%M%S")
    archive = Path(tempfile.gettempdir()) / f"facture-backup-{stamp}.zip"
    metadata = {
        "application": "Fiducia Facture",
        "backup_at": datetime.now().isoformat(timespec="seconds"),
        "database_schema": _read_schema_version(db_path),
        "database_file": db_path.name,
    }
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, arcname="facture_app.db")
        zf.writestr("backup-info.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    return archive


def _read_schema_version(db_path: Path) -> int:
    try:
        conn = sqlite3.connect(str(db_path), timeout=10)
        row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
        conn.close()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def backup_now(interactive: bool = True, keep_local: bool = True, manual: bool = False) -> str:
    if not token_present():
        ensure_token_file()
        raise RuntimeError(f"Token Telegram vide. Ajoutez votre token dans : {TOKEN_PATH}")
    chat_id = _read_chat_id()
    if chat_id is None:
        connect()
        chat_id = _read_chat_id()
    if chat_id is None:
        raise RuntimeError("Telegram n'est pas encore connecté. Envoyez /start au bot.")

    local_path = create_local_backup(manual=manual)
    archive = _make_backup_archive(local_path)
    try:
        size = archive.stat().st_size
        if size > TELEGRAM_FILE_LIMIT:
            raise RuntimeError(f"La sauvegarde compressée fait {size / 1024 / 1024:.1f} Mo, au-dessus de la limite Telegram de 50 Mo.")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        caption = f"📦 Fiducia Facture — sauvegarde du {stamp}\nTaille : {size / 1024:.0f} Ko"
        result = _api_upload_document(chat_id, archive, caption)
        _set_last_backup_at(datetime.now().isoformat())
        message = result.get("result", {})
        log_info(f"Sauvegarde Telegram réussie : {message.get('message_id', 'inconnu')}")
        return archive.name
    finally:
        archive.unlink(missing_ok=True)


def maybe_backup_daily() -> None:
    """Silent daily backup. Never blocks application startup."""
    try:
        if not is_connected():
            return
        last = get_last_backup_at()
        if last:
            try:
                if datetime.now().date() == datetime.fromisoformat(last).date():
                    return
            except ValueError:
                pass
        backup_now(interactive=False, manual=False)
    except Exception as exc:
        log_exception("Sauvegarde Telegram automatique", exc)


def maybe_backup_weekly():
    return maybe_backup_daily()
