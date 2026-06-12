"""Tkinter dashboard for running the benchmark pipeline."""

import tkinter as tk
from threading import Thread
from tkinter import ttk

from src.ui.backtest_ui_controller import BacktestUiResult, run_backtest_for_ui
from src.ui.data_download_controller import (
    DataDownloadUiResult,
    download_required_ethusdc_1m_data_for_ui,
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


class BacktestApp:
    """Dashboard UI shell for the existing benchmark pipeline."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ETHUSDC Bot V2 - Backtest Dashboard")
        self.root.geometry("900x650")
        self.status_var = tk.StringVar(value="Bereit")
        controls = ttk.Frame(root)
        controls.pack(fill="x", padx=12, pady=8)
        self.download_button = ttk.Button(
            controls,
            text="Daten laden/aktualisieren",
            command=self._start_download,
        )
        self.download_button.pack(side="left", padx=(0, 8))
        self.start_button = ttk.Button(
            controls,
            text="Backtest starten",
            command=self._start_backtest,
        )
        self.start_button.pack(side="left")
        ttk.Label(root, textvariable=self.status_var).pack(fill="x", padx=12, pady=4)
        result_frame = ttk.Frame(root)
        result_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self.result_text = tk.Text(result_frame, wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=scrollbar.set)
        self.result_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._set_dashboard_text(
            "ETHUSDC Bot V2 - Backtest Dashboard\n\n"
            "Noch kein Ergebnis. Bitte Daten laden/aktualisieren oder Backtest starten."
        )

    def _set_dashboard_text(self, content: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, content)
        self.result_text.configure(state="disabled")

    def _start_download(self) -> None:
        self.download_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.status_var.set("Daten werden geladen...")
        Thread(target=self._run_download_worker, daemon=True).start()

    def _run_download_worker(self) -> None:
        result = download_required_ethusdc_1m_data_for_ui(
            progress_callback=self._queue_download_progress
        )
        self.root.after(0, self._show_download_result, result)

    def _queue_download_progress(self, progress: dict) -> None:
        self.root.after(0, self._show_download_progress, progress)

    def _show_download_progress(self, progress: dict) -> None:
        loaded = progress.get("loaded_candles")
        pct = progress.get("progress_pct")
        last_open_time = progress.get("last_open_time")
        self.status_var.set(
            f"Daten werden geladen... {_format_value(loaded)} Candles, {_format_value(pct)}%"
        )
        self._set_dashboard_text(
            "\n".join(
                [
                    "Download gestartet",
                    f"Geladene Candles: {_format_value(loaded)}",
                    f"Fortschritt: {_format_value(pct)}%",
                    f"Letzter Timestamp: {_format_value(last_open_time)}",
                ]
            )
        )

    def _show_download_result(self, result: DataDownloadUiResult) -> None:
        self.download_button.configure(state="normal")
        self.start_button.configure(state="normal")
        self.status_var.set("Daten bereit" if result.success else "Datenfehler")
        self._set_dashboard_text(
            "\n".join(
                [
                    "A) Daten-Download",
                    "",
                    f"Status: {'success' if result.success else 'failed'}",
                    f"Symbol: {result.symbol}",
                    f"Interval: {result.interval}",
                    f"Candles: {_format_value(result.candle_count)}",
                    f"CSV: {_format_value(result.output_path)}",
                    f"Catalog aktualisiert: {result.catalog_updated}",
                    f"Message: {result.message}",
                    "",
                    "Nach erfolgreichem Download kann der Backtest gestartet werden.",
                ]
            )
        )

    def _start_backtest(self) -> None:
        self.start_button.configure(state="disabled")
        self.status_var.set("Backtest läuft...")
        Thread(target=self._run_backtest_worker, daemon=True).start()

    def _run_backtest_worker(self) -> None:
        result = run_backtest_for_ui()
        self.root.after(0, self._show_result, result)

    def _show_result(self, result: BacktestUiResult) -> None:
        self.start_button.configure(state="normal")
        self.status_var.set(result.status)
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
