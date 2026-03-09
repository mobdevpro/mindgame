#!/bin/bash
export ENVIRONMENT="test"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         🧪 Запуск админки — TEST                          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo "  📊 База данных: test.db"
echo "  🌐 Порт: 8081"
echo "  🔗 URL:  http://localhost:8081/admin"
echo ""
python3 admin.py
