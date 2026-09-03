"""Centralized logging for Fiducia Facture."""
from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from app.app_paths import get_log_dir

LOG_PATH = str(get_log_dir() / "app.log")
_logger = logging.getLogger("fiducia_facture")
_logger.setLevel(logging.INFO)
_logger.propagate = False

if not _logger.handlers:
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    _logger.addHandler(handler)


def log_info(message: str):
    _logger.info(message)


def log_warning(message: str):
    _logger.warning(message)


def log_error(message: str):
    _logger.error(message)


def log_exception(context: str, exc: BaseException):
    _logger.error("%s: %s\n%s", context, exc, traceback.format_exc())


def install_global_exception_hook():
    def _hook(exc_type, exc_value, exc_tb):
        _logger.error("Exception non gérée: %s\n%s", exc_value, "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
