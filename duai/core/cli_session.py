import os
import shutil
import subprocess
import tempfile
import threading
import time

from ..utils.paths import expand

SANDBOX_BASE = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "duAI", "cli_sandbox")
POWERSHELL_HISTORY = os.path.join(
    os.path.expandvars("%APPDATA%"),
    "Microsoft", "Windows", "PowerShell", "PSReadLine", "ConsoleHost_history.txt"
)

CLI_TOOLS = {
    "opencode": {
        "name": "OpenCode",
        "exe": "opencode",
        "args": [],
        "config_dirs": [".opencode"],
        "env_overrides": {
            "XDG_CONFIG_HOME": "__SANDBOX__/config",
            "XDG_CACHE_HOME": "__SANDBOX__/cache",
            "HOME": "__SANDBOX__/home",
        },
    },
    "claude": {
        "name": "Claude Code",
        "exe": "claude",
        "args": [],
        "config_dirs": [".claude"],
        "env_overrides": {
            "CLAUDE_CONFIG_DIR": "__SANDBOX__/.claude",
            "HOME": "__SANDBOX__/home",
        },
    },
    "codex": {
        "name": "Codex CLI",
        "exe": "codex",
        "args": [],
        "config_dirs": [".codex"],
        "env_overrides": {
            "OPENAI_CONFIG_DIR": "__SANDBOX__/.codex",
            "HOME": "__SANDBOX__/home",
        },
    },
    "gemini": {
        "name": "Gemini CLI",
        "exe": "gemini",
        "args": [],
        "config_dirs": [".gemini"],
        "env_overrides": {
            "GEMINI_CONFIG_DIR": "__SANDBOX__/.gemini",
            "HOME": "__SANDBOX__/home",
        },
    },
    "aider": {
        "name": "Aider",
        "exe": "aider",
        "args": [],
        "config_dirs": [".aider"],
        "env_overrides": {
            "AIDER_CONFIG_DIR": "__SANDBOX__/.aider",
            "HOME": "__SANDBOX__/home",
        },
    },
}


def list_tools():
    return {k: v["name"] for k, v in CLI_TOOLS.items()}


def cleanup_orphan_sandboxes():
    if not os.path.isdir(SANDBOX_BASE):
        return
    for name in os.listdir(SANDBOX_BASE):
        path = os.path.join(SANDBOX_BASE, name)
        if os.path.isdir(path):
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass


def _create_sandbox(tool_id, custom_name=None):
    ts = int(time.time())
    name = custom_name or f"{tool_id}_{ts}"
    sandbox = os.path.join(SANDBOX_BASE, name)
    os.makedirs(sandbox, exist_ok=True)
    os.makedirs(os.path.join(sandbox, "home"), exist_ok=True)
    os.makedirs(os.path.join(sandbox, "config"), exist_ok=True)
    os.makedirs(os.path.join(sandbox, "cache"), exist_ok=True)
    return sandbox


def _build_env(tool_id, sandbox):
    import copy
    env = copy.deepcopy(os.environ)
    tool = CLI_TOOLS.get(tool_id, {})
    overrides = tool.get("env_overrides", {})
    sandbox_home = os.path.join(sandbox, "home")
    for key, val in overrides.items():
        if val == "__SANDBOX__":
            env[key] = sandbox
        elif val.startswith("__SANDBOX__/"):
            sub = val.replace("__SANDBOX__/", "")
            target = os.path.join(sandbox, sub.replace("/", os.sep))
            os.makedirs(target, exist_ok=True)
            env[key] = target
        elif val == "__SANDBOX__/home":
            env[key] = sandbox_home
        else:
            env[key] = val
    env["USERPROFILE"] = sandbox_home
    env["HOMEDRIVE"] = os.environ.get("HOMEDRIVE", "C:")
    env["HOMEPATH"] = sandbox_home.replace("C:", "") if "C:" in sandbox_home else sandbox_home
    env["APPDATA"] = os.path.join(sandbox, "config")
    env["LOCALAPPDATA"] = os.path.join(sandbox, "cache")
    env["PSReadLineHistorySaveStyle"] = "None"
    env["PROMPT"] = "(duAI sandbox) $P "
    return env


def _purge_powershell_history_ai():
    if not os.path.isfile(POWERSHELL_HISTORY):
        return
    try:
        markers = ["opencode", "claude", "codex", "gemini", "aider", "chatgpt", "openai", "anthropic", "deepseek"]
        with open(POWERSHELL_HISTORY, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        filtered = [line for line in lines if not any(m in line.lower() for m in markers)]
        with open(POWERSHELL_HISTORY, "w", encoding="utf-8") as f:
            f.writelines(filtered)
    except Exception:
        pass


class CLISession:
    def __init__(self, tool_id, cwd=None):
        self.tool_id = tool_id
        self.tool = CLI_TOOLS.get(tool_id, {})
        self.cwd = cwd or os.path.expandvars("%USERPROFILE%")
        self.sandbox = _create_sandbox(tool_id)
        self.env = _build_env(tool_id, self.sandbox)
        self.process = None
        self._finished = False
        self._on_exit = None
        self._watcher = None

    def start(self):
        cmd = [self.tool["exe"]] + self.tool.get("args", [])
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=self.cwd,
                env=self.env,
                creationflags=0x00000010,
            )
            self._start_watcher()
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def _start_watcher(self):
        def _watch():
            if self.process:
                self.process.wait()
            self._finished = True
            self.cleanup()
            if self._on_exit:
                self._on_exit(self)

        self._watcher = threading.Thread(target=_watch, daemon=True)
        self._watcher.start()

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self._finished = True
        self.cleanup()

    def cleanup(self):
        try:
            if os.path.isdir(self.sandbox):
                shutil.rmtree(self.sandbox, ignore_errors=True)
        except Exception:
            pass
        _purge_powershell_history_ai()

    @property
    def is_running(self):
        return self.process is not None and self.process.poll() is None

    @property
    def exit_code(self):
        if self.process:
            return self.process.returncode
        return None


_active_session = None
_lock = threading.Lock()


def start_session(tool_id, cwd=None):
    global _active_session
    with _lock:
        if _active_session and _active_session.is_running:
            return None
        session = CLISession(tool_id, cwd)
        if session.start():
            _active_session = session
            return session
        return None


def stop_session():
    global _active_session
    with _lock:
        if _active_session:
            _active_session.stop()
            _active_session = None


def get_active_session():
    return _active_session


def has_running_session():
    return _active_session is not None and _active_session.is_running
