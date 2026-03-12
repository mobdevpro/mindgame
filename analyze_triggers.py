#!/usr/bin/env python3
"""
Скрипт для анализа старых триггеров и назначения категорий через AI.
Запуск: python3 analyze_triggers.py --test (тестовая БД) или --prod (боевая БД)
"""

import asyncio
import aiosqlite
import argparse
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_service import analyze_trigger
from config import DB_PATH


async def analyze_old_triggers(test_mode: bool = True):
    """Анализирует старые триггеры и назначает категории."""
    
    db_path = "test.db" if test_mode else DB_PATH
    db_name = "ТЕСТОВАЯ" if test_mode else "БОЕВАЯ"
    
    print(f"╔═══════════════════════════════════════════════════════════╗")
    print(f"║         🤖 Анализ триггеров — {db_name} ЗОНА                  ║")
    print(f"╚═══════════════════════════════════════════════════════════╝")
    print(f"")
    print(f"📊 База данных: {db_path}")
    print(f"")
    
    async with aiosqlite.connect(db_path) as db:
        # Находим триггеры без категории или с other
        async with db.execute("""
            SELECT id, raw_text, emotion_code, category_code 
            FROM triggers 
            WHERE category_code IS NULL OR category_code = 'other'
            ORDER BY created_at ASC
            LIMIT 50
        """) as cursor:
            triggers = await cursor.fetchall()
        
        if not triggers:
            print("✅ Все триггеры уже имеют категории!")
            return
        
        print(f"📝 Найдено триггеров для анализа: {len(triggers)}")
        print(f"")
        
        # Анализируем каждый триггер
        updated = 0
        failed = 0
        
        for i, (trigger_id, raw_text, emotion_code, category_code) in enumerate(triggers, 1):
            print(f"[{i}/{len(triggers)}] Триггер #{trigger_id}...")
            print(f"    Текст: {raw_text[:60]}...")
            
            try:
                # AI анализ
                result = await analyze_trigger(raw_text)
                new_category = result.get("category", "other")
                
                if new_category and new_category != "other":
                    # Обновляем категорию
                    await db.execute(
                        "UPDATE triggers SET category_code = ? WHERE id = ?",
                        (new_category, trigger_id)
                    )
                    await db.commit()
                    print(f"    ✅ Категория: {category_code} → {new_category}")
                    updated += 1
                else:
                    print(f"    ⚠️ AI не определил категорию (other)")
                    failed += 1
                    
            except Exception as e:
                print(f"    ❌ Ошибка: {str(e)[:50]}")
                failed += 1
            
            # Небольшая пауза чтобы не спамить API
            await asyncio.sleep(0.5)
        
        print(f"")
        print(f"╔═══════════════════════════════════════════════════════════╗")
        print(f"║                    РЕЗУЛЬТАТЫ                             ║")
        print(f"╚═══════════════════════════════════════════════════════════╝")
        print(f"")
        print(f"📊 Всего триггеров: {len(triggers)}")
        print(f"✅ Обновлено: {updated}")
        print(f"❌ Не удалось: {failed}")
        print(f"")
        
        # Показываем статистику по категориям
        async with db.execute("""
            SELECT category_code, COUNT(*) as cnt 
            FROM triggers 
            WHERE category_code IS NOT NULL 
            GROUP BY category_code 
            ORDER BY cnt DESC
        """) as cursor:
            stats = await cursor.fetchall()
        
        print(f"📈 Категории после анализа:")
        for cat, cnt in stats:
            print(f"   {cat}: {cnt}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Анализ старых триггеров")
    parser.add_argument("--test", action="store_true", help="Тестовая база (test.db)")
    parser.add_argument("--prod", action="store_true", help="Боевая база (game.db)")
    args = parser.parse_args()
    
    if args.prod:
        print("⚠️  ВНИМАНИЕ: Запуск на БОЕВОЙ базе!")
        confirm = input("Продолжить? (yes/no): ")
        if confirm != "yes":
            print("Отменено.")
            sys.exit(0)
    
    test_mode = not args.prod  # По умолчанию тестовая
    
    asyncio.run(analyze_old_triggers(test_mode))
