#!/bin/bash
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         🧪 Обновление тестовой зоны                       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

sshpass -p 'pd3nQEGfKyULQ7o' ssh root@83.136.232.166 "
cd /opt/mindgame

echo '📥 Загрузка кода из GitHub...'
git pull

echo ''
echo '🔄 Перезапуск тестовых сервисов...'
systemctl restart mindgame-test-bot mindgame-test-admin

echo ''
echo '📊 Статус:'
systemctl status mindgame-test-bot mindgame-test-admin --no-pager

echo ''
echo '✅ Готово!'
echo ''
echo '🧪 Тестовый бот: @MindGameTest2Bot'
echo '🧪 Тестовая админка: https://test-admin.vadbag.su/admin'
echo '🎮 Mini App: https://test-admin.vadbag.su/app'
"
