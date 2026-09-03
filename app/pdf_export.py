"""
Generates a PDF for an invoice, matching the company's official template
(logo, teal header, client block, item table, amount in words, totals, footer).
"""

import os
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app import database as db
from app.format_utils import (
    format_price_dh, format_date_fr, compute_echeance_date, amount_to_french_words_dh,
)

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.jpeg")

TEAL = (0x0F / 255, 0x76 / 255, 0x6D / 255)
GRAY = (0x50 / 255, 0x50 / 255, 0x50 / 255)
GRAY_LIGHT = (0x63 / 255, 0x63 / 255, 0x63 / 255)
BLACK = (0, 0, 0)
WHITE = (1, 1, 1)

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


def _set_color(c, rgb):
    c.setFillColorRGB(*rgb)


def generate_invoice_pdf(invoice_id: int, output_path: str):
    """Builds the PDF for the given invoice and writes it to output_path."""
    inv = db.get_invoice(invoice_id)
    if inv is None:
        raise ValueError("Facture introuvable.")
    profile = db.get_company_profile() or {}
    items = db.get_invoice_display_items(inv)

    business_type = inv["business_type"]
    tva_rate = inv["tva_rate"] if business_type == "company" else 0.0

    total_ttc, subtotal_ht, tva_amount = db.compute_invoice_totals(inv)

    echeance_iso = compute_echeance_date(inv["invoice_date"], inv.get("deadline") or "")

    c = canvas.Canvas(output_path, pagesize=A4)
    y = PAGE_H - MARGIN

    # ---------- Header: logo + company name/address ----------
    # Logo is stretched to match the fixed size used in the official docx template
    # (47.7mm x 30mm), not proportionally scaled from the source file's own ratio.
    logo_w = 47.7 * mm
    logo_h = 30 * mm
    if os.path.exists(LOGO_PATH):
        try:
            img = ImageReader(LOGO_PATH)
            c.drawImage(img, MARGIN, y - logo_h, width=logo_w, height=logo_h,
                        preserveAspectRatio=False, mask="auto")
            text_x = MARGIN + logo_w + 6 * mm
        except Exception:
            text_x = MARGIN
    else:
        text_x = MARGIN

    _set_color(c, GRAY)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(text_x, y - 9 * mm, (profile.get("address") or ""))

    # ---------- Header: "Facture" title + numero/date (right side) ----------
    # Lowered as a block so the Date line sits a line below the logo's lowest point.
    date_y = y - (logo_h + 8 * mm)
    numero_y = date_y + 7 * mm
    facture_y = numero_y + 9 * mm

    _set_color(c, TEAL)
    c.setFont("Helvetica-Bold", 22)
    c.drawRightString(PAGE_W - MARGIN, facture_y, "Facture")

    _set_color(c, BLACK)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(PAGE_W - MARGIN, numero_y, f"F° {inv['numero']}")
    _set_color(c, GRAY)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(PAGE_W - MARGIN, date_y, f"Date: {format_date_fr(inv['invoice_date'])}")

    y -= (logo_h + 8 * mm) + 8 * mm  # descend below the lowered Date line (the lowest header element)

    # ---------- Client block ----------
    _set_color(c, TEAL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN, y, "CLIENT:")
    y -= 6 * mm

    _set_color(c, BLACK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, inv["client_name"])
    y -= 5.5 * mm

    _set_color(c, GRAY_LIGHT)
    c.setFont("Helvetica", 9.5)
    if inv.get("client_ice"):
        c.drawString(MARGIN, y, f"ICE: {inv['client_ice']}")
        y -= 5 * mm
    if inv.get("client_address"):
        c.drawString(MARGIN, y, inv["client_address"])
        y -= 5 * mm

    y -= 4 * mm

    # ---------- Note ----------
    if inv.get("notes"):
        _set_color(c, BLACK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(MARGIN, y, f"Note : {inv['notes']}")
        y -= 10 * mm
    else:
        y -= 4 * mm

    # ---------- Items table (paginates if there are enough line items) ----------
    col_desc_x = MARGIN
    table_w = PAGE_W - 2 * MARGIN
    col1_w = table_w * 0.484   # Désignation
    col2_w = table_w * 0.277   # P.U TTC
    col3_w = table_w * 0.239   # Total TTC
    col_divider_1 = MARGIN + col1_w
    col_divider_2 = col_divider_1 + col2_w
    col_pu_x = col_divider_1 + col2_w / 2
    col_total_x = PAGE_W - MARGIN - 5 * mm
    row_h = 8 * mm
    header_h = 8 * mm

    # The totals box, amount-in-words/TVA lines, payment condition, and the
    # (fixed-position) footer all need room below the table's last row on
    # whichever page it ends on. If the table were allowed to run past this
    # point, that content would overlap or spill off the page.
    TABLE_BOTTOM_LIMIT = MARGIN + 70 * mm

    def draw_table_header(top_y):
        c.setFillColorRGB(*TEAL)
        c.rect(MARGIN, top_y - header_h, PAGE_W - 2 * MARGIN, header_h, fill=1, stroke=0)
        _set_color(c, WHITE)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(col_desc_x + 3 * mm, top_y - header_h + 2.8 * mm, "Désignation")
        c.drawCentredString(col_pu_x, top_y - header_h + 2.8 * mm, "P.U TTC")
        c.drawRightString(col_total_x, top_y - header_h + 2.8 * mm, "Total TTC")

    def draw_table_borders(top_y, bottom_y):
        c.setStrokeColorRGB(*TEAL)
        c.setLineWidth(0.4)
        ry = top_y - header_h
        while ry >= bottom_y - 0.01:
            c.line(MARGIN, ry, PAGE_W - MARGIN, ry)
            ry -= row_h
        c.line(col_divider_1, top_y, col_divider_1, bottom_y)
        c.line(col_divider_2, top_y, col_divider_2, bottom_y)
        c.setLineWidth(0.6)
        c.rect(MARGIN, bottom_y, PAGE_W - 2 * MARGIN, top_y - bottom_y, fill=0, stroke=1)

    rows = items if items else [{"description": "Aucun service assigné à ce client.", "price": 0}]

    page_table_top = y
    draw_table_header(page_table_top)
    row_y = page_table_top - header_h

    for idx, row in enumerate(rows):
        if row_y - row_h < TABLE_BOTTOM_LIMIT:
            # Close out this page's table, then continue the table on a new page.
            draw_table_borders(page_table_top, row_y)
            c.showPage()
            page_table_top = PAGE_H - MARGIN
            draw_table_header(page_table_top)
            row_y = page_table_top - header_h

        bg = (0.96, 0.99, 1.0) if idx % 2 == 0 else WHITE
        c.setFillColorRGB(*bg)
        c.rect(MARGIN, row_y - row_h, PAGE_W - 2 * MARGIN, row_h, fill=1, stroke=0)
        _set_color(c, BLACK)
        c.setFont("Helvetica", 9.5)
        c.drawString(col_desc_x + 3 * mm, row_y - row_h + 2.8 * mm, str(row["description"])[:70])
        c.drawCentredString(col_pu_x, row_y - row_h + 2.8 * mm, f"{row['price']:.2f}")
        c.drawRightString(col_total_x, row_y - row_h + 2.8 * mm, f"{row['price']:.2f}")
        row_y -= row_h

    table_bottom = row_y
    draw_table_borders(page_table_top, table_bottom)

    y = table_bottom - 3 * mm

    # ---------- TOTAL TTC box: right under the table, flush with its right edge ----------
    box_w = col2_w + col3_w
    box_h = 12 * mm
    box_x = PAGE_W - MARGIN - box_w
    c.setFillColorRGB(*TEAL)
    c.rect(box_x, y - box_h, box_w, box_h, fill=1, stroke=0)
    _set_color(c, WHITE)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(box_x + 4 * mm, y - box_h + 4 * mm, "TOTAL TTC:")
    c.drawRightString(box_x + box_w - 4 * mm, y - box_h + 4 * mm, format_price_dh(total_ttc))

    y -= box_h + 8 * mm

    # ---------- Amount in words + totals ----------
    totals_x_label = PAGE_W - MARGIN - 55 * mm
    totals_x_value = PAGE_W - MARGIN - 5 * mm

    _set_color(c, GRAY_LIGHT)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(MARGIN, y, "Arrêté le présent devis à la somme de :")

    if business_type == "company":
        c.drawString(totals_x_label, y, "Total HT:")
        c.setFont("Helvetica", 9)
        c.drawRightString(totals_x_value, y, format_price_dh(subtotal_ht))
    y -= 5.5 * mm

    _set_color(c, BLACK)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(MARGIN, y, amount_to_french_words_dh(total_ttc))

    if business_type == "company":
        _set_color(c, GRAY_LIGHT)
        c.setFont("Helvetica", 9)
        c.drawString(totals_x_label, y, f"Total TVA ({tva_rate:g}%):")
        c.drawRightString(totals_x_value, y, format_price_dh(tva_amount))
    y -= 6 * mm

    _set_color(c, BLACK)
    c.setFont("Helvetica", 9.5)
    deadline_text = inv.get("deadline") or "Immédiat"
    condition_label = deadline_text if deadline_text.lower().startswith(("paiement", "immédiat")) else f"Paiement à {deadline_text}"
    c.drawString(MARGIN, y, f"Condition : {condition_label}")

    y -= 5.5 * mm
    _set_color(c, BLACK)
    c.setFont("Helvetica", 9.5)
    c.drawString(MARGIN, y, f"Échéance : {format_date_fr(echeance_iso)}")

    y -= 10 * mm

    # ---------- Footer ----------
    footer_y = MARGIN + 14 * mm
    c.setStrokeColorRGB(*TEAL)
    c.setLineWidth(0.6)
    c.line(MARGIN, footer_y, PAGE_W - MARGIN, footer_y)

    _set_color(c, TEAL)
    c.setFont("Helvetica-Bold", 7.5)
    col1_x = MARGIN
    col3_x = PAGE_W - MARGIN
    center_x = PAGE_W / 2

    line1 = footer_y - 5 * mm
    line2 = footer_y - 9 * mm

    c.drawString(col1_x, line1, f"Siège social : {profile.get('address') or '-'}")
    c.drawRightString(col3_x, line1, f"ICE: {profile.get('ice') or '-'}")

    c.drawString(col1_x, line2, profile.get("bank_details") or "")
    tp_if_cnss = f"TP: {profile.get('patente') or '-'}    IF: {profile.get('if_number') or '-'}    CNSS: {profile.get('cnss') or '-'}"
    c.drawCentredString(center_x, line2, tp_if_cnss)
    c.drawRightString(col3_x, line2, profile.get("email") or "")

    c.showPage()
    c.save()
    return output_path



def generate_list_sf_pdf(invoices, output_path: str):
    """Build a PDF containing the currently displayed List SF invoices."""
    c = canvas.Canvas(output_path, pagesize=A4)

    table_w = PAGE_W - 2 * MARGIN
    col_client_x = MARGIN + 3 * mm
    col_date_x = MARGIN + table_w * 0.58
    col_amount_x = PAGE_W - MARGIN - 3 * mm
    row_h = 8 * mm
    header_h = 9 * mm

    def draw_header(y):
        c.setFillColorRGB(*TEAL)
        c.rect(MARGIN, y - header_h, table_w, header_h, fill=1, stroke=0)
        _set_color(c, WHITE)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col_client_x, y - header_h + 3 * mm, "Client")
        c.drawString(col_date_x, y - header_h + 3 * mm, "Date")
        c.drawRightString(col_amount_x, y - header_h + 3 * mm, "Montant")

    def draw_rows(rows, start_y, start_index):
        row_y = start_y
        for offset, inv in enumerate(rows):
            idx = start_index + offset
            bg = (0.96, 0.99, 1.0) if idx % 2 == 0 else WHITE
            c.setFillColorRGB(*bg)
            c.rect(MARGIN, row_y - row_h, table_w, row_h, fill=1, stroke=0)

            _set_color(c, BLACK)
            c.setFont("Helvetica", 9.5)
            client = str(inv.get("client_name") or "-")
            c.drawString(col_client_x, row_y - row_h + 2.8 * mm, client[:55])
            c.drawString(col_date_x, row_y - row_h + 2.8 * mm, format_date_fr(inv["invoice_date"]))
            montant = db.compute_invoice_totals(inv)[0]
            c.drawRightString(col_amount_x, row_y - row_h + 2.8 * mm, format_price_dh(montant))

            c.setStrokeColorRGB(*TEAL)
            c.setLineWidth(0.25)
            c.line(MARGIN, row_y - row_h, PAGE_W - MARGIN, row_y - row_h)
            row_y -= row_h
        return row_y

    title_y = PAGE_H - MARGIN
    _set_color(c, TEAL)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(MARGIN, title_y, "Liste SF")

    _set_color(c, GRAY_LIGHT)
    c.setFont("Helvetica", 9.5)
    c.drawRightString(PAGE_W - MARGIN, title_y, f"Généré le {format_date_fr(date.today().isoformat())}")

    table_top = title_y - 14 * mm
    available_h = table_top - (MARGIN + 10 * mm)
    rows_per_page = max(1, int((available_h - header_h) // row_h))

    # Precompute totals before writing pages so the PDF always reflects the same rows
    # that were visible in List SF when the user clicked Print.
    rows = list(invoices)
    chunks = [rows[i:i + rows_per_page] for i in range(0, len(rows), rows_per_page)] or [[]]

    for page_index, chunk in enumerate(chunks):
        if page_index > 0:
            c.showPage()
            page_top = PAGE_H - MARGIN
            draw_header(page_top)
            row_start = page_top - header_h
        else:
            draw_header(table_top)
            row_start = table_top - header_h

        row_end = draw_rows(chunk, row_start, page_index * rows_per_page)
        c.setStrokeColorRGB(*TEAL)
        c.setLineWidth(0.6)
        page_table_top = table_top if page_index == 0 else PAGE_H - MARGIN
        c.rect(MARGIN, row_end, table_w, page_table_top - row_end, fill=0, stroke=1)

    c.showPage()
    c.save()
    return output_path
