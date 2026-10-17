"""Windows-first, keyboard-friendly high-contrast status window."""
from __future__ import annotations

from datetime import datetime, timezone
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox

from .outputs import dispatch
from .rules import RuleEngine, Status
from .settings import Settings
from .source import HomeAssistant, Reading, SourceError

_BG = "#101820"
_FG = "#ffffff"
_COLOURS = {Status.LOW: "#e75145", Status.HIGH: "#efa03a",
            Status.NORMAL: "#64d1a2", Status.STALE: "#ffd45e",
            Status.UNAVAILABLE: "#ffd45e", Status.UNCONFIGURED: "#eaeaea"}


def play_sound(widget: tk.Tk) -> None:
    if sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
            return
        except (ImportError, RuntimeError):
            pass
    widget.bell()


class Window:
    def __init__(self, settings: Settings, ha: HomeAssistant):
        self.settings, self.ha = settings, ha
        self.rules = RuleEngine(settings)
        self.lock = threading.Lock()
        self.items: queue.Queue[tuple] = queue.Queue()
        self.busy = False
        self.current: Status = Status.UNAVAILABLE
        self.pulse = False
        self.root = tk.Tk()
        root = self.root
        root.title("LibreBeacon – supplementary display")
        root.configure(bg=_BG)
        root.geometry("690x440")
        root.minsize(480, 360)
        self.status = tk.Label(root, text="CONNECTING", font=("Segoe UI", 34, "bold"),
                               bg=_BG, fg=_FG, pady=20)
        self.status.pack(fill="x")
        self.value = tk.Label(root, text="Reading not yet available", font=("Segoe UI", 23),
                              bg=_BG, fg=_FG)
        self.value.pack(fill="x", pady=4)
        self.detail = tk.Label(root, text="Checking the Home Assistant connection…",
                               font=("Segoe UI", 13), bg=_BG, fg="#dbe4e8", wraplength=590)
        self.detail.pack(fill="x", padx=20, pady=12)
        self.delivery = tk.Label(root, text="External actions are OFF" if settings.dry_run else "External actions enabled",
                                 font=("Segoe UI", 11), bg=_BG, fg="#dbe4e8", wraplength=590)
        self.delivery.pack(fill="x", padx=20)
        bar = tk.Frame(root, bg=_BG)
        bar.pack(pady=22)
        self.ack_button = tk.Button(bar, text="Acknowledge episode", font=("Segoe UI", 13),
                                    command=self.acknowledge, padx=12, pady=10)
        self.ack_button.pack(side="left", padx=10)
        tk.Button(bar, text="Test local sound", font=("Segoe UI", 13),
                  command=lambda: play_sound(root), padx=12, pady=10).pack(side="left", padx=10)
        tk.Label(root, text="NOT a medical alarm • Continue using official Libre alerts",
                 bg=_BG, fg="#c6d0d7", font=("Segoe UI", 11)).pack(side="bottom", pady=15)
        root.bind("<Escape>", lambda _: root.iconify())
        root.after(100, self.drain)
        root.after(1000, self.tick)
        root.after(850, self.screen_pulse)

    def acknowledge(self):
        with self.lock:
            self.rules.acknowledge()
        self.detail.configure(text="Acknowledged for this episode. Official Libre alarms remain active.")

    def tick(self):
        if not self.busy:
            self.busy = True
            threading.Thread(target=self.fetch, daemon=True).start()
        self.root.after(self.settings.poll_seconds * 1000, self.tick)

    def fetch(self):
        error = None
        reading: Reading | None = None
        try:
            reading = self.ha.read(self.settings.glucose_entity, self.settings.timestamp_entity)
        except SourceError:
            error = "Reading unavailable. Check Home Assistant, network and sensor status."
        except Exception:
            error = "Unexpected reading error. Check Home Assistant configuration."
        now = datetime.now(timezone.utc)
        with self.lock:
            decision = self.rules.check(reading, now)
        results = dispatch(decision, reading.mmol_l if reading else None, self.settings, self.ha)
        self.items.put((decision, reading, error, results))

    def drain(self):
        try:
            while True:
                decision, reading, error, results = self.items.get_nowait()
                self.busy = False
                self.current = decision.status
                color = _COLOURS[self.current]
                self.status.configure(text=self.current.value.replace("_", " "), fg=color)
                if reading and self.current not in {Status.UNAVAILABLE, Status.STALE}:
                    self.value.configure(text=f"{reading.mmol_l:.1f} mmol/L")
                else:
                    self.value.configure(text="Reading not verified")
                msg = error or ("Configure personal thresholds before alerts can run." if self.current is Status.UNCONFIGURED
                                else "Check the official Libre app before acting on this reading.")
                if decision.acknowledged:
                    msg += "  •  Supplementary alerts acknowledged"
                self.detail.configure(text=msg)
                self.delivery.configure(text="; ".join(results[-2:]) if results else
                                        ("External actions OFF (dry run)" if self.settings.dry_run else "Monitoring"))
                if decision.local_alarm and self.settings.local_sound:
                    play_sound(self.root)
        except queue.Empty:
            pass
        self.root.after(250, self.drain)

    def screen_pulse(self):
        # Slow visual pulse; default OFF. Status text remains readable in both phases.
        self.pulse = not self.pulse
        active = self.settings.screen_pulse and self.current in {Status.LOW, Status.HIGH} and self.pulse
        self.status.configure(bg="#29333a" if active else _BG)
        self.root.after(850, self.screen_pulse)

    def run(self):
        self.root.mainloop()
