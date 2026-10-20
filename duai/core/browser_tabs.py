"""Browser tab detection for AI sites - supports Chromium CDP + Firefox/Opera/Vivaldi/Arc via history DB."""

import json
import os
import sqlite3
import subprocess
import urllib.request
import urllib.error
import time
from pathlib import Path
from typing import List, Dict, Any, Optional


CHROMIUM_BROWSERS = {
    "chrome": {"process": "chrome.exe", "cdp_port": 9222, "profile": "Default"},
    "edge": {"process": "msedge.exe", "cdp_port": 9223, "profile": "Default"},
    "brave": {"process": "brave.exe", "cdp_port": 9224, "profile": "Default"},
    "vivaldi": {"process": "vivaldi.exe", "cdp_port": 9225, "profile": "Default"},
    "opera": {"process": "opera.exe", "cdp_port": 9226, "profile": "Default"},
    "arc": {"process": "Arc.exe", "cdp_port": 9227, "profile": "Default"},
}

# Firefox uses a different approach - no CDP, uses places.sqlite
FIREFOX_BROWSERS = {
    "firefox": {"process": "firefox.exe", "profiles_ini": "profiles.ini"},
    "firefox_developer": {"process": "firefox.exe", "profiles_ini": "profiles.ini"},
    "librewolf": {"process": "librewolf.exe", "profiles_ini": "profiles.ini"},
    "floorp": {"process": "floorp.exe", "profiles_ini": "profiles.ini"},
}

AI_DOMAINS = [
    "chatgpt.com", "openai.com", "chat.openai.com",
    "claude.ai", "anthropic.com",
    "gemini.google.com", "aistudio.google.com", "bard.google.com",
    "perplexity.ai",
    "copilot.microsoft.com", "bing.com/chat",
    "poe.com", "character.ai", "deepseek.com",
    "mistral.ai", "grok.com", "x.ai",
    "you.com", "phind.com", "metaphor.systems",
    "huggingface.co/chat", "replicate.com",
    "cursor.sh", "github.com/copilot",
]


def _is_browser_running(process_name: str) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return process_name.lower() in result.stdout.lower()
    except Exception:
        return False


def _fetch_tabs(port: int) -> Optional[List[Dict]]:
    try:
        url = f"http://127.0.0.1:{port}/json"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _close_tab(port: int, tab_id: str) -> Optional[str]:
    try:
        url = f"http://127.0.0.1:{port}/json/close/{tab_id}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode()
    except Exception:
        return None


def _is_ai_url(url: str) -> bool:
    if not url:
        return False
    url_lower = url.lower()
    return any(domain in url_lower for domain in AI_DOMAINS)


def _get_chromium_profile_path(browser_id: str, profile: str = "Default") -> Optional[Path]:
    """Get Chromium-based browser profile path."""
    env_map = {
        "chrome": "LOCALAPPDATA",
        "edge": "LOCALAPPDATA",
        "brave": "LOCALAPPDATA",
        "vivaldi": "LOCALAPPDATA",
        "opera": "APPDATA",
        "arc": "LOCALAPPDATA",
    }
    path_map = {
        "chrome": r"Google\Chrome\User Data",
        "edge": r"Microsoft\Edge\User Data",
        "brave": r"BraveSoftware\Brave-Browser\User Data",
        "vivaldi": r"Vivaldi\User Data",
        "opera": r"Opera Software\Opera Stable",
        "arc": r"Arc\User Data",
    }
    env_var = env_map.get(browser_id, "LOCALAPPDATA")
    rel_path = path_map.get(browser_id)
    if not rel_path:
        return None
    base = os.environ.get(env_var, "")
    if not base:
        return None
    return Path(base) / rel_path / profile


def _get_firefox_profile_path() -> Optional[Path]:
    """Get Firefox default profile path from profiles.ini."""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return None
    profiles_ini = Path(appdata) / "Mozilla" / "Firefox" / "profiles.ini"
    if not profiles_ini.exists():
        return None
    
    import configparser
    config = configparser.ConfigParser()
    config.read(profiles_ini)
    
    for section in config.sections():
        if config[section].get("Default") == "1" or config[section].get("Default") == "true":
            path = config[section].get("Path", "")
            if path:
                full_path = Path(appdata) / "Mozilla" / "Firefox" / path
                if full_path.exists():
                    return full_path
    
    # Fallback: first profile
    for section in config.sections():
        path = config[section].get("Path", "")
        if path:
            full_path = Path(appdata) / "Mozilla" / "Firefox" / path
            if full_path.exists():
                return full_path
    return None


def _get_firefox_history(profile_path: Path, limit: int = 100) -> List[Dict]:
    """Extract recent history from Firefox places.sqlite."""
    places_db = profile_path / "places.sqlite"
    if not places_db.exists():
        return []
    
    # Copy to temp to avoid locking
    import tempfile
    import shutil
    temp_db = Path(tempfile.gettempdir()) / f"firefox_places_{int(time.time())}.sqlite"
    try:
        shutil.copy2(places_db, temp_db)
        
        conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get recent visits to AI domains
        placeholders = ",".join("?" for _ in AI_DOMAINS)
        query = f"""
            SELECT url, title, last_visit_date
            FROM moz_places
            WHERE url LIKE '%' || ? || '%'
            ORDER BY last_visit_date DESC
            LIMIT ?
        """
        # Build OR conditions
        conditions = " OR ".join(["url LIKE ?" for _ in AI_DOMAINS])
        query = f"""
            SELECT url, title, last_visit_date
            FROM moz_places
            WHERE {conditions}
            ORDER BY last_visit_date DESC
            LIMIT ?
        """
        params = [f"%{d}%" for d in AI_DOMAINS] + [limit]
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [{"url": r["url"], "title": r["title"], "last_visit": r["last_visit_date"]} for r in rows]
    except Exception:
        return []
    finally:
        if temp_db.exists():
            temp_db.unlink(missing_ok=True)


def _get_chromium_history(profile_path: Path, limit: int = 100) -> List[Dict]:
    """Extract recent history from Chromium History database."""
    history_db = profile_path / "History"
    if not history_db.exists():
        return []
    
    import tempfile
    import shutil
    temp_db = Path(tempfile.gettempdir()) / f"chromium_history_{int(time.time())}.sqlite"
    try:
        shutil.copy2(history_db, temp_db)
        
        conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        conditions = " OR ".join(["url LIKE ?" for _ in AI_DOMAINS])
        query = f"""
            SELECT url, title, last_visit_time
            FROM urls
            WHERE {conditions}
            ORDER BY last_visit_time DESC
            LIMIT ?
        """
        params = [f"%{d}%" for d in AI_DOMAINS] + [limit]
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [{"url": r["url"], "title": r["title"], "last_visit": r["last_visit_time"]} for r in rows]
    except Exception:
        return []
    finally:
        if temp_db.exists():
            temp_db.unlink(missing_ok=True)


def detect_cdp_browsers() -> List[Dict]:
    """Detect Chromium-based browsers with CDP enabled."""
    found = []
    for browser_id, info in CHROMIUM_BROWSERS.items():
        if _is_browser_running(info["process"]):
            tabs = _fetch_tabs(info["cdp_port"])
            if tabs is not None:
                found.append({
                    "id": browser_id,
                    "port": info["cdp_port"],
                    "tabs": tabs,
                    "method": "cdp",
                })
            else:
                found.append({
                    "id": browser_id,
                    "port": info["cdp_port"],
                    "tabs": None,
                    "method": "cdp",
                    "note": "CDP no disponible (el navegador no fue abierto con --remote-debugging-port)",
                })
    return found


def detect_firefox_browsers() -> List[Dict]:
    """Detect Firefox-based browsers via history DB."""
    found = []
    for browser_id, info in FIREFOX_BROWSERS.items():
        if _is_browser_running(info["process"]):
            profile = _get_firefox_profile_path()
            if profile:
                history = _get_firefox_history(profile, limit=50)
                found.append({
                    "id": browser_id,
                    "profile_path": str(profile),
                    "tabs": None,  # No live tabs via CDP
                    "history": history,
                    "method": "history_db",
                    "note": "Firefox detectado via history DB (no live tabs)",
                })
            else:
                found.append({
                    "id": browser_id,
                    "tabs": None,
                    "history": [],
                    "method": "history_db",
                    "note": "Perfil Firefox no encontrado",
                })
    return found


def detect_all_browsers() -> List[Dict]:
    """Detect all supported browsers (CDP + history DB)."""
    return detect_cdp_browsers() + detect_firefox_browsers()


def find_ai_tabs(browsers: Optional[List[Dict]] = None) -> List[Dict]:
    """Find AI-related tabs across all detected browsers."""
    if browsers is None:
        browsers = detect_all_browsers()
    
    results = []
    for browser in browsers:
        method = browser.get("method", "cdp")
        
        if method == "cdp":
            tabs = browser.get("tabs")
            if tabs is None:
                results.append({
                    "browser": browser["id"],
                    "ai_tabs": [],
                    "note": browser.get("note", "CDP no disponible"),
                    "method": "cdp",
                })
                continue
            ai_tabs = []
            for tab in tabs:
                if tab.get("type") == "page" and _is_ai_url(tab.get("url", "")):
                    ai_tabs.append({
                        "id": tab.get("id"),
                        "title": tab.get("title", ""),
                        "url": tab.get("url", ""),
                    })
            results.append({
                "browser": browser["id"],
                "ai_tabs": ai_tabs,
                "method": "cdp",
            })
        
        elif method == "history_db":
            history = browser.get("history", [])
            ai_entries = []
            for entry in history:
                if _is_ai_url(entry.get("url", "")):
                    ai_entries.append({
                        "title": entry.get("title", ""),
                        "url": entry.get("url", ""),
                        "last_visit": entry.get("last_visit"),
                    })
            results.append({
                "browser": browser["id"],
                "ai_tabs": ai_entries,
                "note": browser.get("note", ""),
                "method": "history_db",
            })
    
    return results


def close_ai_tabs(browsers: Optional[List[Dict]] = None) -> Dict:
    """Close AI tabs in CDP-enabled browsers. Firefox tabs cannot be closed remotely."""
    if browsers is None:
        browsers = detect_cdp_browsers()
    
    report = {"closed": 0, "browsers": []}
    for browser in browsers:
        if browser.get("method") != "cdp":
            report["browsers"].append({
                "browser": browser["id"],
                "closed": 0,
                "note": "Solo CDP permite cerrar pestañas remotamente",
            })
            continue
        
        tabs = browser.get("tabs")
        port = browser.get("port")
        if tabs is None:
            report["browsers"].append({
                "browser": browser["id"],
                "closed": 0,
                "note": browser.get("note", "CDP no disponible"),
            })
            continue
        
        closed_count = 0
        for tab in tabs:
            if tab.get("type") == "page" and _is_ai_url(tab.get("url", "")):
                result = _close_tab(port, tab.get("id"))
                if result is not None:
                    closed_count += 1
        report["closed"] += closed_count
        report["browsers"].append({
            "browser": browser["id"],
            "closed": closed_count,
        })
    return report


def verify_browsers_closed(browsers: List[Dict]) -> Dict:
    """Verify that AI tabs are actually closed by re-checking."""
    time.sleep(0.5)  # Brief wait
    after = find_ai_tabs(browsers)
    remaining = sum(len(b.get("ai_tabs", [])) for b in after)
    return {
        "remaining_ai_tabs": remaining,
        "browsers": after,
        "all_closed": remaining == 0,
    }