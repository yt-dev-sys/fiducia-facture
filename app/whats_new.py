"""One-time "Nouveautés" window shown the first time a new version is opened.

The text comes from app/assets/whats_new.txt, which you can edit freely before
each release: the first non-empty line is the window title, everything after it
is the body (any text, any length). Lines starting with '#' are ignored, so you
can leave notes to yourself. If the file is empty, nothing is shown.
"""
from __future__ import annotations

import json
import os
from typing import Optional, Tuple

from app.app_logger import log_exception
from app.app_paths import get_state_dir
from app.version import APP_VERSION

NOTES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "whats_new.txt")
_STATE_FILE = "last_seen_version.json"


def load_notes() -> Optional[Tuple[str, str]]:
    """Returns (title, body) from whats_new.txt, or None if there is nothing to show."""
    try:
        with open(NOTES_PATH, "r", encoding="utf-8-sig") as f:
            lines = [ln.rstrip() for ln in f.read().splitlines() if not ln.lstrip().startswith("#")]
    except OSError:
        return None
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return None
    title = lines[0].strip()
    body = "\n".join(lines[1:]).strip()
    if not body:
        return None
    return title, body


def _read_last_seen() -> Optional[str]:
    path = get_state_dir() / _STATE_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("version")
    except Exception:
        return None


def mark_seen() -> bool:
    """Mark current version as seen. Returns True on success, False on failure."""
    try:
        state_dir = get_state_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / _STATE_FILE).write_text(json.dumps({"version": APP_VERSION}), encoding="utf-8")
        return True
    except Exception as exc:
        log_exception("Enregistrement de la version vue", exc)
        return False


def pending_notes() -> Optional[Tuple[str, str]]:
    """Notes to show now (first launch of this version), or None. Does not mark them as seen."""
    if _read_last_seen() == APP_VERSION:
        return None
    return load_notes()


def is_new_version() -> bool:
    return _read_last_seen() != APP_VERSION


def show_if_needed(parent) -> bool:
    """
    Show the whats-new dialog if this version hasn't been seen yet.
    Returns True if dialog was shown, False otherwise.
    """
    notes = pending_notes()
    if not notes:
        return False
    # Only mark as seen if we're actually going to show the dialog
    if mark_seen():
        from app.tabs.whats_new_dialog import WhatsNewDialog
        WhatsNewDialog(parent, *notes)
        return True
    return False
