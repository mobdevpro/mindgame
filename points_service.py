from config import POINTS, get_level, get_next_level_threshold
import database as db


async def award_subscription(telegram_id: int) -> int:
    user = await db.get_user(telegram_id)
    if not user:
        return 0
    balance = await db.award_points(
        telegram_id, POINTS["subscription"],
        "subscription", "Подписка на канал – стартовый бонус"
    )
    return balance or 0


async def award_trigger(telegram_id: int, trigger_id: int,
                        has_emotion: bool, has_intensity: bool,
                        has_insight: bool, has_zone: bool,
                        is_first_today: bool, is_first_ever: bool,
                        is_voice: bool = False) -> dict:
    total = POINTS["trigger_base"]
    breakdown = [f"📝 Запись триггера: +{POINTS['trigger_base']}"]
    
    # Бонус за голосовой триггер
    if is_voice:
        total += 5  # +5 очков за голосовой
        breakdown.append(f"🎤 Голосовой триггер: +5")

    if is_first_ever:
        total += POINTS["first_trigger"]
        breakdown.append(f"🌱 Первый триггер: +{POINTS['first_trigger']}")
    if is_first_today:
        total += POINTS["first_daily_trigger"]
        breakdown.append(f"☀️ Первая запись дня: +{POINTS['first_daily_trigger']}")
    if has_emotion:
        total += POINTS["trigger_emotion"]
        breakdown.append(f"💭 Эмоция: +{POINTS['trigger_emotion']}")
    if has_intensity:
        total += POINTS["trigger_intensity"]
        breakdown.append(f"⚡ Интенсивность: +{POINTS['trigger_intensity']}")
    if has_insight:
        total += POINTS["trigger_insight"]
        breakdown.append(f"💡 Вывод: +{POINTS['trigger_insight']}")
    if has_zone:
        total += POINTS["trigger_zone"]
        breakdown.append(f"🎯 Зона влияния: +{POINTS['trigger_zone']}")

    balance = await db.award_points(
        telegram_id, total, "trigger",
        f"Триггер #{trigger_id}",
        source_type="trigger", source_id=trigger_id
    )

    await db.update_trigger(trigger_id, points_awarded=total)

    return {"total": total, "balance": balance or 0, "breakdown": breakdown}


async def award_diary(telegram_id: int, entry_id: int, is_full: bool) -> dict:
    points = POINTS["diary_full"] if is_full else POINTS["diary_short"]
    balance = await db.award_points(
        telegram_id, points, "diary",
        "Запись в дневник осознанности",
        source_type="diary", source_id=entry_id
    )
    return {"total": points, "balance": balance or 0}


async def check_and_award_achievements(telegram_id: int) -> list[str]:
    user = await db.get_user(telegram_id)
    if not user:
        return []

    awarded = []
    existing = await db.get_user_achievements(user["id"])

    trigger_count = await db.count_triggers_total(user["id"])

    checks = [
        ("first_trigger", trigger_count >= 1),
        ("trigger_10", trigger_count >= 10),
        ("trigger_50", trigger_count >= 50),
        ("streak_7", user.get("streak_days", 0) >= 7),
        ("streak_30", user.get("streak_days", 0) >= 30),
    ]

    for code, condition in checks:
        if condition and code not in existing:
            success = await db.award_achievement(user["id"], code)
            if success:
                awarded.append(code)

    return awarded


def format_progress(user: dict) -> str:
    points = user.get("points_balance", 0)
    xp = user.get("xp_balance", 0)
    streak = user.get("streak_days", 0)
    level_num, level_name = get_level(xp)
    next_threshold = get_next_level_threshold(xp)

    progress_bar = ""
    if next_threshold:
        prev_thresholds = [0, 100, 300, 700, 1500]
        prev = prev_thresholds[level_num - 1]
        progress = (xp - prev) / (next_threshold - prev)
        filled = int(progress * 10)
        progress_bar = f"\n{'█' * filled}{'░' * (10 - filled)} {int(progress * 100)}%"
        progress_bar += f"\nДо уровня {level_num + 1}: {next_threshold - xp} XP"

    text = (
        f"🏆 <b>Твой прогресс</b>\n\n"
        f"📛 Уровень {level_num}: {level_name}\n"
        f"⚡ XP: {xp}{progress_bar}\n\n"
        f"💰 Баллы: {points}\n"
        f"🔥 Серия дней: {streak}\n"
    )
    return text
