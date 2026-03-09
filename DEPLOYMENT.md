# 🚀 Безопасный деплой MindGame Bot

## ⚠️ Важно: Как не потерять данные

### Система миграций базы данных

Все изменения схемы БД происходят через **миграции** (`migrations.py`), которые:

✅ **Безопасны** — никогда не удаляют данные
✅ **Идемпотентны** — можно запускать несколько раз
✅ **Отслеживаются** — ведут историю примененных изменений
✅ **Автоматические** — запускаются при старте бота

---

## 📋 Процесс развертывания на сервер

### 1. На локальной машине (Mac)

```bash
cd /Users/vadimbagautdinov/Bot

# Убедись что БД НЕ удалена!
ls -lh game.db

# Проверь код
python3 -c "import ast; ast.parse(open('database.py').read())"
```

### 2. Загрузка на сервер

```bash
export SSHPASS='pd3nQEGfKyULQ7o'

# Загрузи ВСЕ файлы КРОМЕ game.db
sshpass -e rsync -avz --progress \
  --exclude='game.db' \
  --exclude='__pycache__' \
  -e "ssh -o StrictHostKeyChecking=no" \
  /Users/vadimbagautdinov/Bot/ \
  root@83.136.232.166:/opt/mindgame/
```

### 3. Перезапуск сервисов (миграции запустятся автоматически)

```bash
export SSHPASS='pd3nQEGfKyULQ7o'

sshpass -e ssh -o StrictHostKeyChecking=no root@83.136.232.166 "
cd /opt/mindgame

# Перезапустить сервисы
systemctl restart mindgame-bot mindgame-admin

# Проверить логи
journalctl -u mindgame-bot -n 10 --no-pager | grep -E 'migration|database'
"
```

---

## 📝 Как добавить новую миграцию

### 1. Добавить функцию в `migrations.py`

```python
async def migrate_002_add_new_table():
    """Описание: что делает эта миграция"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверить, существует ли таблица
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='new_table'"
        ) as cur:
            if await cur.fetchone():
                return True  # Уже существует

        # Создать таблицу
        await db.execute("""
            CREATE TABLE new_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL
            )
        """)
        await db.commit()
        return True
```

### 2. Добавить в список MIGRATIONS

```python
MIGRATIONS = [
    ("001_add_points_config", migrate_001_add_points_config),
    ("002_add_new_table", migrate_002_add_new_table),  # ← новая миграция
]
```

### 3. Протестировать локально

```bash
# Удали локальную БД
rm game.db

# Запусти бота — миграции применятся автоматически
python3 -c "
import asyncio
from database import init_db
asyncio.run(init_db())
"

# Проверь таблицы
sqlite3 game.db '.tables'
sqlite3 game.db '.schema new_table'
```

---

## 🔄 Резервные копии

### Автоматические бэкапы

При каждой миграции создается резервная копия:
```
game.db.backup_20260307_212345
```

### Восстановление из бэкапа

```bash
export SSHPASS='pd3nQEGfKyULQ7o'

sshpass -e ssh -o StrictHostKeyChecking=no root@83.136.232.166 "
cd /opt/mindgame

# Остановить сервис
systemctl stop mindgame-bot mindgame-admin

# Восстановить из бэкапа (если что-то пошло не так)
cp game.db.backup_20260307_212345 game.db

# Запустить снова
systemctl start mindgame-bot mindgame-admin
"
```

---

## ❌ Что НЕ делать

❌ **НЕ удаляй `game.db` на сервере вручную**
❌ **НЕ переписывай старые файлы без проверки**
❌ **НЕ запускай `CREATE TABLE` без проверки существования**

---

## ✅ Проверочный список перед деплоем

- [ ] Локальная БД не удалена
- [ ] Все файлы содержат правильный код
- [ ] Миграция добавлена в `MIGRATIONS` список
- [ ] Новая миграция протестирована локально
- [ ] Использовано `--exclude='game.db'` при rsync
- [ ] Сервисы перезапущены после загрузки
- [ ] Логи проверены на ошибки

---

## 📊 Проверка статуса БД

```bash
export SSHPASS='pd3nQEGfKyULQ7o'

sshpass -e ssh -o StrictHostKeyChecking=no root@83.136.232.166 "
cd /opt/mindgame

echo 'Примененные миграции:'
sqlite3 game.db 'SELECT migration_name, applied_at FROM schema_migrations'

echo ''
echo 'Статистика:'
sqlite3 game.db 'SELECT name FROM sqlite_master WHERE type=\"table\" ORDER BY name'
"
```

---

## 🆘 Помощь

Если что-то пошло не так:

1. Проверь логи: `journalctl -u mindgame-bot -n 30`
2. Восстанови из бэкапа
3. Проверь, что миграция идемпотентна (проверяет существование таблицы)
4. Убедись, что новая миграция создает индексы, не переписывает данные
