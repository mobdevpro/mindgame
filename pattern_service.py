"""
Pattern Service — бизнес-логика анализа паттернов триггеров.
"""
import json
from datetime import datetime, timedelta
from ai_service import analyze_patterns
import database as db
from config import TRGR


# ═══════════════════════════════════════════════════════════════
# КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════

MIN_TRIGGERS_FOR_ANALYSIS = 5  # Минимум триггеров для анализа
MAX_TRIGGERS_FOR_ANALYSIS = 50  # Максимум триггеров для анализа
PATTERN_COOLDOWN_DAYS = 7  # Лимит: 1 анализ в 7 дней


# ═══════════════════════════════════════════════════════════════
# ОСНОВНАЯ ЛОГИКА
# ═══════════════════════════════════════════════════════════════

async def can_analyze_patterns(user_id: int) -> tuple[bool, str]:
    """
    Проверить можно ли запустить анализ паттернов.
    
    Returns:
        (можно_ли, причина)
    """
    # Проверяем количество триггеров
    trigger_count = await db.count_user_triggers(user_id)
    if trigger_count < MIN_TRIGGERS_FOR_ANALYSIS:
        return False, f"Нужно минимум {MIN_TRIGGERS_FOR_ANALYSIS} триггеров. У вас: {trigger_count}"
    
    # Проверяем cooldown
    last_analysis = await db.get_last_pattern_analysis(user_id)
    if last_analysis:
        analysis_date = datetime.fromisoformat(last_analysis["analysis_date"].replace(" ", "T"))
        if datetime.now() - analysis_date < timedelta(days=PATTERN_COOLDOWN_DAYS):
            days_left = PATTERN_COOLDOWN_DAYS - (datetime.now() - analysis_date).days
            return False, f"Анализ уже был {days_left} д. назад. Следующий через {days_left} д."
    
    return True, "OK"


async def run_pattern_analysis(user_id: int) -> dict:
    """
    Запустить AI-анализ паттернов пользователя.
    
    Returns:
        dict с результатом анализа
    """
    # Проверяем возможность анализа
    can_run, reason = await can_analyze_patterns(user_id)
    if not can_run:
        return {"ok": False, "error": reason}
    
    # Получаем триггеры
    triggers = await db.get_triggers_for_pattern_analysis(
        user_id, 
        limit=MAX_TRIGGERS_FOR_ANALYSIS
    )
    
    if len(triggers) < MIN_TRIGGERS_FOR_ANALYSIS:
        return {"ok": False, "error": "Недостаточно триггеров для анализа"}
    
    # Считаем статистику
    stats = await _calculate_trigger_stats(triggers, user_id)
    
    # Запускаем AI анализ
    analysis_result = await analyze_patterns(triggers, stats)
    
    # Сохраняем результат в БД
    try:
        analysis_id = await db.save_pattern_analysis(
            user_id=user_id,
            pattern_chain_json=json.dumps(analysis_result.get("pattern_chain", []), ensure_ascii=False),
            core_belief=analysis_result.get("core_belief", ""),
            confidence=analysis_result.get("confidence", 0),
            recommendation=analysis_result.get("recommendation", "")
        )
        
        # Создаём кластеры триггеров
        for pattern in analysis_result.get("pattern_chain", []):
            await db.create_trigger_cluster(
                user_id=user_id,
                cluster_theme=pattern.get("theme", ""),
                cluster_level=pattern.get("level", 1),
                trigger_ids=pattern.get("trigger_ids", [])
            )
        
        return {
            "ok": True,
            "analysis_id": analysis_id,
            "result": analysis_result,
            "stats": stats
        }
        
    except Exception as e:
        import logging
        logging.error(f"Error saving pattern analysis: {e}")
        return {"ok": False, "error": "Ошибка при сохранении результата"}


async def _calculate_trigger_stats(triggers: list[dict], user_id: int) -> dict:
    """Посчитать статистику по триггерам."""
    # Считаем эмоции
    emotion_counts = {}
    category_counts = {}
    
    for t in triggers:
        emotion = t.get("emotion_code", "unknown")
        category = t.get("category_code", "unknown")
        
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
    
    # Находим топ
    top_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "unknown"
    top_category = max(category_counts, key=category_counts.get) if category_counts else "unknown"
    
    # Считаем дни активности
    if triggers:
        first_trigger = min(t["created_at"] for t in triggers)
        last_trigger = max(t["created_at"] for t in triggers)
        
        try:
            first_date = datetime.fromisoformat(first_trigger.replace(" ", "T"))
            last_date = datetime.fromisoformat(last_trigger.replace(" ", "T"))
            days_active = (last_date - first_date).days + 1
        except:
            days_active = 1
    else:
        days_active = 1
    
    return {
        "total": len(triggers),
        "days": days_active,
        "top_emotion": top_emotion,
        "top_category": top_category,
        "emotion_counts": emotion_counts,
        "category_counts": category_counts
    }


async def mark_pattern_processed(analysis_id: int, telegram_id: int) -> dict:
    """
    Отметить паттерн как проработанный и наградить TRGR.

    Returns:
        dict с результатом
    """
    # Отмечаем как проработанный
    await db.mark_pattern_processed(analysis_id)

    # Награждаем TRGR
    balance = await db.award_points(
        telegram_id=telegram_id,
        points=TRGR.get("pattern_processed", 10),
        event_type="pattern_processed",
        description="Проработка AI-паттерна",
        source_type="pattern_analysis",
        source_id=analysis_id
    )

    return {
        "ok": True,
        "points": TRGR.get("pattern_processed", 10),
        "balance": balance or 0
    }


async def get_pattern_result(user_id: int) -> dict | None:
    """
    Получить последний результат анализа паттернов.
    
    Returns:
        dict с результатом или None
    """
    last_analysis = await db.get_last_pattern_analysis(user_id)
    
    if not last_analysis:
        return None
    
    # Парсим JSON
    try:
        pattern_chain = json.loads(last_analysis["pattern_chain_json"])
    except:
        pattern_chain = []
    
    return {
        "analysis_id": last_analysis["id"],
        "analysis_date": last_analysis["analysis_date"],
        "pattern_chain": pattern_chain,
        "core_belief": last_analysis.get("core_belief", ""),
        "confidence": last_analysis.get("confidence", 0),
        "recommendation": last_analysis.get("recommendation", ""),
        "is_processed": bool(last_analysis.get("is_processed", 0))
    }


def format_pattern_message(result: dict) -> str:
    """
    Сформировать красивое сообщение с результатом анализа.
    
    Args:
        result: dict из get_pattern_result()
    
    Returns:
        str с форматированным сообщением
    """
    pattern_chain = result.get("pattern_chain", [])
    core_belief = result.get("core_belief", "")
    recommendation = result.get("recommendation", "")
    
    # Заголовок
    text = "🧩 <b>AI-анализ паттернов</b>\n\n"
    text += "🔗 <b>Цепочка связей:</b>\n\n"
    
    # Выводим каждый уровень
    for pattern in pattern_chain:
        level = pattern.get("level", 1)
        theme = pattern.get("theme", "???")
        count = pattern.get("trigger_count", 0)
        examples = pattern.get("examples", [])
        
        # Иконка для уровня
        level_icons = {1: "📍", 2: "🔍", 3: "💎", 4: "🌊"}
        icon = level_icons.get(level, "•")
        
        text += f"{icon} <b>Уровень {level}:</b> {theme} ({count} триггеров)\n"
        
        # Примеры
        for ex in examples[:2]:  # Максимум 2 примера
            short_ex = ex[:80] + "..." if len(ex) > 80 else ex
            text += f"   • «{short_ex}»\n"
        
        text += "\n"
    
    # Глубинное убеждение
    if core_belief:
        text += f"💎 <b>Глубинное убеждение:</b>\n"
        text += f"«{core_belief}»\n\n"
    
    # Рекомендация
    if recommendation:
        text += f"🎯 <b>Рекомендация AI:</b>\n"
        text += f"{recommendation}\n\n"
    
    # Статус
    if result.get("is_processed"):
        text += "✅ <i>Паттерн проработан</i>\n"
    
    return text
