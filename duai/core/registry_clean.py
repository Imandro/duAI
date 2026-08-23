import codecs
import os

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

_EXPLORER_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Explorer"
KEYS_AI_FILTERED = {
    "UserAssist": _EXPLORER_ROOT + r"\UserAssist",
    "MuiCache": r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache",
}
KEYS_GENERAL = {
    "RunMRU": _EXPLORER_ROOT + r"\RunMRU",
    "TypedPaths": _EXPLORER_ROOT + r"\TypedPaths",
    "RecentDocs": _EXPLORER_ROOT + r"\RecentDocs",
    "OpenSavePidlMRU": _EXPLORER_ROOT + r"\ComDlg32\OpenSavePidlMRU",
    "LastVisitedPidlMRU": _EXPLORER_ROOT + r"\ComDlg32\LastVisitedPidlMRU",
}


def rot13(text):
    return codecs.encode(text, "rot_13")


def _matches_ai(name):
    lowered = name.lower()
    return any(marker in lowered for marker in MARKERS)


def collect_registry_traces():
    import winreg

    counts = {}

    for label, path in KEYS_AI_FILTERED.items():
        count = 0
        try:
            if label == "UserAssist":
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as root:
                    index = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(root, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            with winreg.OpenKey(root, sub_name + r"\Count") as count_key:
                                value_index = 0
                                while True:
                                    try:
                                        value_name, _, _ = winreg.EnumValue(count_key, value_index)
                                    except OSError:
                                        break
                                    value_index += 1
                                    if _matches_ai(rot13(value_name)):
                                        count += 1
                        except OSError:
                            continue
            else:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                    value_index = 0
                    while True:
                        try:
                            value_name, _, _ = winreg.EnumValue(key, value_index)
                        except OSError:
                            break
                        value_index += 1
                        if _matches_ai(value_name):
                            count += 1
        except OSError:
            pass
        counts[label] = count

    for label, path in KEYS_GENERAL.items():
        count = 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                info = winreg.QueryInfoKey(key)
                count = info[0] + info[1]
        except OSError:
            pass
        counts[label] = count

    return counts


def clean_registry():
    import winreg

    removed = {}

    for label, path in KEYS_AI_FILTERED.items():
        count = 0
        if label == "UserAssist":
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as root:
                    index = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(root, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            with winreg.OpenKey(root, sub_name + r"\Count", 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as count_key:
                                names = []
                                value_index = 0
                                while True:
                                    try:
                                        value_name, _, _ = winreg.EnumValue(count_key, value_index)
                                    except OSError:
                                        break
                                    value_index += 1
                                    names.append(value_name)
                                for value_name in names:
                                    if _matches_ai(rot13(value_name)):
                                        try:
                                            winreg.DeleteValue(count_key, value_name)
                                            count += 1
                                        except OSError:
                                            pass
                        except OSError:
                            continue
            except OSError:
                pass
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
                    names = []
                    value_index = 0
                    while True:
                        try:
                            value_name, _, _ = winreg.EnumValue(key, value_index)
                        except OSError:
                            break
                        value_index += 1
                        names.append(value_name)
                    for value_name in names:
                        if _matches_ai(value_name):
                            try:
                                winreg.DeleteValue(key, value_name)
                                count += 1
                            except OSError:
                                pass
            except OSError:
                pass
        removed[label] = count

    for label, path in KEYS_GENERAL.items():
        count = 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as key:
                if label in ("RunMRU", "TypedPaths"):
                    info = winreg.QueryInfoKey(key)
                    for value_index in range(info[1] - 1, -1, -1):
                        value_name = winreg.EnumValue(key, value_index)[0]
                        try:
                            winreg.DeleteValue(key, value_name)
                            count += 1
                        except OSError:
                            pass
                else:
                    info = winreg.QueryInfoKey(key)
                    for sub_index in range(info[0] - 1, -1, -1):
                        sub_name = winreg.EnumKey(key, sub_index)
                        try:
                            winreg.DeleteKey(key, sub_name)
                            count += 1
                        except OSError:
                            pass
        except OSError:
            pass
        removed[label] = count

    return removed
