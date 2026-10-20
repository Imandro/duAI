"""Smoke test for duAI - verifies all views load and navigate correctly."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["duai"]

from duai.app import create_app

app, win = create_app()
print(f"App created. NAV={len(win.NAV)} Stack={win.stack.count()}")

for i in range(win.stack.count()):
    win.navigate(i)
    print(f"  tab {i:2d} OK -> {win.NAV[i]}")

# Test core modules importable
from duai.core import (
    scanner, cleaner, quarantine, targets, reporter, session, panic,
    browser_tabs, registry_clean, system_clean, selfclean, uninstaller,
    viral, privacy_score, quick_clean, streak, notifications, report_image,
    updater, scheduler, auto_clean, leaderboard,
)
print("All core modules import OK")

# Test key functions
from duai.core.leaderboard import get_user_rank, get_leaderboard
print("Leaderboard rank:", get_user_rank())
print("Leaderboard entries:", len(get_leaderboard(10)))

from duai.core.viral import get_stats, generate_share_report, get_challenge_manager
stats = get_stats()
print("Referral code:", stats.get_referral_code())
print("Achievements:", len(stats.get_all_achievements()))
print("Challenge:", get_challenge_manager().get_today_challenge())

from duai.core.updater import RollbackManager, get_update_history
rm = RollbackManager()
print("Rollback backups:", len(rm.list_backups()))

from duai.core.auto_clean import get_auto_clean_service
svc = get_auto_clean_service()
print("AutoClean service OK, enabled:", svc.is_enabled if hasattr(svc, 'is_enabled') else 'n/a')

from duai.core.scheduler import get_scheduler, TaskScheduler
sched = get_scheduler()
print("Scheduler tasks:", len(sched.list_tasks()))
print("Scheduler status:", sched.get_status())

from duai.core.registry_clean import collect_registry_traces, clean_registry
print("Registry traces:", collect_registry_traces())
dry = clean_registry(ai_only=True, dry_run=True, create_backup=False)
print("Registry dry-run removed:", dry["removed"])

from duai.core.browser_tabs import detect_all_browsers, find_ai_tabs
browsers = detect_all_browsers()
print("Browsers detected:", [b["id"] for b in browsers])
print("AI tabs:", find_ai_tabs(browsers))

from duai.core.selfclean import list_self_backups
print("Self backups:", len(list_self_backups()))

print("\nALL SMOKE TESTS PASSED")
