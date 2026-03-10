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
    """Миграция: добавить поля для голосовых триггеров и задач."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверить существование колонок в triggers
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
        
        # Проверить существование колонок в tasks
        async with db.execute("PRAGMA table_info(tasks)") as cur:
            task_columns = [row[1] for row in await cur.fetchall()]
        
        # Добавить is_voice для задач
        if 'is_voice' not in task_columns:
            await db.execute("ALTER TABLE tasks ADD COLUMN is_voice INTEGER DEFAULT 0")

        await db.commit()
        return True


async def migrate_004_add_message_templates():
    """Миграция: добавить таблицу шаблонов сообщений."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(message_templates)") as cur:
            if await cur.fetchone():
                return True  # Таблица уже существует

        await db.execute("""
            CREATE TABLE message_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_key TEXT UNIQUE NOT NULL,
                template_name TEXT NOT NULL,
                message_text TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',  -- text, notification, reminder
                category TEXT DEFAULT 'general',  -- general, trigger, diary, task, stop, shop, onboarding
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Seed всех сообщений из бота
        await db.executemany("""
            INSERT OR IGNORE INTO message_templates 
            (template_key, template_name, message_text, message_type, category, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            # Onboarding
            ("onboarding_step1", "Онбординг: Шаг 1 - Добро пожаловать", 
             "🎮 <b>Добро пожаловать в игру осознанности!</b>\n\n"
             "Здесь твоя жизнь – это поле роста.\n"
             "Ты получаешь очки не за маски, а за честность с собой, "
             "осознанность и реальные действия.", 
             "text", "onboarding", 1),
            ("onboarding_step2", "Онбординг: Шаг 2 - Замечай", 
             "👁 <b>Шаг 1 – Замечай</b>\n\n"
             "Каждый раз, когда что-то тебя задело, раздражило или выбило "
             "из равновесия – это триггер.\n\n"
             "Зафиксируй его и получи очки. Ты уже не на автопилоте – "
             "ты наблюдаешь.", 
             "text", "onboarding", 2),
            ("onboarding_step3", "Онбординг: Шаг 3 - Очки", 
             "⚡ <b>Очки за осознанность</b>\n\n"
             "📝 Запись триггера – очки\n"
             "💭 Назвал эмоцию – ещё очки\n"
             "💡 Нашёл вывод – ещё больше очков\n"
             "📔 Дневник каждый день – бонусы\n"
             "🔥 Серия дней подряд – мультипликатор", 
             "text", "onboarding", 3),
            ("onboarding_step4", "Онбординг: Шаг 4 - Награды", 
             "🎯 <b>Реальные действия = реальные награды</b>\n\n"
             "Из каждого триггера рождается действие.\n"
             "Из каждого действия – рост.\n\n"
             "Твои баллы – это не просто цифры. Их можно тратить на "
             "продукты и материалы автора.", 
             "text", "onboarding", 4),
            ("subscription_request", "Запрос подписки", 
             "🔐 <b>Последний шаг</b>\n\n"
             "Подпишись на канал {channel} – там выходят материалы, "
             "связанные с практикой.\n\n"
             "После подписки получишь <b>50 стартовых баллов</b> 🎁", 
             "text", "onboarding", 5),
            ("subscription_success", "Успешная подписка", 
             "✅ <b>Подписка подтверждена!</b>\n\n"
             "🎁 Начислено 50 стартовых баллов\n"
             "💰 Твой баланс: {balance} баллов\n\n"
             "Игра началась! Зафиксируй свой первый триггер 👇", 
             "text", "onboarding", 6),
            ("welcome_back", "Возвращение пользователя", 
             "С возвращением, {name}! 👋\n\n"
             "Что фиксируем сегодня?", 
             "text", "general", 7),
            
            # Triggers
            ("trigger_ask", "Запрос триггера", 
             "📝 <b>Запиши триггер</b>\n\n"
             "Что тебя задело? Опиши ситуацию своими словами.\n\n"
             "<i>Пример: «Меня разозлило, что коллега перебил меня на встрече»</i>", 
             "text", "trigger", 10),
            ("trigger_too_short", "Триггер слишком короткий", 
             "Напиши чуть подробнее – хотя бы несколько слов 🙏", 
             "text", "trigger", 11),
            ("trigger_voice_recording", "Запись голосового триггера", 
             "🎤 Записываю голос...", 
             "text", "trigger", 12),
            ("trigger_voice_error", "Ошибка распознавания голоса", 
             "❌ Не удалось распознать:\n{error}\n\n"
             "Попробуй записать ещё раз или напиши текстом.", 
             "text", "trigger", 13),
            ("trigger_voice_too_short", "Голос слишком короткий", 
             "❌ Не удалось разобрать слова. "
             "Говори чётче или напиши текстом.", 
             "text", "trigger", 14),
            ("trigger_analyzed", "Триггер проанализирован", 
             "{voice_badge}✅ <b>Триггер зафиксирован.</b>\n\n"
             "Ты уже не внутри автопилота – ты наблюдаешь.\n\n"
             "<i>{ai_response}</i>\n\n"
             "🏷 Категория: {category}\n"
             "💭 Эмоция: {emotion}\n\n"
             "Выбери эмоцию точнее или подтверди:", 
             "text", "trigger", 15),
            ("trigger_points", "Начисление баллов за триггер", 
             "🎉 <b>+{total} очков!</b>\n\n"
             "{breakdown}\n\n"
             "💰 Баланс: {balance} баллов", 
             "text", "trigger", 16),
            ("trigger_ask_emotion", "Запрос эмоции", 
             "💭 Выбери эмоцию или пропусти:", 
             "text", "trigger", 17),
            ("trigger_ask_intensity", "Запрос интенсивности", 
             "⚡ Интенсивность: {intensity}/10\n\n"
             "<b>Следующий шаг:</b>\n{step_q}\n\n"
             "<i>(Напиши ответ или пропусти)</i>", 
             "text", "trigger", 18),
            ("trigger_ask_insight", "Запрос инсайта", 
             "💡 Что ты понял(а) из этой ситуации?\n\n"
             "Напиши кратко или пропусти:", 
             "text", "trigger", 19),
            ("trigger_ask_zone", "Запрос зоны контроля", 
             "🎯 Что было в твоей зоне контроля?\n\n"
             "Напиши или пропусти:", 
             "text", "trigger", 20),
            ("trigger_list_empty", "Список триггеров пуст", 
             "📋 <b>Мои триггеры</b>\n\n"
             "Пока нет записей.\n\n"
             "Запиши первый триггер – это начало пути!", 
             "text", "trigger", 21),
            
            # Diary
            ("diary_ask", "Запрос записи дневника", 
             "📔 <b>Дневник осознанности</b>\n\n"
             "Опиши свой день, мысли, инсайты.\n\n"
             "<i>Это пространство только для тебя</i>", 
             "text", "diary", 30),
            ("diary_too_short", "Дневник слишком короткий", 
             "Напиши чуть больше – хотя бы пару предложений 🙏", 
             "text", "diary", 31),
            ("diary_saved", "Дневник сохранён", 
             "✅ <b>Запись сохранена!</b>\n\n"
             "📝 Текст: {length} симв.\n"
             "💭 Настроение: {mood}\n"
             "⚡ Энергия: {energy}/10\n\n"
             "🎉 +{points} баллов\n"
             "💰 Баланс: {balance}", 
             "text", "diary", 32),
            ("diary_already_written", "Дневник уже написан сегодня", 
             "✅ Сегодня уже записано в дневник!\n\n"
             "Заходи завтра за новой порцией инсайтов 🌟", 
             "text", "diary", 33),
            
            # Tasks
            ("task_ask", "Запрос задачи", 
             "➕ <b>Новая задача</b>\n\n"
             "Опиши задачу — что конкретно нужно сделать?\n\n"
             "<i>Примеры хороших задач:\n"
             "• «Позвонить клиенту и договориться о встрече»\n"
             "• «Провести сложный разговор с коллегой»\n"
             "• «Записаться к врачу»\n"
             "• «Пойти на тренировку, хотя не хочется»</i>\n\n"
             "🎤 Можно отправить голосовым!", 
             "text", "task", 40),
            ("task_voice_recording", "Запись голосовой задачи", 
             "🎤 Записываю голос...", 
             "text", "task", 41),
            ("task_saved", "Задача сохранена", 
             "✅ <b>Задача добавлена!</b>\n\n"
             "📋 {task_text}\n"
             "{label} • После выполнения: <b>+{points} баллов</b>\n"
             "{voice_text}"
             "Когда сделаешь — отметь выполненной и получи очки! 🎯", 
             "text", "task", 42),
            ("task_list_empty", "Список задач пуст", 
             "✅ <b>Мои задачи</b>\n\n"
             "Задач пока нет.\n\n"
             "Задача — это реальное действие из жизни, которое ты хочешь сделать.\n"
             "За каждую выполненную задачу начисляются баллы! 🎯", 
             "text", "task", 43),
            ("task_completed", "Задача выполнена", 
             "🎉 <b>Задача выполнена!</b>\n\n"
             "📋 {task_title}\n"
             "🎁 +{points} баллов\n"
             "💰 Баланс: {balance}", 
             "text", "task", 44),
            
            # Stop Mode
            ("stop_ask_feeling", "Стоп-режим: запрос чувства", 
             "🛑 <b>Стоп-режим активирован</b>\n\n"
             "Что ты сейчас чувствуешь?\n\n"
             "Выбери или напиши:", 
             "text", "stop", 50),
            ("stop_ask_intensity", "Стоп-режим: запрос интенсивности", 
             "Насколько сильно это чувство?\n\n"
             "Выбери от 1 до 10:", 
             "text", "stop", 51),
            ("stop_completed", "Стоп-режим завершён", 
             "✅ <b>Ты справился(ась)!</b>\n\n"
             "Ты заметил(а) эмоцию и дал(а) ей место.\n"
             "Это и есть осознанность 🙏", 
             "text", "stop", 52),
            
            # Subscription
            ("subscription_required", "Требуется подписка", 
             "⚠️ <b>Ты отписался от канала!</b>\n\n"
             "Чтобы продолжить пользоваться ботом, подпишись на канал {channel}\n\n"
             "После подписки все функции станут доступны.", 
             "text", "general", 60),
            ("not_subscribed", "Не подписан", 
             "Похоже, ты ещё не подписался. Подпишись и нажми ещё раз! 👇", 
             "text", "general", 61),
            
            # Common
            ("start_bot_first", "Сначала запусти бота", 
             "Сначала запусти бота командой /start", 
             "text", "general", 70),
            ("main_menu", "Главное меню", 
             "🎮 <b>Главное меню</b>\n\nВыбери действие:", 
             "text", "general", 71),
            ("webapp_prompt", "Предложение открыть приложение", 
             "📱 Или открой полное приложение:", 
             "text", "general", 72),
        ])

        await db.commit()
        return True


# Список всех миграций в порядке применения
MIGRATIONS = [
    ("001_add_points_config", migrate_001_add_points_config),
    ("002_add_menu_settings", migrate_002_add_menu_settings),
    ("003_add_voice_fields", migrate_003_add_voice_fields),
    ("004_add_message_templates", migrate_004_add_message_templates),
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
