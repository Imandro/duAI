import ctypes
import ctypes.wintypes
import subprocess
import sys

from PySide6.QtCore import QThread

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x1
MOD_CONTROL = 0x2
VK_D = 0x44


class HotkeyWorker(QThread):
    triggered = None

    def __init__(self, callback):
        super().__init__()
        self._callback = callback
        self._thread_id = None

    def run(self):
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT, VK_D):
            return
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == 1:
                try:
                    self._callback()
                except Exception:
                    pass
            elif msg.message == WM_QUIT:
                break
        user32.UnregisterHotKey(None, 1)

    def stop(self):
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self.wait(3000)


def create_logon_task(task_name="duAI_AutoClean", args="--panic"):
    if getattr(sys, "frozen", False):
        action = f'"{sys.executable}" {args}'
    else:
        python_exe = sys.executable
        main_py = get_main_path()
        action = f'"{python_exe}" "{main_py}" {args}'
    result = subprocess.run(
        ["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/RL", "LIMITED",
         "/TN", task_name, "/TR", action],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def remove_logon_task(task_name="duAI_AutoClean"):
    result = subprocess.run(
        ["schtasks", "/Delete", "/F", "/TN", task_name],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def logon_task_exists(task_name="duAI_AutoClean"):
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def get_main_path():
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
