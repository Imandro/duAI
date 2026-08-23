import json
import os
import subprocess
import urllib.request
import urllib.error

CHROMIUM_BROWSERS = {
    "chrome": {"process": "chrome.exe", "cdp_port": 9222},
    "edge": {"process": "msedge.exe", "cdp_port": 9223},
    "brave": {"process": "brave.exe", "cdp_port": 9224},
}

AI_DOMAINS = [
    "chatgpt.com",
    "openai.com",
    "claude.ai",
    "anthropic.com",
    "gemini.google.com",
    "aistudio.google.com",
    "perplexity.ai",
    "copilot.microsoft.com",
    "poe.com",
    "character.ai",
    "deepseek.com",
    "mistral.ai",
    "grok.com",
]


def _is_browser_running(process_name):
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return process_name.lower() in result.stdout.lower()
    except Exception:
        return False


def _fetch_tabs(port):
    try:
        url = f"http://127.0.0.1:{port}/json"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _close_tab(port, tab_id):
    try:
        url = f"http://127.0.0.1:{port}/json/close/{tab_id}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode()
    except Exception:
        return None


def _is_ai_url(url):
    if not url:
        return False
    url_lower = url.lower()
    return any(domain in url_lower for domain in AI_DOMAINS)


def detect_cdp_browsers():
    found = []
    for browser_id, info in CHROMIUM_BROWSERS.items():
        if _is_browser_running(info["process"]):
            tabs = _fetch_tabs(info["cdp_port"])
            if tabs is not None:
                found.append({
                    "id": browser_id,
                    "port": info["cdp_port"],
                    "tabs": tabs,
                })
            else:
                found.append({
                    "id": browser_id,
                    "port": info["cdp_port"],
                    "tabs": None,
                    "note": "CDP no disponible (el navegador no fue abierto con --remote-debugging-port)",
                })
    return found


def find_ai_tabs(browsers=None):
    if browsers is None:
        browsers = detect_cdp_browsers()
    results = []
    for browser in browsers:
        tabs = browser.get("tabs")
        if tabs is None:
            results.append({
                "browser": browser["id"],
                "ai_tabs": [],
                "note": browser.get("note", "CDP no disponible"),
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
        })
    return results


def close_ai_tabs(browsers=None):
    if browsers is None:
        browsers = detect_cdp_browsers()
    report = {"closed": 0, "browsers": []}
    for browser in browsers:
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
