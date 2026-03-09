import aiosqlite
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT DEFAULT 'ru',
                timezone TEXT DEFAULT 'Europe/Moscow',
                current_level INTEGER DEFAULT 1,
                xp_balance INTEGER DEFAULT 0,
                points_balance INTEGER DEFAULT 0,
                streak_days INTEGER DEFAULT 0,
                last_activity_date TEXT,
                referral_code TEXT UNIQUE,
                referred_by_user_id INTEGER,
                is_subscribed INTEGER DEFAULT 0,
                subscribed_checked_at TEXT,
                onboarding_done INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS triggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_type TEXT DEFAULT 'text',
                raw_text TEXT NOT NULL,
                transcript_text TEXT,
                normalized_text TEXT,
                emotion_code TEXT,
                intensity INTEGER,
                category_code TEXT,
                happened_at TEXT,
                zone_of_control_text TEXT,
                insight_text TEXT,
                next_action_text TEXT,
                ai_tags TEXT,
                points_awarded INTEGER DEFAULT 0,
                status TEXT DEFAULT 'recorded',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS trigger_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_id INTEGER NOT NULL,
                question_key TEXT NOT NULL,
                answer_text TEXT,
                points_awarded INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (trigger_id) REFERENCES triggers(id)
            );

            CREATE TABLE IF NOT EXISTS diary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                body TEXT NOT NULL,
                mood_code TEXT,
                energy_level INTEGER,
                tension_level INTEGER,
                insight_text TEXT,
                points_awarded INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS rewards_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                source_entity_type TEXT,
                source_entity_id INTEGER,
                points_delta INTEGER DEFAULT 0,
                xp_delta INTEGER DEFAULT 0,
                balance_after INTEGER DEFAULT 0,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT '🏆',
                rule_type TEXT,
                rule_value INTEGER,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS user_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_id INTEGER NOT NULL,
                awarded_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, achievement_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (achievement_id) REFERENCES achievements(id)
            );

            CREATE TABLE IF NOT EXISTS notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                diary_enabled INTEGER DEFAULT 1,
                diary_time TEXT DEFAULT '20:00',
                trigger_reminders_enabled INTEGER DEFAULT 1,
                random_checkin_enabled INTEGER DEFAULT 1,
                random_checkin_max_per_day INTEGER DEFAULT 2,
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                estimated_difficulty_score TEXT DEFAULT 'easy',
                estimated_points INTEGER DEFAULT 5,
                status TEXT DEFAULT 'new',
                points_awarded INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'digital',
                price_points INTEGER NOT NULL DEFAULT 100,
                stock INTEGER DEFAULT -1,
                is_active INTEGER DEFAULT 1,
                image_url TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                payment_mode TEXT DEFAULT 'points',
                points_amount INTEGER DEFAULT 0,
                payment_status TEXT DEFAULT 'completed',
                access_status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
        """)

        # Seed achievements
        await db.executemany("""
            INSERT OR IGNORE INTO achievements (code, title, description, icon, rule_type, rule_value)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ("first_trigger", "Первый шаг", "Зафиксировал первый триггер", "🌱", "trigger_count", 1),
            ("trigger_10", "Наблюдатель", "10 зафиксированных триггеров", "👁", "trigger_count", 10),
            ("trigger_50", "Честный игрок", "50 честных записей", "🎯", "trigger_count", 50),
            ("streak_7", "7 дней осознанности", "7 дней подряд без пропуска", "🔥", "streak", 7),
            ("streak_30", "Месяц практики", "30 дней дневника", "📅", "streak", 30),
        ])

        # Seed demo products
        await db.executemany("""
            INSERT OR IGNORE INTO products (id, title, description, category, price_points, stock, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (1, "🧘 Гайд по осознанности", "PDF-гайд «7 практик осознанности» — скачать сразу после покупки", "digital", 100, -1, 1),
            (2, "📞 Консультация 30 мин", "Личная сессия с психологом — запишем тебя после покупки", "consultation", 500, 10, 1),
            (3, "📚 Курс «Эмоции под контролем»", "Онлайн-курс из 8 уроков о работе с триггерами", "course", 300, -1, 1),
            (4, "🎁 Фирменный стикерпак", "Эксклюзивный стикерпак в Telegram от создателей бота", "digital", 50, -1, 1),
        ])

        await db.commit()

    # Run migrations to safely add new tables and features
    from migrations import run_migrations
    await run_migrations()


async def get_user(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_user(telegram_id: int, username: str, first_name: str,
                      last_name: str = "", language_code: str = "ru",
                      referred_by: int = None) -> dict:
    import random
    import string
    referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users
            (telegram_id, username, first_name, last_name, language_code, referral_code, referred_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (telegram_id, username, first_name, last_name, language_code, referral_code, referred_by))
        await db.execute("""
            INSERT OR IGNORE INTO notification_settings (user_id)
            SELECT id FROM users WHERE telegram_id = ?
        """, (telegram_id,))
        await db.commit()
    return await get_user(telegram_id)


async def update_user(telegram_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [telegram_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {fields}, updated_at = datetime('now') WHERE telegram_id = ?",
            values
        )
        await db.commit()


async def award_points(telegram_id: int, points: int, event_type: str,
                       description: str, source_type: str = None, source_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, points_balance, xp_balance FROM users WHERE telegram_id = ?",
            (telegram_id,)
        ) as cursor:
            user = await cursor.fetchone()
        if not user:
            return

        new_balance = user["points_balance"] + points
        new_xp = user["xp_balance"] + points

        await db.execute("""
            UPDATE users SET points_balance = ?, xp_balance = ?,
            updated_at = datetime('now') WHERE telegram_id = ?
        """, (new_balance, new_xp, telegram_id))

        await db.execute("""
            INSERT INTO rewards_log
            (user_id, event_type, source_entity_type, source_entity_id,
             points_delta, xp_delta, balance_after, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user["id"], event_type, source_type, source_id,
              points, points, new_balance, description))

        await db.commit()
        return new_balance


async def save_trigger(user_id: int, raw_text: str, emotion_code: str = None,
                       intensity: int = None, category_code: str = None,
                       ai_tags: str = None, points: int = 0,
                       audio_file_id: str = None, audio_duration: int = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO triggers
            (user_id, raw_text, emotion_code, intensity, category_code, ai_tags, 
             points_awarded, audio_file_id, audio_duration, transcription_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, raw_text, emotion_code, intensity, category_code, ai_tags, 
              points, audio_file_id, audio_duration,
              'voice' if audio_file_id else 'text'))
        trigger_id = cursor.lastrowid
        await db.commit()
        return trigger_id


async def update_trigger(trigger_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [trigger_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE triggers SET {fields}, updated_at = datetime('now') WHERE id = ?",
            values
        )
        await db.commit()


async def get_triggers(user_id: int, limit: int = 10, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM triggers WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, (user_id, limit, offset)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def count_triggers_today(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM triggers
            WHERE user_id = ? AND date(created_at) = date('now')
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0]


async def count_triggers_total(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM triggers WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0]


async def save_diary_entry(user_id: int, body: str, mood_code: str = None,
                           energy_level: int = None, tension_level: int = None,
                           insight_text: str = None, points: int = 0) -> int:
    from datetime import date
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO diary_entries
            (user_id, entry_date, body, mood_code, energy_level, tension_level, insight_text, points_awarded)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, str(date.today()), body, mood_code, energy_level, tension_level, insight_text, points))
        entry_id = cursor.lastrowid
        await db.commit()
        return entry_id


async def get_diary_entries(user_id: int, limit: int = 7) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM diary_entries WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def check_diary_today(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM diary_entries
            WHERE user_id = ? AND date(created_at) = date('now')
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] > 0


async def get_user_achievements(user_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT a.code FROM achievements a
            JOIN user_achievements ua ON a.id = ua.achievement_id
            WHERE ua.user_id = ?
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def award_achievement(user_id: int, achievement_code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM achievements WHERE code = ?", (achievement_code,)
        ) as cursor:
            ach = await cursor.fetchone()
        if not ach:
            return False
        try:
            await db.execute("""
                INSERT INTO user_achievements (user_id, achievement_id)
                VALUES (?, ?)
            """, (user_id, ach[0]))
            await db.commit()
            return True
        except Exception:
            return False


async def get_weekly_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM triggers
            WHERE user_id = ? AND created_at >= datetime('now', '-7 days')
        """, (user_id,)) as cursor:
            triggers_week = (await cursor.fetchone())[0]

        async with db.execute("""
            SELECT COUNT(*) FROM diary_entries
            WHERE user_id = ? AND created_at >= datetime('now', '-7 days')
        """, (user_id,)) as cursor:
            diary_week = (await cursor.fetchone())[0]

        async with db.execute("""
            SELECT COALESCE(SUM(points_delta), 0) FROM rewards_log
            WHERE user_id = ? AND created_at >= datetime('now', '-7 days')
        """, (user_id,)) as cursor:
            points_week = (await cursor.fetchone())[0]

    return {
        "triggers": triggers_week,
        "diary": diary_week,
        "points": points_week,
    }


# ─── Tasks ────────────────────────────────────────────────────────────────────

TASK_POINTS = {
    "easy": 5,
    "medium": 12,
    "hard": 30,
    "uncomfortable": 50,
}


async def save_task(user_id: int, title: str, difficulty: str) -> int:
    points = TASK_POINTS.get(difficulty, 5)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO tasks (user_id, title, estimated_difficulty_score, estimated_points, status)
            VALUES (?, ?, ?, ?, 'new')
        """, (user_id, title, difficulty, points))
        task_id = cursor.lastrowid
        await db.commit()
        return task_id


async def get_tasks(user_id: int, status: str = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            q = "SELECT * FROM tasks WHERE user_id=? AND status=? ORDER BY created_at DESC"
            params = (user_id, status)
        else:
            q = "SELECT * FROM tasks WHERE user_id=? AND status != 'cancelled' ORDER BY created_at DESC LIMIT 20"
            params = (user_id,)
        async with db.execute(q, params) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_task(task_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_task_status(task_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET status=?, updated_at=datetime('now') WHERE id=?",
            (status, task_id)
        )
        await db.commit()


async def complete_task(task_id: int, telegram_id: int) -> dict:
    """Mark task done, award points, return result. telegram_id = Telegram user ID."""
    task = await get_task(task_id)
    if not task:
        return {"ok": False}
    points = task.get("estimated_points") or TASK_POINTS.get(
        task.get("estimated_difficulty_score", "easy"), 5
    )
    await update_task_status(task_id, "done")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET points_awarded=?, updated_at=datetime('now') WHERE id=?",
            (points, task_id)
        )
        await db.commit()
    balance = await award_points(
        telegram_id, points, "task_complete",
        f"Задача выполнена: {task['title'][:40]}",
        source_type="task", source_id=task_id
    )
    return {"ok": True, "points": points, "balance": balance or 0}


# ─── Notifications helpers ────────────────────────────────────────────────────

async def get_users_needing_diary_reminder() -> list[dict]:
    """Users with diary enabled who haven't written today."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.telegram_id, u.first_name, ns.diary_time
            FROM users u
            JOIN notification_settings ns ON ns.user_id = u.id
            WHERE ns.diary_enabled = 1
              AND u.onboarding_done = 1
              AND u.id NOT IN (
                  SELECT user_id FROM diary_entries
                  WHERE date(created_at) = date('now')
              )
        """) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_users_needing_trigger_reminder() -> list[dict]:
    """Users who haven't logged a trigger today."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.telegram_id, u.first_name
            FROM users u
            JOIN notification_settings ns ON ns.user_id = u.id
            WHERE ns.trigger_reminders_enabled = 1
              AND u.onboarding_done = 1
              AND u.id NOT IN (
                  SELECT user_id FROM triggers
                  WHERE date(created_at) = date('now')
              )
        """) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_users_for_random_checkin() -> list[dict]:
    """Users with random check-in enabled."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.telegram_id, u.first_name
            FROM users u
            JOIN notification_settings ns ON ns.user_id = u.id
            WHERE ns.random_checkin_enabled = 1
              AND u.onboarding_done = 1
        """) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_inviter_by_db_id(user_db_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE id = ?", (user_db_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def award_referral(inviter_telegram_id: int, invited_name: str) -> int:
    """Award referral points to inviter, return new balance."""
    from config import POINTS
    balance = await award_points(
        inviter_telegram_id,
        POINTS["referral"],
        "referral",
        f"Реферал: {invited_name} зарегистрировался по твоей ссылке"
    )
    return balance or 0


# ─── Shop ─────────────────────────────────────────────────────────────────────

async def get_products(active_only: bool = True) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where = "WHERE is_active = 1" if active_only else ""
        async with db.execute(f"SELECT * FROM products {where} ORDER BY price_points ASC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_product(product_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def buy_product(telegram_id: int, product_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cur:
            user = dict(await cur.fetchone())
        async with db.execute("SELECT * FROM products WHERE id = ? AND is_active = 1", (product_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return {"ok": False, "error": "not_found"}
            product = dict(row)

        price = product.get("price_points") or 0
        if user["points_balance"] < price:
            return {"ok": False, "error": "insufficient_funds",
                    "need": price, "balance": user["points_balance"]}

        new_balance = user["points_balance"] - price
        await db.execute(
            "UPDATE users SET points_balance = ?, updated_at = datetime('now') WHERE telegram_id = ?",
            (new_balance, telegram_id)
        )
        await db.execute("""
            INSERT INTO purchases (user_id, product_id, payment_mode, points_amount, payment_status, access_status)
            VALUES (?, ?, 'points', ?, 'paid', 'granted')
        """, (user["id"], product_id, price))
        await db.execute("""
            INSERT INTO rewards_log (user_id, event_type, source_entity_type, source_entity_id,
                points_delta, xp_delta, balance_after, description)
            VALUES (?, 'purchase', 'product', ?, ?, 0, ?, ?)
        """, (user["id"], product_id, -price, new_balance, f"Покупка: {product['title']}"))
        await db.commit()
        return {"ok": True, "product": product, "spent": price, "balance": new_balance}


async def get_user_purchases(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT pu.*, pr.title, pr.description, pr.category
            FROM purchases pu JOIN products pr ON pr.id = pu.product_id
            WHERE pu.user_id = ? ORDER BY pu.created_at DESC
        """, (user_id,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ─── Patterns ─────────────────────────────────────────────────────────────────

async def get_trigger_patterns(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT emotion_code, COUNT(*) as cnt FROM triggers
            WHERE user_id = ? AND emotion_code IS NOT NULL
            GROUP BY emotion_code ORDER BY cnt DESC LIMIT 5
        """, (user_id,)) as cur:
            top_emotions = [{"emotion": r[0], "count": r[1]} for r in await cur.fetchall()]

        async with db.execute("""
            SELECT category_code, COUNT(*) as cnt FROM triggers
            WHERE user_id = ? AND category_code IS NOT NULL
            GROUP BY category_code ORDER BY cnt DESC LIMIT 5
        """, (user_id,)) as cur:
            top_categories = [{"category": r[0], "count": r[1]} for r in await cur.fetchall()]

        async with db.execute("""
            SELECT raw_text, emotion_code, intensity FROM triggers
            WHERE user_id = ? AND intensity >= 7
              AND created_at >= datetime('now', '-30 days')
            ORDER BY intensity DESC LIMIT 5
        """, (user_id,)) as cur:
            intense = [{"text": r[0], "emotion": r[1], "intensity": r[2]}
                       for r in await cur.fetchall()]

        async with db.execute("SELECT COUNT(*) FROM triggers WHERE user_id = ?", (user_id,)) as cur:
            total = (await cur.fetchone())[0]

        async with db.execute("""
            SELECT COUNT(*) FROM triggers
            WHERE user_id = ? AND created_at >= datetime('now', '-7 days')
        """, (user_id,)) as cur:
            week_count = (await cur.fetchone())[0]

    return {
        "top_emotions": top_emotions,
        "top_categories": top_categories,
        "intense_triggers": intense,
        "total": total,
        "week_count": week_count,
    }


# ─── Points Configuration ──────────────────────────────────────────────────────

async def get_all_points_rules() -> list[dict]:
    """Get all points configuration rules."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, rule_name, points_value, category, description, updated_at FROM points_config ORDER BY category, rule_name"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_points_rule(rule_name: str) -> dict | None:
    """Get a single points rule."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM points_config WHERE rule_name = ?", (rule_name,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_points_rule(rule_name: str, points_value: int) -> bool:
    """Update a points rule value."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE points_config SET points_value = ?, updated_at = datetime('now') WHERE rule_name = ?",
            (points_value, rule_name)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_points_config_dict() -> dict:
    """Get all points config as a simple dict {rule_name: points_value}."""
    rules = await get_all_points_rules()
    return {r["rule_name"]: r["points_value"] for r in rules}


# ─── Menu Settings ─────────────────────────────────────────────────────────────

async def get_menu_settings_all() -> list[dict]:
    """Return all menu_settings rows (key, value, label)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT key, value, label FROM menu_settings ORDER BY key"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_menu_settings_dict() -> dict:
    """Return {key: bool} dict of all menu settings."""
    rows = await get_menu_settings_all()
    return {r["key"]: bool(r["value"]) for r in rows}


async def update_menu_setting(key: str, value: bool):
    """Enable or disable a single menu item."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE menu_settings SET value = ?, updated_at = datetime('now') WHERE key = ?",
            (1 if value else 0, key)
        )
        await db.commit()
