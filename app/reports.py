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
    """Format per CSV:
    Main table: Date | N° Facture | Client | MT  (sorted by numero)
    Summary rows (same column layout, Client col = label, MT col = value):
      Total TTC  | A
      TVA        | A/6
      --- separator line ---
      Service    | HT          ← sub-header
      <name>     | value/1.2   ← one row per service that has value in this month
    """
    invoices = _invoices_for_month(status=None, year=year, month=month, date_field="invoice_date")
    invoices.sort(key=lambda inv: inv["numero"] or "")

    # Build main rows and compute A (sum of MT = total_ttc)
    rows = []
    A = 0.0
    for inv in invoices:
        total_ttc, _, _ = db.compute_invoice_totals(inv)
        A += total_ttc
        rows.append([
            format_date_fr(inv["invoice_date"]),
            inv["numero"],
            inv["client_name"],
            format_price_dh(total_ttc),
        ])

    # All services that appear in this month's invoices (checked items only)
    all_services = db.get_top_services_for_month(year, month, limit=9999)

    title = f"État des ventes — {month:02d}/{year}"
    headers = ["Date", "N° Facture", "Client", "MT"]
    col_weights = [0.15, 0.18, 0.42, 0.25]

    profile = db.get_company_profile() or {}
    company_line = profile.get("name") or ""
    ice = profile.get("ice") or ""
    if ice:
        company_line += f"   —   ICE : {ice}"

    table_w = PAGE_W - 2 * MARGIN
    col_widths = [table_w * w for w in col_weights]

    def col_x(i):
        return MARGIN + sum(col_widths[:i])

    # The summary uses the Client column (col 2) as label and MT column (col 3) as value
    # so it aligns perfectly with the main table above.
    label_col_x  = col_x(2) + 3 * mm
    value_col_x  = col_x(3) + 3 * mm
    value_col_rx = col_x(3) + col_widths[3] - 3 * mm   # right edge of MT column

    c = canvas.Canvas(output_path, pagesize=landscape(A4))

    def _draw_page_header():
        c.setFillColorRGB(*BLACK)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(MARGIN, PAGE_H - MARGIN, company_line)
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(*TEAL)
        c.line(MARGIN, PAGE_H - MARGIN - 3 * mm, PAGE_W - MARGIN, PAGE_H - MARGIN - 3 * mm)
        c.setFillColorRGB(*BLACK)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(MARGIN, PAGE_H - MARGIN - 12 * mm, title)

    def _draw_table_header(y):
        c.setFillColorRGB(*TEAL)
        c.rect(MARGIN, y - HEADER_H, table_w, HEADER_H, fill=1, stroke=0)
        c.setFillColorRGB(*WHITE)
        c.setFont("Helvetica-Bold", 9.5)
        for i, h in enumerate(headers):
            c.drawString(col_x(i) + 3 * mm, y - HEADER_H + 3 * mm, h)
        return y - HEADER_H

    # How much vertical space does the summary need?
    # Total TTC + TVA + separator + Service/HT header + one row per service
    summary_rows_count = 2 + 1 + len(all_services)  # 2 fixed + separator + services
    summary_h = summary_rows_count * ROW_H + 6 * mm  # +gap before block

    _draw_page_header()
    y = PAGE_H - MARGIN - 24 * mm
    y = _draw_table_header(y)

    # --- Data rows ---
    for idx, row in enumerate(rows):
        # If not enough space for this row plus the summary, start new page
        if y - ROW_H < MARGIN + summary_h:
            c.showPage()
            _draw_page_header()
            y = PAGE_H - MARGIN - 24 * mm
            y = _draw_table_header(y)

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
        y -= 12 * mm

    # --- Summary block ---
    y -= 6 * mm   # small gap after last data row

    tva = A / 6.0

    # Row 1: Total TTC
    c.setFillColorRGB(*TEAL)
    c.rect(col_x(2), y - ROW_H, col_widths[2] + col_widths[3], ROW_H, fill=1, stroke=0)
    c.setFillColorRGB(*WHITE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(label_col_x, y - ROW_H + 2.5 * mm, "Total TTC")
    c.drawRightString(value_col_rx, y - ROW_H + 2.5 * mm, format_price_dh(A) if rows else "")
    y -= ROW_H

    # Row 2: TVA
    c.setFillColorRGB(*GRAY_LIGHT)
    c.rect(col_x(2), y - ROW_H, col_widths[2] + col_widths[3], ROW_H, fill=1, stroke=0)
    c.setFillColorRGB(*BLACK)
    c.setFont("Helvetica", 9)
    c.drawString(label_col_x, y - ROW_H + 2.5 * mm, "TVA")
    c.drawRightString(value_col_rx, y - ROW_H + 2.5 * mm, format_price_dh(tva) if rows else "")
    y -= ROW_H

    # Separator line
    c.setStrokeColorRGB(*TEAL)
    c.setLineWidth(0.8)
    c.line(col_x(2), y - 2 * mm, col_x(3) + col_widths[3], y - 2 * mm)
    y -= 5 * mm

    # Service / HT sub-header
    c.setFillColorRGB(*TEAL)
    c.rect(col_x(2), y - ROW_H, col_widths[2] + col_widths[3], ROW_H, fill=1, stroke=0)
    c.setFillColorRGB(*WHITE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(label_col_x, y - ROW_H + 2.5 * mm, "Service")
    c.drawRightString(value_col_rx, y - ROW_H + 2.5 * mm, "HT")
    y -= ROW_H

    # One row per service
    for idx, svc in enumerate(all_services):
        # New page if needed
        if y - ROW_H < MARGIN:
            c.showPage()
            _draw_page_header()
            y = PAGE_H - MARGIN - 24 * mm
            # Repeat service sub-header on new page
            c.setFillColorRGB(*TEAL)
            c.rect(col_x(2), y - ROW_H, col_widths[2] + col_widths[3], ROW_H, fill=1, stroke=0)
            c.setFillColorRGB(*WHITE)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(label_col_x, y - ROW_H + 2.5 * mm, "Service (suite)")
            c.drawRightString(value_col_rx, y - ROW_H + 2.5 * mm, "HT")
            y -= ROW_H

        svc_ht = svc["total"] / 1.2
        bg = GRAY_LIGHT if idx % 2 == 0 else WHITE
        c.setFillColorRGB(*bg)
        c.rect(col_x(2), y - ROW_H, col_widths[2] + col_widths[3], ROW_H, fill=1, stroke=0)
        c.setFillColorRGB(*BLACK)
        c.setFont("Helvetica", 9)
        c.drawString(label_col_x, y - ROW_H + 2.5 * mm, svc["name"])
        c.drawRightString(value_col_rx, y - ROW_H + 2.5 * mm, format_price_dh(svc_ht))
        y -= ROW_H

    c.save()
    return A


def generate_etat_des_paiements(year: int, month: int, output_path: str):
    """Paid invoices whose payment date falls in the given month/year. Returns the Montant TTC sum."""
    invoices = _invoices_for_month(status="paid", year=year, month=month, date_field="payment_date")
    invoices.sort(key=lambda inv: inv["numero"] or "")

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
    invoices.sort(key=lambda inv: inv["numero"] or "")

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
