from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Voice
from aiogram.fsm.context import FSMContext
import os

import database as db
import keyboards as kb
import points_service as ps
import ai_service as ai
from states import TriggerStates
from config import CHANNEL_ID

router = Router()


async def check_subscription(bot: Bot, user_id: int) -> bool:
    """Проверка подписки. Возвращает True если подписан."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ("left", "kicked", "banned"):
            return False
        return True
    except Exception:
        return True  # Если не можем проверить, разрешаем доступ


# ─── Start recording a trigger ───────────────────────────────────────────────

@router.message(F.text == "📝 Записать триггер")
async def start_trigger(message: Message, state: FSMContext, bot: Bot):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return
    
    # Проверка подписки
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "⚠️ <b>Ты отписался от канала!</b>\n\n"
            f"Чтобы продолжить пользоваться ботом, подпишись на канал {CHANNEL_ID}\n\n"
            f"После подписки все функции станут доступны.",
            parse_mode="HTML",
            reply_markup=kb.subscription_keyboard(CHANNEL_ID)
        )
        return

    await state.set_state(TriggerStates.waiting_trigger_text)
    await message.answer(
        "📝 <b>Запиши триггер</b>\n\n"
        "Что тебя задело? Опиши ситуацию своими словами.\n\n"
        "<i>Пример: «Меня разозлило, что коллега перебил меня на встрече»</i>",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )


@router.callback_query(F.data == "new_trigger")
async def new_trigger_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TriggerStates.waiting_trigger_text)
    await callback.message.answer(
        "📝 <b>Запиши триггер</b>\n\n"
        "Что тебя задело? Опиши ситуацию своими словами.",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )
    await callback.answer()


# ─── Receive trigger text ─────────────────────────────────────────────────────

@router.message(TriggerStates.waiting_trigger_text, F.text)
async def receive_trigger_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Напиши чуть подробнее – хотя бы несколько слов 🙏")
        return

    # Process the trigger
    await process_trigger_text(message, text, state)


# ─── Voice trigger handler ────────────────────────────────────────────────────

@router.message(TriggerStates.waiting_trigger_text, F.voice)
async def handle_voice_trigger(message: Message, state: FSMContext):
    """Обработка голосовых триггеров через Vosk."""
    
    voice = message.voice
    
    # Проверка длительности (макс 2 минуты)
    if voice.duration > 120:
        await message.answer(
            "❌ Голосовое слишком длинное (макс 2 минуты).\n"
            "Запиши короче или напиши текстом."
        )
        return
    
    # Скачиваем файл
    wait_msg = await message.answer("🎤 Записываю голос...")
    
    try:
        file = await message.bot.get_file(voice.file_id)
        file_path = f"temp/voice_{message.from_user.id}_{voice.file_unique_id}.ogg"
        
        os.makedirs("temp", exist_ok=True)
        await message.bot.download_file(file.file_path, file_path)
        
        # Транскрибация через Vosk
        result = await ai.transcribe_voice_vosk(file_path)
        
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if result.get("error"):
            await wait_msg.edit_text(
                f"❌ Не удалось распознать:\n{result['error']}\n\n"
                f"Попробуй записать ещё раз или напиши текстом."
            )
            return
        
        text = result["text"]
        duration = result.get("duration", 0)
        
        if not text or len(text) < 3:
            await wait_msg.edit_text(
                "❌ Не удалось разобрать слова. "
                "Говори чётче или напиши текстом."
            )
            return
        
        # Показываем результат
        await wait_msg.edit_text(
            f"✅ Распознал ({duration:.1f} сек):\n\n«{text}»\n\n"
            f"Анализирую..."
        )
        
        # Process the trigger with audio info
        await process_trigger_text(
            message, text, state,
            audio_file_id=voice.file_id,
            audio_duration=duration
        )
        
    except Exception as e:
        await wait_msg.edit_text(
            f"❌ Ошибка при обработке:\n{str(e)}\n\n"
            f"Попробуй ещё раз или напиши текстом."
        )


async def process_trigger_text(message: Message, text: str, state: FSMContext,
                               audio_file_id: str = None, audio_duration: int = None):
    """Общая функция для текстовых и голосовых триггеров."""
    
    # AI analysis
    analysis = await ai.analyze_trigger(text)
    emotion_code = analysis.get("emotion", "other")
    category_code = analysis.get("category", "other")
    ai_response = analysis.get("brief_response", "")
    
    # Save draft trigger state
    await state.update_data(
        raw_text=text,
        emotion_code=emotion_code,
        category_code=category_code,
        ai_response=ai_response,
        audio_file_id=audio_file_id,
        audio_duration=audio_duration
    )
    
    # Build response
    emotion_label = ai.EMOTION_LABELS.get(emotion_code, "💭 Другое")
    category_label = ai.CATEGORY_LABELS.get(category_code, "💭 Другое")
    
    # Voice badge
    voice_badge = "🎤 " if audio_file_id else ""
    
    resp = (
        f"{voice_badge}✅ <b>Триггер зафиксирован.</b>\n"
        f"Ты уже не внутри автопилота – ты наблюдаешь.\n\n"
    )
    if ai_response:
        resp += f"<i>{ai_response}</i>\n\n"
    resp += (
        f"🏷 Категория: {category_label}\n"
        f"💭 Эмоция: {emotion_label}\n\n"
        f"Выбери эмоцию точнее или подтверди:"
    )
    
    await message.answer(resp, parse_mode="HTML", reply_markup=kb.emotion_keyboard())
    await state.set_state(TriggerStates.waiting_emotion)


# ─── Emotion selection ────────────────────────────────────────────────────────

@router.callback_query(TriggerStates.waiting_emotion, F.data.startswith("emotion:"))
async def select_emotion(callback: CallbackQuery, state: FSMContext):
    emotion = callback.data.split(":")[1]
    await state.update_data(emotion_code=emotion)
    emotion_label = ai.EMOTION_LABELS.get(emotion, "💭")

    await callback.message.edit_text(
        f"💭 Эмоция: {emotion_label}\n\n"
        f"Насколько сильно это тебя задело?\n"
        f"Выбери от 1 (слабо) до 10 (очень сильно):",
        reply_markup=kb.intensity_keyboard()
    )
    await state.set_state(TriggerStates.waiting_intensity)
    await callback.answer()


# ─── Intensity selection ──────────────────────────────────────────────────────

@router.callback_query(TriggerStates.waiting_intensity, F.data.startswith("intensity:"))
async def select_intensity(callback: CallbackQuery, state: FSMContext):
    intensity = int(callback.data.split(":")[1])
    await state.update_data(intensity=intensity)

    data = await state.get_data()
    step_q = await ai.generate_reflection_prompt(
        data["raw_text"], data.get("emotion_code", "other"), step=3
    )

    await callback.message.edit_text(
        f"⚡ Интенсивность: {intensity}/10\n\n"
        f"<b>Следующий шаг:</b>\n{step_q}\n\n"
        f"<i>(Напиши ответ или пропусти)</i>",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )
    await state.set_state(TriggerStates.waiting_zone)
    await callback.answer()


# ─── Zone of influence ────────────────────────────────────────────────────────

@router.message(TriggerStates.waiting_zone, F.text)
async def receive_zone(message: Message, state: FSMContext):
    await state.update_data(zone_text=message.text.strip())
    data = await state.get_data()

    step_q = await ai.generate_reflection_prompt(
        data["raw_text"], data.get("emotion_code", "other"), step=5
    )
    await message.answer(
        f"✍️ Записано.\n\n"
        f"<b>Последний вопрос:</b>\n{step_q}\n\n"
        f"<i>(Напиши или пропусти)</i>",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )
    await state.set_state(TriggerStates.waiting_insight)


@router.callback_query(TriggerStates.waiting_zone, F.data == "skip_step")
async def skip_zone(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    step_q = await ai.generate_reflection_prompt(
        data["raw_text"], data.get("emotion_code", "other"), step=5
    )
    await callback.message.edit_text(
        f"<b>Следующий вопрос:</b>\n{step_q}\n\n"
        f"<i>(Напиши или пропусти)</i>",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )
    await state.set_state(TriggerStates.waiting_insight)
    await callback.answer()


# ─── Insight / conclusion ─────────────────────────────────────────────────────

@router.message(TriggerStates.waiting_insight, F.text)
async def receive_insight(message: Message, state: FSMContext):
    await state.update_data(insight_text=message.text.strip())
    await save_trigger_and_finish(message, state)


@router.callback_query(TriggerStates.waiting_insight, F.data == "skip_step")
async def skip_insight(callback: CallbackQuery, state: FSMContext):
    await save_trigger_and_finish(callback.message, state, user_id=callback.from_user.id)
    await callback.answer()


# ─── Skip emotion step ────────────────────────────────────────────────────────

@router.callback_query(TriggerStates.waiting_emotion, F.data == "skip_step")
async def skip_emotion(callback: CallbackQuery, state: FSMContext):
    await save_trigger_and_finish(callback.message, state, user_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(TriggerStates.waiting_intensity, F.data == "skip_step")
async def skip_intensity(callback: CallbackQuery, state: FSMContext):
    await save_trigger_and_finish(callback.message, state, user_id=callback.from_user.id)
    await callback.answer()


# ─── Save trigger and calculate points ───────────────────────────────────────

async def save_trigger_and_finish(message: Message, state: FSMContext, user_id: int = None):
    if user_id is None:
        user_id = message.chat.id

    data = await state.get_data()
    await state.clear()

    user = await db.get_user(user_id)
    if not user:
        return

    raw_text = data.get("raw_text", "")
    emotion_code = data.get("emotion_code")
    intensity = data.get("intensity")
    zone_text = data.get("zone_text")
    insight_text = data.get("insight_text")
    category_code = data.get("category_code")

    # Count for bonuses
    triggers_today = await db.count_triggers_today(user["id"])
    triggers_total = await db.count_triggers_total(user["id"])

    # Save to DB
    trigger_id = await db.save_trigger(
        user_id=user["id"],
        raw_text=raw_text,
        emotion_code=emotion_code,
        intensity=intensity,
        category_code=category_code,
        audio_file_id=data.get("audio_file_id"),
        audio_duration=data.get("audio_duration"),
    )
    if zone_text:
        await db.update_trigger(trigger_id, zone_of_control_text=zone_text)
    if insight_text:
        await db.update_trigger(trigger_id, insight_text=insight_text)

    # Award points
    is_voice = bool(data.get("audio_file_id"))
    result = await ps.award_trigger(
        telegram_id=user_id,
        trigger_id=trigger_id,
        has_emotion=bool(emotion_code and emotion_code != "other"),
        has_intensity=bool(intensity),
        has_insight=bool(insight_text),
        has_zone=bool(zone_text),
        is_first_today=(triggers_today == 0),
        is_first_ever=(triggers_total == 0),
        is_voice=is_voice,
    )

    # Check achievements
    new_achievements = await ps.check_and_award_achievements(user_id)

    # Build response
    breakdown_text = "\n".join(f"  {line}" for line in result["breakdown"])
    response = (
        f"🎉 <b>+{result['total']} очков!</b>\n\n"
        f"{breakdown_text}\n\n"
        f"💰 Баланс: {result['balance']} баллов"
    )

    if new_achievements:
        from database import DB_PATH
        import aiosqlite
        for code in new_achievements:
            async with aiosqlite.connect(DB_PATH) as db_conn:
                async with db_conn.execute(
                    "SELECT title, icon FROM achievements WHERE code = ?", (code,)
                ) as cursor:
                    ach = await cursor.fetchone()
                    if ach:
                        response += f"\n\n🏆 <b>Достижение разблокировано!</b>\n{ach[1]} {ach[0]}"

    await message.answer(
        response,
        parse_mode="HTML",
        reply_markup=kb.after_trigger_keyboard(trigger_id)
    )


# ─── Deep reflection ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reflect:"))
async def start_reflection(callback: CallbackQuery, state: FSMContext):
    trigger_id = int(callback.data.split(":")[1])
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM triggers WHERE id = ?", (trigger_id,)
        ) as cursor:
            trigger = await cursor.fetchone()

    if not trigger:
        await callback.answer("Триггер не найден")
        return

    await state.update_data(
        reflect_trigger_id=trigger_id,
        reflect_text=trigger["raw_text"],
        reflect_emotion=trigger["emotion_code"] or "other",
        reflect_step=1
    )

    q = await ai.generate_reflection_prompt(trigger["raw_text"], trigger["emotion_code"] or "other", step=1)
    await callback.message.edit_text(
        f"🔍 <b>Разбор триггера</b>\n\n"
        f"<i>«{trigger['raw_text'][:100]}»</i>\n\n"
        f"<b>Шаг 1/3:</b> {q}\n\n<i>(Напиши ответ или пропусти)</i>",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )
    await state.set_state(TriggerStates.reflect_step_1)
    await callback.answer()


# Handler for reflection step 1 answer
@router.message(TriggerStates.reflect_step_1, F.text)
async def reflect_step_1_answer(message: Message, state: FSMContext):
    answer = message.text.strip()
    data = await state.get_data()
    trigger_id = data.get("reflect_trigger_id")
    
    # Save answer
    if answer and answer != "⏭ Пропустить":
        await db.save_trigger_reflection(trigger_id, "step_1", answer)
    
    # Step 2
    q = await ai.generate_reflection_prompt(data["reflect_text"], data["reflect_emotion"], step=2)
    await message.answer(
        f"✅ Шаг 1 принят.\n\n"
        f"<b>Шаг 2/3:</b> {q}\n\n<i>(Напиши ответ или пропусти)</i>",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )
    await state.set_state(TriggerStates.reflect_step_2)


# Handler for reflection step 2 answer
@router.message(TriggerStates.reflect_step_2, F.text)
async def reflect_step_2_answer(message: Message, state: FSMContext):
    answer = message.text.strip()
    data = await state.get_data()
    trigger_id = data.get("reflect_trigger_id")
    
    # Save answer
    if answer and answer != "⏭ Пропустить":
        await db.save_trigger_reflection(trigger_id, "step_2", answer)
    
    # Step 3 - FINAL
    q = await ai.generate_reflection_prompt(data["reflect_text"], data["reflect_emotion"], step=3)
    await message.answer(
        f"✅ Шаг 2 принят.\n\n"
        f"<b>Шаг 3/3:</b> {q}\n\n<i>(Напиши ответ или пропусти)</i>",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )
    await state.set_state(TriggerStates.reflect_step_3)


# Handler for reflection step 3 answer - FINAL STEP
@router.message(TriggerStates.reflect_step_3, F.text)
async def reflect_step_3_answer(message: Message, state: FSMContext):
    answer = message.text.strip()
    data = await state.get_data()
    trigger_id = data.get("reflect_trigger_id")
    
    # Save answer
    if answer and answer != "⏭ Пропустить":
        await db.save_trigger_reflection(trigger_id, "step_3", answer)
    
    # Complete reflection (3 steps)
    await message.answer(
        f"✅ <b>Разбор завершён!</b>\n\n"
        f"Ты прошёл(а) все 3 шага рефлексии.\n"
        f"Это большой шаг к осознанности! 🙏\n\n"
        f"🎉 +10 очков за глубокую работу!",
        parse_mode="HTML",
        reply_markup=kb.after_trigger_keyboard(trigger_id)
    )
    
    # Award bonus points for completing reflection
    user = await db.get_user(message.from_user.id)
    if user:
        await db.award_points(message.from_user.id, 10, "reflection_complete", f"Рефлексия триггера #{trigger_id}")
    
    await state.clear()


# Skip handlers for reflection (3 steps)
@router.callback_query(TriggerStates.reflect_step_1, F.data == "skip_step")
@router.callback_query(TriggerStates.reflect_step_2, F.data == "skip_step")
@router.callback_query(TriggerStates.reflect_step_3, F.data == "skip_step")
async def reflect_skip_step(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_state = await state.get_state()
    step_num = int(current_state.split("_")[-1])
    trigger_id = data.get("reflect_trigger_id")
    
    # Save empty answer for skipped step
    await db.save_trigger_reflection(trigger_id, f"step_{step_num}", "")
    
    if step_num >= 3:
        # Final step - complete
        await callback.message.answer(
            f"✅ <b>Разбор завершён!</b>\n\n"
            f"Ты прошёл(а) все 3 шага рефлексии.\n"
            f"Это большой шаг к осознанности! 🙏",
            parse_mode="HTML",
            reply_markup=kb.after_trigger_keyboard(trigger_id)
        )
        await state.clear()
    else:
        # Next step
        next_step = step_num + 1
        q = await ai.generate_reflection_prompt(data["reflect_text"], data["reflect_emotion"], step=next_step)
        await callback.message.answer(
            f"✅ Пропущено.\n\n"
            f"<b>Шаг {next_step}/3:</b> {q}\n\n<i>(Напиши ответ или пропусти)</i>",
            parse_mode="HTML",
            reply_markup=kb.skip_keyboard()
        )
        await state.set_state(getattr(TriggerStates, f"reflect_step_{next_step}"))
    
    await callback.answer()


# ─── View triggers list ───────────────────────────────────────────────────────

@router.message(F.text == "📋 Мои триггеры")
@router.callback_query(F.data == "show_triggers")
async def show_triggers(update, state: FSMContext):
    if isinstance(update, CallbackQuery):
        message = update.message
        user_id = update.from_user.id
    else:
        message = update
        user_id = update.from_user.id

    await state.clear()
    user = await db.get_user(user_id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return

    triggers = await db.get_triggers(user["id"], limit=10)
    total = await db.count_triggers_total(user["id"])

    if not triggers:
        await message.answer(
            "📋 <b>Мои триггеры</b>\n\n"
            "У тебя ещё нет записей.\n"
            "Нажми «📝 Записать триггер», чтобы начать!",
            parse_mode="HTML",
            reply_markup=kb.main_menu()
        )
        if isinstance(update, CallbackQuery):
            await update.answer()
        return

    text = f"📋 <b>Мои триггеры</b> (всего: {total})\n\nВыбери запись для просмотра:"
    await message.answer(text, parse_mode="HTML", reply_markup=kb.triggers_list_keyboard(triggers))

    if isinstance(update, CallbackQuery):
        await update.answer()


@router.callback_query(F.data.startswith("triggers_page:"))
async def triggers_page(callback: CallbackQuery, state: FSMContext):
    offset = int(callback.data.split(":")[1])
    user = await db.get_user(callback.from_user.id)
    if not user:
        return

    triggers = await db.get_triggers(user["id"], limit=10, offset=offset)
    total = await db.count_triggers_total(user["id"])

    await callback.message.edit_text(
        f"📋 <b>Мои триггеры</b> (всего: {total})",
        parse_mode="HTML",
        reply_markup=kb.triggers_list_keyboard(triggers, offset)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_trigger:"))
async def view_trigger(callback: CallbackQuery, state: FSMContext):
    trigger_id = int(callback.data.split(":")[1])
    import aiosqlite
    from config import DB_PATH

    async with aiosqlite.connect(DB_PATH) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM triggers WHERE id = ?", (trigger_id,)
        ) as cursor:
            t = await cursor.fetchone()

    if not t:
        await callback.answer("Запись не найдена")
        return

    t = dict(t)
    emotion_label = ai.EMOTION_LABELS.get(t.get("emotion_code"), "—")
    category_label = ai.CATEGORY_LABELS.get(t.get("category_code"), "—")

    text = (
        f"📌 <b>Триггер</b>\n"
        f"<i>{db.fmt_date(t['created_at'], short=True)}</i>\n\n"
        f"📝 {t['raw_text']}\n\n"
        f"💭 Эмоция: {emotion_label}\n"
        f"⚡ Интенсивность: {t.get('intensity') or '—'}/10\n"
        f"🏷 Категория: {category_label}\n"
    )
    if t.get("zone_of_control_text"):
        text += f"\n🎯 Зона влияния:\n<i>{t['zone_of_control_text']}</i>\n"
    if t.get("insight_text"):
        text += f"\n💡 Вывод:\n<i>{t['insight_text']}</i>\n"
    text += f"\n✨ Начислено: {t.get('points_awarded', 0)} баллов"

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=kb.trigger_detail_keyboard(trigger_id)
    )
    await callback.answer()
