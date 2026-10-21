"""Robust task scheduler with health checks, persistence, and Windows Task Scheduler integration."""

import ctypes
import ctypes.wintypes
import os
import json
import sys
import time
import threading
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field, asdict
from ..utils.logger import log, base_dir
from ..utils.settings import get_settings
from ..utils.paths import is_admin


# ============================================================
# HOTKEY GLOBAL (Win32 RegisterHotKey)
# ============================================================

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x1
MOD_CONTROL = 0x2
MOD_SHIFT = 0x4
MOD_WIN = 0x8
VK_D = 0x44
VK_P = 0x50
VK_X = 0x58


def _resolve_hotkey(combo: str):
    """Convierte 'Ctrl+Shift+P' en (modifiers, vk_code)."""
    parts = [p.strip().lower() for p in (combo or "Ctrl+Shift+P").split("+")]
    mods = 0
    vk = VK_P

    vk_map = {
        "p": VK_P, "x": VK_X, "d": VK_D,
        "a": 0x41, "b": 0x42, "c": 0x43, "e": 0x45, "f": 0x46,
        "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B,
        "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F, "q": 0x51,
        "r": 0x52, "s": 0x53, "t": 0x54, "u": 0x55, "v": 0x56,
        "w": 0x57, "y": 0x59, "z": 0x5A,
    }

    for part in parts:
        if part == "ctrl":
            mods |= MOD_CONTROL
        elif part == "alt":
            mods |= MOD_ALT
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part in ("win", "meta", "super"):
            mods |= MOD_WIN
        elif part in vk_map:
            vk = vk_map[part]

    return mods, vk


class HotkeyWorker:
    """Registra un atajo global de Windows para activar el modo panico.

    Usa un hilo dedicado con RegisterHotKey / GetMessageW.
    """

    def __init__(self, callback, combo: str = "Ctrl+Shift+P"):
        self._callback = callback
        self._combo = combo
        self._thread = None
        self._thread_id = None
        self._stop_event = threading.Event()

    def start(self):
        """Inicia el hilo que registra el atajo."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
        except Exception:
            return

        self._thread_id = kernel32.GetCurrentThreadId()
        mods, vk = _resolve_hotkey(self._combo)

        if not user32.RegisterHotKey(None, 1, mods, vk):
            log("hotkey", error="RegisterHotKey failed", combo=self._combo)
            return

        msg = ctypes.wintypes.MSG()
        try:
            while not self._stop_event.is_set():
                # GetMessageW bloquea; timeout para poder comprobar el stop
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 1000)
                if result in (0, -1):
                    break
                if msg.message == WM_HOTKEY and msg.wParam == 1:
                    try:
                        self._callback()
                    except Exception:
                        pass
                elif msg.message == WM_QUIT:
                    break
        finally:
            user32.UnregisterHotKey(None, 1)

    def stop(self):
        """Detiene el hilo y libera el atajo."""
        self._stop_event.set()
        if self._thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3)


# ============================================================
# TAREAS PROGRAMADAS DE WINDOWS (schtasks)
# ============================================================

def get_main_path() -> str:
    """Ruta al entrypoint principal (main.py) o al ejecutable congelado."""
    import os

    if getattr(sys, "frozen", False):
        return sys.executable
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "main.py"),
        os.path.join(os.path.dirname(sys.argv[0]) or ".", "main.py"),
    ]
    for candidate in candidates:
        path = os.path.normpath(candidate)
        if os.path.isfile(path):
            return path
    return os.path.abspath("main.py")


def create_logon_task(task_name: str = "duAI_AutoClean", args: str = "--panic") -> bool:
    """Crea una tarea programada de Windows que se ejecuta al iniciar sesion."""
    if getattr(sys, "frozen", False):
        action = f'"{sys.executable}" {args}'
    else:
        action = f'"{sys.executable}" "{get_main_path()}" {args}'
    try:
        result = subprocess.run(
            ["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/RL", "LIMITED",
             "/TN", task_name, "/TR", action],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def remove_logon_task(task_name: str = "duAI_AutoClean") -> bool:
    """Elimina la tarea programada de Windows."""
    try:
        result = subprocess.run(
            ["schtasks", "/Delete", "/F", "/TN", task_name],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def logon_task_exists(task_name: str = "duAI_AutoClean") -> bool:
    """Comprueba si la tarea programada existe."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", task_name],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DISABLED = "disabled"


class TaskTrigger(Enum):
    STARTUP = "startup"
    IDLE = "idle"
    TIME = "time"
    INTERVAL = "interval"
    MANUAL = "manual"
    EVENT = "event"


@dataclass
class ScheduledTask:
    """A scheduled task definition."""
    id: str
    name: str
    description: str
    trigger: TaskTrigger
    action: str  # Function name to call
    params: Dict[str, Any] = field(default_factory=dict)
    schedule: Dict[str, Any] = field(default_factory=dict)  # cron-like or interval
    enabled: bool = True
    run_as_admin: bool = False
    max_runtime: int = 300  # seconds
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    run_count: int = 0
    failure_count: int = 0
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data["trigger"] = self.trigger.value
        data["status"] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ScheduledTask":
        data = data.copy()
        data["trigger"] = TaskTrigger(data["trigger"])
        data["status"] = TaskStatus(data["status"])
        return cls(**data)


class TaskScheduler:
    """Robust task scheduler with persistence and health monitoring."""
    
    def __init__(self, tasks_file: str = None):
        self.tasks_file = tasks_file or os.path.join(base_dir(), "scheduled_tasks.json")
        self.tasks: Dict[str, ScheduledTask] = {}
        self._running_tasks: Dict[str, threading.Thread] = {}
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._action_handlers: Dict[str, Callable] = {}
        self._health_check_interval = 60  # seconds
        
        # Default tasks
        self._register_default_tasks()
        self.load_tasks()
    
    def _register_default_tasks(self):
        """Register default duAI tasks."""
        defaults = [
            ScheduledTask(
                id="startup_scan",
                name="Startup Quick Scan",
                description="Run a quick scan on startup if enabled",
                trigger=TaskTrigger.STARTUP,
                action="quick_scan",
                params={"silent": True},
                schedule={},
                enabled=False,  # Disabled by default
                tags=["scan", "startup"],
            ),
            ScheduledTask(
                id="daily_cleanup",
                name="Daily Cleanup",
                description="Clean AI traces daily at configured time",
                trigger=TaskTrigger.TIME,
                action="auto_clean",
                params={"mode": "recycle"},
                schedule={"hour": 3, "minute": 0},  # 3 AM
                enabled=True,
                tags=["clean", "daily"],
            ),
            ScheduledTask(
                id="idle_cleanup",
                name="Idle Cleanup",
                description="Clean when system is idle for 10 minutes",
                trigger=TaskTrigger.IDLE,
                action="auto_clean",
                params={"mode": "recycle"},
                schedule={"idle_minutes": 10},
                enabled=False,
                tags=["clean", "idle"],
            ),
            ScheduledTask(
                id="weekly_deep_scan",
                name="Weekly Deep Scan",
                description="Full system scan weekly",
                trigger=TaskTrigger.TIME,
                action="full_scan",
                params={"deep": True},
                schedule={"weekday": 0, "hour": 2, "minute": 0},  # Sunday 2 AM
                enabled=True,
                tags=["scan", "weekly"],
            ),
            ScheduledTask(
                id="update_check",
                name="Update Check",
                description="Check for updates daily",
                trigger=TaskTrigger.TIME,
                action="check_updates",
                params={},
                schedule={"hour": 12, "minute": 0},  # Noon
                enabled=True,
                tags=["update", "daily"],
            ),
            ScheduledTask(
                id="quarantine_purge",
                name="Quarantine Auto-Purge",
                description="Purge old quarantine items (older than 30 days)",
                trigger=TaskTrigger.INTERVAL,
                action="purge_quarantine",
                params={"days": 30},
                schedule={"interval_hours": 168},  # Weekly
                enabled=True,
                tags=["quarantine", "maintenance"],
            ),
            ScheduledTask(
                id="stats_backup",
                name="Stats Backup",
                description="Backup stats and settings",
                trigger=TaskTrigger.INTERVAL,
                action="backup_stats",
                params={},
                schedule={"interval_hours": 24},
                enabled=True,
                tags=["backup", "maintenance"],
            ),
        ]
        
        for task in defaults:
            if task.id not in self.tasks:
                self.tasks[task.id] = task
    
    def register_action(self, name: str, handler: Callable):
        """Register an action handler."""
        self._action_handlers[name] = handler
    
    def load_tasks(self):
        """Load tasks from file."""
        if not os.path.exists(self.tasks_file):
            self.save_tasks()
            return
        
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for task_data in data.get("tasks", []):
                task = ScheduledTask.from_dict(task_data)
                self.tasks[task.id] = task
            
            log("scheduler", loaded=len(self.tasks))
        except Exception as e:
            log("scheduler", load_error=str(e))
    
    def save_tasks(self):
        """Save tasks to file."""
        try:
            data = {
                "version": 1,
                "updated": datetime.now().isoformat(),
                "tasks": [task.to_dict() for task in self.tasks.values()],
            }
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log("scheduler", save_error=str(e))
    
    def add_task(self, task: ScheduledTask) -> bool:
        """Add or update a task."""
        task.updated_at = datetime.now().isoformat()
        self.tasks[task.id] = task
        self.save_tasks()
        self._recalculate_next_run(task)
        return True
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            self.save_tasks()
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def list_tasks(self, tag: str = None, enabled_only: bool = False) -> List[ScheduledTask]:
        """List tasks with optional filtering."""
        tasks = list(self.tasks.values())
        if tag:
            tasks = [t for t in tasks if tag in t.tags]
        if enabled_only:
            tasks = [t for t in tasks if t.enabled]
        return sorted(tasks, key=lambda t: t.next_run or "")
    
    def enable_task(self, task_id: str, enabled: bool = True) -> bool:
        """Enable or disable a task."""
        task = self.tasks.get(task_id)
        if task:
            task.enabled = enabled
            task.updated_at = datetime.now().isoformat()
            if enabled:
                self._recalculate_next_run(task)
            else:
                task.next_run = None
            self.save_tasks()
            return True
        return False
    
    def _recalculate_next_run(self, task: ScheduledTask):
        """Calculate next run time for a task."""
        now = datetime.now()
        
        if task.trigger == TaskTrigger.STARTUP:
            task.next_run = now.isoformat()
        elif task.trigger == TaskTrigger.TIME:
            schedule = task.schedule
            next_run = now.replace(
                hour=schedule.get("hour", 0),
                minute=schedule.get("minute", 0),
                second=0,
                microsecond=0
            )
            if "weekday" in schedule:
                # Weekly
                days_ahead = schedule["weekday"] - next_run.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                next_run += timedelta(days=days_ahead)
            if next_run <= now:
                next_run += timedelta(days=1)
            task.next_run = next_run.isoformat()
        elif task.trigger == TaskTrigger.INTERVAL:
            interval_hours = task.schedule.get("interval_hours", 24)
            if task.last_run:
                last = datetime.fromisoformat(task.last_run)
                task.next_run = (last + timedelta(hours=interval_hours)).isoformat()
            else:
                task.next_run = (now + timedelta(hours=interval_hours)).isoformat()
        elif task.trigger == TaskTrigger.IDLE:
            task.next_run = "idle"
        else:
            task.next_run = None
    
    def start(self):
        """Start the scheduler."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._scheduler_thread.start()
        log("scheduler", status="started", tasks=len(self.tasks))
    
    def stop(self):
        """Stop the scheduler."""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=10)
        # Wait for running tasks
        for task_id, thread in self._running_tasks.items():
            thread.join(timeout=5)
        log("scheduler", status="stopped")
    
    def _run_loop(self):
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            try:
                self._check_tasks()
                self._health_check()
            except Exception as e:
                log("scheduler", loop_error=str(e))
            
            # Sleep in small increments
            for _ in range(10):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
    
    def _check_tasks(self):
        """Check and run due tasks."""
        now = datetime.now()
        
        for task in self.tasks.values():
            if not task.enabled:
                continue
            
            if task.id in self._running_tasks:
                # Check for timeout
                thread = self._running_tasks[task.id]
                if not thread.is_alive():
                    del self._running_tasks[task_id]
                continue
            
            should_run = False
            
            if task.trigger == TaskTrigger.STARTUP:
                should_run = task.last_run is None  # Only run once per session
            elif task.trigger == TaskTrigger.TIME:
                if task.next_run:
                    next_run = datetime.fromisoformat(task.next_run)
                    should_run = now >= next_run
            elif task.trigger == TaskTrigger.INTERVAL:
                if task.next_run and task.next_run != "idle":
                    next_run = datetime.fromisoformat(task.next_run)
                    should_run = now >= next_run
            elif task.trigger == TaskTrigger.IDLE:
                # Check idle time
                from ..core.auto_clean import IdleDetector
                idle = IdleDetector()
                idle_minutes = task.schedule.get("idle_minutes", 10)
                should_run = idle.is_idle(idle_minutes * 60)
            
            if should_run:
                self._execute_task(task)
    
    def _execute_task(self, task: ScheduledTask):
        """Execute a task in a separate thread."""
        if task.run_as_admin and not is_admin():
            log("scheduler", task=task.id, skipped="admin_required")
            task.status = TaskStatus.SKIPPED
            self.save_tasks()
            return
        
        handler = self._action_handlers.get(task.action)
        if not handler:
            log("scheduler", task=task.id, error="no_handler")
            task.status = TaskStatus.FAILED
            task.failure_count += 1
            self.save_tasks()
            return
        
        def run_task():
            task.status = TaskStatus.RUNNING
            task.last_run = datetime.now().isoformat()
            task.run_count += 1
            self.save_tasks()
            
            log("scheduler", task=task.id, action=task.action, started=True)
            
            try:
                # Run with timeout
                result = handler(**task.params)
                
                task.status = TaskStatus.COMPLETED
                task.failure_count = 0
                log("scheduler", task=task.id, completed=True, result=str(result)[:100])
            except Exception as e:
                task.failure_count += 1
                task.status = TaskStatus.FAILED
                log("scheduler", task=task.id, error=str(e))
                
                # Retry logic
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    # Schedule retry
                    retry_time = datetime.now() + timedelta(seconds=task.retry_delay)
                    task.next_run = retry_time.isoformat()
                    log("scheduler", task=task.id, retry=task.retry_count)
                else:
                    task.retry_count = 0
            
            self._recalculate_next_run(task)
            task.updated_at = datetime.now().isoformat()
            self.save_tasks()
            
            # Clean up
            if task.id in self._running_tasks:
                del self._running_tasks[task.id]
        
        thread = threading.Thread(target=run_task, daemon=True)
        self._running_tasks[task.id] = thread
        thread.start()
    
    def _health_check(self):
        """Perform health checks on running tasks."""
        now = datetime.now()
        
        for task_id, thread in list(self._running_tasks.items()):
            task = self.tasks.get(task_id)
            if not task:
                continue
            
            if not thread.is_alive():
                del self._running_tasks[task_id]
                continue
            
            # Check for timeout
            if task.last_run:
                last_run = datetime.fromisoformat(task.last_run)
                if (now - last_run).total_seconds() > task.max_runtime:
                    log("scheduler", task=task_id, timeout=True, max_runtime=task.max_runtime)
                    # Note: Can't forcibly kill thread in Python, but we can mark it
                    task.status = TaskStatus.FAILED
                    task.failure_count += 1
                    self._recalculate_next_run(task)
                    self.save_tasks()
                    del self._running_tasks[task_id]
    
    def run_task_now(self, task_id: str) -> bool:
        """Manually trigger a task."""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.trigger = TaskTrigger.MANUAL
        self._execute_task(task)
        return True
    
    def get_status(self) -> Dict:
        """Get scheduler status."""
        running = len(self._running_tasks)
        pending = sum(1 for t in self.tasks.values() if t.enabled and t.status == TaskStatus.PENDING)
        failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)
        
        return {
            "running_tasks": running,
            "pending_tasks": pending,
            "failed_tasks": failed,
            "total_tasks": len(self.tasks),
            "enabled_tasks": sum(1 for t in self.tasks.values() if t.enabled),
        }
    
    def install_windows_task(self, task_id: str) -> bool:
        """Install task in Windows Task Scheduler."""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if not is_admin():
            log("scheduler", task=task_id, install_failed="admin_required")
            return False
        
        try:
            # Create XML for task scheduler
            xml = self._generate_task_xml(task)
            xml_path = os.path.join(base_dir(), f"task_{task_id}.xml")
            with open(xml_path, "w") as f:
                f.write(xml)
            
            # Register with schtasks
            cmd = [
                "schtasks", "/Create",
                "/TN", f"duAI_{task_id}",
                "/XML", xml_path,
                "/F"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                log("scheduler", task=task_id, windows_installed=True)
                return True
            else:
                log("scheduler", task=task_id, windows_install_error=result.stderr)
                return False
        except Exception as e:
            log("scheduler", task=task_id, windows_install_error=str(e))
            return False
    
    def _generate_task_xml(self, task: ScheduledTask) -> str:
        """Generate Windows Task Scheduler XML."""
        # Simplified XML generation
        schedule = task.schedule
        trigger_xml = ""
        
        if task.trigger == TaskTrigger.TIME:
            hour = schedule.get("hour", 0)
            minute = schedule.get("minute", 0)
            if "weekday" in schedule:
                trigger_xml = f"""
                <WeeklyTrigger>
                    <StartBoundary>{datetime.now().strftime('%Y-%m-%d')}T{hour:02d}:{minute:02d}:00</StartBoundary>
                    <Enabled>true</Enabled>
                    <DaysOfWeek><Sunday/></DaysOfWeek>
                </WeeklyTrigger>
                """
            else:
                trigger_xml = f"""
                <DailyTrigger>
                    <StartBoundary>{datetime.now().strftime('%Y-%m-%d')}T{hour:02d}:{minute:02d}:00</StartBoundary>
                    <Enabled>true</Enabled>
                </DailyTrigger>
                """
        elif task.trigger == TaskTrigger.INTERVAL:
            interval = schedule.get("interval_hours", 24)
            trigger_xml = f"""
            <TimeTrigger>
                <StartBoundary>{datetime.now().strftime('%Y-%m-%d')}T00:00:00</StartBoundary>
                <Enabled>true</Enabled>
                <Repetition>
                    <Interval>PT{interval}H</Interval>
                    <Duration>P1D</Duration>
                </Repetition>
            </TimeTrigger>
            """
        
        exe_path = sys.executable
        script_args = f"-m duai.cli run_task {task.id}"
        
        return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
    <RegistrationInfo>
        <Description>{task.description}</Description>
        <Author>duAI</Author>
    </RegistrationInfo>
    <Triggers>
        {trigger_xml}
    </Triggers>
    <Principals>
        <Principal id="Author">
            <RunLevel>LeastAvailable</RunLevel>
        </Principal>
    </Principals>
    <Settings>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <AllowHardTerminate>true</AllowHardTerminate>
        <StartWhenAvailable>true</StartWhenAvailable>
        <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    </Settings>
    <Actions Context="Author">
        <Exec>
            <Command>{exe_path}</Command>
            <Arguments>{script_args}</Arguments>
        </Exec>
    </Actions>
</Task>
"""
    
    def uninstall_windows_task(self, task_id: str) -> bool:
        """Uninstall task from Windows Task Scheduler."""
        try:
            cmd = ["schtasks", "/Delete", "/TN", f"duAI_{task_id}", "/F"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False


# Global scheduler instance
_scheduler = None


def get_scheduler() -> TaskScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


def start_scheduler():
    get_scheduler().start()


def stop_scheduler():
    get_scheduler().stop()