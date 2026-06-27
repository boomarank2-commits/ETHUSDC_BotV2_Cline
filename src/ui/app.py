"""Tkinter dashboard for running the benchmark pipeline."""

import tkinter as tk
from threading import Thread
from tkinter import ttk

from src.ui.backtest_ui_controller import (
    BacktestUiResult,
    BacktestUiSettings,
    load_active_backtest_result_for_ui,
    load_latest_completed_backtest_result_for_ui,
    run_backtest_for_ui,
)

TARGET_QUOTE_PER_DAY = 3.0


def _format_value(value: object) -> str:
    if value is None:
        return "Noch nicht vorhanden"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _format_money(value: float | None) -> str:
    if value is None:
        return "Noch nicht vorhanden"
    return f"{value:.2f}"


def _format_signed(value: float | None) -> str:
    if value is None:
        return "Noch nicht vorhanden"
    return f"{value:+.2f}"


def _format_pct(value: float | None) -> str:
    if value is None:
        return "Noch nicht vorhanden"
    return f"{value:+.2f}%"


def _format_age_hours(value: object) -> str:
    if value is None:
        return "Noch nicht vorhanden"
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return str(value)
    if hours < 24:
        return f"{hours:.2f} Stunden"
    return f"{hours / 24:.2f} Tage"


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "Noch nicht vorhanden"
    seconds = int(max(0.0, value))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {secs:02d}s"
    return f"{minutes:d}m {secs:02d}s"


def _blindtest_days(result: BacktestUiResult) -> float | None:
    if not result.blindtest_start or not result.blindtest_end:
        return None
    try:
        from datetime import datetime

        start = datetime.fromisoformat(result.blindtest_start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(result.blindtest_end.replace("Z", "+00:00"))
    except ValueError:
        return None
    days = (end - start).total_seconds() / 86400
    if days < 0:
        return None
    return max(1.0, days + (1 / 1440))


def _format_trade_rate(trade_count: int | None, result: BacktestUiResult) -> str:
    if trade_count is None:
        return "Noch nicht vorhanden"
    blindtest_days = _blindtest_days(result)
    if blindtest_days is None or blindtest_days <= 0:
        return "Noch nicht vorhanden"
    return f"{trade_count / blindtest_days:.2f}"


def _format_month(label: str | None, value: float | None) -> str:
    if label is None or value is None:
        return "Noch nicht vorhanden"
    return f"{label}: {_format_signed(value)} USDC"


class BacktestApp:
    """Dashboard UI shell for the existing benchmark pipeline."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ETHUSDC Bot V2 - Backtest Dashboard")
        self.root.geometry("900x650")
        self.status_var = tk.StringVar(value="Bereit")
        self.phase_var = tk.StringVar(value="Phase: bereit")
        self.progress_var = tk.StringVar(value="Fortschritt: 0%")
        self.detail_var = tk.StringVar(value="Detail: Noch kein Lauf gestartet")
        self.candles_var = tk.StringVar(value="Candles: Noch nicht geprüft")
        self.stake_var = tk.StringVar(value="100")
        self.profile_var = tk.StringVar(value="normal")
        self.smoke_days_var = tk.StringVar(value="7 Tage Blindtest")
        self.showing_latest_completed = False
        self.pause_dashboard_text_updates = False
        self.current_displayed_run_id: str | None = None
        self.current_displayed_run_status: str | None = None

        controls = ttk.Frame(root)
        controls.pack(fill="x", padx=12, pady=8)
        ttk.Label(controls, text="Einsatz pro Trade (USDC):").pack(side="left", padx=(0, 4))
        self.stake_entry = ttk.Entry(controls, textvariable=self.stake_var, width=12)
        self.stake_entry.pack(side="left", padx=(0, 8))
        ttk.Label(controls, text="Profil:").pack(side="left", padx=(0, 4))
        self.profile_combo = ttk.Combobox(
            controls,
            textvariable=self.profile_var,
            values=("vorsichtig", "normal", "aggressiv"),
            width=12,
            state="readonly",
        )
        self.profile_combo.pack(side="left", padx=(0, 8))
        self.start_button = ttk.Button(
            controls,
            text="Backtest starten",
            command=self._start_backtest,
        )
        self.start_button.pack(side="left")
        ttk.Label(controls, text="Smoke-Dauer:").pack(side="left", padx=(8, 4))
        self.smoke_days_combo = ttk.Combobox(
            controls,
            textvariable=self.smoke_days_var,
            values=("1 Tag Blindtest", "7 Tage Blindtest", "14 Tage Blindtest", "30 Tage Blindtest"),
            width=18,
            state="readonly",
        )
        self.smoke_days_combo.pack(side="left", padx=(0, 8))
        self.smoke_button = ttk.Button(
            controls,
            text="Smoke-Test starten",
            command=self._start_smoke_test,
        )
        self.smoke_button.pack(side="left")
        self.refresh_button = ttk.Button(
            controls,
            text="Letzten Lauf laden",
            command=self._toggle_run_view,
        )
        self.refresh_button.pack(side="left", padx=(8, 0))
        self.pause_button = ttk.Button(
            controls,
            text="Anzeige pausieren",
            command=self._toggle_dashboard_pause,
        )
        self.pause_button.pack(side="left", padx=(8, 0))
        ttk.Label(root, textvariable=self.status_var).pack(fill="x", padx=12, pady=4)
        status_frame = ttk.Frame(root)
        status_frame.pack(fill="x", padx=12, pady=4)
        ttk.Label(status_frame, textvariable=self.phase_var).pack(anchor="w")
        ttk.Label(status_frame, textvariable=self.progress_var).pack(anchor="w")
        ttk.Label(status_frame, textvariable=self.detail_var).pack(anchor="w")
        ttk.Label(status_frame, textvariable=self.candles_var).pack(anchor="w")
        result_frame = ttk.Frame(root)
        result_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self.result_text = tk.Text(result_frame, wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=scrollbar.set)
        self.result_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._set_dashboard_text(
            "ETHUSDC Bot V2 - Backtest Dashboard\n\n"
            "Noch kein Ergebnis. Bitte Stake/Profil wählen und Backtest starten.",
            force=True,
        )
        self._load_active_run()
        self._schedule_active_run_refresh()

    def _set_dashboard_text(self, content: str, force: bool = False) -> None:
        if self.pause_dashboard_text_updates and not force:
            return
        scroll_position = self.result_text.yview()
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, content)
        self.result_text.configure(state="disabled")
        self.result_text.yview_moveto(scroll_position[0])

    def _toggle_dashboard_pause(self) -> None:
        self.pause_dashboard_text_updates = not self.pause_dashboard_text_updates
        self.pause_button.configure(
            text="Anzeige weiter aktualisieren" if self.pause_dashboard_text_updates else "Anzeige pausieren"
        )

    def _queue_progress(self, progress: dict) -> None:
        self.root.after(0, self._show_progress, progress)

    def _show_progress(self, progress: dict) -> None:
        phase = progress.get("phase") or progress.get("mode") or "läuft"
        detail = progress.get("detail") or progress.get("message") or "Arbeite..."
        pct = progress.get("progress_pct")
        loaded = progress.get("loaded_candles")
        candle_count = progress.get("candle_count") or loaded
        last_open_time = progress.get("last_open_time")
        data_age = progress.get("data_age_hours")
        self.status_var.set(str(detail))
        self.phase_var.set(f"Phase: {_format_value(phase)}")
        self.progress_var.set(f"Fortschritt: {_format_value(pct)}%")
        self.detail_var.set(f"Detail: {_format_value(detail)}")
        candle_text = (
            f"Candles: {_format_value(candle_count)} | "
            f"Letzte Candle: {_format_value(last_open_time)} | "
            f"Alter: {_format_age_hours(data_age)}"
        )
        self.candles_var.set(candle_text)

    def _load_active_run(self) -> None:
        result = load_active_backtest_result_for_ui()
        if result is None:
            return
        self.showing_latest_completed = False
        self._show_result(result)

    def _load_latest_completed_run(self) -> None:
        active_result = load_active_backtest_result_for_ui()
        if active_result is not None and active_result.status == "running":
            self.showing_latest_completed = False
            self._show_result(active_result)
            return
        result = load_latest_completed_backtest_result_for_ui()
        if result is None:
            return
        self.showing_latest_completed = True
        self._show_result(result)

    def _toggle_run_view(self) -> None:
        if self.showing_latest_completed:
            self._load_active_run()
        else:
            self._load_latest_completed_run()

    def _schedule_active_run_refresh(self) -> None:
        result = load_active_backtest_result_for_ui()
        if result is not None and result.status == "running":
            self.showing_latest_completed = False
            if self.current_displayed_run_id != result.run_id:
                self._show_result(result)
            else:
                self._update_status_labels(result)
        elif not self.showing_latest_completed and result is not None:
            if self.current_displayed_run_id != result.run_id or self.current_displayed_run_status == "running":
                self._show_result(result)
        self.root.after(5000, self._schedule_active_run_refresh)

    def _read_stake_quote_amount(self) -> float:
        raw_value = self.stake_var.get().strip()
        try:
            stake = float(raw_value.replace(",", "."))
        except ValueError as error:
            msg = "Einsatz pro Trade (USDC) muss eine positive Zahl sein."
            raise ValueError(msg) from error
        if stake <= 0:
            msg = "Einsatz pro Trade (USDC) muss größer als 0 sein."
            raise ValueError(msg)
        return stake

    def _read_smoke_blindtest_days(self) -> int:
        return int(self.smoke_days_var.get().split()[0])

    def _start_backtest(self) -> None:
        self._start_run("full_backtest")

    def _start_smoke_test(self) -> None:
        self._start_run("smoke_test")

    def _start_run(self, run_type: str) -> None:
        profile_map = {"vorsichtig": "conservative", "normal": "normal", "aggressiv": "aggressive"}
        try:
            self.current_settings = BacktestUiSettings(
                stake_quote_amount=self._read_stake_quote_amount(),
                profile=profile_map[self.profile_var.get()],
                run_type=run_type,
                blindtest_days=self._read_smoke_blindtest_days() if run_type == "smoke_test" else None,
            )
        except ValueError as error:
            self.status_var.set("Eingabefehler")
            self.detail_var.set(f"Detail: {error}")
            self._set_dashboard_text(f"Eingabefehler\n\n{error}")
            return
        self.start_button.configure(state="disabled")
        self.smoke_button.configure(state="disabled")
        self.showing_latest_completed = False
        self.status_var.set("Prüfe lokale Daten...")
        self.phase_var.set("Phase: Datenprüfung")
        self.progress_var.set("Fortschritt: 0%")
        self.detail_var.set("Detail: Download nur bei fehlenden, unvollständigen oder älter als 7 Tage alten Daten")
        self._set_dashboard_text(
            f"{'Smoke-Test' if run_type == 'smoke_test' else 'Backtest'} läuft\n\n"
            "Oben werden Fortschritt, Laufzeit und geschätzte Restzeit automatisch aktualisiert.\n"
            "Unten erscheint nach Abschluss nur die Entscheidungsübersicht.",
            force=True,
        )
        Thread(target=self._run_backtest_worker, daemon=True).start()

    def _run_backtest_worker(self) -> None:
        result = run_backtest_for_ui(self.current_settings, progress_callback=self._queue_progress)
        self.root.after(0, self._show_result, result)

    def _show_result(self, result: BacktestUiResult) -> None:
        self._update_status_labels(result)
        self.current_displayed_run_id = result.run_id
        self.current_displayed_run_status = result.status
        self._set_dashboard_text(self._format_result_dashboard(result))

    def _format_result_dashboard(self, result: BacktestUiResult) -> str:
        blindtest_days = _blindtest_days(result)
        window_text = (
            f"Training: {_format_value(result.training_start)} bis {_format_value(result.training_end)}\n"
            f"Blindtest: {_format_value(result.blindtest_start)} bis {_format_value(result.blindtest_end)}"
        )
        if blindtest_days is not None:
            window_text += f"\nBlindtest-Dauer: {blindtest_days:.1f} Tage"
        return "\n".join(
            [
                "BACKTEST-ENTSCHEIDUNG",
                self._decision_text(result),
                "",
                "KERNERGEBNIS",
                f"Run-ID: {_format_value(result.run_id)} | Typ: {_format_value(result.run_type)} | Status: {result.status}",
                f"Gewinn/Tag: {_format_signed(result.quote_per_day)} USDC / Ziel: {TARGET_QUOTE_PER_DAY:.2f} USDC",
                f"Zielquote: {_format_value(result.target_min_training_ratio)}",
                f"Gesamt-PnL: {_format_signed(result.total_pnl)} USDC ({_format_pct(result.total_pnl_pct)})",
                f"Start/Ende: {_format_money(result.start_capital)} -> {_format_money(result.final_capital)} USDC",
                f"Trades: {_format_value(result.trade_count)} gesamt | {_format_trade_rate(result.trade_count, result)} pro Tag",
                "",
                "STABILITÄT",
                f"Positive/negative Tage: {_format_value(result.positive_days)} / {_format_value(result.negative_days)}",
                f"Bester/schlechtester Tag: {_format_signed(result.best_day_pnl)} / {_format_signed(result.worst_day_pnl)} USDC",
                f"Bester Monat: {_format_month(result.best_month, result.best_month_pnl)}",
                f"Schlechtester Monat: {_format_month(result.worst_month, result.worst_month_pnl)}",
                "",
                "STRATEGIE-FREIGABE",
                f"Strategie/Familie: {_format_value(result.selected_family)}",
                f"Kandidat: {_format_value(result.selected_candidate_name)}",
                f"Candidate-Space: {_format_value(result.candidate_space_status)}",
                f"Training bester Kandidat: {_format_signed(result.best_training_quote_per_day)} USDC/Tag",
                f"Zielnähe: {_format_value(result.target_feasibility_status)}",
                f"Kein robuster Kandidat: {_format_value(result.no_robust_positive_candidate)}",
                "",
                "DATENQUALITÄT",
                self._format_data_quality_summary(result),
                "",
                "ZEITFENSTER",
                window_text,
                "",
                "REPORT",
                f"Ordner: {_format_value(result.report_folder)}",
            ]
        )

    def _decision_text(self, result: BacktestUiResult) -> str:
        if result.status == "running":
            return "LÄUFT: Ergebnis noch nicht bewerten."
        if not result.success:
            return "FEHLGESCHLAGEN: Backtest/Smoke technisch prüfen."
        if (
            result.no_robust_positive_candidate
            and result.candidate_space_status == "trade_allowed_blocked"
        ):
            return "NICHT UEBERNEHMEN: Training-Kandidaten vorhanden, aber Validation/Robustheit blockiert."
        if result.no_robust_positive_candidate:
            return "NICHT ÜBERNEHMEN: Kein trade_allowed Kandidat gefunden."
        if result.quote_per_day is not None and result.quote_per_day >= TARGET_QUOTE_PER_DAY:
            return "ZIEL ERREICHT: Kandidat für genauere Prüfung / Full-Backtest."
        if result.quote_per_day is not None and result.quote_per_day > 0:
            return "ZWISCHENERFOLG: Positiv, aber Ziel noch nicht erreicht."
        return "NICHT ÜBERNEHMEN: Kein positiver Blindtest-Vorteil sichtbar."

    def _format_data_quality_summary(self, result: BacktestUiResult) -> str:
        base = (
            f"ETHUSDC Candles: {_format_value(result.candle_count)} | "
            f"Gaps: {_format_value(result.detected_gaps)} | "
            f"Usable: {_format_value(result.usable_for_backtest)}"
        )
        if not result.data_areas:
            return base
        usable = sum(1 for area in result.data_areas if area.get("usable_for_backtest") is True)
        used = sum(1 for area in result.data_areas if area.get("used_in_backtest") is True)
        unavailable = sum(1 for area in result.data_areas if area.get("usable_for_backtest") is False)
        return f"{base}\nDatenbereiche: {usable} usable, {used} im Backtest verwendet, {unavailable} nicht verfügbar."

    def _update_status_labels(self, result: BacktestUiResult) -> None:
        self.start_button.configure(state="disabled" if result.status == "running" else "normal")
        self.smoke_button.configure(state="disabled" if result.status == "running" else "normal")
        self.refresh_button.configure(text="Aktuellen Lauf anzeigen" if self.showing_latest_completed else "Letzten Lauf laden")
        self.status_var.set(result.status)
        phase_label = "läuft" if result.status == "running" else ("fertig" if result.success else "fehlgeschlagen")
        self.phase_var.set(f"Phase: {phase_label}")
        if result.status == "running":
            self.progress_var.set(
                f"Fortschritt: {_format_value(result.progress_pct)}% | Laufzeit: {_format_seconds(result.elapsed_seconds)} | Rest ca.: {_format_seconds(result.estimated_remaining_seconds)}"
            )
        else:
            self.progress_var.set("Fortschritt: 100%")
        self.detail_var.set(f"Detail: {result.message}")


def main() -> None:
    """Start the minimal Tkinter app."""
    root = tk.Tk()
    BacktestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
