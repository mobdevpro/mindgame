from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
import points_service as ps
import ai_service as ai
from states import DiaryStates

router = Router()

DIARY_PROMPTS = [
    "Что тебя сегодня задело или удивило?",
    "Что ты почувствовал / почувствовала?",
    "Что ты понял / поняла про себя?",
    "Где ты был / была в реакции, а где в выборе?",
    "Что берёшь с собой на завтра?",
]


@router.message(F.text == "📔 Дневник")
async def start_diary(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return

    already_done = await db.check_diary_today(user["id"])

    if already_done:
        entries = await db.get_diary_entries(user["id"], limit=5)
        text = "📔 <b>Дневник осознанности</b>\n\nТы уже сделал запись сегодня! 🌟\n\n"
        text += "<b>Последние записи:</b>\n\n"
        for e in entries:
            date = db.fmt_date(e['created_at'], short=True)
            preview = e["body"][:60] + "..." if len(e["body"]) > 60 else e["body"]
            text += f"📅 {date}\n<i>{preview}</i>\n\n"
        await message.answer(text, parse_mode="HTML", reply_markup=kb.main_menu())
        return

    await state.set_state(DiaryStates.waiting_entry)
    import random
    prompts = random.sample(DIARY_PROMPTS, 3)
    questions = "\n".join(f"• {q}" for q in prompts)

    await message.answer(
        f"📔 <b>Дневник осознанности</b>\n\n"
        f"Ответь на один или несколько вопросов – или просто напиши, что хочется:\n\n"
        f"{questions}\n\n"
        f"<i>Пиши свободно, это только для тебя.</i>",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )


@router.message(DiaryStates.waiting_entry, F.text)
async def receive_diary_entry(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 10:
        await message.answer("Напиши чуть больше – хотя бы пару предложений 🙏")
        return

    await state.update_data(diary_text=text)

    await message.answer(
        "Как твоё настроение прямо сейчас?",
        reply_markup=kb.mood_keyboard()
    )
    await state.set_state(DiaryStates.waiting_mood)


@router.callback_query(DiaryStates.waiting_mood, F.data.startswith("mood:"))
async def select_diary_mood(callback: CallbackQuery, state: FSMContext):
    mood = callback.data.split(":")[1]
    await state.update_data(mood=mood)

    await callback.message.edit_text(
        "⚡ Оцени уровень энергии от 1 до 10:",
        reply_markup=kb.energy_keyboard()
    )
    await state.set_state(DiaryStates.waiting_energy)
    await callback.answer()


@router.callback_query(DiaryStates.waiting_energy, F.data.startswith("energy:"))
async def select_energy(callback: CallbackQuery, state: FSMContext):
    energy = int(callback.data.split(":")[1])
    await state.update_data(energy=energy)
    await save_diary_and_finish(callback.message, state, user_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(DiaryStates.waiting_energy, F.data == "skip_diary_step")
async def skip_energy(callback: CallbackQuery, state: FSMContext):
    await save_diary_and_finish(callback.message, state, user_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(DiaryStates.waiting_mood, F.data == "skip_diary_step")
async def skip_mood(callback: CallbackQuery, state: FSMContext):
    await save_diary_and_finish(callback.message, state, user_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(DiaryStates.waiting_entry, F.data == "skip_step")
async def skip_diary(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Дневник подождёт. Возвращайся, когда будет время! 📔")
    await callback.message.answer("🏠 Главное меню", reply_markup=kb.main_menu())
    await callback.answer()


async def save_diary_and_finish(message: Message, state: FSMContext, user_id: int = None):
    if user_id is None:
        user_id = message.chat.id

    data = await state.get_data()
    await state.clear()

    text = data.get("diary_text", "")
    mood = data.get("mood")
    energy = data.get("energy")

    user = await db.get_user(user_id)
    if not user:
        return

    # AI analysis
    ai_result = await ai.classify_diary_mood(text)
    if not mood:
        mood = ai_result.get("mood", "neutral")
    insight = ai_result.get("insight", "")

    # Determine if full entry (>100 chars)
    is_full = len(text) > 100

    entry_id = await db.save_diary_entry(
        user_id=user["id"],
        body=text,
        mood_code=mood,
        energy_level=energy,
        insight_text=insight,
        points=0
    )

    result = await ps.award_diary(user_id, entry_id, is_full)

    # Update streak
    streak = user.get("streak_days", 0) + 1
    await db.update_user(user_id, streak_days=streak)

    # Check achievements
    new_achievements = await ps.check_and_award_achievements(user_id)

    mood_labels = {
        "good": "😊 Хорошо",
        "neutral": "😐 Нейтрально",
        "bad": "😔 Плохо",
        "tense": "😤 Напряжённо",
        "tired": "😴 Устало",
        "energetic": "⚡ Энергично",
    }
    mood_label = mood_labels.get(mood, "😐")

    response = (
        f"✅ <b>Запись в дневнике сохранена!</b>\n\n"
        f"🌟 Настроение: {mood_label}\n"
    )
    if energy:
        response += f"⚡ Энергия: {energy}/10\n"
    if insight:
        response += f"\n💡 <i>{insight}</i>\n"
    response += (
        f"\n🎉 <b>+{result['total']} очков</b>\n"
        f"💰 Баланс: {result['balance']} баллов\n"
        f"🔥 Серия дней: {streak}"
    )

    if new_achievements:
        import aiosqlite
        from config import DB_PATH
        for code in new_achievements:
            async with aiosqlite.connect(DB_PATH) as db_conn:
                async with db_conn.execute(
                    "SELECT title, icon FROM achievements WHERE code = ?", (code,)
                ) as cursor:
                    ach = await cursor.fetchone()
                    if ach:
                        response += f"\n\n🏆 <b>Достижение!</b>\n{ach[1]} {ach[0]}"

    await message.answer(response, parse_mode="HTML", reply_markup=kb.main_menu())
