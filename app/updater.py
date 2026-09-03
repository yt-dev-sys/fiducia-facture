"""Non-blocking GitHub Releases updater.

The installed application never needs Git. It talks to GitHub over HTTPS and
hands the verified installer to Windows/Inno Setup. A public release feed is
required unless a future private update gateway is configured.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app.app_logger import log_exception, log_info
from app.app_paths import get_update_dir, get_state_dir
from app.version import APP_VERSION, GITHUB_OWNER, GITHUB_REPOSITORY, github_releases_url

CHECK_INTERVAL_HOURS = 24
USER_AGENT = "FiduciaFacture-Updater/1.0"


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    name: str
    body: str
    installer_url: str
    installer_name: str
    checksum_url: Optional[str]


def _version_tuple(value: str):
    value = value.strip().lstrip("vV").split("+")[0]
    value = value.split("-")[0]
    parts = value.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Version invalide: {value}")
    return tuple(int(p) for p in parts)


def is_newer(version: str) -> bool:
    try:
        return _version_tuple(version) > _version_tuple(APP_VERSION)
    except ValueError:
        return False


def _request_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_latest_release() -> Optional[ReleaseInfo]:
    if GITHUB_OWNER.startswith("YOUR_") or GITHUB_REPOSITORY.startswith("YOUR_"):
        return None
    data = _request_json(github_releases_url())
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name", "")
    version = tag.lstrip("vV")
    if not is_newer(version):
        return None

    assets = data.get("assets") or []
    installer = next((a for a in assets if str(a.get("name", "")).lower().endswith(".exe")), None)
    if not installer:
        return None
    checksum = next((a for a in assets if str(a.get("name", "")).lower().endswith(".sha256")), None)
    return ReleaseInfo(
        version=version,
        tag_name=tag,
        name=data.get("name") or tag,
        body=data.get("body") or "",
        installer_url=installer["browser_download_url"],
        installer_name=installer["name"],
        checksum_url=checksum.get("browser_download_url") if checksum else None,
    )


def _download(url: str, destination: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response, open(destination, "wb") as out:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)


def _verify_sha256(installer: Path, checksum_url: str) -> bool:
    expected_text = _read_text(checksum_url).strip()
    expected_match = re.search(r"\b([0-9a-fA-F]{64})\b", expected_text)
    if not expected_match:
        return False
    expected = expected_match.group(1).lower()
    digest = hashlib.sha256()
    with open(installer, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower() == expected


def download_and_verify(release: ReleaseInfo) -> Path:
    update_dir = get_update_dir()
    for old in update_dir.glob("FiduciaFacture-Setup-*"):
        try:
            old.unlink()
        except OSError:
            pass
    installer = update_dir / release.installer_name
    _download(release.installer_url, installer)
    if not release.checksum_url:
        # Never install an unverified binary. Publishing releases should always
        # include a .sha256 file; if one is missing, refuse the auto-update
        # rather than silently installing an unverified .exe.
        installer.unlink(missing_ok=True)
        raise RuntimeError(
            "La mise à jour n'a pas de fichier de vérification SHA-256 publié. "
            "Installation automatique annulée par sécurité."
        )
    if not _verify_sha256(installer, release.checksum_url):
        installer.unlink(missing_ok=True)
        raise RuntimeError("La vérification SHA-256 du programme téléchargé a échoué.")
    return installer


def launch_installer(installer: Path) -> None:
    # Inno Setup handles waiting for the current process to exit. Passing /CLOSEAPPLICATIONS
    # lets it close the running app cleanly while leaving Documents untouched.
    subprocess.Popen([str(installer), "/CLOSEAPPLICATIONS"], close_fds=True)


def prepare_update(release: ReleaseInfo) -> Path:
    installer = download_and_verify(release)
    log_info(f"Mise à jour {release.version} téléchargée et vérifiée.")
    return installer


def _auto_check_allowed() -> bool:
    state_file = get_state_dir() / "update_check.json"
    try:
        data = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
        import time
        return time.time() - float(data.get("last_check", 0)) >= CHECK_INTERVAL_HOURS * 3600
    except Exception:
        return True


def _mark_checked() -> None:
    import time
    state_file = get_state_dir() / "update_check.json"
    state_file.write_text(json.dumps({"last_check": time.time()}), encoding="utf-8")


def check_in_background(on_available: Callable[[ReleaseInfo], None], on_error: Optional[Callable[[Exception], None]] = None, force=False):
    try:
        if not force and not _auto_check_allowed():
            return
        _mark_checked()
        release = fetch_latest_release()
        if release:
            on_available(release)
    except Exception as exc:
        log_exception("Vérification des mises à jour", exc)
        if on_error:
            on_error(exc)
