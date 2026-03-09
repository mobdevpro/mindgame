"""
Database migration system — безопасное обновление схемы БД без потери данных.
Каждая миграция идемпотентна и проверяет существование таблиц перед созданием.
"""
import aiosqlite
from datetime import datetime
from config import DB_PATH


async def create_migrations_table():
    """Создать таблицу для отслеживания примененных миграций."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()


async def get_applied_migrations() -> set[str]:
    """Получить список примененных миграций."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT migration_name FROM schema_migrations") as cur:
            return {row[0] for row in await cur.fetchall()}


async def mark_migration_applied(migration_name: str):
    """Отметить миграцию как примененную."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration_name) VALUES (?)",
            (migration_name,)
        )
        await db.commit()


async def backup_database():
    """Создать резервную копию БД перед миграциями."""
    import shutil
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.backup_{timestamp}"
    try:
        shutil.copy(DB_PATH, backup_path)
        return backup_path
    except Exception as e:
        print(f"⚠️ Ошибка при создании резервной копии: {e}")
        return None


async def migrate_001_add_points_config():
    """Миграция: добавить таблицу points_config для управления очками."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверить, существует ли таблица
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='points_config'"
        ) as cur:
            if await cur.fetchone():
                return True  # Таблица уже существует

        # Создать таблицу
        await db.execute("""
            CREATE TABLE points_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name TEXT UNIQUE NOT NULL,
                points_value INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                category TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Инициализировать стандартные значения
        from config import POINTS as DEFAULT_POINTS
        await db.executemany("""
            INSERT OR IGNORE INTO points_config (rule_name, points_value, category, description)
            VALUES (?, ?, ?, ?)
        """, [
            ("subscription", DEFAULT_POINTS.get("subscription", 50), "events", "За подписку на канал"),
            ("first_trigger", DEFAULT_POINTS.get("first_trigger", 20), "triggers", "За первый триггер"),
            ("trigger_base", DEFAULT_POINTS.get("trigger_base", 5), "triggers", "За запись триггера"),
            ("trigger_emotion", DEFAULT_POINTS.get("trigger_emotion", 2), "triggers", "За выбор эмоции"),
            ("trigger_intensity", DEFAULT_POINTS.get("trigger_intensity", 1), "triggers", "За оценку интенсивности"),
            ("trigger_insight", DEFAULT_POINTS.get("trigger_insight", 3), "triggers", "За инсайт к триггеру"),
            ("trigger_zone", DEFAULT_POINTS.get("trigger_zone", 3), "triggers", "За зону контроля"),
            ("first_daily_trigger", DEFAULT_POINTS.get("first_daily_trigger", 5), "triggers", "За первый триггер в день"),
            ("diary_short", DEFAULT_POINTS.get("diary_short", 5), "diary", "За короткую запись в дневник"),
            ("diary_full", DEFAULT_POINTS.get("diary_full", 10), "diary", "За полную запись в дневник"),
            ("diary_streak_7", DEFAULT_POINTS.get("diary_streak_7", 20), "diary", "За 7-дневный стрик дневника"),
            ("referral", DEFAULT_POINTS.get("referral", 50), "events", "За каждого приглашённого друга"),
        ])

        await db.commit()
        return True


async def migrate_002_add_menu_settings():
    """Миграция: таблица menu_settings для включения/отключения кнопок меню."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='menu_settings'"
        ) as cur:
            if await cur.fetchone():
                return True  # Already exists

        await db.execute("""
            CREATE TABLE menu_settings (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 1,
                label TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.executemany(
            "INSERT OR IGNORE INTO menu_settings (key, value, label) VALUES (?, 1, ?)",
            [
                ("show_diary",         "📔 Дневник"),
                ("show_triggers_list", "📋 Мои триггеры"),
                ("show_tasks",         "✅ Мои задачи"),
                ("show_progress",      "📊 Мой прогресс"),
                ("show_checkin",       "✅ Быстрый чек-ин"),
                ("show_shop",          "🛍 Магазин"),
                ("show_stop",          "🛑 Стоп"),
                ("show_settings",      "⚙️ Настройки"),
            ]
        )
        await db.commit()
        return True


async def migrate_003_add_voice_fields():
    """Миграция: добавить поля для голосовых триггеров."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверить существование колонок
        async with db.execute("PRAGMA table_info(triggers)") as cur:
            columns = [row[1] for row in await cur.fetchall()]
        
        # Добавить audio_file_id
        if 'audio_file_id' not in columns:
            await db.execute("ALTER TABLE triggers ADD COLUMN audio_file_id TEXT")
        
        # Добавить audio_duration
        if 'audio_duration' not in columns:
            await db.execute("ALTER TABLE triggers ADD COLUMN audio_duration INTEGER")
        
        # Добавить transcription_status
        if 'transcription_status' not in columns:
            await db.execute("ALTER TABLE triggers ADD COLUMN transcription_status TEXT DEFAULT 'text'")
        
        await db.commit()
        return True


# Список всех миграций в порядке применения
MIGRATIONS = [
    ("001_add_points_config", migrate_001_add_points_config),
    ("002_add_menu_settings", migrate_002_add_menu_settings),
    ("003_add_voice_fields", migrate_003_add_voice_fields),
]


async def run_migrations():
    """Запустить все невыполненные миграции."""
    await create_migrations_table()

    applied = await get_applied_migrations()
    pending = [name for name, _ in MIGRATIONS if name not in applied]

    if not pending:
        print("✓ Все миграции уже применены")
        return

    print(f"📦 Найдено {len(pending)} новых миграций")

    # Создать резервную копию перед миграциями
    backup_path = await backup_database()
    if backup_path:
        print(f"💾 Резервная копия: {backup_path}")

    # Применить миграции
    for name, migration_func in MIGRATIONS:
        if name in applied:
            continue

        print(f"⬆️  Применяю миграцию: {name}")
        try:
            await migration_func()
            await mark_migration_applied(name)
            print(f"✓ Миграция {name} применена успешно")
        except Exception as e:
            print(f"❌ Ошибка при применении миграции {name}: {e}")
            raise

    print("🎉 Все миграции применены успешно")
