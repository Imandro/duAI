# duAI v2.0 — "Viral" release

Privacy tool for Windows that detects and removes every trace of AI usage. **100% local. No telemetry. No accounts.**

This is the biggest duAI release yet: a real installer, a true portable mode, a redesigned UI with multiple themes, local analytics, gamification, a guided demo, a verified updater and a browser extension.

## Highlights

- **Privacy Score** — 0–100 score based on the traces found, with historical trend.
- **Analytics** — Activity charts, category breakdown, scan/clean ratio and Privacy Score trend (7/30/90 days or all time), powered by QtCharts.
- **Clean day streak** — Keep a daily streak by scanning and cleaning.
- **Quick Clean** — One-click cleanup straight from the dashboard.
- **Achievements with tiers** — 30+ medals (bronze/silver/gold/platinum), daily challenges and referral codes.
- **Anonymous leaderboard** — Opt-in ranking with a non-PII identifier; disable anytime.
- **Visual report** — Generate a shareable PNG privacy report.
- **Background auto-clean** — Idle- or interval-based cleanup with stealth mode.
- **Notifications** — Native notifications for completed cleans and unlocked achievements.
- **Demo mode** — Interactive guided tour of the whole app.

## UI

- **4 themes** — dark, high-contrast dark, light, high-contrast light, with automatic system-theme detection.
- **8 accent colors** and a consistent, high-contrast design.
- Accessibility: accessible names/descriptions, reduced-motion support, keyboard navigation.

## Distribution

- **Installer** — `duAI-Setup-2.0.0.exe` (Inno Setup) with Start menu + desktop shortcuts, a clean uninstaller and optional run-at-logon.
- **Portable** — `duAI.exe --portable` stores everything in a `duAI_data` folder next to the executable. It does **not** write to `%LOCALAPPDATA%`.
- **Verified updates** — downloads from GitHub Releases and verifies **SHA-256** and an optional **Ed25519** signature before installing.
- **Browser extension** — MV3 companion (`browser_extension/`) for Chrome/Edge/Brave using Declarative Net Request.

## Safety

- Recycle bin remains the default cleanup destination.
- Panic mode and permanent deletion always require explicit confirmation.
- The global panic hotkey is **disabled by default**; if a password is set it is requested before triggering.
- Worker cancellation is cooperative and progress is throttled.

## Internationalization

- Full Spanish and English coverage — all UI keys are translated (verified with `i18n_check.py`, 0 missing).
- External JSON translations, CLDR pluralization and a `es → en` fallback chain.

## Internal / quality

- Config with schema validation, Fernet encryption, versioned migration and backup/restore.
- Rotating async logging (5 MB × 10 files).
- Parallel scanner with DNS cache and throttled UI updates.
- Test suites: `smoke_test.py`, `e2e_test.py`, `modules_test.py`, `ui_test.py` — all passing.

## Install

1. Download `duAI-Setup-2.0.0.exe` and run the wizard, **or**
2. Download `duAI.exe` and run it with `--portable`.

## Requirements

Windows 10/11. Python 3.14+ only if you run from source.
