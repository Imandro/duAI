"""Auto-clean background service with idle detection and time-based scheduling."""

import os
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
from ..core.panic import perform_silent_clean
from ..core.viral import get_stats
from ..utils.logger import log
from ..utils.settings import get_settings
from ..utils.paths import is_admin


class IdleDetector:
    """Detects system idle time using Windows API."""
    
    def __init__(self):
        self._last_input_time = 0
        try:
            import ctypes
            from ctypes import wintypes
            
            self._user32 = ctypes.windll.user32
            self._GetLastInputInfo = self._user32.GetLastInputInfo
            self._GetLastInputInfo.argtypes = [ctypes.POINTER(wintypes.LASTINPUTINFO)]
            self._GetLastInputInfo.restype = wintypes.BOOL
            self._available = True
        except Exception:
            self._available = False
    
    def get_idle_seconds(self) -> float:
        """Get seconds since last user input."""
        if not self._available:
            return 0.0
        
        try:
            import ctypes
            from ctypes import wintypes
            
            lii = wintypes.LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(wintypes.LASTINPUTINFO)
            if self._GetLastInputInfo(ctypes.byref(lii)):
                current_tick = ctypes.windll.kernel32.GetTickCount()
                idle_ticks = current_tick - lii.dwTime
                return idle_ticks / 1000.0
        except Exception:
            pass
        return 0.0
    
    def is_idle(self, threshold_seconds: int) -> bool:
        """Check if system has been idle for at least threshold seconds."""
        return self.get_idle_seconds() >= threshold_seconds


class AutoCleanService:
    """Background auto-clean service."""
    
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._idle_detector = IdleDetector()
        self._last_clean_time = 0
        self._last_idle_clean = 0
        self._clean_callback: Optional[Callable] = None
        self._progress_callback: Optional[Callable] = None
        
        # Config
        self._enabled = False
        self._idle_threshold = 300  # 5 minutes
        self._time_interval = 3600  # 1 hour
        self._require_admin = False
        self._clean_mode = "recycle"
        self._min_freed_mb = 1  # Minimum MB to consider clean "worth it"
    
    def configure(self, 
                  enabled: bool = True,
                  idle_threshold: int = 300,
                  time_interval: int = 3600,
                  require_admin: bool = False,
                  clean_mode: str = "recycle",
                  min_freed_mb: int = 1):
        """Configure auto-clean settings."""
        self._enabled = enabled
        self._idle_threshold = idle_threshold
        self._time_interval = time_interval
        self._require_admin = require_admin
        self._clean_mode = clean_mode
        self._min_freed_mb = min_freed_mb
        
        # Save to settings
        settings = get_settings()
        settings.set("auto_clean.enabled", enabled)
        settings.set("auto_clean.idle_threshold", idle_threshold)
        settings.set("auto_clean.time_interval", time_interval)
        settings.set("auto_clean.require_admin", require_admin)
        settings.set("auto_clean.mode", clean_mode)
        settings.set("auto_clean.min_freed_mb", min_freed_mb)
        settings.save()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from settings and return it as a dict."""
        settings = get_settings()
        self._enabled = settings.get("auto_clean.enabled", False)
        self._idle_threshold = settings.get("auto_clean.idle_threshold", 300)
        self._time_interval = settings.get("auto_clean.time_interval", 3600)
        self._require_admin = settings.get("auto_clean.require_admin", False)
        self._clean_mode = settings.get("auto_clean.mode", "recycle")
        self._min_freed_mb = settings.get("auto_clean.min_freed_mb", 1)
        return {
            "enabled": self._enabled,
            "idle_threshold": self._idle_threshold,
            "time_interval": self._time_interval,
            "require_admin": self._require_admin,
            "mode": self._clean_mode,
            "min_freed_mb": self._min_freed_mb,
        }

    @property
    def config(self) -> Dict[str, Any]:
        """Configuracion actual (sin recargar de disco)."""
        return {
            "enabled": self._enabled,
            "idle_threshold": self._idle_threshold,
            "time_interval": self._time_interval,
            "require_admin": self._require_admin,
            "mode": self._clean_mode,
            "min_freed_mb": self._min_freed_mb,
        }
    
    def set_callbacks(self, clean_callback: Callable = None, progress_callback: Callable = None):
        """Set callbacks for clean completion and progress."""
        self._clean_callback = clean_callback
        self._progress_callback = progress_callback
    
    def start(self):
        """Start the background service."""
        if self._thread and self._thread.is_alive():
            return
        
        self.load_config()
        if not self._enabled:
            log("auto_clean", status="disabled")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        log("auto_clean", status="started", idle_threshold=self._idle_threshold, 
            time_interval=self._time_interval)
    
    def stop(self):
        """Stop the background service."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        log("auto_clean", status="stopped")
    
    def _run_loop(self):
        """Main service loop."""
        check_interval = 30  # Check every 30 seconds
        
        while not self._stop_event.is_set():
            try:
                self._check_and_clean()
            except Exception as e:
                log("auto_clean", error=str(e))
            
            # Sleep in small increments to allow quick shutdown
            for _ in range(check_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
    
    def _check_and_clean(self):
        """Check conditions and run clean if appropriate."""
        now = time.time()
        
        # Check time-based clean
        time_due = (now - self._last_clean_time) >= self._time_interval
        
        # Check idle-based clean
        idle_due = False
        if self._idle_detector.is_idle(self._idle_threshold):
            # Only clean once per idle session
            if (now - self._last_idle_clean) >= self._idle_threshold:
                idle_due = True
        
        if not (time_due or idle_due):
            return
        
        # Check if we should run (admin rights, etc.)
        if self._require_admin and not is_admin():
            log("auto_clean", skipped="admin_required")
            return
        
        # Run silent clean
        log("auto_clean", trigger="time" if time_due else "idle", starting=True)
        
        def progress(result):
            if self._progress_callback:
                self._progress_callback(result)
        
        def done(result):
            freed_mb = result.freed_bytes / (1024 * 1024)
            if freed_mb >= self._min_freed_mb:
                self._last_clean_time = now
                if idle_due:
                    self._last_idle_clean = now
                
                stats = get_stats()
                stats.record_clean(result.removed_items, result.freed_bytes)
                
                log("auto_clean", completed=True, freed_mb=round(freed_mb, 2), 
                    items=result.removed_items)
                
                if self._clean_callback:
                    self._clean_callback(result)
            else:
                log("auto_clean", skipped="below_threshold", freed_mb=round(freed_mb, 2))
        
        perform_silent_clean(
            permanent=(self._clean_mode == "permanent"),
            progress=done,
        )
    
    def force_clean(self) -> Dict[str, Any]:
        """Force an immediate clean (for manual trigger).

        Devuelve siempre un dict:
          {"ok": True, "removed_items": int, "freed_bytes": int,
           "errors": int, "result": CleanResult}
        o {"error": "<motivo>"} si algo falla.
        """
        if self._require_admin and not is_admin():
            return {"error": "admin_required"}

        container: Dict[str, Any] = {}
        done_event = threading.Event()

        def done(result):
            container["result"] = result
            done_event.set()

        try:
            perform_silent_clean(
                permanent=(self._clean_mode == "permanent"),
                progress=done,
            )
        except Exception as exc:  # noqa: BLE001 - nunca dejar la UI colgada
            log("auto_clean", error=str(exc))
            return {"error": str(exc)}

        done_event.wait(timeout=60)

        result = container.get("result")
        if result is None:
            return {"error": "timeout"}

        return {
            "ok": True,
            "removed_items": getattr(result, "removed_items", 0),
            "freed_bytes": getattr(result, "freed_bytes", 0),
            "errors": getattr(result, "errors", 0),
            "result": result,
        }


# Global service instance
_auto_clean_service = None


def get_auto_clean_service() -> AutoCleanService:
    global _auto_clean_service
    if _auto_clean_service is None:
        _auto_clean_service = AutoCleanService()
    return _auto_clean_service


def start_auto_clean():
    """Start auto-clean service."""
    get_auto_clean_service().start()


def stop_auto_clean():
    """Stop auto-clean service."""
    get_auto_clean_service().stop()


def configure_auto_clean(**kwargs):
    """Configure auto-clean settings."""
    get_auto_clean_service().configure(**kwargs)


def force_auto_clean() -> Dict[str, Any]:
    """Force immediate auto-clean."""
    return get_auto_clean_service().force_clean()