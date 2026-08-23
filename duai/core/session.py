import os
import shutil
import subprocess
import uuid

from ..utils.logger import log
from ..utils.paths import expand

BROWSER_CANDIDATES = {
    "edge": [
        r"%ProgramFiles(x86)%/Microsoft/Edge/Application/msedge.exe",
        r"%ProgramFiles%/Microsoft/Edge/Application/msedge.exe",
    ],
    "chrome": [
        r"%ProgramFiles%/Google/Chrome/Application/chrome.exe",
        r"%ProgramFiles(x86)%/Google/Chrome/Application/chrome.exe",
        r"%LOCALAPPDATA%/Google/Chrome/Application/chrome.exe",
    ],
    "brave": [
        r"%LOCALAPPDATA%/BraveSoftware/Brave-Browser/Application/brave.exe",
        r"%ProgramFiles%/BraveSoftware/Brave-Browser/Application/brave.exe",
    ],
}

AI_SITES = [
    ("CHATGPT", "https://chatgpt.com"),
    ("CLAUDE", "https://claude.ai"),
    ("GEMINI", "https://gemini.google.com"),
    ("PERPLEXITY", "https://perplexity.ai"),
    ("COPILOT", "https://copilot.microsoft.com"),
    ("POE", "https://poe.com"),
    ("DEEPSEEK", "https://chat.deepseek.com"),
]


def available_browsers():
    found = []
    for browser_id, candidates in BROWSER_CANDIDATES.items():
        for candidate in candidates:
            path = expand(candidate)
            if os.path.isfile(path):
                found.append((browser_id, path))
                break
    return found


def session_profile_dir():
    return expand("%LOCALAPPDATA%/duAI/session_profile")


class ProtectedSession:
    def __init__(self, browser_exe, url):
        self.browser_exe = browser_exe
        self.url = url
        self.process = None
        self.profile = session_profile_dir()

    def start(self):
        if self.is_running():
            return False
        shutil.rmtree(self.profile, ignore_errors=True)
        os.makedirs(self.profile, exist_ok=True)
        args = [
            self.browser_exe,
            f"--user-data-dir={self.profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=msImplicitSignin,msSignIn",
            self.url,
        ]
        self.process = subprocess.Popen(
            args, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
        log("session_start", browser=self.browser_exe, url=self.url)
        return True

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def stop_and_wipe(self):
        stopped = False
        if self.process is not None:
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                capture_output=True,
            )
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            stopped = True
            self.process = None
        wiped = False
        for _attempt in range(5):
            try:
                shutil.rmtree(self.profile, ignore_errors=False)
                wiped = True
                break
            except OSError:
                import time

                time.sleep(0.6)
        if not wiped:
            shutil.rmtree(self.profile, ignore_errors=True)
            wiped = not os.path.exists(self.profile)
        log("session_stop", wiped=wiped)
        return stopped or wiped


_active_session = None


def get_active_session():
    return _active_session


def start_session(browser_exe, url):
    global _active_session
    if _active_session and _active_session.is_running():
        return False
    _active_session = ProtectedSession(browser_exe, url)
    return _active_session.start()


def stop_session():
    global _active_session
    if _active_session is None:
        return True
    result = _active_session.stop_and_wipe()
    _active_session = None
    return result


def has_running_session():
    return _active_session is not None and _active_session.is_running()
