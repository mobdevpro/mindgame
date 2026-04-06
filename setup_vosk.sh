#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Установка модели Vosk для распознавания голоса
# ═══════════════════════════════════════════════════════════════

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         🎤 Установка модели Vosk                          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

cd /opt/mindgame

# Проверяем что модель ещё не установлена
if [ -d "vosk-model-small-ru-0.22" ]; then
    echo "✅ Модель уже установлена"
    ls -la vosk-model-small-ru-0.22/
    exit 0
fi

echo "📥 Скачиваем модель (50MB)..."
wget -q https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip

echo "📦 Распаковываем..."
unzip -q vosk-model-small-ru-0.22.zip

echo "🗑 Удаляем архив..."
rm vosk-model-small-ru-0.22.zip

echo ""
echo "✅ Модель установлена!"
ls -la vosk-model-small-ru-0.22/

echo ""
echo "🔄 Перезапускаем бота..."
systemctl restart mindgame-bot
sleep 2

if systemctl is-active mindgame-bot > /dev/null 2>&1; then
    echo "✅ Бот перезапущен успешно"
else
    echo "❌ Ошибка при запуске бота"
    systemctl status mindgame-bot --no-pager
    exit 1
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         🎉 Готово! Голосовое распознавание работает       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "📱 Проверь:"
echo "   1. Отправь боту голосовое сообщение"
echo "   2. Бот должен распознать текст"
echo "   3. Создаст триггер автоматически"
echo ""
