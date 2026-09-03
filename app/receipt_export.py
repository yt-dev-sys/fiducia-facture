"""
Generates a payment receipt ("Reçu") PDF, matching the paper template provided:
a bordered slip with Date / Reçu de / La somme de / Pour fields. Currency shown as DH.
"""

import os
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app import database as db
from app.format_utils import format_price_dh, format_date_fr

PAGE_W = 190 * mm
PAGE_H = 85 * mm

BLACK = (0, 0, 0)

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.jpeg")


def generate_receipt_pdf(invoice_id: int, payment_date: str, output_path: str):
    """Builds the payment receipt PDF for the given invoice and writes it to output_path."""
    inv = db.get_invoice(invoice_id)
    if inv is None:
        raise ValueError("Facture introuvable.")
    total_ttc, _, _ = db.compute_invoice_totals(inv)

    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    c.setFillColorRGB(*BLACK)
    c.setStrokeColorRGB(*BLACK)

    margin = 6 * mm
    c.setLineWidth(1.2)
    c.rect(margin, margin, PAGE_W - 2 * margin, PAGE_H - 2 * margin, fill=0, stroke=1)

    # ---------- Logo (top left) ----------
    if os.path.exists(LOGO_PATH):
        try:
            logo_w, logo_h = 26 * mm, 17 * mm
            logo_x = margin + 4 * mm
            logo_y = PAGE_H - margin - 3 * mm - logo_h
            c.drawImage(ImageReader(LOGO_PATH), logo_x, logo_y, width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # ---------- Title ----------
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - margin - 8 * mm, "Reçu")

    y = PAGE_H - margin - 17 * mm
    label_x = margin + 6 * mm
    value_x = margin + 32 * mm
    right_edge = PAGE_W - margin - 6 * mm

    # ---------- Date ----------
    c.setFont("Helvetica-Bold", 10.5)
    date_label_x = PAGE_W / 2 + 10 * mm
    c.drawString(date_label_x, y, "Date :")
    c.setFont("Helvetica", 10.5)
    date_value_x = date_label_x + 15 * mm
    c.drawString(date_value_x + 2 * mm, y, format_date_fr(payment_date))
    c.setLineWidth(0.6)
    c.line(date_value_x, y - 1.5 * mm, right_edge, y - 1.5 * mm)

    y -= 12 * mm

    # ---------- Reçu de (client name) ----------
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(label_x, y, "Reçu de :")
    c.setFont("Helvetica", 10.5)
    c.drawString(value_x + 2 * mm, y, inv["client_name"])
    c.line(value_x, y - 1.5 * mm, right_edge, y - 1.5 * mm)

    y -= 12 * mm

    # ---------- La somme de (montant) ----------
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(label_x, y, "La somme de :")
    c.setFont("Helvetica", 10.5)
    amount_text = f"{format_price_dh(total_ttc)}"
    c.drawString(value_x + 2 * mm, y, amount_text)
    c.line(value_x, y - 1.5 * mm, right_edge, y - 1.5 * mm)

    y -= 12 * mm

    # ---------- Pour facture numero : (numero de facture) ----------
    pour_label = "Pour facture numero :"
    pour_value_x = label_x + 50 * mm
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(label_x, y, pour_label)
    c.setFont("Helvetica", 10.5)
    c.drawString(pour_value_x + 2 * mm, y, inv["numero"])
    c.line(pour_value_x, y - 1.5 * mm, right_edge, y - 1.5 * mm)

    y -= 10 * mm
    c.setLineWidth(0.8)
    c.line(margin + 4 * mm, y, PAGE_W - margin - 4 * mm, y)

    c.showPage()
    c.save()
    return output_path
