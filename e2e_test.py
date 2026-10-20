"""End-to-end test: scan -> clean -> privacy score -> stats."""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["duai"]

# Consola Windows (cp1252) no puede imprimir UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from duai.core.targets import build_targets
from duai.core.scanner import scan_targets
from duai.core.cleaner import CleanOptions, run_clean
from duai.core.privacy_score import calculate_score, score_label, record_score, get_latest_score
from duai.core.viral import get_stats
from duai.core.quarantine import get_quarantine_stats, verify_quarantine_integrity
from duai.core.quick_clean import run_quick_clean
from duai.core.streak import get_streak, update_streak
from duai.core.report_image import generate_and_open
from duai.core.notifications import notify_clean_complete
import tempfile

print("=== BUILD TARGETS ===")
targets = build_targets()
print(f"Targets: {len(targets)}")

print("\n=== SCAN (first 8 targets) ===")
t0 = time.time()
report = scan_targets(targets[:8])
elapsed = time.time() - t0
found = [e for e in report.entries if e.status in ("found", "ready")]
print(f"Elapsed: {elapsed:.2f}s")
print(f"Found: {len(found)} / {len(report.entries)}")
print(f"Total bytes: {report.total_bytes}")
for e in found[:5]:
    print(f"  - {e.target.name}: {len(e.items)} items, {e.total_bytes} bytes")

print("\n=== PRIVACY SCORE ===")
score = calculate_score(report)
print(f"Score: {score}/100 -> {score_label(score)}")
record_score(score, report)
latest = get_latest_score()
print(f"Latest: {latest}")

print("\n=== CLEAN (preview) ===")
options = CleanOptions(selected=set(), mode="recycle", preview=True)
result = run_clean(report, options)
print(f"Preview removed: {result.removed_items}")

print("\n=== CLEAN (quarantine, selected) ===")
selected = {e.target.id for e in found[:2]}
options = CleanOptions(selected=selected, mode="quarantine", preview=False)
result = run_clean(report, options)
print(f"Removed: {result.removed_items}, freed: {result.freed_bytes}")
print(f"Errors: {result.errors} ({len(result.detailed_errors)} detailed)")
for line in result.lines[:5]:
    print(f"  {line}")

print("\n=== QUARANTINE ===")
stats = get_quarantine_stats()
print(f"Stats: {stats}")
integrity = verify_quarantine_integrity()
print(f"Integrity: verified={integrity.get('verified')} corrupted={integrity.get('corrupted')} missing={integrity.get('missing')}")

print("\n=== STATS ===")
s = get_stats()
s.record_scan(len(found), report.total_bytes)
s.record_clean(result.removed_items, result.freed_bytes)
print(f"Scans: {s.get('scans')}, Cleans: {s.get('cleans')}")
print(f"Referral: {s.get_referral_code()}")
newly = s.check_achievements()
print(f"New achievements: {[a['id'] for a in newly]}")

print("\n=== STREAK ===")
streak = update_streak(len(found))
print(f"Streak: {streak}")

print("\n=== SHARE REPORT ===")
from duai.core.viral import generate_share_report
print(generate_share_report()[:400])

print("\n=== PNG REPORT ===")
path = generate_and_open(score=score, found_count=len(found), freed_bytes=result.freed_bytes,
                         streak_days=streak.get('current', 0), achievements_unlocked=2)
print(f"PNG: {path} (exists={os.path.exists(path)})")

print("\n=== NOTIFICATIONS ===")
notify_clean_complete(result.removed_items, result.freed_bytes)
print("Notification OK")

print("\n=== E2E TEST PASSED ===")
