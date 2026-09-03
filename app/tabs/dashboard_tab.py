import customtkinter as ctk
from datetime import date
from app import database as db
from app.theme import COLORS, body_font, heading_font
from app.widgets import section_title, StatCard
from app.format_utils import compute_echeance_date, format_date_fr


class DashboardTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 16))
        section_title(header, "Dashboard").pack(side="left")

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=24, pady=(0, 24), anchor="n")
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_columnconfigure(1, weight=1)
        cards_frame.grid_columnconfigure(2, weight=1)

        self.clients_card = StatCard(cards_frame, "Nombre de clients", COLORS["baby_blue_deep"])
        self.clients_card.grid(row=0, column=0, sticky="ew", padx=(0, 16))

        self.unpaid_card = StatCard(cards_frame, "Factures impayées", COLORS["danger"])
        self.unpaid_card.grid(row=0, column=1, sticky="ew", padx=16)

        self.paid_card = StatCard(cards_frame, "Factures payées", COLORS["success"])
        self.paid_card.grid(row=0, column=2, sticky="ew", padx=(16, 0))

        # ---------- Prochaines échéances ----------
        section_title(self, "Prochaines échéances").pack(anchor="w", padx=24, pady=(0, 10))

        self.deadlines_frame = ctk.CTkFrame(self, fg_color=COLORS["white"], corner_radius=12)
        self.deadlines_frame.pack(fill="x", padx=24, pady=(0, 24))

    def _build_deadline_rows(self):
        for widget in self.deadlines_frame.winfo_children():
            widget.destroy()

        today_iso = date.today().isoformat()
        unpaid = db.list_invoices(status="unpaid")
        with_echeance = []
        for inv in unpaid:
            echeance_iso = compute_echeance_date(inv["invoice_date"], inv.get("deadline") or "")
            if echeance_iso >= today_iso:  # only upcoming, not overdue
                with_echeance.append((echeance_iso, inv))
        with_echeance.sort(key=lambda pair: pair[0])
        soonest = with_echeance[:5]

        if not soonest:
            ctk.CTkLabel(self.deadlines_frame, text="Aucune échéance à venir.",
                         font=body_font(13), text_color=COLORS["text_muted"]).pack(
                anchor="w", padx=16, pady=14)
            return

        for i, (echeance_iso, inv) in enumerate(soonest):
            row = ctk.CTkFrame(self.deadlines_frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(12 if i == 0 else 0, 12))
            if i > 0:
                sep = ctk.CTkFrame(self.deadlines_frame, fg_color=COLORS["border"], height=1)
                sep.pack(fill="x", padx=16)

            ctk.CTkLabel(row, text=inv["client_name"], font=body_font(13, "bold"),
                         text_color=COLORS["text"]).pack(side="left")
            ctk.CTkLabel(row, text=f"F° {inv['numero']}", font=body_font(12),
                         text_color=COLORS["text_muted"]).pack(side="left", padx=(10, 0))
            ctk.CTkLabel(row, text=f"Échéance : {format_date_fr(echeance_iso)}",
                         font=body_font(13, "bold"), text_color=COLORS["danger"]).pack(side="right")

        # If the last shown day has more unpaid invoices than what fit in the top 5,
        # add one summary line for the overflow on that specific day.
        last_date = soonest[-1][0]
        total_on_last_date = sum(1 for d, _ in with_echeance if d == last_date)
        shown_on_last_date = sum(1 for d, _ in soonest if d == last_date)
        overflow = total_on_last_date - shown_on_last_date
        if overflow > 0:
            sep = ctk.CTkFrame(self.deadlines_frame, fg_color=COLORS["border"], height=1)
            sep.pack(fill="x", padx=16)
            overflow_row = ctk.CTkFrame(self.deadlines_frame, fg_color="transparent")
            overflow_row.pack(fill="x", padx=16, pady=12)
            ctk.CTkLabel(
                overflow_row, text=f"+{overflow} autre(s) facture(s) le {format_date_fr(last_date)}",
                font=body_font(12, slant="italic"), text_color=COLORS["text_muted"]
            ).pack(anchor="w")

    def refresh(self):
        self.clients_card.set_value(db.count_clients())
        self.unpaid_card.set_value(db.count_invoices_by_status("unpaid"))
        self.paid_card.set_value(db.count_invoices_by_status("paid"))
        self._build_deadline_rows()
