"""Panic mode - emergency cleanup with confirmation, parallelism, and extended AI tool detection."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from .cleaner import CleanOptions, run_clean
from .browser_tabs import close_ai_tabs, detect_all_browsers, verify_browsers_closed
from .scanner import scan_targets
from .targets import AI_MARKERS, build_targets, detect_running_ai_tools
from ..utils.logger import log
from ..utils.paths import is_admin
from ..utils.settings import get_settings

_VALID_MODES = ("recycle", "permanent", "quarantine")

# Extended AI tools for panic detection (25+ new tools)
EXTENDED_AI_TOOLS = {
    # IDE extensions
    "github_copilot": ["github.copilot", "copilot.vim", "copilot.lua"],
    "cursor_ai": ["cursor", "cursor-agent", "cursor-chat"],
    "codeium": ["codeium", "codeium.vim"],
    "tabnine": ["tabnine", "tabnine-vim"],
    "amazon_codewhisperer": ["aws.codewhisperer", "codewhisperer"],
    "replit_ghostwriter": ["replit.ghostwriter"],
    "continue_dev": ["continue", "continue-ide"],
    "aider": ["aider", "aider-chat"],
    
    # Terminal AI
    "warp_ai": ["warp-terminal", "warp.ai"],
    "fig_ai": ["fig.io", "fig.ai"],
    "shell_gpt": ["shell_gpt", "sgpt"],
    
    # Browser extensions (process names)
    "chatgpt_extension": ["chatgpt", "openai-chat"],
    "claude_extension": ["claude", "anthropic-claude"],
    "perplexity_extension": ["perplexity", "perplexity-ai"],
    "bing_copilot_extension": ["copilot", "bing-copilot"],
    
    # Local LLMs
    "ollama": ["ollama", "ollama-server"],
    "llama_cpp": ["llama.cpp", "llama-server"],
    "llamafile": ["llamafile"],
    "gpt4all": ["gpt4all", "gpt4all-desktop"],
    "lm_studio": ["lm-studio", "local-ai"],
    "jan_ai": ["jan", "jan-ai"],
    "koboldcpp": ["koboldcpp"],
    "text_generation_webui": ["text-generation-webui", "oobabooga"],
    
    # AI Assistants
    "windows_copilot": ["copilot", "ms-copilot", "windows-copilot"],
    "macos_siri": ["siri", "siri-knowledge"],
    "google_assistant": ["google-assistant", "assistant"],
    
    # AI-powered apps
    "notion_ai": ["notion", "notion-ai"],
    "obsidian_ai": ["obsidian", "obsidian-ai", "obsidian-copilot"],
    "craft_ai": ["craft", "craft-ai"],
    "mem_ai": ["mem", "mem-ai"],
    "reflect_ai": ["reflect", "reflect-ai"],
    "roam_ai": ["roam", "roam-research"],
    
    # Code assistants
    "sourcegraph_cody": ["cody", "sourcegraph-cody"],
    "mutable_ai": ["mutable-ai"],
    "codegeex": ["codegeex"],
    "starcoder": ["starcoder"],
    "wizardcoder": ["wizardcoder"],
    "phind_vscode": ["phind", "phind-vscode"],
    
    # AI image/video
    "stable_diffusion": ["stable-diffusion", "automatic1111", "comfyui"],
    "midjourney": ["midjourney"],
    "runwayml": ["runwayml", "runway"],
    "pika": ["pika", "pika-labs"],
    
    # AI audio
    "elevenlabs": ["elevenlabs", "elevenlabs-app"],
    "whisper": ["whisper", "whisper.cpp", "whisper-desktop"],
    "rvc": ["rvc", "retrieval-based-voice-conversion"],
}


def _panic_mode(settings, permanent=None):
    if permanent is True:
        return "permanent"
    mode = settings.get("panic_mode")
    return mode if mode in _VALID_MODES else "recycle"


def _build_extended_targets(settings, admin):
    """Build targets including extended AI tool detection."""
    exclusions = set(settings.get("exclusions") or [])
    targets = build_targets(exclusions=exclusions)
    
    # Add dynamic AI tool detection
    running_tools = detect_running_ai_tools()
    for tool in running_tools:
        # Tool already adds dynamic targets
        pass
    
    # Add extended AI tool patterns
    from .targets import Target, AI_PATTERNS
    import os
    
    # Add common AI tool paths
    ai_tool_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Cursor"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Warp"),
        os.path.expandvars(r"%LOCALAPPDATA%\GitHub Copilot"),
        os.path.expandvars(r"%APPDATA%\Codeium"),
        os.path.expandvars(r"%APPDATA%\TabNine"),
        os.path.expandvars(r"%LOCALAPPDATA%\LM Studio"),
        os.path.expandvars(r"%LOCALAPPDATA%\GPT4All"),
        os.path.expandvars(r"%LOCALAPPDATA%\Jan"),
        os.path.expandvars(r"%USERPROFILE%\.ollama"),
        os.path.expandvars(r"%LOCALAPPDATA%\Ollama"),
    ]
    
    for path in ai_tool_paths:
        if os.path.exists(path):
            tool_name = os.path.basename(path)
            targets.append(Target(
                id=f"ai_tool_{tool_name.lower()}",
                name=f"AI Tool: {tool_name}",
                category="ai_tools",
                kind="files",
                paths=[path],
                requires_admin=False,
                detail=f"AI tool install directory: {path}",
            ))
    
    if not admin:
        targets = [t for t in targets if not t.requires_admin]
    
    return targets


def _parallel_clean_targets(report, options, max_workers=4):
    """Clean entries in parallel for faster panic mode.

    Devuelve un CleanResult fusionado (sin condiciones de carrera).
    """
    from .cleaner import clean_entry, merge_clean_results, CleanResult

    selected_entries = [
        entry for entry in report.entries
        if entry.target.id in options.selected and entry.status in ("found", "ready")
    ]

    partials = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(clean_entry, entry, options): entry
            for entry in selected_entries
        }

        for future in as_completed(futures):
            entry = futures[future]
            try:
                partials.append(future.result())
            except Exception as e:
                from .cleaner import CleanErrorType
                failed = CleanResult()
                failed.add_error(entry.target.id, CleanErrorType.UNKNOWN, str(e))
                partials.append(failed)

    if not partials:
        return CleanResult()
    return merge_clean_results(partials)


def perform_panic(
    progress=None,
    permanent=None,
    mode=None,
    confirm_callback=None,
    parallel: bool = True,
    max_workers: int = 4,
    close_browsers: bool = True,
    verify_browser_close: bool = True,
):
    """
    Perform emergency panic cleanup.
    
    Args:
        progress: Callback for progress updates
        permanent: Force permanent deletion
        mode: Override clean mode
        confirm_callback: Function to call for confirmation (should return True/False)
        parallel: Use parallel cleaning
        max_workers: Max parallel workers
        close_browsers: Close AI browser tabs
        verify_browser_close: Verify tabs are actually closed
    """
    settings = get_settings()
    clean_mode = mode if mode in _VALID_MODES else _panic_mode(settings, permanent)
    
    # Confirmation required
    if confirm_callback:
        if not confirm_callback():
            from .cleaner import CleanResult
            cancelled = CleanResult()
            cancelled.add("Cancelado por el usuario.")
            return cancelled
    
    # Close AI browser tabs
    tabs_closed = 0
    browser_report = {"closed": 0, "browsers": []}
    if close_browsers:
        browsers = detect_all_browsers()
        browser_report = close_ai_tabs(browsers)
        tabs_closed = browser_report.get("closed", 0)
        
        # Verify closure
        if verify_browser_close and tabs_closed > 0:
            verification = verify_browsers_closed(browsers)
            if not verification["all_closed"]:
                log("panic", warning=f"Some AI tabs may remain open: {verification['remaining_ai_tabs']}")
    
    # Scan targets
    admin = is_admin()
    targets = _build_extended_targets(settings, admin)
    report = scan_targets(targets)
    
    selected = set()
    for entry in report.entries:
        if entry.status in ("found", "ready"):
            selected.add(entry.target.id)
    
    options = CleanOptions(selected=selected, mode=clean_mode, preview=False)
    
    if parallel and len(selected) > 1:
        # Parallel cleaning for speed (each entry cleans into its own
        # CleanResult, then all partial results are merged).
        result = _parallel_clean_targets(report, options, max_workers)
    else:
        result = run_clean(report, options)
    
    result.tabs_closed = tabs_closed
    result.browser_report = browser_report
    
    log("panic", removed=result.removed_items, freed_bytes=result.freed_bytes,
        errors=result.errors, mode=clean_mode, tabs_closed=tabs_closed)
    
    if progress:
        progress(result)
    return result


def perform_silent_clean(permanent=True, progress=None, mode=None):
    """Silent background cleanup for auto-clean."""
    settings = get_settings()
    admin = is_admin()
    targets = _build_extended_targets(settings, admin)
    report = scan_targets(targets)
    selected = {
        entry.target.id
        for entry in report.entries
        if entry.status in ("found", "ready")
        and not entry.target.requires_admin
    }
    clean_mode = mode or ("permanent" if permanent else "recycle")
    options = CleanOptions(selected=selected, mode=clean_mode, preview=False)
    result = run_clean(report, options)
    log("auto_clean", removed=result.removed_items, freed_bytes=result.freed_bytes,
        errors=result.errors)
    if progress:
        progress(result)
    return result


def format_result_summary(result):
    lines = [result.summary(), ""]
    tabs = getattr(result, "tabs_closed", 0)
    if tabs:
        lines.append(f"PESTAÑAS DE IA CERRADAS: {tabs}")
    lines.extend(result.lines)
    return "\n".join(lines)