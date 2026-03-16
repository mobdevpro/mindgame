from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, Voice
from aiogram.fsm.context import FSMContext
import os

import database as db
import keyboards as kb
import ai_service as ai
from states import TaskStates

router = Router()

DIFFICULTY_LABELS = {
    "easy":          ("🟢 Лёгкая",          5),
    "medium":        ("🟡 Средняя",         12),
    "hard":          ("🔴 Сложная",         30),
    "uncomfortable": ("🔥 Дискомфортная",   50),
}


# ─── Entry points ─────────────────────────────────────────────────────────────

@router.message(F.text == "✅ Мои задачи")
@router.callback_query(F.data == "show_tasks")
async def show_tasks(update, state: FSMContext):
    msg = update.message if isinstance(update, CallbackQuery) else update
    uid = update.from_user.id

    await state.clear()
    user = await db.get_user(uid)
    if not user:
        await msg.answer("Сначала запусти бота командой /start")
        return

    tasks = await db.get_tasks(user["id"])

    if not tasks:
        await msg.answer(
            "✅ <b>Мои задачи</b>\n\n"
            "Задач пока нет.\n\n"
            "Задача — это реальное действие из жизни, которое ты хочешь сделать.\n"
            "За каждую выполненную задачу начисляются TRGR! 🎯",
            parse_mode="HTML",
            reply_markup=kb.tasks_list_keyboard([])
        )
    else:
        done = sum(1 for t in tasks if t["status"] == "done")
        active = [t for t in tasks if t["status"] != "done"]
        await msg.answer(
            f"✅ <b>Мои задачи</b>\n\n"
            f"Активных: {len(active)}  •  Выполнено: {done}\n\n"
            f"Выбери задачу или добавь новую:",
            parse_mode="HTML",
            reply_markup=kb.tasks_list_keyboard(tasks)
        )

    if isinstance(update, CallbackQuery):
        await update.answer()


# ─── New task ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "new_task")
async def new_task(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TaskStates.waiting_text)
    await callback.message.answer(
        "➕ <b>Новая задача</b>\n\n"
        "Опиши задачу — что конкретно нужно сделать?\n\n"
        "<i>Примеры хороших задач:\n"
        "• «Позвонить клиенту и договориться о встрече»\n"
        "• «Провести сложный разговор с коллегой»\n"
        "• «Записаться к врачу»\n"
        "• «Пойти на тренировку, хотя не хочется»</i>\n\n"
        "🎤 Можно отправить голосовым!",
        parse_mode="HTML",
        reply_markup=kb.skip_keyboard()
    )
    await callback.answer()


# ─── Voice task handler ───────────────────────────────────────────────────────

@router.message(TaskStates.waiting_text, F.voice)
async def handle_voice_task(message: Message, state: FSMContext):
    """Обработка голосовых задач через Vosk."""
    
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
        file_path = f"temp/voice_task_{message.from_user.id}_{voice.file_unique_id}.ogg"
        
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
        
        # Показываем результат и сохраняем задачу
        await process_task_text(message, text, state, is_voice=True, wait_msg=wait_msg)

    except Exception as e:
        await wait_msg.edit_text(
            f"❌ Ошибка при обработке:\n{str(e)}\n\n"
            f"Попробуй ещё раз или напиши текстом."
        )


@router.message(TaskStates.waiting_text, F.text)
async def receive_task_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Опиши задачу чуть подробнее 🙏")
        return
    await process_task_text(message, text, state, is_voice=False)


async def process_task_text(message: Message, text: str, state: FSMContext, is_voice: bool = False, wait_msg: Message = None):
    """Общая функция для текстовых и голосовых задач."""
    await state.update_data(task_text=text, is_voice=is_voice)
    await state.set_state(TaskStates.waiting_difficulty)
    
    voice_badge = "🎤 " if is_voice else ""
    
    # Если есть wait_msg (от голосового), редактируем его
    if wait_msg:
        await wait_msg.edit_text(
            f"{voice_badge}📋 <b>«{text[:60]}»</b>\n\n"
            f"Насколько эта задача сложная или дискомфортная для тебя?",
            parse_mode="HTML",
            reply_markup=kb.task_difficulty_keyboard()
        )
    else:
        await message.answer(
            f"{voice_badge}📋 <b>«{text[:60]}»</b>\n\n"
            f"Насколько эта задача сложная или дискомфортная для тебя?",
            parse_mode="HTML",
            reply_markup=kb.task_difficulty_keyboard()
        )


@router.callback_query(TaskStates.waiting_difficulty, F.data.startswith("task_diff:"))
async def receive_difficulty(callback: CallbackQuery, state: FSMContext):
    difficulty = callback.data.split(":")[1]
    data = await state.get_data()
    await state.clear()

    user = await db.get_user(callback.from_user.id)
    if not user:
        return

    is_voice = data.get("is_voice", False)
    task_id = await db.save_task(user["id"], data["task_text"], difficulty, is_voice)
    label, points = DIFFICULTY_LABELS.get(difficulty, ("Задача", 5))
    
    # Бонус за голосовую задачу
    voice_bonus = 2 if is_voice else 0
    total_points = points + voice_bonus
    
    voice_text = "🎤 Голосовая задача\n" if voice_bonus else ""

    await callback.message.edit_text(
        f"✅ <b>Задача добавлена!</b>\n\n"
        f"📋 {data['task_text']}\n"
        f"{label} • После выполнения: <b>+{total_points} TRGR</b>\n"
        f"{voice_text}"
        f"Когда сделаешь — отметь выполненной и получи TRGR! 🎯",
        parse_mode="HTML",
        reply_markup=kb.task_detail_keyboard(task_id, "new")
    )
    await callback.answer()


# ─── View task ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("view_task:"))
async def view_task(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    task = await db.get_task(task_id)
    if not task:
        await callback.answer("Задача не найдена")
        return

    status_labels = {
        "new":        "🆕 Новая",
        "in_progress": "⏳ В процессе",
        "done":       "✅ Выполнена",
        "cancelled":  "❌ Отменена",
    }
    label, points = DIFFICULTY_LABELS.get(
        task.get("estimated_difficulty_score", "easy"), ("Задача", 5)
    )
    status = status_labels.get(task["status"], task["status"])

    text = (
        f"📋 <b>Задача</b>\n\n"
        f"{task['title']}\n\n"
        f"Сложность: {label}\n"
        f"Статус: {status}\n"
        f"Награда: +{task.get('estimated_points') or points} TRGR\n"
        f"Добавлена: {db.fmt_date(task['created_at'], short=True)}"
    )
    if task.get("points_awarded"):
        text += f"\n\n🎉 Получено: <b>+{task['points_awarded']} TRGR</b>"

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=kb.task_detail_keyboard(task_id, task["status"])
    )
    await callback.answer()


# ─── Task actions ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("task_start:"))
async def task_start(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    await db.update_task_status(task_id, "in_progress")
    task = await db.get_task(task_id)
    await callback.message.edit_text(
        f"⏳ <b>Задача в работе!</b>\n\n"
        f"{task['title']}\n\n"
        f"<i>Ты взял(а) её в работу. Возвращайся, когда выполнишь!</i>",
        parse_mode="HTML",
        reply_markup=kb.task_detail_keyboard(task_id, "in_progress")
    )
    await callback.answer("⏳ Задача в работе!")


@router.callback_query(F.data.startswith("task_done:"))
async def task_done(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    result = await db.complete_task(task_id, callback.from_user.id)

    if not result["ok"]:
        await callback.answer("Задача не найдена")
        return

    task = await db.get_task(task_id)
    await callback.message.edit_text(
        f"🎉 <b>Задача выполнена!</b>\n\n"
        f"✅ {task['title']}\n\n"
        f"<b>+{result['points']} TRGR</b>\n"
        f"💰 Баланс: {result['balance']} TRGR\n\n"
        f"<i>Каждое выполненное действие — это реальный рост.</i>",
        parse_mode="HTML",
        reply_markup=kb.tasks_list_keyboard([])
    )
    await callback.answer(f"✅ +{result['points']} TRGR!")
