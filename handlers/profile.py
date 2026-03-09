from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import config
import database as db
import keyboards as kb
import points_service as ps
import ai_service as ai
from states import CheckinStates

router = Router()


# ─── Progress / profile ───────────────────────────────────────────────────────

@router.message(F.text == "📊 Мой прогресс")
async def show_progress(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return

    text = ps.format_progress(user)

    # Weekly stats
    stats = await db.get_weekly_stats(user["id"])
    text += (
        f"\n<b>За эту неделю:</b>\n"
        f"📝 Триггеров: {stats['triggers']}\n"
        f"📔 Записей в дневнике: {stats['diary']}\n"
        f"💰 Заработано баллов: {stats['points']}\n"
    )

    # Achievements
    achievements = await db.get_user_achievements(user["id"])
    if achievements:
        text += "\n<b>Достижения:</b>\n"
        import aiosqlite
        from config import DB_PATH
        async with aiosqlite.connect(DB_PATH) as db_conn:
            for code in achievements:
                async with db_conn.execute(
                    "SELECT title, icon FROM achievements WHERE code = ?", (code,)
                ) as cursor:
                    ach = await cursor.fetchone()
                    if ach:
                        text += f"{ach[1]} {ach[0]}\n"

    # Total triggers
    total_triggers = await db.count_triggers_total(user["id"])
    text += f"\n📊 Всего триггеров: {total_triggers}"

    # Referral link
    ref_code = user.get("referral_code", "")
    if ref_code and config.BOT_USERNAME:
        text += (
            f"\n\n🔗 <b>Реферальная ссылка:</b>\n"
            f"<code>https://t.me/{config.BOT_USERNAME}?start={ref_code}</code>"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=kb.main_menu())


# ─── Quick check-in ───────────────────────────────────────────────────────────

@router.message(F.text == "✅ Быстрый чек-ин")
async def start_checkin(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return

    await state.set_state(CheckinStates.waiting_feeling)
    await message.answer(
        "✅ <b>Быстрый чек-ин</b>\n\n"
        "Что ты сейчас чувствуешь? Опиши в 1-2 словах или фразе.",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )


@router.message(CheckinStates.waiting_feeling, F.text)
async def checkin_feeling(message: Message, state: FSMContext):
    await state.update_data(feeling=message.text.strip())
    await message.answer(
        "⚡ Оцени уровень энергии от 1 до 10:",
        reply_markup=kb.energy_keyboard()
    )
    await state.set_state(CheckinStates.waiting_energy)


@router.callback_query(CheckinStates.waiting_energy, F.data.startswith("energy:"))
async def checkin_energy(callback: CallbackQuery, state: FSMContext):
    energy = int(callback.data.split(":")[1])
    await state.update_data(energy=energy)

    await callback.message.edit_text(
        "😤 Насколько ты сейчас напряжён? (от 1 – спокойно, до 10 – очень напряжённо)",
        reply_markup=kb.intensity_keyboard()
    )
    await state.set_state(CheckinStates.waiting_tension)
    await callback.answer()


@router.callback_query(CheckinStates.waiting_tension, F.data.startswith("intensity:"))
async def checkin_tension(callback: CallbackQuery, state: FSMContext):
    tension = int(callback.data.split(":")[1])
    data = await state.get_data()
    await state.clear()

    feeling = data.get("feeling", "—")
    energy = data.get("energy", "—")

    emoji_energy = "🔋" if isinstance(energy, int) and energy >= 7 else ("⚡" if isinstance(energy, int) and energy >= 4 else "🪫")
    emoji_tension = "😌" if tension <= 3 else ("😐" if tension <= 6 else "😤")

    await callback.message.edit_text(
        f"✅ <b>Чек-ин зафиксирован</b>\n\n"
        f"💭 Чувствую: {feeling}\n"
        f"{emoji_energy} Энергия: {energy}/10\n"
        f"{emoji_tension} Напряжение: {tension}/10\n\n"
        f"<i>Ты замечаешь себя – это уже практика.</i>",
        parse_mode="HTML"
    )
    await callback.message.answer("🏠 Главное меню", reply_markup=kb.main_menu())
    await callback.answer()


@router.callback_query(CheckinStates.waiting_feeling, F.data == "skip_step")
@router.callback_query(CheckinStates.waiting_energy, F.data == "skip_step")
@router.callback_query(CheckinStates.waiting_tension, F.data == "skip_step")
async def skip_checkin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Чек-ин пропущен. Возвращайся! ✌️")
    await callback.message.answer("🏠 Главное меню", reply_markup=kb.main_menu())
    await callback.answer()


# ─── Settings ─────────────────────────────────────────────────────────────────

@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return

    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM notification_settings WHERE user_id = ?", (user["id"],)
        ) as cursor:
            ns = await cursor.fetchone()
            ns = dict(ns) if ns else {}

    diary_status = "✅" if ns.get("diary_enabled", 1) else "❌"
    trigger_status = "✅" if ns.get("trigger_reminders_enabled", 1) else "❌"
    checkin_status = "✅" if ns.get("random_checkin_enabled", 1) else "❌"

    await message.answer(
        f"⚙️ <b>Настройки</b>\n\n"
        f"📔 Напоминание дневника: {diary_status}\n"
        f"📝 Напоминание триггеров: {trigger_status}\n"
        f"✅ Случайные чек-ины: {checkin_status}\n"
        f"⏰ Время дневника: {ns.get('diary_time', '20:00')}\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n"
        f"<code>https://t.me/{config.BOT_USERNAME}?start={user.get('referral_code', '')}</code>\n\n"
        f"За каждого приглашённого друга +{config.POINTS['referral']} баллов!\n\n"
        f"<i>Настройка уведомлений через /settings в следующей версии</i>",
        parse_mode="HTML",
        reply_markup=kb.main_menu()
    )
