from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import keyboards as kb
from states import StopStates

router = Router()

EMOTION_LABELS = {
    "anger":    "😤 Злость/раздражение",
    "fear":     "😨 Страх/тревога",
    "sadness":  "😔 Обида/грусть",
    "shame":    "😳 Стыд/вина",
    "numbness": "😶 Онемение",
}

PAUSE_TEXTS = [
    "Сделай глубокий вдох через нос — 4 секунды.",
    "Задержи дыхание на 2 секунды.",
    "Медленно выдохни через рот — 6 секунд.",
    "Повтори ещё раз, если нужно.",
]


@router.message(F.text == "🛑 Стоп")
async def stop_mode(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🛑 <b>СТОП</b>\n\n"
        "Ты сейчас в сильной эмоции или на грани реакции.\n\n"
        "<b>Шаг 1.</b> Остановись. Не пиши, не звони, не отвечай.\n\n"
        "Что ты сейчас чувствуешь?",
        parse_mode="HTML",
        reply_markup=kb.stop_feeling_keyboard()
    )
    await state.set_state(StopStates.step_feeling)


@router.callback_query(StopStates.step_feeling, F.data.startswith("stop_feel:"))
async def stop_feeling(callback: CallbackQuery, state: FSMContext):
    emotion = callback.data.split(":")[1]
    label = EMOTION_LABELS.get(emotion, "сильную эмоцию")
    await state.update_data(emotion=emotion, emotion_label=label)

    await callback.message.edit_text(
        f"<b>Шаг 2.</b> Ты чувствуешь: {label}\n\n"
        f"Насколько сильно это ощущение прямо сейчас?\n"
        f"<i>(1 — почти спокойно, 10 — невыносимо)</i>",
        parse_mode="HTML",
        reply_markup=kb.stop_intensity_keyboard()
    )
    await state.set_state(StopStates.step_intensity)
    await callback.answer()


@router.callback_query(StopStates.step_intensity, F.data.startswith("stop_int:"))
async def stop_intensity(callback: CallbackQuery, state: FSMContext):
    intensity = int(callback.data.split(":")[1])
    data = await state.get_data()
    label = data.get("emotion_label", "эмоция")

    # Breathing exercise
    await callback.message.edit_text(
        f"<b>Шаг 3.</b> Интенсивность: {intensity}/10\n\n"
        f"{'Это очень сильно. Тело сейчас напряжено — помоги ему.' if intensity >= 7 else 'Хорошо, что ты заметил(а).'}\n\n"
        f"<b>Сделай дыхательную паузу:</b>\n\n"
        f"🫁 Вдох — 4 секунды\n"
        f"⏸ Пауза — 2 секунды\n"
        f"💨 Выдох — 6 секунд\n\n"
        f"Повтори 2–3 раза. Я жду.",
        parse_mode="HTML",
        reply_markup=kb.stop_intensity_keyboard()
    )
    await state.update_data(intensity=intensity)
    await state.set_state(StopStates.step_pause)

    # Edit with next step after breathing prompt
    await callback.message.edit_text(
        f"<b>Шаг 3.</b> Интенсивность: {intensity}/10\n\n"
        f"<b>Сейчас — дыхательная пауза:</b>\n\n"
        f"🫁 Вдох носом — 4 сек\n"
        f"⏸ Пауза — 2 сек\n"
        f"💨 Выдох ртом — 6 сек\n\n"
        f"Сделай 2–3 цикла. Когда будешь готов(а) — нажми кнопку.",
        parse_mode="HTML",
        reply_markup=_pause_done_keyboard()
    )
    await callback.answer()


def _pause_done_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="✅ Я подышал(а), продолжить",
        callback_data="stop_breathed"
    ))
    return builder.as_markup()


@router.callback_query(StopStates.step_pause, F.data == "stop_breathed")
async def stop_breathed(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    label = data.get("emotion_label", "эмоция")
    intensity = data.get("intensity", 5)

    # Decide on next action message based on intensity
    if intensity >= 8:
        advice = (
            "Не предпринимай никаких действий прямо сейчас.\n"
            "Подожди минимум <b>10 минут</b> — эмоция немного спадёт."
        )
    elif intensity >= 5:
        advice = (
            "Ты можешь действовать — но осознанно.\n"
            "Спроси себя: <i>«Что я хочу получить в итоге?»</i>"
        )
    else:
        advice = (
            "Ты справляешься.\n"
            "Заметь: ты остановился(ась) и выбрал(а) осознанность."
        )

    await callback.message.edit_text(
        f"<b>Шаг 4–5.</b> {advice}\n\n"
        f"<b>Шаг 6. Выбери зрелый следующий шаг:</b>\n\n"
        f"• Что я <i>на самом деле</i> хочу сказать или сделать?\n"
        f"• Как бы я поступил(а), если бы был(а) в ресурсе?\n"
        f"• Что будет через неделю — важно ли это будет так же?\n\n"
        f"<i>{label} — это сигнал о чём-то важном, а не приговор.</i>",
        parse_mode="HTML",
        reply_markup=kb.stop_next_keyboard()
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "stop_done")
async def stop_done(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "💪 <b>Отлично.</b>\n\n"
        "Ты выбрал(а) осознанность вместо автоматической реакции.\n"
        "Это и есть практика.\n\n"
        "<i>+3 TRGR за остановку перед реакцией</i>",
        parse_mode="HTML"
    )
    await callback.message.answer("🏠 Главное меню", reply_markup=kb.main_menu())
    await callback.answer()
