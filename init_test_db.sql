-- Создаём таблицу menu_settings
CREATE TABLE IF NOT EXISTS menu_settings (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 1,
    label TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Добавляем все настройки меню включая show_patterns
INSERT OR REPLACE INTO menu_settings (key, value, label) VALUES 
    ('show_diary', 1, '📔 Дневник'),
    ('show_triggers_list', 1, '📋 Мои триггеры'),
    ('show_tasks', 1, '✅ Мои задачи'),
    ('show_progress', 1, '📊 Мой прогресс'),
    ('show_checkin', 1, '✅ Быстрый чек-ин'),
    ('show_patterns', 1, '🧩 Найти паттерны'),
    ('show_shop', 1, '🛍 Магазин'),
    ('show_stop', 1, '🛑 Стоп'),
    ('show_settings', 1, '⚙️ Настройки');

-- Таблицы для паттернов
CREATE TABLE IF NOT EXISTS pattern_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    analysis_date TEXT DEFAULT (datetime('now')),
    pattern_chain_json TEXT NOT NULL,
    core_belief TEXT,
    confidence REAL,
    recommendation TEXT,
    is_processed INTEGER DEFAULT 0,
    processed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS trigger_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    cluster_theme TEXT NOT NULL,
    cluster_level INTEGER DEFAULT 1,
    trigger_ids TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
