import os
import shutil
import subprocess

MARKERS = [
    "chatgpt",
    "openai",
    "claude",
    "anthropic",
    "copilot",
    "cursor",
    "ollama",
    "windsurf",
    "codeium",
    "lm studio",
    "lm-studio",
    "gpt4all",
    "nomic.ai",
    "perplexity",
    "gemini",
    "deepseek",
    "mistral",
]

UNINSTALL_KEYS = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def is_ai_app_name(name):
    lowered = str(name).lower()
    return any(marker in lowered for marker in MARKERS)


def _read_values(key):
    import winreg

    out = {}
    index = 0
    while True:
        try:
            name, value, _ = winreg.EnumValue(key, index)
        except OSError:
            break
        index += 1
        out[name.lower()] = "" if value is None else str(value)
    return out


def find_installed_ai_apps():
    import winreg

    results = []
    seen = set()
    for hive_name, path in UNINSTALL_KEYS:
        hive = winreg.HKEY_CURRENT_USER if hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        index = 0
        while True:
            try:
                sub_key = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            try:
                key = winreg.OpenKey(root, sub_key)
            except OSError:
                continue
            try:
                data = _read_values(key)
            finally:
                winreg.CloseKey(key)
            name = data.get("displayname", "")
            if not name or not is_ai_app_name(name):
                continue
            if data.get("systemcomponent") == "1":
                continue
            if not data.get("uninstallstring"):
                continue
            fingerprint = (name.lower(), data["uninstallstring"].lower())
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            results.append(
                {
                    "name": name,
                    "hive": hive_name,
                    "key": path + "\\" + sub_key,
                    "uninstall_string": data["uninstallstring"],
                    "quiet_string": data.get("quietuninstallstring", ""),
                    "install_location": data.get("installlocation", ""),
                }
            )
    return results


def build_silent_command(entry):
    base = entry.get("quiet_string") or entry.get("uninstall_string") or ""
    base = base.strip()
    if not base:
        return None
    lowered = base.lower()

    def has(*flags):
        return any(flag in lowered for flag in flags)

    if "msiexec" in lowered:
        if has("/x"):
            return base if has("/quiet") else base + " /quiet /norestart"
        return base
    if "update.exe" in lowered:
        if not has("--uninstall", "-uninstall"):
            return base + " --uninstall -s"
        if not has("-s", "/s", "--silent", "-q", "--quiet"):
            return base + " -s"
        return base
    if has("unins", "setup"):
        suffix = ""
        if not has("/verysilent", "/silent", "/s", "-s", "--silent"):
            suffix += " /VERYSILENT /SUPPRESSMSGBOXES"
        if not has("/norestart"):
            suffix += " /NORESTART"
        return base + suffix
    if not has("/s", "-s", "--silent", "/quiet", "-q", "--quiet"):
        return base + " /S"
    return base


def run_uninstall(entry, timeout=1800):
    command = build_silent_command(entry)
    if not command:
        return False, "sin comando de desinstalacion util"
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return False, "tiempo de desinstalacion agotado"
    except OSError as exc:
        return False, f"fallo al ejecutar: {exc}"
    ok = proc.returncode in (0, 3010)
    detail = f"exit={proc.returncode}"
    location = entry.get("install_location", "")
    if ok and location and os.path.isdir(location):
        shutil.rmtree(location, ignore_errors=True)
        if not os.path.isdir(location):
            detail += " · carpeta residual eliminada"
    return ok, detail


def targets_for_app(app_name):
    from ..utils.settings import get_settings
    from .targets import build_targets

    lowered = app_name.lower()
    markers = [m for m in MARKERS if m in lowered]
    exclusions = set(get_settings().get("exclusions") or [])
    matches = []
    for target in build_targets(exclusions=exclusions):
        haystack = (target.id + " " + target.name).lower()
        if any(marker in haystack for marker in markers):
            matches.append(target)
    return matches


def clean_traces_for_app(app_name):
    from .cleaner import CleanOptions, run_clean
    from .scanner import scan_targets

    targets = targets_for_app(app_name)
    if not targets:
        return None
    report = scan_targets(targets)
    options = CleanOptions(selected={t.id for t in targets}, mode="permanent", preview=False)
    result = run_clean(report, options)
    return result
