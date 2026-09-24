import customtkinter as ctk
from datetime import date
from app import database as db
from app.theme import COLORS, body_font, heading_font
from app.widgets import section_title, StatCard, ConfirmDialog
from app.format_utils import compute_echeance_date, format_date_fr


class DashboardTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        self._build_ui()
        # Populate service stats on first launch (counts everything from scratch
        # if the table is empty, no-op if already populated)
        self.after_idle(self._init_service_stats)
        self.refresh()

    def _init_service_stats(self):
        """On first launch, if service_stats is empty, build it from existing invoices."""
        try:
            rows = db.get_service_leaderboard()
            if all(r["cumulative"] == 0 for r in rows):
                db.rebuild_service_stats_from_scratch()
                self._refresh_leaderboard()
        except Exception:
            pass

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 16))
        section_title(header, "Dashboard").pack(side="left")

        # Top stats cards
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

        # Main content row: deadlines (70%) + leaderboard (30%)
        content_row = ctk.CTkFrame(self, fg_color="transparent")
        content_row.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        content_row.grid_columnconfigure(0, weight=7)
        content_row.grid_columnconfigure(1, weight=3)
        content_row.grid_rowconfigure(0, weight=1)

        # --- Left: Prochaines échéances ---
        left_col = ctk.CTkFrame(content_row, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        section_title(left_col, "Prochaines échéances").pack(anchor="w", pady=(0, 10))
        self.deadlines_frame = ctk.CTkFrame(left_col, fg_color=COLORS["white"], corner_radius=12)
        self.deadlines_frame.pack(fill="x")

        # --- Right: Service leaderboard ---
        right_col = ctk.CTkFrame(content_row, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew")

        section_title(right_col, "Top services (DH)").pack(anchor="w", pady=(0, 10))

        self.leaderboard_frame = ctk.CTkFrame(right_col, fg_color=COLORS["white"], corner_radius=12)
        self.leaderboard_frame.pack(fill="x")

        from app.widgets import danger_button
        danger_button(right_col, "Réinitialiser", self._confirm_reset, width=140).pack(anchor="w", pady=(10, 0))

    def _confirm_reset(self):
        ConfirmDialog(
            self,
            "Réinitialiser le classement des services ?\n\n"
            "Les compteurs seront remis à zéro. Seules les factures\n"
            "créées APRÈS cette réinitialisation seront comptabilisées.\n\n"
            "Cette action n'affecte aucune facture existante.",
            self._do_reset
        )

    def _do_reset(self):
        reset_date = date.today().isoformat()
        db.rebuild_service_stats_from_scratch(reset_date=reset_date)
        self._refresh_leaderboard()

    def _refresh_leaderboard(self):
        for w in self.leaderboard_frame.winfo_children():
            w.destroy()

        rows = db.get_service_leaderboard()

        if not rows:
            ctk.CTkLabel(
                self.leaderboard_frame, text="Aucun service.",
                font=body_font(12), text_color=COLORS["text_muted"]
            ).pack(anchor="w", padx=12, pady=10)
            return

        for i, row in enumerate(rows):
            item = ctk.CTkFrame(self.leaderboard_frame, fg_color="transparent")
            item.pack(fill="x", padx=12, pady=(8 if i == 0 else 0, 8))

            if i > 0:
                sep = ctk.CTkFrame(self.leaderboard_frame, fg_color=COLORS["border"], height=1)
                sep.pack(fill="x", padx=12)

            rank_label = ctk.CTkLabel(
                item, text=f"{i + 1}.", font=body_font(12, "bold"),
                text_color=COLORS["text_muted"], width=24, anchor="w"
            )
            rank_label.pack(side="left")

            name_label = ctk.CTkLabel(
                item, text=row["name"], font=body_font(12),
                text_color=COLORS["text"], anchor="w"
            )
            name_label.pack(side="left", expand=True, fill="x", padx=(4, 8))

            val_label = ctk.CTkLabel(
                item, text=f"{row['cumulative']:,.0f} DH".replace(",", " "),
                font=body_font(12, "bold"), text_color=COLORS["baby_blue_deep"], anchor="e"
            )
            val_label.pack(side="right")

    def _build_deadline_rows(self):
        for widget in self.deadlines_frame.winfo_children():
            widget.destroy()

        today_iso = date.today().isoformat()
        unpaid = db.list_invoices(status="unpaid")
        with_echeance = []
        for inv in unpaid:
            echeance_iso = compute_echeance_date(inv["invoice_date"], inv.get("deadline") or "")
            if echeance_iso >= today_iso:
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
        self._refresh_leaderboard()
