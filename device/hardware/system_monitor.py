import logging
import threading
import time

try:
    import psutil
except Exception:  # pragma: no cover - fallback for dev/test envs without psutil
    class _Mem:
        used = 0
        total = 0
        percent = 0

    class _Disk:
        percent = 0

    class _PsutilFallback:
        @staticmethod
        def cpu_percent(interval=0):
            return 0

        @staticmethod
        def virtual_memory():
            return _Mem()

        @staticmethod
        def disk_usage(_path):
            return _Disk()

    psutil = _PsutilFallback()

logger = logging.getLogger("system.monitor")


class SystemMonitor:
    def __init__(self, interval=30):
        self.interval = interval
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            self._log_stats()
            time.sleep(self.interval)

    def _log_stats(self):
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        temp = self._get_temp()
        logger.info(
            f"CPU:{cpu}% "
            f"RAM:{mem.used//1024//1024}MB/"
            f"{mem.total//1024//1024}MB "
            f"({mem.percent}%) "
            f"DISK:{disk.percent}% "
            f"TEMP:{temp}°C"
        )

    def _get_temp(self):
        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                return round(int(f.read()) / 1000, 1)
        except Exception:
            return 0

    def get_snapshot(self) -> dict:
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "ram_used_mb": mem.used // 1024 // 1024,
            "ram_total_mb": mem.total // 1024 // 1024,
            "ram_percent": mem.percent,
            "temp_c": self._get_temp(),
            "disk_percent": psutil.disk_usage('/').percent,
        }
