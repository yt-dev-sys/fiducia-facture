"""Draws the company signature (transparent PNG) onto generated PDFs."""

import os
from reportlab.lib.utils import ImageReader

SIGNATURE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "signature.png")

_SIGNATURE_RATIO = None  # width / height of the PNG, read once


def draw_signature(c, right_x, bottom_y, height):
    """Draw the signature with its bottom-right corner at (right_x, bottom_y).
    Silently does nothing if the image is missing, so PDFs still generate."""
    global _SIGNATURE_RATIO
    if not os.path.exists(SIGNATURE_PATH):
        return
    try:
        img = ImageReader(SIGNATURE_PATH)
        if _SIGNATURE_RATIO is None:
            w, h = img.getSize()
            _SIGNATURE_RATIO = w / h
        width = height * _SIGNATURE_RATIO
        c.drawImage(img, right_x - width, bottom_y, width=width, height=height,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass
