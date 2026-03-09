#!/bin/bash
# Проверка тестовой зоны

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Проверка тестовой зоны MindGame                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

ssh root@83.136.232.166 "
echo '📊 Статус сервисов:'
systemctl status mindgame-test-bot mindgame-test-admin --no-pager

echo ''
echo '📝 Логи тестового бота (последние 20 строк):'
journalctl -u mindgame-test-bot -n 20 --no-pager

echo ''
echo '📝 Логи тестовой админки (последние 20 строк):'
journalctl -u mindgame-test-admin -n 20 --no-pager

echo ''
echo '🗄 Файлы в /opt/mindgame:'
ls -la /opt/mindgame/

echo ''
echo '📊 Тестовая БД:'
sqlite3 /opt/mindgame/test.db '.tables' 2>/dev/null || echo 'БД нет или пуста'

echo ''
echo '🔍 Переменная ENVIRONMENT:'
echo \"ENVIRONMENT=test\" | cat
"
