import json
import os
import sys
from dataclasses import dataclass, field

from ..utils.paths import expand

AI_MARKERS = [
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


def catalog_path():
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), "config", "targets.json")
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "targets.json")
    )


KIND_FILES = "files"
KIND_REGISTRY = "registry"


@dataclass
class Target:
    id: str
    name: str
    category: str
    kind: str = KIND_FILES
    paths: list = field(default_factory=list)
    processes: list = field(default_factory=list)
    requires_admin: bool = False
    filter_markers: bool = False
    kind_action: str = ""
    meta: dict = field(default_factory=dict)
    detail: str = ""


def load_catalog():
    with open(catalog_path(), "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_targets(exclusions=None):
    exclusions = exclusions or set()
    catalog = load_catalog()
    targets = []

    for category in catalog.get("categories", []):
        for spec in category.get("targets", []):
            target_id = spec["id"]
            if target_id in exclusions:
                continue
            targets.append(
                Target(
                    id=target_id,
                    name=spec["name"],
                    category=category["name"],
                    paths=[p.replace("/", os.sep) for p in spec.get("paths", [])],
                    processes=spec.get("processes", []),
                    requires_admin=bool(spec.get("requires_admin")),
                    filter_markers=bool(spec.get("filter_markers")),
                    kind_action=spec.get("kind_action", ""),
                )
            )

    domains = [d.lower() for d in catalog.get("domains", [])]
    for browser in catalog.get("browsers", []):
        browser_id = browser["id"]
        if browser_id + "_history" not in exclusions:
            targets.append(
                Target(
                    id=browser_id + "_history",
                    name=browser["name"] + ": historial IA",
                    category="Navegador",
                    kind="browser_history",
                    processes=browser.get("processes", []),
                    meta={
                        "base": browser["base"],
                        "profile_dirs": browser.get("profile_dirs", ["Default"]),
                        "engine": browser.get("engine", "chromium"),
                        "domains": domains,
                    },
                    detail="Borra del historial solo las visitas a sitios de IA",
                )
            )
        if browser_id + "_storage" not in exclusions:
            targets.append(
                Target(
                    id=browser_id + "_storage",
                    name=browser["name"] +": sesiones y almacenamiento local",
                    category="Navegador",
                    kind="browser_storage",
                    processes=browser.get("processes", []),
                    meta={
                        "base": browser["base"],
                        "profile_dirs": browser.get("profile_dirs", ["Default"]),
                        "engine": browser.get("engine", "chromium"),
                    },
                    detail="Elimina localStorage y sesiones de todos los sitios del perfil",
                )
            )

    return targets


def all_target_ids():
    return [t.id for t in build_targets()]


def list_all_entries():
    catalog = load_catalog()
    entries = []
    for category in catalog.get("categories", []):
        for spec in category.get("targets", []):
            entries.append(
                {"id": spec["id"], "name": spec["name"], "category": category["name"]}
            )
    for browser in catalog.get("browsers", []):
        name = browser["name"]
        entries.append(
            {"id": browser["id"] + "_history", "name": name + ": historial IA",
             "category": "Navegador"}
        )
        entries.append(
            {"id": browser["id"] + "_storage", "name": name + ": sesiones y almacenamiento local",
             "category": "Navegador"}
        )
    return entries
