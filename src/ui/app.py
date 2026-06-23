"""Tkinter dashboard for running the benchmark pipeline."""

import tkinter as tk
from threading import Thread
from tkinter import messagebox, ttk

from src.maintenance.clean_project_data import clean_downloaded_data_and_reports

from src.ui.backtest_ui_controller import (
    BacktestUiResult,
    BacktestUiSettings,
    load_active_backtest_result_for_ui,
    load_latest_completed_backtest_result_for_ui,
    run_backtest_for_ui,
)


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
        self.clean_button = ttk.Button(
            controls,
            text="Alle Daten löschen / Bot clean machen",
            command=self._confirm_and_clean_data,
        )
        self.clean_button.pack(side="left", padx=(8, 0))
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
        data_kind = progress.get("data_kind") or progress.get("interval") or "candles_1m"
        data_status = progress.get("data_status") or progress.get("mode")
        data_age = progress.get("data_age_hours")
        expected = progress.get("expected_candles")
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
            "Dieser Detailbereich bleibt während des Laufes stabil, damit du scrollen und lesen kannst.\n"
            "Datenart: siehe Datenbereiche im geladenen Ergebnis.\n"
            "Datenstatus: siehe Datenbereiche im geladenen Ergebnis.",
            force=True,
        )
        Thread(target=self._run_backtest_worker, daemon=True).start()

    def _run_backtest_worker(self) -> None:
        result = run_backtest_for_ui(self.current_settings, progress_callback=self._queue_progress)
        self.root.after(0, self._show_result, result)

    def _confirm_and_clean_data(self) -> None:
        first_warning = (
            "Achtung: Hiermit werden alle heruntergeladenen Markt-/Backtestdaten und alten Reports gelöscht. "
            "Sind Sie sicher?"
        )
        if not messagebox.askyesno("Alle Daten löschen / Bot clean machen", first_warning):
            return
        second_warning = (
            "Sind Sie 100% sicher? Alle historischen Candles, Kontextdaten, später gesammelten Echtzeitdaten "
            "und alten Backtest-Reports werden gelöscht. Der Bot ist danach im cleanen Zustand. Beim nächsten "
            "Backtest müssen alle nötigen Daten neu heruntergeladen oder neu gesammelt werden. Dadurch können "
            "spätere Backtests anders oder schlechter ausfallen."
        )
        if not messagebox.askyesno("Clean-Zustand bestätigen", second_warning):
            return
        result = clean_downloaded_data_and_reports()
        self.status_var.set("Clean-Zustand")
        self.phase_var.set("Phase: clean")
        self.progress_var.set("Fortschritt: 100%")
        self.detail_var.set(f"Detail: {result.message}")
        self.candles_var.set("Candles: gelöscht / nicht vorhanden")
        self._set_dashboard_text(result.message)

    def _show_result(self, result: BacktestUiResult) -> None:
        self._update_status_labels(result)
        self.current_displayed_run_id = result.run_id
        self.current_displayed_run_status = result.status
        windows_present = bool(result.training_start and result.blindtest_start)
        data_area_lines = self._format_data_areas(result.data_areas)
        self._set_dashboard_text(
            "\n".join(
                [
                    "A) Laufansicht",
                    f"Ansicht: {'letzter abgeschlossener Lauf' if self.showing_latest_completed else 'aktueller aktiver Lauf'}",
                    f"Run-ID: {_format_value(result.run_id)}",
                    f"Run-Type: {_format_value(result.run_type)}",
                    f"Status: {result.status}",
                    f"Message: {result.message}",
                    f"Progress: {_format_value(result.progress_pct)}%",
                    f"Progress Stage: {_format_value(result.progress_stage)}",
                    f"Laufzeit: {_format_seconds(result.elapsed_seconds)}",
                    f"Restzeit geschätzt: {_format_seconds(result.estimated_remaining_seconds)}",
                    f"Report: {_format_value(result.report_path)}",
                    f"Report-Ordner: {_format_value(result.report_folder)}",
                    "",
                    "B) Datenqualität",
                    f"Symbol: {_format_value(result.symbol)}",
                    f"Candle Count: {_format_value(result.candle_count)}",
                    f"Detected Gaps: {_format_value(result.detected_gaps)}",
                    f"Usable for Backtest: {_format_value(result.usable_for_backtest)}",
                    f"Training/Blindtest Daten vorhanden: {'ja' if windows_present else 'nein'}",
                    *data_area_lines,
                    "",
                    "C) Zeitfenster",
                    f"Training Start: {_format_value(result.training_start)}",
                    f"Training Ende: {_format_value(result.training_end)}",
                    f"Blindtest Start: {_format_value(result.blindtest_start)}",
                    f"Blindtest Ende: {_format_value(result.blindtest_end)}",
                    "",
                    "D) Backtest-Ergebnis (aktuell bevorzugter Report)",
                    f"Startkapital: {_format_money(result.start_capital)}",
                    f"Endkapital: {_format_money(result.final_capital)}",
                    f"Total PnL: {_format_signed(result.total_pnl)}",
                    f"Total PnL %: {_format_pct(result.total_pnl_pct)}",
                    f"Trade Count: {_format_value(result.trade_count)}",
                    f"Candidate-Space Status: {_format_value(result.candidate_space_status)}",
                    f"No robust positive candidate: {_format_value(result.no_robust_positive_candidate)}",
                    f"Best final training score: {_format_value(result.best_final_training_score)}",
                    f"Best training USDC/Tag: {_format_value(result.best_training_quote_per_day)}",
                    f"Zielnähe Status: {_format_value(result.target_feasibility_status)}",
                    f"Zielquote zu 3.0 USDC/Tag: {_format_value(result.target_min_training_ratio)}",
                ]
            )
        )


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

    def _format_data_areas(self, data_areas: list[dict] | None) -> list[str]:
        if not data_areas:
            return []
        lines = ["", "B2) Datenbereiche"]
        for area in data_areas:
            lines.extend(
                [
                    f"- {area.get('label')}: {area.get('status')}",
                    f"  Letzter Timestamp: {_format_value(area.get('last_timestamp'))}",
                    f"  Datenalter: {_format_age_hours(area.get('data_age_hours'))}",
                    f"  Rows/Candles: {_format_value(area.get('row_count'))} / Mindestwert: {_format_value(area.get('expected_min_rows'))}",
                    f"  Gaps: {_format_value(area.get('detected_gaps'))} | Usable: {_format_value(area.get('usable_for_backtest'))}",
                    f"  Im Backtest verwendet: {_format_value(area.get('used_in_backtest'))} ({_format_value(area.get('usage_reason'))})",
                ]
            )
        return lines


def main() -> None:
    """Start the minimal Tkinter app."""
    root = tk.Tk()
    BacktestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
