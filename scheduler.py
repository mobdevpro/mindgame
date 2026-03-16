"""
Scheduler for push notifications.
Runs inside the bot process alongside polling.
"""
import asyncio
import logging
import random
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

import database as db

logger = logging.getLogger(__name__)

DIARY_REMINDERS = [
    "📔 Как прошёл твой день? Есть минута написать в дневник?",
    "📔 Один маленький инсайт в конце дня — и день прожит осознанно.",
    "📔 Что зацепило тебя сегодня? Запиши в дневник — это займёт 2 минуты.",
    "📔 Дневник ждёт. Что ты заметил(а) про себя сегодня?",
]

TRIGGER_REMINDERS = [
    "📝 Было ли что-то, что тебя задело сегодня? Зафикируй триггер — +5 TRGR.",
    "📝 Что тебя сегодня зацепило? Запись триггера занимает 30 секунд.",
    "📝 Напоминаю: каждый замеченный триггер — это шаг к осознанности. Запиши!",
]

CHECKIN_MESSAGES = [
    "✅ Эй! Что ты сейчас чувствуешь? Где твоё внимание?\n\n"
    "Ты сейчас в реакции или в выборе?",
    "✅ Быстрый чек-ин: что происходит в теле прямо сейчас?\n\n"
    "Открой бота и нажми «✅ Быстрый чек-ин».",
    "✅ Стоп-момент. Где ты сейчас — в голове или в теле?\n\n"
    "Сделай один осознанный вдох и напиши, что чувствуешь.",
    "✅ Антиавтопилот: ты сейчас на автомате или присутствуешь?\n\n"
    "Останови на секунду. Что происходит внутри?",
]

WEEKLY_REPORT_INTRO = [
    "📊 <b>Твоя неделя осознанности</b>",
    "🎮 <b>Итоги недели</b>",
    "📈 <b>Отчёт за неделю</b>",
]


async def send_message(bot: Bot, telegram_id: int, text: str) -> bool:
    try:
        await bot.send_message(telegram_id, text, parse_mode="HTML")
        return True
    except Exception as e:
        logger.warning(f"Failed to send to {telegram_id}: {e}")
        return False


async def job_diary_reminder(bot: Bot):
    """20:00 — remind users who haven't written diary today."""
    now = datetime.now()
    logger.info(f"[scheduler] diary reminder {now.strftime('%H:%M')}")
    users = await db.get_users_needing_diary_reminder()
    text = random.choice(DIARY_REMINDERS)
    for u in users:
        await send_message(bot, u["telegram_id"], text)
        await asyncio.sleep(0.05)
    logger.info(f"[scheduler] diary: sent to {len(users)} users")


async def job_trigger_reminder(bot: Bot):
    """13:00 — remind users who haven't logged a trigger today."""
    logger.info("[scheduler] trigger reminder")
    users = await db.get_users_needing_trigger_reminder()
    text = random.choice(TRIGGER_REMINDERS)
    for u in users:
        await send_message(bot, u["telegram_id"], text)
        await asyncio.sleep(0.05)
    logger.info(f"[scheduler] triggers: sent to {len(users)} users")


async def job_random_checkin(bot: Bot):
    """Random check-in — runs every few hours, picks random subset."""
    logger.info("[scheduler] random checkin")
    users = await db.get_users_for_random_checkin()
    # Only ping ~30% of users per run to feel "random"
    selected = random.sample(users, max(0, len(users) * 3 // 10))
    text = random.choice(CHECKIN_MESSAGES)
    for u in selected:
        await send_message(bot, u["telegram_id"], text)
        await asyncio.sleep(0.05)
    logger.info(f"[scheduler] checkin: sent to {len(selected)} users")


async def job_weekly_report(bot: Bot):
    """Sunday 19:00 — weekly summary for all active users."""
    logger.info("[scheduler] weekly report")
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT u.telegram_id, u.first_name,
                   u.points_balance, u.streak_days,
                   (SELECT COUNT(*) FROM triggers t WHERE t.user_id = u.id
                    AND t.created_at >= datetime('now','-7 days')) as week_triggers,
                   (SELECT COUNT(*) FROM diary_entries d WHERE d.user_id = u.id
                    AND d.created_at >= datetime('now','-7 days')) as week_diary,
                   (SELECT COALESCE(SUM(points_delta),0) FROM rewards_log r
                    WHERE r.user_id = u.id
                    AND r.created_at >= datetime('now','-7 days')) as week_points
            FROM users u WHERE u.onboarding_done = 1
        """) as cursor:
            users = [dict(r) for r in await cursor.fetchall()]

    title = random.choice(WEEKLY_REPORT_INTRO)
    for u in users:
        if u["week_triggers"] == 0 and u["week_diary"] == 0:
            continue  # skip completely inactive
        text = (
            f"{title}\n\n"
            f"Привет, {u['first_name'] or 'игрок'}! Вот твоя неделя:\n\n"
            f"📝 Триггеров замечено: <b>{u['week_triggers']}</b>\n"
            f"📔 Записей в дневнике: <b>{u['week_diary']}</b>\n"
            f"💰 Заработано TRGR: <b>{u['week_points']}</b>\n"
            f"🔥 Серия дней: <b>{u['streak_days']}</b>\n\n"
        )
        if u["week_triggers"] >= 5:
            text += "🌟 Отличная неделя! Ты в потоке осознанности.\n"
        elif u["week_triggers"] >= 2:
            text += "👍 Хорошее начало! На следующей неделе — ещё глубже.\n"
        else:
            text += "💡 Каждый замеченный триггер — это уже победа. Возвращайся!\n"

        await send_message(bot, u["telegram_id"], text)
        await asyncio.sleep(0.05)
    logger.info(f"[scheduler] weekly: sent to {len(users)} users")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    # Daily diary reminder at 20:00
    scheduler.add_job(
        job_diary_reminder, "cron",
        hour=20, minute=0,
        args=[bot], id="diary_reminder"
    )
    # Trigger reminder at 13:00
    scheduler.add_job(
        job_trigger_reminder, "cron",
        hour=13, minute=0,
        args=[bot], id="trigger_reminder"
    )
    # Random check-ins at 10:00, 15:00, 18:00
    for hour in [10, 15, 18]:
        scheduler.add_job(
            job_random_checkin, "cron",
            hour=hour, minute=0,
            args=[bot], id=f"checkin_{hour}"
        )
    # Weekly report every Sunday at 19:00
    scheduler.add_job(
        job_weekly_report, "cron",
        day_of_week="sun", hour=19, minute=0,
        args=[bot], id="weekly_report"
    )

    return scheduler
