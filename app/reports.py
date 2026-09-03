"""
Generates the 3 "Editions" report PDFs: Etat des ventes, Etat des paiements, Etat des créances.
Simple table reports (title + table), no company letterhead.
"""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app import database as db
from app.format_utils import format_price_dh, format_date_fr, compute_echeance_date

TEAL = (0x0F / 255, 0x76 / 255, 0x6D / 255)
BLACK = (0, 0, 0)
WHITE = (1, 1, 1)
GRAY_LIGHT = (0.94, 0.97, 0.98)

PAGE_W, PAGE_H = landscape(A4)
MARGIN = 15 * mm
ROW_H = 8 * mm
HEADER_H = 9 * mm


def _draw_table(c, title, headers, col_weights, rows, total_col_index=None, total_value=None):
    """Draws a titled table (with a company name/ICE header) starting at the top of a
    fresh page, paginating as needed. If total_col_index/total_value are given, a bold
    TOTAL row is drawn under the table, right-aligned under that column."""
    profile = db.get_company_profile() or {}
    company_line = profile.get("name") or ""
    ice = profile.get("ice") or ""
    if ice:
        company_line += f"   —   ICE : {ice}"

    table_w = PAGE_W - 2 * MARGIN
    col_widths = [table_w * w for w in col_weights]

    def col_x(i):
        return MARGIN + sum(col_widths[:i])

    def new_page():
        c.setFillColorRGB(*BLACK)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(MARGIN, PAGE_H - MARGIN, company_line)
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(*TEAL)
        c.line(MARGIN, PAGE_H - MARGIN - 3 * mm, PAGE_W - MARGIN, PAGE_H - MARGIN - 3 * mm)

        c.setFillColorRGB(*BLACK)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(MARGIN, PAGE_H - MARGIN - 12 * mm, title)
        y = PAGE_H - MARGIN - 24 * mm
        _draw_header(y)
        return y - HEADER_H

    def _draw_header(y):
        c.setFillColorRGB(*TEAL)
        c.rect(MARGIN, y - HEADER_H, table_w, HEADER_H, fill=1, stroke=0)
        c.setFillColorRGB(*WHITE)
        c.setFont("Helvetica-Bold", 9.5)
        for i, h in enumerate(headers):
            c.drawString(col_x(i) + 3 * mm, y - HEADER_H + 3 * mm, h)

    y = new_page()
    for idx, row in enumerate(rows):
        if y - ROW_H < MARGIN:
            c.showPage()
            y = new_page()
        bg = GRAY_LIGHT if idx % 2 == 0 else WHITE
        c.setFillColorRGB(*bg)
        c.rect(MARGIN, y - ROW_H, table_w, ROW_H, fill=1, stroke=0)
        c.setFillColorRGB(*BLACK)
        c.setFont("Helvetica", 9)
        for i, cell in enumerate(row):
            c.drawString(col_x(i) + 3 * mm, y - ROW_H + 2.5 * mm, str(cell))
        y -= ROW_H

    if not rows:
        c.setFillColorRGB(*BLACK)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(MARGIN, y - 8 * mm, "Aucune donnée pour cette période.")
    elif total_col_index is not None and total_value is not None:
        if y - ROW_H < MARGIN:
            c.showPage()
            y = new_page()
        c.setFillColorRGB(*TEAL)
        c.rect(MARGIN, y - ROW_H, table_w, ROW_H, fill=1, stroke=0)
        c.setFillColorRGB(*WHITE)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(col_x(0) + 3 * mm, y - ROW_H + 2.5 * mm, "TOTAL")
        c.drawString(col_x(total_col_index) + 3 * mm, y - ROW_H + 2.5 * mm, total_value)
        y -= ROW_H

    c.save()


def _invoices_for_month(status, year, month, date_field="invoice_date"):
    """Returns invoices matching status (or any status if None) whose date_field
    (or, for 'echeance', the computed échéance date) falls in the given year/month."""
    all_invoices = db.list_invoices(status=status) if status else db.list_invoices()
    prefix = f"{year:04d}-{month:02d}"
    matched = []
    for inv in all_invoices:
        if date_field == "echeance":
            d = compute_echeance_date(inv["invoice_date"], inv.get("deadline") or "")
        else:
            d = inv[date_field]
        if d and d.startswith(prefix):
            matched.append(inv)
    return matched


def generate_etat_des_ventes(year: int, month: int, output_path: str):
    """All invoices (paid + unpaid) created in the given month/year. Returns the Montant TTC sum."""
    invoices = _invoices_for_month(status=None, year=year, month=month, date_field="invoice_date")
    invoices.sort(key=lambda inv: inv["invoice_date"])

    rows = []
    sum_ttc = 0.0
    for inv in invoices:
        total_ttc, subtotal_ht, tva_amount = db.compute_invoice_totals(inv)
        sum_ttc += total_ttc
        rows.append([
            format_date_fr(inv["invoice_date"]),
            inv["numero"],
            inv["client_name"],
            format_price_dh(subtotal_ht),
            format_price_dh(tva_amount),
            format_price_dh(total_ttc),
        ])

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    _draw_table(
        c, f"État des ventes — {month:02d}/{year}",
        ["Date", "Facture", "Client", "Montant HT", "Montant TVA", "Montant TTC"],
        [0.13, 0.17, 0.30, 0.13, 0.13, 0.14],
        rows,
        total_col_index=5, total_value=format_price_dh(sum_ttc) if rows else None,
    )
    return sum_ttc


def generate_etat_des_paiements(year: int, month: int, output_path: str):
    """Paid invoices whose payment date falls in the given month/year. Returns the Montant TTC sum."""
    invoices = _invoices_for_month(status="paid", year=year, month=month, date_field="payment_date")
    invoices.sort(key=lambda inv: inv.get("payment_date") or "")

    rows = []
    sum_ttc = 0.0
    for inv in invoices:
        total_ttc, _, _ = db.compute_invoice_totals(inv)
        sum_ttc += total_ttc
        rows.append([
            inv["numero"],
            inv["client_name"],
            format_price_dh(total_ttc),
            format_date_fr(inv.get("payment_date") or ""),
            inv.get("payment_type") or "-",
        ])

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    _draw_table(
        c, f"État des paiements — {month:02d}/{year}",
        ["Facture", "Client", "Montant TTC", "Date de paiement", "Moyen de paiement"],
        [0.16, 0.28, 0.16, 0.20, 0.20],
        rows,
        total_col_index=2, total_value=format_price_dh(sum_ttc) if rows else None,
    )
    return sum_ttc


def generate_etat_des_creances(output_path: str):
    """Unpaid invoices only, no date filter. Returns the Montant TTC sum."""
    invoices = db.list_invoices(status="unpaid")
    invoices.sort(key=lambda inv: inv["invoice_date"])

    rows = []
    sum_ttc = 0.0
    for inv in invoices:
        total_ttc, _, _ = db.compute_invoice_totals(inv)
        sum_ttc += total_ttc
        rows.append([
            inv["client_name"],
            inv["numero"],
            format_price_dh(total_ttc),
        ])

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    _draw_table(
        c, "État des créances",
        ["Client", "Facture", "Montant TTC"],
        [0.40, 0.30, 0.30],
        rows,
        total_col_index=2, total_value=format_price_dh(sum_ttc) if rows else None,
    )
    return sum_ttc


def sum_all_ventes():
    """Sum of Montant TTC across every invoice (paid + unpaid), for the Editions card."""
    return sum(db.compute_invoice_totals(inv)[0] for inv in db.list_invoices())


def sum_all_paiements():
    """Sum of Montant TTC across every paid invoice, for the Editions card."""
    return sum(db.compute_invoice_totals(inv)[0] for inv in db.list_invoices(status="paid"))


def sum_all_creances():
    """Sum of Montant TTC across every unpaid invoice, for the Editions card."""
    return sum(db.compute_invoice_totals(inv)[0] for inv in db.list_invoices(status="unpaid"))
