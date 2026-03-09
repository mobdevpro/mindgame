#!/bin/bash
export ENVIRONMENT="production"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         ⚔️  Запуск админки — PRODUCTION                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo "  📊 База данных: game.db"
echo "  🌐 Порт: 8080"
echo "  🔗 URL:  http://localhost:8080/admin"
echo ""
python3 admin.py
