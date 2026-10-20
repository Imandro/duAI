"""Objetivos de escaneo y catálogo para duAI - Detección IA mejorada."""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Optional

from ..utils.paths import expand


# ============================================================
# MARCADORES IA EXTENDIDOS (50+ herramientas modernas)
# ============================================================

AI_MARKERS = [
    # Asistentes de chat principales
    "chatgpt", "openai", "claude", "anthropic", "copilot", "cursor",
    "ollama", "windsurf", "codeium", "lm studio", "lm-studio", "gpt4all",
    "nomic.ai", "perplexity", "gemini", "deepseek", "mistral", "opencode",
    "codex", "aider", "huggingface", "jan", "continue", "tabnine",
    "grok", "llama", "sillytavern", "lobechat", "open-webui", "koboldcpp",

    # Editores/IDEs con IA
    "v0", "bolt.new", "lovable", "replit", "zed",
    "avante", "codegeex", "magicoder", "starcoder", "wizardcoder",
    "tabby", "cody", "sourcegraph", "codewhisperer", "codeium",

    # Modelos locales y runtimes
    "phi-3", "phi-4", "qwen", "yi-34b", "nemotron", "command-r",
    "solar", "dolphin", "orca", "zephyr", "openhermes", "neural-chat",
    "stablelm", "redpajama", "falcon", "mpt", "bloom", "gpt-neox",
    "llamafile", "llama.cpp", "llama-cpp", "exllama", "ctransformers",
    "mlx", "mlx-lm", "whisper.cpp", "faster-whisper",

    # Frameworks y orquestación IA
    "litellm", "langfuse", "langsmith", "helicone", "portkey",
    "crewai", "autogen", "langgraph", "llamaindex", "haystack",
    "semantic-kernel", "guidance", "instructor", "marvin", "dspy",
    "anything-llm", "private-gpt", "localai", "text-generation-webui",
    "koboldai", "oobabooga", "koboldcpp",

    # Proveedores cloud
    "together.ai", "fireworks.ai", "anyscale.com", "replicate.com",
    "baseten.co", "modal.com", "runpod.io", "vast.ai", "lambda.ai",
    "tensorrt", "triton", "vllm", "tgi", "text-generation-inference",
]

# Patrones regex para detección fuzzy/parcial
AI_PATTERNS = [
    re.compile(r"gpt[-\s]?\d*"),              # gpt, gpt-4, gpt 3.5
    re.compile(r"claude[-\s]?\d*"),            # claude, claude-3
    re.compile(r"llama[-\s]?\d*[bc]?"),        # llama, llama2, llama-3b
    re.compile(r"mistral[-\s]?\d*[bc]?"),      # mistral, mistral-7b
    re.compile(r"gemini[-\s]?(pro|flash|ultra)?"),
    re.compile(r"deepseek[-\s]?(coder|chat)?"),
    re.compile(r"(auto|code|smart)[-\s]?(gpt|llm|ai)"),
    re.compile(r"(local|private)[-\s]?(llm|gpt|ai)"),
    re.compile(r"(code|text)[-\s]?(generation|completion)"),
    re.compile(r"ai[-\s]?(assistant|companion|chat)"),
]


def matches_ai_marker(name: str, threshold: float = 0.8) -> bool:
    """Verifica si nombre de archivo/directorio coincide con marcadores IA (exacto + fuzzy)."""
    name_lower = name.lower()

    # Coincidencia exacta/substring
    for marker in AI_MARKERS:
        if marker in name_lower:
            return True

    # Patrones regex
    for pattern in AI_PATTERNS:
        if pattern.search(name_lower):
            return True

    # Fuzzy matching para nombres largos (ej: "my-chatgpt-client")
    if len(name_lower) > 10:
        for marker in AI_MARKERS:
            if len(marker) > 4:
                ratio = SequenceMatcher(None, marker, name_lower).ratio()
                if ratio >= threshold:
                    return True

    return False


# Dominios de navegador para detección en historial (extendidos)
BROWSER_AI_DOMAINS = [
    # Principales
    "chat.openai.com", "chatgpt.com", "openai.com",
    "claude.ai", "anthropic.com",
    "gemini.google.com", "aistudio.google.com",
    "perplexity.ai",
    "copilot.microsoft.com", "bing.com/chat",
    "poe.com", "character.ai",
    "deepseek.com", "mistral.ai", "grok.com", "x.ai",

    # IDEs y herramientas web
    "v0.dev", "bolt.new", "lovable.dev", "replit.com", "zed.dev",
    "cursor.sh", "codeium.com", "windsurf.com", "codegeex.cn",
    "huggingface.co", "huggingface.chat",
    "ollama.com", "lmstudio.ai", "gpt4all.io", "jan.ai",
    "anything-llm.com", "privategpt.io", "localai.io",
    "text-generation-webui.io", "koboldai.org", "oobabooga.com",
    "llamafile.ai",

    # Proveedores cloud
    "together.ai", "fireworks.ai", "anyscale.com", "replicate.com",
    "baseten.co", "modal.com", "runpod.io", "vast.ai", "lambda.ai",

    # Otros
    "you.com", "phind.com", "sourcegraph.com", "cody.ai",
    "tabnine.com", "codewhisperer.amazonaws.com",
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
    estimated_size: str = "?"  # Para UI: "10 MB", "500 KB", etc.
    risk_level: str = "low"    # low, medium, high, critical


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
                    meta=spec.get("meta", {}),
                    detail=spec.get("detail", ""),
                    estimated_size=spec.get("estimated_size", "?"),
                    risk_level=spec.get("risk_level", "low"),
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
                    estimated_size="?",
                    risk_level="low",
                )
            )
        if browser_id + "_storage" not in exclusions:
            targets.append(
                Target(
                    id=browser_id + "_storage",
                    name=browser["name"] + ": sesiones y almacenamiento local",
                    category="Navegador",
                    kind="browser_storage",
                    processes=browser.get("processes", []),
                    meta={
                        "base": browser["base"],
                        "profile_dirs": browser.get("profile_dirs", ["Default"]),
                        "engine": browser.get("engine", "chromium"),
                    },
                    detail="Elimina localStorage y sesiones de todos los sitios del perfil",
                    estimated_size="?",
                    risk_level="low",
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


# ============================================================
# DETECCIÓN DINÁMICA DE HERRAMIENTAS IA INSTALADAS
# ============================================================

def detect_running_ai_tools() -> List[str]:
    """Detecta herramientas IA desde procesos en ejecución."""
    try:
        import psutil
    except ImportError:
        return []

    ai_process_patterns = [
        "ollama", "llama", "llamafile", "whisper", "vllm",
        "tgi", "text-generation", "lm-studio", "lmstudio",
        "anything-llm", "private-gpt", "localai", "koboldcpp",
        "koboldai", "oobabooga", "tabby", "continue", "cursor",
        "windsurf", "codeium", "avante", "codegeex", "zed",
        "chatgpt", "claude", "perplexity", "copilot", "gemini",
    ]

    detected = []
    for proc in psutil.process_iter(['name', 'exe', 'cmdline']):
        try:
            name = (proc.info['name'] or '').lower()
            exe = (proc.info['exe'] or '').lower()
            cmdline = ' '.join(proc.info['cmdline'] or []).lower()

            for pattern in ai_process_patterns:
                if pattern in name or pattern in exe or pattern in cmdline:
                    detected.append(proc.info['name'])
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return list(set(detected))


def get_ai_tool_install_paths() -> List[str]:
    """Obtiene rutas comunes de instalación de herramientas IA."""
    paths = []
    env_vars = ["LOCALAPPDATA", "APPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"]

    for env in env_vars:
        base = os.environ.get(env, "")
        if not base:
            continue

        common_paths = [
            # Ollama
            os.path.join(base, "ollama"),
            os.path.join(base, "Ollama"),
            # LM Studio
            os.path.join(base, "LM Studio"),
            # AnythingLLM
            os.path.join(base, "AnythingLLM"),
            # Jan
            os.path.join(base, "Jan"),
            # KoboldCPP
            os.path.join(base, "koboldcpp"),
            # LM Studio models
            os.path.join(base, "LM Studio", "models"),
            # Ollama models
            os.path.join(base, "ollama", "models"),
            # GPT4All
            os.path.join(base, "nomic.ai", "GPT4All"),
            # HuggingFace
            os.path.join(base, "huggingface"),
        ]
        paths.extend(common_paths)

    return [p for p in paths if os.path.exists(p)]


def scan_file_content_for_ai(path: str, max_bytes: int = 8192) -> bool:
    """Escanea contenido de archivo en busca de patrones IA."""
    ai_indicators = [
        b"openai", b"anthropic", b"chatgpt", b"claude",
        b"api_key", b"api.token", b"authorization: bearer",
        b"huggingface", b"ollama", b"langchain", b"llama_index",
        b"completion", b"embedding", b"tokenizer",
        b"system_prompt", b"user_prompt", b"assistant_prompt",
    ]

    try:
        with open(path, "rb") as f:
            content = f.read(max_bytes).lower()
            return any(indicator in content for indicator in ai_indicators)
    except (OSError, PermissionError):
        return False