import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@vadbag")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "mindgame2024")
SESSION_SECRET = os.getenv("SESSION_SECRET", "s3cr3t-ch4ng3-1n-pr0d")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

DB_PATH = "game.db"

# Populated at bot startup via getMe()
BOT_USERNAME = ""

# Points rules (defaults, can be overridden from database)
POINTS = {
    "subscription": 50,
    "first_trigger": 20,
    "trigger_base": 5,
    "trigger_emotion": 2,
    "trigger_intensity": 1,
    "trigger_insight": 3,
    "trigger_zone": 3,
    "first_daily_trigger": 5,
    "diary_short": 5,
    "diary_full": 10,
    "diary_streak_7": 20,
    "referral": 50,
}

# Cache for points loaded from database
_POINTS_CACHE = None
_POINTS_CACHE_LOADED = False

async def load_points_from_db():
    """Load points configuration from database and cache it."""
    global _POINTS_CACHE, _POINTS_CACHE_LOADED
    try:
        from database import get_points_config_dict
        _POINTS_CACHE = await get_points_config_dict()
        _POINTS_CACHE_LOADED = True
        return _POINTS_CACHE
    except Exception:
        # If database is not available, use defaults
        _POINTS_CACHE = POINTS.copy()
        _POINTS_CACHE_LOADED = True
        return _POINTS_CACHE

def get_points(rule_name: str, default: int = None) -> int:
    """Get a points value by rule name, using cache if available."""
    global _POINTS_CACHE, _POINTS_CACHE_LOADED
    if _POINTS_CACHE is None and not _POINTS_CACHE_LOADED:
        # Not loaded yet, use default POINTS
        return POINTS.get(rule_name, default or 0)
    if _POINTS_CACHE is None:
        _POINTS_CACHE = POINTS.copy()
    return _POINTS_CACHE.get(rule_name, default or POINTS.get(rule_name, 0))

# Levels
LEVELS = [
    (0, "Наблюдатель 👁"),
    (100, "Исследователь себя 🔍"),
    (300, "Практик осознанности 🧘"),
    (700, "Игрок своей жизни 🎮"),
    (1500, "Автор своей реальности ✨"),
]

def get_level(points: int) -> tuple[int, str]:
    level_num = 1
    level_name = LEVELS[0][1]
    for i, (threshold, name) in enumerate(LEVELS):
        if points >= threshold:
            level_num = i + 1
            level_name = name
    return level_num, level_name

def get_next_level_threshold(points: int) -> int | None:
    for threshold, _ in LEVELS:
        if points < threshold:
            return threshold
    return None


# ─── Menu Settings ────────────────────────────────────────────────────────────

# Default values (all items shown)
MENU_DEFAULTS = {
    "show_diary":         True,
    "show_triggers_list": True,
    "show_tasks":         True,
    "show_progress":      True,
    "show_checkin":       True,
    "show_shop":          True,
    "show_stop":          True,
    "show_settings":      True,
}

async def load_menu_from_db():
    """No-op kept for backward compat — settings are now read live from DB."""
    pass


def get_menu_setting(key: str) -> bool:
    """Read a menu setting directly from DB each time (no cache — two-process safe).
    Falls back to MENU_DEFAULTS if the table doesn't exist yet."""
    try:
        import sqlite3
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT value FROM menu_settings WHERE key = ?", (key,)
            ).fetchone()
        if row is not None:
            return bool(row[0])
    except Exception:
        pass
    return MENU_DEFAULTS.get(key, True)
