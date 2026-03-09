#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# MindGame Bot — Деплой (TEST → PRODUCTION)
# ═══════════════════════════════════════════════════════════════

set -e

# Настройки
SERVER_USER="root"
SERVER_HOST="83.136.232.166"
SERVER_PATH="/opt/mindgame"
LOCAL_BACKUP_DIR="./backups"
MESSAGE="${1:-Deploy}"
BACKUP_RETAIN_DAYS=30

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         🚀 MindGame Bot — Деплой на сервер               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# ═══════════════════════════════════════════════════════════════
# ЭТАП 1: Коммит и отправка на GitHub
# ═══════════════════════════════════════════════════════════════

echo -e "${YELLOW}[1/9] Проверка Git статуса...${NC}"
git status --short

echo -e "${YELLOW}[2/9] Коммит и отправка на GitHub...${NC}"
git add .
git commit -m "$MESSAGE

Co-authored-by: Qwen-Coder <qwen-coder@alibabacloud.com>"
git push
echo -e "${GREEN}✅ Отправлено на GitHub${NC}"

# ═══════════════════════════════════════════════════════════════
# ЭТАП 2: ТЕСТОВАЯ ЗОНА
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${PURPLE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${PURPLE}║           🧪 ЭТАП 1: ТЕСТОВАЯ ЗОНА                        ║${NC}"
echo -e "${PURPLE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}[3/9] Деплой на TEST окружение...${NC}"

ssh ${SERVER_USER}@${SERVER_HOST} "
cd ${SERVER_PATH}

echo ''
echo '🧪 ТЕСТОВАЯ ЗОНА — загрузка кода...'
export ENVIRONMENT=test
git pull

echo ''
echo '📦 Установка зависимостей...'
pip install -r requirements.txt

echo ''
echo '🔄 Перезапуск тестовых сервисов...'
systemctl restart mindgame-test-bot mindgame-test-admin

echo ''
echo '✅ Статус тестовых сервисов:'
systemctl is-active mindgame-test-bot mindgame-test-admin || echo '⚠️ Сервисы не активны'

echo ''
echo '📊 Статистика тестовой БД:'
sqlite3 test.db 'SELECT \"Пользователей: \" || COUNT(*) FROM users' 2>/dev/null || echo 'Тестовая БД пуста'
sqlite3 test.db 'SELECT \"Триггеров: \" || COUNT(*) FROM triggers' 2>/dev/null || echo ''
"

echo -e "${GREEN}✅ Тестовая зона обновлена${NC}"
echo ""
echo -e "${YELLOW}⏸️  ПАУЗА: Проверь тестового бота перед продолжением${NC}"
echo -e "${BLUE}   Тестовый бот: https://t.me/MindGameTestBot${NC}"
echo -e "${BLUE}   Тестовая админка: http://${SERVER_HOST}:8081/admin${NC}"
echo ""
read -p "✅ Продолжить деплой на PRODUCTION? (нажми Enter когда готов) "

# ═══════════════════════════════════════════════════════════════
# ЭТАП 3: БОЕВАЯ ЗОНА
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${PURPLE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${PURPLE}║           ⚔️ ЭТАП 2: БОЕВАЯ ЗОНА                          ║${NC}"
echo -e "${PURPLE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}[4/9] Бэкап БД на сервере...${NC}"

BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REMOTE_BACKUP_FILE="${SERVER_PATH}/game.db.backup_${BACKUP_TIMESTAMP}"
LOCAL_BACKUP_FILE="${LOCAL_BACKUP_DIR}/game.db.backup_${BACKUP_TIMESTAMP}"

mkdir -p "${LOCAL_BACKUP_DIR}"

ssh ${SERVER_USER}@${SERVER_HOST} "
cd ${SERVER_PATH}

echo '💾 Создание бэкапа на сервере...'
cp game.db '${REMOTE_BACKUP_FILE}'
echo \"✅ Бэкап создан: ${REMOTE_BACKUP_FILE}\"

gzip -c game.db > game.db.backup_${BACKUP_TIMESTAMP}.sql.gz
echo '📦 Бэкап сжат для загрузки'
"

echo -e "${BLUE}[5/9] Загрузка бэкапа на локальный Mac...${NC}"
scp ${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/game.db.backup_${BACKUP_TIMESTAMP}.sql.gz ${LOCAL_BACKUP_FILE}.sql.gz 2>/dev/null && echo -e "${GREEN}✅ Бэкап загружен локально${NC}" || echo -e "${RED}⚠️ Не удалось загрузить бэкап${NC}"

find "${LOCAL_BACKUP_DIR}" -name 'game.db.backup_*' -mtime +${BACKUP_RETAIN_DAYS} -delete 2>/dev/null
LOCAL_COUNT=$(ls -1 "${LOCAL_BACKUP_DIR}"/game.db.backup_* 2>/dev/null | wc -l)
echo "📁 Локальных бэкапов: ${LOCAL_COUNT}"

echo -e "${BLUE}[6/9] Очистка старых бэкапов на сервере...${NC}"
ssh ${SERVER_USER}@${SERVER_HOST} "
cd ${SERVER_PATH}
find . -name 'game.db.backup_*' -mtime +${BACKUP_RETAIN_DAYS} -delete
find . -name 'game.db.backup_*.sql.gz' -mtime +${BACKUP_RETAIN_DAYS} -delete
SERVER_COUNT=\$(ls -1 game.db.backup_* 2>/dev/null | wc -l)
echo \"📁 Бэкапов на сервере: \${SERVER_COUNT}\"
"

echo -e "${YELLOW}[7/9] Деплой кода на PRODUCTION...${NC}"
ssh ${SERVER_USER}@${SERVER_HOST} "
cd ${SERVER_PATH}

echo ''
echo '⚔️ БОЕВАЯ ЗОНА — загрузка кода...'
export ENVIRONMENT=production
git pull

echo ''
echo '📦 Установка зависимостей...'
pip install -r requirements.txt

echo ''
echo '🔄 Перезапуск боевых сервисов...'
systemctl restart mindgame-bot mindgame-admin

echo ''
echo '✅ Статус боевых сервисов:'
systemctl is-active mindgame-bot mindgame-admin
"

echo -e "${YELLOW}[8/9] Проверка целостности БД...${NC}"
ssh ${SERVER_USER}@${SERVER_HOST} "
sqlite3 ${SERVER_PATH}/game.db 'PRAGMA integrity_check' | grep -q 'ok' && echo '✅ БД цела' || echo '❌ Ошибка БД!'
"

echo -e "${YELLOW}[9/9] Проверка логов...${NC}"
ssh ${SERVER_USER}@${SERVER_HOST} "
journalctl -u mindgame-bot -n 10 --no-pager | grep -i error || echo 'Ошибок не найдено ✅'
"

# ═══════════════════════════════════════════════════════════════
# ИТОГ
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✅ Деплой завершён успешно!                 ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "📍 Сервер: ${SERVER_HOST}"
echo "📂 Путь: ${SERVER_PATH}"
echo ""
echo "🤖 Боты:"
echo "   ⚔️ PRODUCTION: https://t.me/Vadimbagautdinov_bot"
echo "   🧪 TEST:       https://t.me/MindGameTestBot"
echo ""
echo "🎛 Админки:"
echo "   ⚔️ PRODUCTION: http://${SERVER_HOST}:8080/admin"
echo "   🧪 TEST:       http://${SERVER_HOST}:8081/admin"
echo ""
echo "📝 Полезные команды:"
echo "   • Логи бота:      ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u mindgame-bot -f'"
echo "   • Логи тест-бота: ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u mindgame-test-bot -f'"
echo ""
