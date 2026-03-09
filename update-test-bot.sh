#!/bin/bash
# Обновление тестового бота на сервере

echo "📝 Обновление тестового токена на сервере..."

ssh root@83.136.232.166 "
cd /opt/mindgame

# Обновить .env с новым токеном
echo '🔧 Обновление токена...'
sed -i 's/TEST_BOT_TOKEN=.*/TEST_BOT_TOKEN=8602349722:AAEcLUFo5tlTBmu2IYkmQ_H9MSJZ8YSzoOo/' .env

# Проверить
echo '✅ Токен:'
grep TEST_BOT_TOKEN .env

# Обновить код из GitHub
echo ''
echo '📥 Загрузка кода из GitHub...'
git pull

# Перезапустить тестовые сервисы
echo ''
echo '🔄 Перезапуск тестовых сервисов...'
systemctl restart mindgame-test-bot mindgame-test-admin

# Проверить статус
echo ''
echo '📊 Статус:'
systemctl status mindgame-test-bot mindgame-test-admin --no-pager

# Логи
echo ''
echo '📝 Логи:'
journalctl -u mindgame-test-bot -n 10 --no-pager
"

echo ""
echo "✅ Готово!"
echo ""
echo "🧪 Тестовый бот: https://t.me/MindGameTest2Bot"
echo "🧪 Тестовая админка: http://83.136.232.166:8081/admin"
