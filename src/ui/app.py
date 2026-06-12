"""Tkinter dashboard for running the benchmark pipeline."""

import tkinter as tk
from threading import Thread
from tkinter import ttk

from src.ui.backtest_ui_controller import BacktestUiResult, BacktestUiSettings, run_backtest_for_ui


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
            "Noch kein Ergebnis. Bitte Stake/Profil wählen und Backtest starten."
        )

    def _set_dashboard_text(self, content: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, content)
        self.result_text.configure(state="disabled")

    def _queue_progress(self, progress: dict) -> None:
        self.root.after(0, self._show_progress, progress)

    def _show_progress(self, progress: dict) -> None:
        phase = progress.get("phase") or progress.get("mode") or "läuft"
        detail = progress.get("detail") or progress.get("message") or "Arbeite..."
        pct = progress.get("progress_pct")
        loaded = progress.get("loaded_candles")
        candle_count = progress.get("candle_count") or loaded
        last_open_time = progress.get("last_open_time")
        self.status_var.set(str(detail))
        self.phase_var.set(f"Phase: {_format_value(phase)}")
        self.progress_var.set(f"Fortschritt: {_format_value(pct)}%")
        self.detail_var.set(f"Detail: {_format_value(detail)}")
        candle_text = (
            f"Candles: {_format_value(candle_count)} | "
            f"Letzte Candle: {_format_value(last_open_time)}"
        )
        self.candles_var.set(candle_text)
        self._set_dashboard_text(
            "\n".join(
                [
                    "Backtest läuft",
                    f"Phase: {_format_value(phase)}",
                    f"Fortschritt: {_format_value(pct)}%",
                    f"Detail: {_format_value(detail)}",
                    f"Candles: {_format_value(candle_count)}",
                    f"Letzter Timestamp: {_format_value(last_open_time)}",
                ]
            )
        )

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

    def _start_backtest(self) -> None:
        profile_map = {"vorsichtig": "conservative", "normal": "normal", "aggressiv": "aggressive"}
        try:
            self.current_settings = BacktestUiSettings(
                stake_quote_amount=self._read_stake_quote_amount(),
                profile=profile_map[self.profile_var.get()],
            )
        except ValueError as error:
            self.status_var.set("Eingabefehler")
            self.detail_var.set(f"Detail: {error}")
            self._set_dashboard_text(f"Eingabefehler\n\n{error}")
            return
        self.start_button.configure(state="disabled")
        self.status_var.set("Prüfe/aktualisiere Daten...")
        self.phase_var.set("Phase: Datenprüfung")
        self.progress_var.set("Fortschritt: 0%")
        self.detail_var.set("Detail: Automatische Datenprüfung startet")
        Thread(target=self._run_backtest_worker, daemon=True).start()

    def _run_backtest_worker(self) -> None:
        result = run_backtest_for_ui(self.current_settings, progress_callback=self._queue_progress)
        self.root.after(0, self._show_result, result)

    def _show_result(self, result: BacktestUiResult) -> None:
        self.start_button.configure(state="normal")
        self.status_var.set(result.status)
        self.phase_var.set(f"Phase: {'fertig' if result.success else 'fehlgeschlagen'}")
        self.progress_var.set("Fortschritt: 100%")
        self.detail_var.set(f"Detail: {result.message}")
        windows_present = bool(result.training_start and result.blindtest_start)
        self._set_dashboard_text(
            "\n".join(
                [
                    "A) Letzter Lauf",
                    f"Run-ID: {_format_value(result.run_id)}",
                    f"Status: {result.status}",
                    f"Message: {result.message}",
                    f"Report: {_format_value(result.report_path)}",
                    f"Report-Ordner: {_format_value(result.report_folder)}",
                    "",
                    "B) Datenqualität",
                    f"Symbol: {_format_value(result.symbol)}",
                    f"Candle Count: {_format_value(result.candle_count)}",
                    f"Detected Gaps: {_format_value(result.detected_gaps)}",
                    f"Usable for Backtest: {_format_value(result.usable_for_backtest)}",
                    f"Training/Blindtest Daten vorhanden: {'ja' if windows_present else 'nein'}",
                    "",
                    "C) Zeitfenster",
                    f"Training Start: {_format_value(result.training_start)}",
                    f"Training Ende: {_format_value(result.training_end)}",
                    f"Blindtest Start: {_format_value(result.blindtest_start)}",
                    f"Blindtest Ende: {_format_value(result.blindtest_end)}",
                    "",
                    "D) Buy-&-Hold Benchmark",
                    f"Startkapital: {_format_money(result.start_capital)}",
                    f"Endkapital: {_format_money(result.final_capital)}",
                    f"Total PnL: {_format_signed(result.total_pnl)}",
                    f"Total PnL %: {_format_pct(result.total_pnl_pct)}",
                    f"Trade Count: {_format_value(result.trade_count)}",
                ]
            )
        )


def main() -> None:
    """Start the minimal Tkinter app."""
    root = tk.Tk()
    BacktestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
