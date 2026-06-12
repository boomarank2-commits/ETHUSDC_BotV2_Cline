"""Minimal Tkinter app for running the benchmark pipeline."""

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
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


class BacktestApp:
    """Minimal UI shell for the existing benchmark pipeline."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ETHUSDC Bot V2")
        self.status_var = tk.StringVar(value="Bereit")
        self.result_var = tk.StringVar(value="Noch kein Ergebnis.")
        self.download_button = ttk.Button(
            root,
            text="Daten laden/aktualisieren",
            command=self._start_download,
        )
        self.download_button.pack(padx=12, pady=8, fill="x")
        self.start_button = ttk.Button(
            root,
            text="Backtest starten",
            command=self._start_backtest,
        )
        self.start_button.pack(padx=12, pady=8, fill="x")
        ttk.Label(root, textvariable=self.status_var).pack(padx=12, pady=4, anchor="w")
        ttk.Label(root, textvariable=self.result_var, justify="left").pack(
            padx=12, pady=8, anchor="w"
        )

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
        self.result_var.set(
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
        self.result_var.set(
            "\n".join(
                [
                    f"Status: {'success' if result.success else 'failed'}",
                    f"Symbol: {result.symbol}",
                    f"Interval: {result.interval}",
                    f"Candles: {_format_value(result.candle_count)}",
                    f"CSV: {_format_value(result.output_path)}",
                    f"Catalog aktualisiert: {result.catalog_updated}",
                    f"Message: {result.message}",
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
        self.result_var.set(
            "\n".join(
                [
                    f"Run-ID: {_format_value(result.run_id)}",
                    f"Status: {result.status}",
                    f"Startkapital: {_format_value(result.start_capital)}",
                    f"Endkapital: {_format_value(result.final_capital)}",
                    f"PnL: {_format_value(result.total_pnl)}",
                    f"PnL %: {_format_value(result.total_pnl_pct)}",
                    f"Trades: {_format_value(result.trade_count)}",
                    "Training: "
                    f"{_format_value(result.training_start)} bis "
                    f"{_format_value(result.training_end)}",
                    "Blindtest: "
                    f"{_format_value(result.blindtest_start)} bis "
                    f"{_format_value(result.blindtest_end)}",
                    f"Message: {result.message}",
                    f"Report: {_format_value(result.report_path)}",
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
