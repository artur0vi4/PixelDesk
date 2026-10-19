"""Системные метрики: CPU, RAM, сеть, температуры CPU/GPU + GPU
(NVIDIA через nvidia-smi, AMD/Intel/другие — счётчики «GPU Engine»).

Температуры (Windows, по цепочке, что первый сработает):
  1. LibreHardwareMonitor (WMI root/LibreHardwareMonitor) — CPU и GPU;
  2. OpenHardwareMonitor (WMI root/OpenHardwareMonitor) — CPU и GPU;
  3. MSAcpi_ThermalZoneTemperature (WMI root/wmi) — только CPU/плата.
Вне Windows — psutil.sensors_temperatures().
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import threading
import time

import psutil
from PySide6.QtCore import QObject, QTimer, Signal

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _run(cmd: list, timeout: float = 15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None


class SystemMonitor(QObject):
    """Публикует сигналы tick (раз в секунду) и gpu (раз в ~4 секунды)."""

    tick = Signal(dict)     # {"cpu", "ram", "down", "up"}
    gpu = Signal(object)    # {"util", "temp", "cpu_temp"} | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_net = None
        self._last_t = 0.0
        self._stop = threading.Event()
        self._temps: dict = {}      # {"cpu": .., "gpu": ..} — кэш на 12 с
        self._temps_ts = 0.0
        self._thread: threading.Thread | None = None
        psutil.cpu_percent(None)  # первичный замер
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._sample)

    def start(self) -> None:
        self._timer.start()
        self._thread = threading.Thread(target=self._gpu_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._timer.stop()
        self._stop.set()

    # ------------------------------------------------------------------ #
    def _sample(self) -> None:
        cpu = psutil.cpu_percent(None)
        ram = psutil.virtual_memory().percent
        cnt = psutil.net_io_counters()
        now = time.monotonic()
        down = up = 0.0
        if self._last_net is not None:
            dt = max(1e-6, now - self._last_t)
            down = (cnt.bytes_recv - self._last_net.bytes_recv) * 8 / 1e6 / dt
            up = (cnt.bytes_sent - self._last_net.bytes_sent) * 8 / 1e6 / dt
        self._last_net, self._last_t = cnt, now
        self.tick.emit({"cpu": cpu, "ram": ram,
                        "down": max(0.0, down), "up": max(0.0, up)})

    # ------------------------------------------------------------------ #
    #  GPU: NVIDIA -> nvidia-smi;  AMD/Intel -> GPU Engine (WMI)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _find_nvidia_smi():
        exe = shutil.which("nvidia-smi")
        if exe:
            return exe
        if os.name == "nt":
            p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                             "System32", "nvidia-smi.exe")
            if os.path.exists(p):
                return p
        return None

    def _gpu_nvidia(self):
        exe = self._find_nvidia_smi()
        if not exe:
            return None
        out = _run([exe, "--query-gpu=utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits"], timeout=6)
        if not out:
            return None
        try:
            parts = out.splitlines()[0].split(",")
            util = float(parts[0].strip().replace("%", ""))
            temp = None
            if len(parts) > 1:
                t = parts[1].strip()
                if t and t.upper() != "N/A":
                    temp = float(t)
            return {"util": max(0.0, min(100.0, util)), "temp": temp}
        except Exception:
            return None

    def _gpu_wmi(self):
        """Счётчики «GPU Engine» — универсально для AMD, Intel и NVIDIA
        (Windows 10 1803+). Языконезависимые классы WMI."""
        if os.name != "nt":
            return None
        out = _run([
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "(Get-CimInstance -ClassName "
            "Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | "
            "Measure-Object -Property UtilizationPercentage -Sum).Sum",
        ], timeout=25)
        if not out:
            return None
        try:
            val = float(out)
            return {"util": max(0.0, min(100.0, val)), "temp": None}
        except ValueError:
            return None

    # ------------------------------------------------------------------ #
    #  Температуры: Libre/OpenHardwareMonitor -> ACPI -> psutil
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_temp_csv(out: str) -> dict:
        """CSV «Name","Value" из HardwareMonitor -> {"cpu": .., "gpu": ..}."""
        res: dict = {}
        cpu_vals, gpu_vals = [], []
        try:
            rows = list(csv.reader(io.StringIO(out)))
        except Exception:
            return res
        if len(rows) < 2:
            return res
        name_i = val_i = None
        for i, h in enumerate(rows[0]):
            if h.strip().lower() == "name":
                name_i = i
            elif h.strip().lower() == "value":
                val_i = i
        if name_i is None or val_i is None:
            return res
        for row in rows[1:]:
            if len(row) <= max(name_i, val_i):
                continue
            name = (row[name_i] or "").lower()
            raw = (row[val_i] or "").replace(",", ".").strip()
            try:
                v = float(raw)
            except ValueError:
                continue
            if -20.0 < v < 130.0:
                if "cpu" in name:
                    cpu_vals.append(v)
                elif "gpu" in name:
                    gpu_vals.append(v)
        if cpu_vals:
            res["cpu"] = max(cpu_vals)
        if gpu_vals:
            res["gpu"] = max(gpu_vals)
        return res

    def _hwmon_temps(self, namespace: str) -> dict | None:
        """Температуры из WMI Libre/OpenHardwareMonitor (если запущены)."""
        if os.name != "nt":
            return None
        out = _run([
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "(Get-CimInstance -Namespace " + namespace + " -ClassName Sensor "
            "-Filter SensorType='Temperature' | Select-Object Name,Value | "
            "ConvertTo-Csv -NoTypeInformation)",
        ], timeout=15)
        if not out or "Name" not in out:
            return None
        res = self._parse_temp_csv(out)
        return res or None

    def _acpi_temp(self) -> float | None:
        """MSAcpi_ThermalZoneTemperature — десятые доли Кельвина."""
        if os.name != "nt":
            return None
        out = _run([
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "(Get-CimInstance -Namespace root/wmi -ClassName "
            "MSAcpi_ThermalZoneTemperature | Measure-Object -Property "
            "CurrentTemperature -Maximum).Maximum",
        ], timeout=15)
        if not out:
            return None
        try:
            k = float(out.strip())
            c = k / 10.0 - 273.15
        except ValueError:
            return None
        return round(c, 1) if -20.0 < c < 130.0 else None

    @staticmethod
    def _linux_cpu_temp() -> float | None:
        if os.name == "nt":
            return None
        try:
            zones = psutil.sensors_temperatures()
        except Exception:
            return None
        vals = []
        for key in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"):
            for e in zones.get(key, []):
                if e.current and -20.0 < e.current < 130.0:
                    vals.append(float(e.current))
        return max(vals) if vals else None

    def _read_temps(self) -> dict:
        """Обновляет кэш температур. Вызывается не чаще раза в 12 секунд."""
        for ns in ("root/LibreHardwareMonitor", "root/OpenHardwareMonitor"):
            res = self._hwmon_temps(ns)
            if res:
                return res
        t = self._acpi_temp()
        if t is not None:
            return {"cpu": t}
        t = self._linux_cpu_temp()
        if t is not None:
            return {"cpu": t}
        return {}

    def _gpu_loop(self) -> None:
        fails = 0
        while not self._stop.is_set():
            gpu = self._gpu_nvidia()
            if gpu is None:
                gpu = self._gpu_wmi()
            if time.monotonic() - self._temps_ts > 12:
                self._temps = self._read_temps()
                self._temps_ts = time.monotonic()
            cpu_t = self._temps.get("cpu")
            gpu_t = (gpu or {}).get("temp")
            if gpu_t is None:
                gpu_t = self._temps.get("gpu")
            if gpu is None and cpu_t is None and gpu_t is None:
                fails += 1
                if fails <= 2:
                    self.gpu.emit(None)
                self._stop.wait(10 if fails >= 2 else 5)
                continue
            fails = 0
            self.gpu.emit({
                "util": (gpu or {}).get("util"),
                "temp": gpu_t,
                "cpu_temp": cpu_t,
            })
            self._stop.wait(4)
