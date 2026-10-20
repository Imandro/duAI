"""Anonymous opt-in leaderboard for duAI viral features."""

import json
import os
import hashlib
import uuid
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from ..utils.logger import base_dir, log
from ..utils.settings import get_settings
from ..core.viral import get_stats


LEADERBOARD_FILE = os.path.join(base_dir(), "leaderboard.json")
LEADERBOARD_CACHE_FILE = os.path.join(base_dir(), "leaderboard_cache.json")

# Anonymous ID generation
def _get_anonymous_id() -> str:
    """Get or generate anonymous user ID."""
    settings = get_settings()
    anon_id = settings.get("leaderboard.anonymous_id")
    
    if not anon_id:
        # Generate from hardware-ish fingerprint (non-PII)
        import platform
        fingerprint = f"{platform.node()}{platform.machine()}{os.getlogin()}"
        anon_id = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
        settings.set("leaderboard.anonymous_id", anon_id)
        settings.save()
    
    return anon_id


def _get_display_name() -> str:
    """Get or generate display name."""
    settings = get_settings()
    name = settings.get("leaderboard.display_name")
    
    if not name:
        adjectives = ["Swift", "Silent", "Stealthy", "Privacy", "Secure", "Clean", "Sharp", "Keen"]
        nouns = ["Fox", "Hawk", "Ghost", "Shadow", "Ninja", "Agent", "Guard", "Scout"]
        import random
        name = f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(100, 999)}"
        settings.set("leaderboard.display_name", name)
        settings.save()
    
    return name


class LeaderboardEntry:
    """Single leaderboard entry."""
    def __init__(self, data: Dict = None):
        self.anonymous_id = data.get("anonymous_id", "") if data else ""
        self.display_name = data.get("display_name", "") if data else ""
        self.score = data.get("score", 0) if data else 0
        self.privacy_score = data.get("privacy_score", 0) if data else 0
        self.streak = data.get("streak", 0) if data else 0
        self.total_freed = data.get("total_freed", 0) if data else 0
        self.scans = data.get("scans", 0) if data else 0
        self.cleans = data.get("cleans", 0) if data else 0
        self.achievements = data.get("achievements", 0) if data else 0
        self.rank = data.get("rank", 0) if data else 0
        self.last_update = data.get("last_update", datetime.now().isoformat()) if data else datetime.now().isoformat()
        self.tier = data.get("tier", "bronze") if data else "bronze"
        self.country = data.get("country", "XX") if data else "XX"  # Optional, coarse geo
    
    def to_dict(self) -> Dict:
        return {
            "anonymous_id": self.anonymous_id,
            "display_name": self.display_name,
            "score": self.score,
            "privacy_score": self.privacy_score,
            "streak": self.streak,
            "total_freed": self.total_freed,
            "scans": self.scans,
            "cleans": self.cleans,
            "achievements": self.achievements,
            "rank": self.rank,
            "last_update": self.last_update,
            "tier": self.tier,
            "country": self.country,
        }
    
    @classmethod
    def from_local_stats(cls) -> "LeaderboardEntry":
        """Create entry from local stats."""
        stats = get_stats()
        latest_score = stats.get("privacy_score_history", [])[-1] if stats.get("privacy_score_history") else {}
        streak_data = {
            "current": stats.get("streak_days", 0),
        }
        
        # Calculate composite score
        score = (
            min(stats.get("scans", 0) * 2, 200) +
            min(stats.get("cleans", 0) * 5, 300) +
            min(stats.get("panics", 0) * 10, 100) +
            min(stats.get("total_freed_bytes", 0) // (1024**3), 200) +  # GB freed
            min(stats.get("streak_days", 0) * 3, 300) +
            min(len(stats.get("achievements_unlocked", [])) * 20, 500) +
            (latest_score.get("score", 0) if latest_score else 0)
        )
        
        # Determine tier
        if score >= 2000:
            tier = "platinum"
        elif score >= 1000:
            tier = "gold"
        elif score >= 500:
            tier = "silver"
        else:
            tier = "bronze"
        
        entry = cls()
        entry.anonymous_id = _get_anonymous_id()
        entry.display_name = _get_display_name()
        entry.score = score
        entry.privacy_score = latest_score.get("score", 0) if latest_score else 0
        entry.streak = stats.get("streak_days", 0)
        entry.total_freed = stats.get("total_freed_bytes", 0)
        entry.scans = stats.get("scans", 0)
        entry.cleans = stats.get("cleans", 0)
        entry.achievements = len(stats.get("achievements_unlocked", []))
        entry.tier = tier
        entry.last_update = datetime.now().isoformat()
        
        return entry


class LeaderboardManager:
    """Manages local and remote leaderboard data."""
    
    def __init__(self):
        self._local_entry: Optional[LeaderboardEntry] = None
        self._entries: List[LeaderboardEntry] = []
        self._enabled = False
        self._last_sync = 0
        self._sync_interval = 3600  # 1 hour
    
    def is_enabled(self) -> bool:
        """Check if leaderboard participation is enabled."""
        return get_settings().get("leaderboard.enabled", False)
    
    def set_enabled(self, enabled: bool):
        """Enable or disable leaderboard participation."""
        get_settings().set("leaderboard.enabled", enabled)
        get_settings().save()
        self._enabled = enabled
    
    def get_local_entry(self) -> LeaderboardEntry:
        """Get or create local leaderboard entry."""
        if self._local_entry is None:
            self._local_entry = LeaderboardEntry.from_local_stats()
        return self._local_entry
    
    def update_local_entry(self):
        """Update local entry with current stats."""
        self._local_entry = LeaderboardEntry.from_local_stats()
        self._save_local_cache()
    
    def _save_local_cache(self):
        """Save local entry to cache file."""
        if self._local_entry:
            try:
                with open(LEADERBOARD_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self._local_entry.to_dict(), f, indent=2)
            except Exception:
                pass
    
    def load_cached_entries(self) -> List[LeaderboardEntry]:
        """Load cached leaderboard entries."""
        try:
            with open(LEADERBOARD_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [LeaderboardEntry(d) for d in data]
            elif isinstance(data, dict):
                return [LeaderboardEntry(data)]
        except Exception:
            pass
        return []
    
    def get_local_leaderboard(self, limit: int = 100) -> List[LeaderboardEntry]:
        """Get local leaderboard (simulated with some demo entries)."""
        # In a real implementation, this would fetch from a server
        # For now, return local entry plus some generated demo entries
        entries = [self.get_local_entry()]
        
        # Generate demo entries for visual reference
        import random
        demo_names = [
            "PrivacyPro999", "CleanMaster42", "StealthAgent77", "GhostInTheMachine",
            "DataGuardian", "ScanMaster", "PanicButton", "StreakKeeper",
            "QuarantineKing", "ScoreHunter", "AchievementUnlocked", "NoTrackersHere"
        ]
        
        tiers = ["platinum", "gold", "silver", "bronze"]
        tier_weights = [0.05, 0.15, 0.30, 0.50]
        
        for i, name in enumerate(demo_names):
            tier = random.choices(tiers, weights=tier_weights)[0]
            base_score = {"platinum": 2500, "gold": 1500, "silver": 750, "bronze": 200}[tier]
            score = base_score + random.randint(-100, 200)
            
            entry = LeaderboardEntry()
            entry.anonymous_id = f"demo_{i:04d}"
            entry.display_name = name
            entry.score = score
            entry.privacy_score = random.randint(60, 100)
            entry.streak = random.randint(1, 100)
            entry.total_freed = random.randint(100_000_000, 50_000_000_000)
            entry.scans = random.randint(10, 500)
            entry.cleans = random.randint(5, 200)
            entry.achievements = random.randint(1, 30)
            entry.tier = tier
            entry.last_update = (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
            entries.append(entry)
        
        # Sort by score
        entries.sort(key=lambda e: e.score, reverse=True)
        
        # Assign ranks
        for i, entry in enumerate(entries):
            entry.rank = i + 1
        
        return entries[:limit]
    
    def get_user_rank(self) -> Dict:
        """Get current user's rank and percentile."""
        entries = self.get_local_leaderboard(1000)
        local = self.get_local_entry()
        
        # Find user's position
        user_entry = None
        for entry in entries:
            if entry.anonymous_id == local.anonymous_id:
                user_entry = entry
                break
        
        if not user_entry:
            return {"rank": 0, "percentile": 0, "tier": "bronze"}
        
        total = len(entries)
        percentile = int((1 - user_entry.rank / total) * 100) if total > 0 else 0
        
        return {
            "rank": user_entry.rank,
            "total": total,
            "percentile": percentile,
            "tier": user_entry.tier,
            "score": user_entry.score,
        }
    
    def get_tier_distribution(self) -> Dict[str, int]:
        """Get distribution of users across tiers."""
        entries = self.get_local_leaderboard(1000)
        dist = {"platinum": 0, "gold": 0, "silver": 0, "bronze": 0}
        for entry in entries:
            dist[entry.tier] = dist.get(entry.tier, 0) + 1
        return dist
    
    def get_weekly_stats(self) -> Dict:
        """Get weekly leaderboard statistics."""
        entries = self.get_local_leaderboard(1000)
        
        if not entries:
            return {}
        
        return {
            "top_score": entries[0].score,
            "avg_score": sum(e.score for e in entries) // len(entries),
            "top_streak": max(e.streak for e in entries),
            "avg_streak": sum(e.streak for e in entries) // len(entries),
            "total_users": len(entries),
            "tier_distribution": self.get_tier_distribution(),
        }


# Global instance
_leaderboard_manager = None


def get_leaderboard_manager() -> LeaderboardManager:
    global _leaderboard_manager
    if _leaderboard_manager is None:
        _leaderboard_manager = LeaderboardManager()
    return _leaderboard_manager


def is_leaderboard_enabled() -> bool:
    return get_leaderboard_manager().is_enabled()


def set_leaderboard_enabled(enabled: bool):
    get_leaderboard_manager().set_enabled(enabled)


def get_user_rank() -> Dict:
    return get_leaderboard_manager().get_user_rank()


def get_leaderboard(limit: int = 50) -> List[Dict]:
    entries = get_leaderboard_manager().get_local_leaderboard(limit)
    return [e.to_dict() for e in entries]


def get_weekly_stats() -> Dict:
    return get_leaderboard_manager().get_weekly_stats()


def get_tier_distribution() -> Dict[str, int]:
    return get_leaderboard_manager().get_tier_distribution()


def get_local_entry() -> Dict:
    return get_leaderboard_manager().get_local_entry().to_dict()


def sync_leaderboard() -> bool:
    """Sync with remote leaderboard (placeholder for future implementation)."""
    # TODO: Implement actual server sync
    # For now, just update local entry
    get_leaderboard_manager().update_local_entry()
    return True