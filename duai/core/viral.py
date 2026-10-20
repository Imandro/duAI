"""Funciones virales y gamificacion para duAI.

Incluye:
- Generacion de reporte compartible (sin datos sensibles) para redes sociales.
- Sistema de logros/medallas basado en estadisticas de uso con tiers (bronze/silver/gold/platinum).
- Privacy Score calculation y tracking.
- Challenge system para engagement diario/semanal.
- Referral codes para crecimiento viral.
- Contador de racha y totales acumulados.
"""

from __future__ import annotations

import json
import os
import time
import uuid
import hashlib
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional

from ..utils.logger import base_dir, log
from ..utils.paths import fmt_bytes
from ..utils.settings import get_settings
from ..core.privacy_score import calculate_score, get_latest_score

STATS_FILE = os.path.join(base_dir(), "stats.json")
CHALLENGES_FILE = os.path.join(base_dir(), "challenges.json")

# Tiered Achievements: bronze, silver, gold, platinum
ACHIEVEMENTS = [
    # Scan achievements
    {
        "id": "first_scan",
        "name": "First Scan",
        "desc": "Perform your first AI trace scan.",
        "icon": "🔍",
        "tier": "bronze",
        "target": 1,
        "unit": "scan",
        "condition": lambda s: s.get("scans", 0) >= 1,
    },
    {
        "id": "scan_10",
        "name": "Scanner",
        "desc": "Perform 10 scans.",
        "icon": "🔎",
        "tier": "silver",
        "target": 10,
        "unit": "scans",
        "condition": lambda s: s.get("scans", 0) >= 10,
    },
    {
        "id": "scan_50",
        "name": "Detective",
        "desc": "Perform 50 scans.",
        "icon": "🕵️",
        "tier": "gold",
        "target": 50,
        "unit": "scans",
        "condition": lambda s: s.get("scans", 0) >= 50,
    },
    {
        "id": "scan_100",
        "name": "Omniscient",
        "desc": "Perform 100 scans.",
        "icon": "🧠",
        "tier": "platinum",
        "target": 100,
        "unit": "scans",
        "condition": lambda s: s.get("scans", 0) >= 100,
    },
    # Clean achievements
    {
        "id": "first_clean",
        "name": "First Clean",
        "desc": "Clean AI traces for the first time.",
        "icon": "🧹",
        "tier": "bronze",
        "target": 1,
        "unit": "clean",
        "condition": lambda s: s.get("cleans", 0) >= 1,
    },
    {
        "id": "clean_10",
        "name": "Janitor",
        "desc": "Clean 10 times.",
        "icon": "🧼",
        "tier": "silver",
        "target": 10,
        "unit": "cleans",
        "condition": lambda s: s.get("cleans", 0) >= 10,
    },
    {
        "id": "clean_50",
        "name": "Sanitizer",
        "desc": "Clean 50 times.",
        "icon": "✨",
        "tier": "gold",
        "target": 50,
        "unit": "cleans",
        "condition": lambda s: s.get("cleans", 0) >= 50,
    },
    # Panic achievements
    {
        "id": "panic_user",
        "name": "Panic Mode",
        "desc": "Execute the panic button for the first time.",
        "icon": "🚨",
        "tier": "bronze",
        "target": 1,
        "unit": "panic",
        "condition": lambda s: s.get("panics", 0) >= 1,
    },
    {
        "id": "panic_5",
        "name": "Paranoid",
        "desc": "Use panic mode 5 times.",
        "icon": "😰",
        "tier": "silver",
        "target": 5,
        "unit": "panics",
        "condition": lambda s: s.get("panics", 0) >= 5,
    },
    # Freed space achievements
    {
        "id": "mb_freed",
        "name": "Megabyte Freed",
        "desc": "Free 1 MB of space.",
        "icon": "💾",
        "tier": "bronze",
        "target": 1024 * 1024,
        "unit": "MB",
        "condition": lambda s: s.get("total_freed_bytes", 0) >= 1024 * 1024,
    },
    {
        "id": "gb_freed",
        "name": "Gigabyte Freed",
        "desc": "Free 1 GB of space.",
        "icon": "💿",
        "tier": "silver",
        "target": 1024 ** 3,
        "unit": "GB",
        "condition": lambda s: s.get("total_freed_bytes", 0) >= 1024 ** 3,
    },
    {
        "id": "gb10_freed",
        "name": "Space Liberator",
        "desc": "Free 10 GB of space.",
        "icon": "🚀",
        "tier": "gold",
        "target": 10 * 1024 ** 3,
        "unit": "GB",
        "condition": lambda s: s.get("total_freed_bytes", 0) >= 10 * 1024 ** 3,
    },
    {
        "id": "gb100_freed",
        "name": "Storage Titan",
        "desc": "Free 100 GB of space.",
        "icon": "🏆",
        "tier": "platinum",
        "target": 100 * 1024 ** 3,
        "unit": "GB",
        "condition": lambda s: s.get("total_freed_bytes", 0) >= 100 * 1024 ** 3,
    },
    # Streak achievements
    {
        "id": "streak_3",
        "name": "Threepeat",
        "desc": "3 day streak.",
        "icon": "🔥",
        "tier": "bronze",
        "target": 3,
        "unit": "days",
        "condition": lambda s: s.get("streak_days", 0) >= 3,
    },
    {
        "id": "streak_7",
        "name": "Weekly Warrior",
        "desc": "7 day streak.",
        "icon": "📅",
        "tier": "silver",
        "target": 7,
        "unit": "days",
        "condition": lambda s: s.get("streak_days", 0) >= 7,
    },
    {
        "id": "streak_30",
        "name": "Monthly Master",
        "desc": "30 day streak.",
        "icon": "🗓️",
        "tier": "gold",
        "target": 30,
        "unit": "days",
        "condition": lambda s: s.get("streak_days", 0) >= 30,
    },
    {
        "id": "streak_100",
        "name": "Centurion",
        "desc": "100 day streak.",
        "icon": "💯",
        "tier": "platinum",
        "target": 100,
        "unit": "days",
        "condition": lambda s: s.get("streak_days", 0) >= 100,
    },
    # Privacy Score achievements
    {
        "id": "score_80",
        "name": "Privacy Conscious",
        "desc": "Reach 80 Privacy Score.",
        "icon": "🛡️",
        "tier": "bronze",
        "target": 80,
        "unit": "score",
        "condition": lambda s: (get_latest_score() or {}).get("score", 0) >= 80,
    },
    {
        "id": "score_90",
        "name": "Privacy Advocate",
        "desc": "Reach 90 Privacy Score.",
        "icon": "🔐",
        "tier": "silver",
        "target": 90,
        "unit": "score",
        "condition": lambda s: (get_latest_score() or {}).get("score", 0) >= 90,
    },
    {
        "id": "score_100",
        "name": "Perfect Privacy",
        "desc": "Reach 100 Privacy Score.",
        "icon": "🏅",
        "tier": "gold",
        "target": 100,
        "unit": "score",
        "condition": lambda s: (get_latest_score() or {}).get("score", 0) >= 100,
    },
    # Social achievements
    {
        "id": "share_1",
        "name": "Sharer",
        "desc": "Share your report once.",
        "icon": "📤",
        "tier": "bronze",
        "target": 1,
        "unit": "share",
        "condition": lambda s: s.get("shares", 0) >= 1,
    },
    {
        "id": "share_10",
        "name": "Influencer",
        "desc": "Share 10 times.",
        "icon": "📢",
        "tier": "silver",
        "target": 10,
        "unit": "shares",
        "condition": lambda s: s.get("shares", 0) >= 10,
    },
    {
        "id": "referral_1",
        "name": "Recruiter",
        "desc": "Get 1 referral signup.",
        "icon": "🤝",
        "tier": "silver",
        "target": 1,
        "unit": "referral",
        "condition": lambda s: s.get("referral_count", 0) >= 1,
    },
    {
        "id": "referral_5",
        "name": "Community Builder",
        "desc": "Get 5 referral signups.",
        "icon": "👥",
        "tier": "gold",
        "target": 5,
        "unit": "referrals",
        "condition": lambda s: s.get("referral_count", 0) >= 5,
    },
    # Quarantine achievements
    {
        "id": "quarantine_1",
        "name": "Quarantine User",
        "desc": "Quarantine an item for the first time.",
        "icon": "📦",
        "tier": "bronze",
        "target": 1,
        "unit": "item",
        "condition": lambda s: s.get("quarantine_items", 0) >= 1,
    },
    {
        "id": "quarantine_restore_10",
        "name": "Restorer",
        "desc": "Restore 10 items from quarantine.",
        "icon": "♻️",
        "tier": "silver",
        "target": 10,
        "unit": "restores",
        "condition": lambda s: s.get("quarantine_restores", 0) >= 10,
    },
    # Stealth achievements
    {
        "id": "stealth_5",
        "name": "Ghost",
        "desc": "Exit stealth mode 5 times.",
        "icon": "👻",
        "tier": "bronze",
        "target": 5,
        "unit": "exits",
        "condition": lambda s: s.get("stealth_exits", 0) >= 5,
    },
    # Update achievements
    {
        "id": "updater_1",
        "name": "Up to Date",
        "desc": "Install an update.",
        "icon": "⬆️",
        "tier": "bronze",
        "target": 1,
        "unit": "update",
        "condition": lambda s: s.get("updates_installed", 0) >= 1,
    },
    # Challenge achievements
    {
        "id": "challenge_1",
        "name": "Challenger",
        "desc": "Complete your first daily challenge.",
        "icon": "🎯",
        "tier": "bronze",
        "target": 1,
        "unit": "challenge",
        "condition": lambda s: s.get("challenges_completed", 0) >= 1,
    },
    {
        "id": "challenge_7",
        "name": "Challenge Ace",
        "desc": "Complete 7 daily challenges.",
        "icon": "🏅",
        "tier": "silver",
        "target": 7,
        "unit": "challenges",
        "condition": lambda s: s.get("challenges_completed", 0) >= 7,
    },
    {
        "id": "challenge_30",
        "name": "Challenge Master",
        "desc": "Complete 30 daily challenges.",
        "icon": "🥇",
        "tier": "gold",
        "target": 30,
        "unit": "challenges",
        "condition": lambda s: s.get("challenges_completed", 0) >= 30,
    },
]


TIER_COLORS = {
    "bronze": "#CD7F32",
    "silver": "#C0C0C0",
    "gold": "#FFD700",
    "platinum": "#E5E4E2",
}

TIER_ORDER = {"bronze": 0, "silver": 1, "gold": 2, "platinum": 3}


class Stats:
    """Estadisticas acumuladas de uso de duAI."""

    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return self._default_data()

    def _default_data(self) -> dict:
        return {
            "scans": 0,
            "cleans": 0,
            "panics": 0,
            "total_freed_bytes": 0,
            "total_items_removed": 0,
            "streak_days": 0,
            "last_streak_date": None,
            "stealth_exits": 0,
            "quarantine_items": 0,
            "quarantine_restores": 0,
            "achievements_unlocked": [],
            "achievements_progress": {},
            "shares": 0,
            "referral_code": None,
            "referral_count": 0,
            "share_streak": 0,
            "last_share_date": None,
            "updates_installed": 0,
            "challenges_completed": 0,
            "challenge_streak": 0,
            "last_challenge_date": None,
            "privacy_score_history": [],
            "install_date": datetime.now().isoformat(),
            "version": "2.0.0",
        }

    def save(self):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def increment(self, key, amount=1):
        self._data[key] = self._data.get(key, 0) + amount
        self.save()

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def _ensure_referral_code(self):
        if not self._data.get("referral_code"):
            # Generate unique referral code
            unique = hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest()[:8].upper()
            self._data["referral_code"] = f"DUAI-{unique}"
            self.save()

    def get_referral_code(self) -> str:
        self._ensure_referral_code()
        return self._data.get("referral_code", "DUAI-XXXX")

    def record_scan(self, found: int, freed_bytes: int):
        if not get_settings().get("gamification", True):
            return
        self.increment("scans")
        self._update_streak()
        self._check_and_unlock_achievements()
        self.save()

    def record_clean(self, removed_items: int, freed_bytes: int):
        if not get_settings().get("gamification", True):
            return
        self.increment("cleans")
        self.increment("total_items_removed", removed_items)
        self.increment("total_freed_bytes", freed_bytes)
        self._check_and_unlock_achievements()
        self.save()

    def record_panic(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("panics")
        self._check_and_unlock_achievements()
        self.save()

    def record_stealth_exit(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("stealth_exits")
        self._check_and_unlock_achievements()
        self.save()

    def record_quarantine_item(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("quarantine_items")
        self._check_and_unlock_achievements()
        self.save()

    def record_quarantine_restore(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("quarantine_restores")
        self._check_and_unlock_achievements()
        self.save()

    def record_share(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("shares")
        self._update_share_streak()
        self._check_and_unlock_achievements()
        self.save()

    def record_referral(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("referral_count")
        self._check_and_unlock_achievements()
        self.save()

    def record_update(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("updates_installed")
        self._check_and_unlock_achievements()
        self.save()

    def record_challenge_complete(self):
        if not get_settings().get("gamification", True):
            return
        self.increment("challenges_completed")
        self._update_challenge_streak()
        self._check_and_unlock_achievements()
        self.save()

    def record_privacy_score(self, score: int):
        if not get_settings().get("gamification", True):
            return
        history = self._data.get("privacy_score_history", [])
        history.append({
            "score": score,
            "date": datetime.now().isoformat(),
        })
        # Keep last 100 scores
        self._data["privacy_score_history"] = history[-100:]
        self._check_and_unlock_achievements()
        self.save()

    def _update_streak(self):
        today = date.today().isoformat()
        last = self._data.get("last_streak_date")
        if last == today:
            return  # Already counted today
        if last:
            last_date = date.fromisoformat(last)
            if (date.today() - last_date).days == 1:
                # Continue streak
                self._data["streak_days"] = self._data.get("streak_days", 0) + 1
            elif (date.today() - last_date).days > 1:
                # Streak broken
                self._data["streak_days"] = 1
        else:
            self._data["streak_days"] = 1
        self._data["last_streak_date"] = today

    def _update_share_streak(self):
        today = date.today().isoformat()
        last = self._data.get("last_share_date")
        if last == today:
            return
        if last:
            last_date = date.fromisoformat(last)
            if (date.today() - last_date).days == 1:
                self._data["share_streak"] = self._data.get("share_streak", 0) + 1
            elif (date.today() - last_date).days > 1:
                self._data["share_streak"] = 1
        else:
            self._data["share_streak"] = 1
        self._data["last_share_date"] = today

    def _update_challenge_streak(self):
        today = date.today().isoformat()
        last = self._data.get("last_challenge_date")
        if last == today:
            return
        if last:
            last_date = date.fromisoformat(last)
            if (date.today() - last_date).days == 1:
                self._data["challenge_streak"] = self._data.get("challenge_streak", 0) + 1
            elif (date.today() - last_date).days > 1:
                self._data["challenge_streak"] = 1
        else:
            self._data["challenge_streak"] = 1
        self._data["last_challenge_date"] = today

    def unlocked_achievements(self) -> List[Dict]:
        unlocked = set(self._data.get("achievements_unlocked", []))
        progress = self._data.get("achievements_progress", {})
        result = []
        for ach in ACHIEVEMENTS:
            ach_unlocked = ach["id"] in unlocked
            ach_progress = progress.get(ach["id"], 0)
            result.append({
                **ach,
                "unlocked": ach_unlocked,
                "progress": ach_progress,
            })
        # Sort: unlocked first, then by tier, then by target
        result.sort(key=lambda x: (
            0 if x["unlocked"] else 1,
            TIER_ORDER.get(x["tier"], 0),
            x["target"]
        ))
        return result

    def get_all_achievements(self) -> List[Dict]:
        """Get all achievements including locked ones with progress."""
        return self.unlocked_achievements()

    def unlock_achievement(self, ach_id: str) -> bool:
        if not get_settings().get("gamification", True):
            return False
        unlocked = set(self._data.get("achievements_unlocked", []))
        if ach_id in unlocked:
            return False
        unlocked.add(ach_id)
        self._data["achievements_unlocked"] = sorted(unlocked)
        self.save()
        return True

    def _check_and_unlock_achievements(self):
        """Revisa y desbloquea logros segun estadisticas actuales.

        Devuelve la lista de logros recien desbloqueados.
        """
        if not get_settings().get("gamification", True):
            return []
        newly = []
        for ach in ACHIEVEMENTS:
            if ach["id"] not in set(self._data.get("achievements_unlocked", [])):
                if ach["condition"](self._data):
                    self.unlock_achievement(ach["id"])
                    newly.append(ach)
        if newly:
            log("viral", achievements_unlocked=[a["id"] for a in newly])
        return newly

    def check_achievements(self) -> List[Dict]:
        """Revisa los logros y devuelve los recien desbloqueados (o [])."""
        newly = self._check_and_unlock_achievements()
        self.update_achievement_progress()
        return newly

    def update_achievement_progress(self):
        """Update progress for all locked achievements."""
        progress = {}
        for ach in ACHIEVEMENTS:
            if ach["id"] not in set(self._data.get("achievements_unlocked", [])):
                # Calculate progress based on condition type
                current = 0
                if "scans" in ach["id"]:
                    current = self._data.get("scans", 0)
                elif "cleans" in ach["id"]:
                    current = self._data.get("cleans", 0)
                elif "panics" in ach["id"]:
                    current = self._data.get("panics", 0)
                elif "freed" in ach["id"]:
                    current = self._data.get("total_freed_bytes", 0)
                elif "streak" in ach["id"]:
                    current = self._data.get("streak_days", 0)
                elif "score" in ach["id"]:
                    current = (get_latest_score() or {}).get("score", 0)
                elif "share" in ach["id"]:
                    current = self._data.get("shares", 0)
                elif "referral" in ach["id"]:
                    current = self._data.get("referral_count", 0)
                elif "quarantine" in ach["id"]:
                    if "restore" in ach["id"]:
                        current = self._data.get("quarantine_restores", 0)
                    else:
                        current = self._data.get("quarantine_items", 0)
                elif "stealth" in ach["id"]:
                    current = self._data.get("stealth_exits", 0)
                elif "update" in ach["id"]:
                    current = self._data.get("updates_installed", 0)
                elif "challenge" in ach["id"]:
                    current = self._data.get("challenges_completed", 0)
                
                progress[ach["id"]] = min(current, ach.get("target", 1))
        
        self._data["achievements_progress"] = progress
        self.save()


_stats = None


def get_stats() -> Stats:
    global _stats
    if _stats is None:
        _stats = Stats()
    return _stats


def gamification_enabled() -> bool:
    """Indica si la gamificacion y registro de estadisticas esta activada."""
    return bool(get_settings().get("gamification", True))


def set_gamification(enabled: bool):
    """Activa o desactiva la gamificacion y registro de estadisticas."""
    get_settings().set("gamification", bool(enabled))


def reset_stats():
    """Reinicia todas las estadisticas y logros."""
    global _stats
    if _stats is not None:
        _stats._data = _stats._default_data()
        _stats.save()


# ==================== Privacy Score ====================

def get_privacy_score_trend(days: int = 30) -> List[Dict]:
    """Get privacy score trend for charts."""
    stats = get_stats()
    history = stats.get("privacy_score_history", [])
    cutoff = datetime.now() - timedelta(days=days)
    out: List[Dict] = []
    for h in history:
        try:
            if datetime.fromisoformat(h["date"]) >= cutoff:
                out.append({"date": h["date"][:10], "score": h["score"]})
        except (KeyError, ValueError, TypeError):
            continue

    if not out:
        # Fallback: historial persistido por privacy_score.json
        try:
            from .privacy_score import get_score_trend

            for entry in get_score_trend(200):
                stamp = entry.get("timestamp", "")
                try:
                    when = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    continue
                if when >= cutoff:
                    out.append({"date": when.strftime("%Y-%m-%d"),
                                "score": int(entry.get("score", 0))})
        except Exception:
            pass

    return out


# ==================== Challenge System ====================

DAILY_CHALLENGES = [
    {
        "id": "scan_today",
        "name": "Daily Scanner",
        "desc": "Perform a scan today.",
        "type": "scan",
        "target": 1,
        "reward_xp": 10,
    },
    {
        "id": "clean_today",
        "name": "Daily Cleaner",
        "desc": "Clean traces today.",
        "type": "clean",
        "target": 1,
        "reward_xp": 15,
    },
    {
        "id": "share_today",
        "name": "Social Sharer",
        "desc": "Share your privacy report.",
        "type": "share",
        "target": 1,
        "reward_xp": 20,
    },
    {
        "id": "score_check",
        "name": "Score Checker",
        "desc": "Check your Privacy Score.",
        "type": "score_check",
        "target": 1,
        "reward_xp": 5,
    },
    {
        "id": "quarantine_review",
        "name": "Quarantine Review",
        "desc": "Review quarantined items.",
        "type": "quarantine_review",
        "target": 1,
        "reward_xp": 10,
    },
]


class ChallengeManager:
    """Manages daily/weekly challenges."""
    
    def __init__(self):
        self._data = self._load()
    
    def _load(self) -> dict:
        try:
            with open(CHALLENGES_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {"active_challenge": None, "completed_today": False, "last_challenge_date": None}
    
    def save(self):
        try:
            with open(CHALLENGES_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass
    
    def get_today_challenge(self) -> Optional[Dict]:
        """Get or generate today's challenge."""
        today = date.today().isoformat()
        
        if self._data.get("last_challenge_date") == today and self._data.get("active_challenge"):
            return self._data["active_challenge"]
        
        # Generate new challenge
        import random
        challenge = random.choice(DAILY_CHALLENGES).copy()
        challenge["date"] = today
        challenge["completed"] = False
        challenge["progress"] = 0
        
        self._data["active_challenge"] = challenge
        self._data["last_challenge_date"] = today
        self._data["completed_today"] = False
        self.save()
        return challenge
    
    def update_challenge_progress(self, challenge_type: str, amount: int = 1):
        """Update progress on active challenge."""
        challenge = self._data.get("active_challenge")
        if not challenge or challenge.get("completed"):
            return False
        
        if challenge["type"] == challenge_type:
            challenge["progress"] = challenge.get("progress", 0) + amount
            if challenge["progress"] >= challenge["target"]:
                challenge["completed"] = True
                self._data["completed_today"] = True
                # Award XP
                stats = get_stats()
                stats.record_challenge_complete()
                log("viral", challenge_completed=challenge["id"])
            self.save()
            return True
        return False
    
    def is_challenge_completed(self) -> bool:
        return self._data.get("completed_today", False)
    
    def get_challenge_status(self) -> Dict:
        challenge = self.get_today_challenge()
        return {
            "challenge": challenge,
            "completed": self._data.get("completed_today", False),
            "progress": challenge.get("progress", 0) if challenge else 0,
            "target": challenge.get("target", 1) if challenge else 1,
        }


_challenge_manager = None


def get_challenge_manager() -> ChallengeManager:
    global _challenge_manager
    if _challenge_manager is None:
        _challenge_manager = ChallengeManager()
    return _challenge_manager


# ==================== Sharing ====================

def generate_share_report(scan_result=None, clean_result=None, template: str = "detailed") -> str:
    """Genera un reporte corto y sin datos sensibles para compartir en redes."""
    stats = get_stats()
    latest_score = get_latest_score()
    streak = get_streak()
    
    templates = {
        "minimal": f"🛡️ duAI Privacy Score: {latest_score.get('score', '—')}/100\n#duAI #PrivacyFirst",
        "detailed": _generate_detailed_report(stats, latest_score, streak, scan_result, clean_result),
        "fun": f"Just cleaned {fmt_bytes(stats.get('total_freed_bytes', 0))} of trackers with duAI! 🚀\nStreak: {streak.get('current', 0)} days 🔥\n#duAI #Privacy",
        "achievement": _generate_achievement_report(stats),
    }
    
    return templates.get(template, templates["detailed"])


def _generate_detailed_report(stats: Stats, latest_score: Dict, streak: Dict, scan_result, clean_result) -> str:
    lines = []
    lines.append("duAI — Don't Use AI")
    lines.append("=" * 30)
    lines.append("")
    
    if latest_score:
        lines.append(f"🛡️ Privacy Score: {latest_score.get('score', '—')}/100 ({latest_score.get('label', '')})")
        lines.append("")
    
    if scan_result:
        found = len(getattr(scan_result, "found_entries", []) or [])
        total_bytes = getattr(scan_result, "total_bytes", 0)
        lines.append(f"🔍 AI traces detected: {found}")
        if total_bytes:
            lines.append(f"⚠️ Space at risk: {fmt_bytes(total_bytes)}")
        lines.append("")
    
    if clean_result:
        lines.append(f"🧹 Items cleaned: {getattr(clean_result, 'removed_items', 0)}")
        freed = getattr(clean_result, "freed_bytes", 0)
        if freed:
            lines.append(f"💾 Space freed: {fmt_bytes(freed)}")
        lines.append("")
    
    lines.append(f"📊 Lifetime Stats:")
    lines.append(f"   • Total freed: {fmt_bytes(stats.get('total_freed_bytes', 0))}")
    lines.append(f"   • Scans: {stats.get('scans', 0)}")
    lines.append(f"   • Cleans: {stats.get('cleans', 0)}")
    lines.append(f"   • Panic uses: {stats.get('panics', 0)}")
    lines.append(f"   • 🔥 Streak: {streak.get('current', 0)} days")
    lines.append("")
    lines.append("100% local. No telemetry. No accounts.")
    lines.append("#duAI #Privacy #DontUseAI")
    
    return "\n".join(lines)


def _generate_achievement_report(stats: Stats) -> str:
    unlocked = stats.unlocked_achievements()
    unlocked_count = sum(1 for a in unlocked if a["unlocked"])
    total = len(unlocked)
    
    lines = []
    lines.append("🏆 duAI Achievements")
    lines.append("=" * 30)
    lines.append(f"Unlocked: {unlocked_count}/{total}")
    lines.append("")
    
    # Show top 3 recent
    recent = [a for a in unlocked if a["unlocked"]][-3:]
    for ach in recent:
        lines.append(f"{ach['icon']} {ach['name']}")
    
    lines.append("")
    lines.append("#duAI #Achievements #Privacy")
    return "\n".join(lines)


def copy_to_clipboard(text: str) -> bool:
    """Copia texto al portapapeles de Windows."""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            h_global = kernel32.GlobalAlloc(0x0002, len(text) + 1)
            if not h_global:
                return False
            locked = kernel32.GlobalLock(h_global)
            if not locked:
                kernel32.GlobalFree(h_global)
                return False
            ctypes.memmove(locked, text.encode("utf-16-le"), len(text) * 2 + 2)
            kernel32.GlobalUnlock(h_global)
            user32.SetClipboardData(13, h_global)  # CF_UNICODETEXT
            return True
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


def open_share_url(platform: str, text: str) -> str:
    """Devuelve la URL para compartir en una plataforma determinada."""
    import urllib.parse

    encoded = urllib.parse.quote(text)
    urls = {
        "twitter": f"https://twitter.com/intent/tweet?text={encoded}",
        "x": f"https://twitter.com/intent/tweet?text={encoded}",
        "linkedin": f"https://www.linkedin.com/sharing/share-offsite/?url={encoded}",
        "mastodon": f"https://mastodon.social/share?text={encoded}",
        "bluesky": f"https://bsky.app/intent/compose?text={encoded}",
        "reddit": f"https://reddit.com/submit?title={encoded}",
        "email": f"mailto:?subject=duAI Privacy Report&body={encoded}",
        "telegram": f"https://t.me/share/url?url={encoded}",
        "whatsapp": f"https://wa.me/?text={encoded}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={encoded}",
    }
    return urls.get(platform.lower(), urls["twitter"])


# ==================== Streak (import from streak.py) ====================

def get_streak() -> Dict:
    """Get current streak info."""
    from ..core.streak import get_streak as _get_streak
    return _get_streak()