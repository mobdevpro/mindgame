#!/bin/bash
# Скрипт для настройки тестовых сервисов на сервере
# Запусти его по SSH: ssh root@83.136.232.166 "bash -s" < setup-test-services.sh

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Настройка тестовых сервисов MindGame             ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

cd /opt/mindgame

# Тестовый бот
echo "📝 Создание сервиса тестового бота..."
cat > /etc/systemd/system/mindgame-test-bot.service << 'SERVICEEOF'
[Unit]
Description=MindGame Test Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mindgame
Environment="ENVIRONMENT=test"
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Тестовая админка
echo "📝 Создание сервиса тестовой админки..."
cat > /etc/systemd/system/mindgame-test-admin.service << 'SERVICEEOF'
[Unit]
Description=MindGame Test Admin Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mindgame
Environment="ENVIRONMENT=test"
ExecStart=/usr/bin/python3 admin.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Перезагрузка systemd
echo "🔄 Перезагрузка systemd..."
systemctl daemon-reload

# Включение сервисов
echo "✅ Включение сервисов..."
systemctl enable mindgame-test-bot mindgame-test-admin

# Запуск сервисов
echo "🚀 Запуск сервисов..."
systemctl start mindgame-test-bot mindgame-test-admin

# Проверка статуса
echo ""
echo "📊 Статус сервисов:"
systemctl status mindgame-test-bot mindgame-test-admin --no-pager

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                  ✅ Готово!                               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "🧪 Тестовый бот: https://t.me/MindGameTestBot"
echo "🧪 Тестовая админка: http://83.136.232.166:8081/admin"
echo "   Логин: admin"
echo "   Пароль: admin123"
echo ""
echo "⚔️  Боевой бот: https://t.me/Vadimbagautdinov_bot"
echo "⚔️  Боевая админка: http://83.136.232.166:8080/admin"
echo "   Логин: admin"
echo "   Пароль: mindgame2024"
echo ""
