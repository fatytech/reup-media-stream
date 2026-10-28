"""
GUI local runner — python gui_local.py [--interval HOURS]

Console: full DEBUG log (gồm ffmpeg stderr)
GUI log area: INFO+ step log rút gọn
Auto-schedule: sau mỗi session tự đếm ngược và chạy lại.
"""
import argparse
import queue
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import scrolledtext
from datetime import datetime, timedelta

# ── Loguru setup phải đặt TRƯỚC khi import bất kỳ module src nào ──────────────
from loguru import logger

logger.remove()

_gui_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()


def _gui_sink(message) -> None:
    level = message.record["level"].name
    _gui_queue.put((level, str(message).rstrip("\n")))


# Console: DEBUG — hiện toàn bộ log kể cả ffmpeg
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}",
    level="DEBUG",
    colorize=True,
)
# File log
logger.add("logs/reup.log", rotation="10 MB", retention="7 days", level="DEBUG")
# GUI sink: chỉ INFO+ (step log rút gọn)
logger.add(_gui_sink, format="{time:HH:mm:ss} | {level:<7} | {message}", level="INFO")

# ── Import src sau khi loguru đã set up (tránh src.main reset handlers) ────────
from src.config.settings import Settings, load  # noqa: E402
from src.worker import ReelsReupWorker  # noqa: E402

# ── Màu theo level ─────────────────────────────────────────────────────────────
_LEVEL_TAG: dict[str, str] = {
    "DEBUG":    "dim",
    "INFO":     "info",
    "SUCCESS":  "success",
    "WARNING":  "warn",
    "ERROR":    "error",
    "CRITICAL": "error",
}


def _parse_args() -> float:
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=float, default=3.0, metavar="HOURS",
                   help="Giờ giữa mỗi lần chạy (mặc định: 3)")
    return p.parse_args().interval


class App(tk.Tk):
    def __init__(self, interval_hours: float) -> None:
        super().__init__()
        self.interval_secs = int(interval_hours * 3600)
        self.title("Reels TikTok Reup — Local")
        self.geometry("860x520")
        self.minsize(600, 360)
        self._running = False
        self._next_run: datetime | None = None
        self._build_ui()
        self._poll_queue()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        bar = tk.Frame(self, bg="#252526")
        bar.pack(fill=tk.X, padx=0, pady=0)

        self.btn = tk.Button(
            bar, text="▶  Run Now", width=12,
            command=self._on_run_clicked,
            bg="#4CAF50", fg="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT, padx=10, pady=6,
            activebackground="#388E3C", activeforeground="white",
            cursor="hand2",
        )
        self.btn.pack(side=tk.LEFT, padx=8, pady=6)

        self.lbl_status = tk.Label(bar, text="Idle", fg="#9cdcfe",
                                   bg="#252526", font=("Segoe UI", 10))
        self.lbl_status.pack(side=tk.LEFT, padx=4)

        self.lbl_next = tk.Label(bar, text="", fg="#6a9955",
                                 bg="#252526", font=("Segoe UI", 9))
        self.lbl_next.pack(side=tk.RIGHT, padx=12)

        mono = tkfont.Font(family="Consolas", size=9)
        self.log = scrolledtext.ScrolledText(
            self, state=tk.DISABLED, wrap=tk.WORD,
            font=mono, bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white", bd=0,
        )
        self.log.pack(fill=tk.BOTH, expand=True)

        self.log.tag_config("info",    foreground="#d4d4d4")
        self.log.tag_config("success", foreground="#4ec994")
        self.log.tag_config("warn",    foreground="#e5c07b")
        self.log.tag_config("error",   foreground="#f44747")
        self.log.tag_config("dim",     foreground="#6a6a6a")

    # ── Handlers ───────────────────────────────────────────────────────────────

    def _on_run_clicked(self) -> None:
        if not self._running:
            self._next_run = None
            self.lbl_next.config(text="")
            self._start_session()

    def _start_session(self) -> None:
        self._running = True
        self.btn.config(state=tk.DISABLED, text="Running…")
        self.lbl_status.config(text="Running…", fg="#9cdcfe")
        threading.Thread(target=self._session_thread, daemon=True).start()

    def _session_thread(self) -> None:
        try:
            settings: Settings = load()
            worker = ReelsReupWorker(settings)
            worker.run_session()
        except Exception as exc:
            logger.error(f"Unhandled error: {exc}")
        finally:
            self.after(0, self._on_session_done)

    def _on_session_done(self) -> None:
        self._running = False
        self.btn.config(state=tk.NORMAL, text="▶  Run Now")
        self.lbl_status.config(text="Done ✓", fg="#4ec994")
        self._next_run = datetime.now() + timedelta(seconds=self.interval_secs)
        self._tick()

    # ── Countdown ──────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if self._next_run is None or self._running:
            return
        remaining = (self._next_run - datetime.now()).total_seconds()
        if remaining <= 0:
            self._next_run = None
            self.lbl_next.config(text="")
            self._start_session()
            return
        h, r = divmod(int(remaining), 3600)
        m, s = divmod(r, 60)
        self.lbl_next.config(text=f"Next run in {h:02d}:{m:02d}:{s:02d}")
        self.after(1000, self._tick)

    # ── Log queue ──────────────────────────────────────────────────────────────

    def _poll_queue(self) -> None:
        try:
            while True:
                level, text = _gui_queue.get_nowait()
                tag = _LEVEL_TAG.get(level, "info")
                self.log.config(state=tk.NORMAL)
                self.log.insert(tk.END, text + "\n", tag)
                self.log.see(tk.END)
                self.log.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)


def main() -> None:
    interval = _parse_args()
    app = App(interval)
    app.mainloop()


if __name__ == "__main__":
    main()
