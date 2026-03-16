"""
Handlers for support messages feature.
Пользователи могут писать в поддержку, админы — отвечать.
"""
from aiogram import Router, F, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
from states import SupportStates

router = Router()


# ─── User: Send message to support ────────────────────────────────────────────

@router.message(F.text == "💬 Написать в поддержку")
async def start_support_message(message: Message, state: FSMContext):
    """Начать написание сообщения в поддержку."""
    await state.clear()
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return
    
    await state.set_state(SupportStates.waiting_message)
    
    await message.answer(
        "💬 <b>Написать в поддержку</b>\n\n"
        "Опиши свой вопрос, предложение или проблему.\n\n"
        "<i>Администратор ответит в ближайшее время.</i>\n\n"
        "❌ Для отмены напиши /cancel",
        parse_mode="HTML",
        reply_markup=kb.cancel_keyboard()
    )


@router.message(SupportStates.waiting_message)
async def process_support_message(message: Message, state: FSMContext):
    """Обработка сообщения пользователя."""
    await state.clear()
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return
    
    text = message.text or ""
    
    # Проверка на отмену
    if text.lower() in ["/cancel", "отмена", "cancel"]:
        await message.answer(
            "❌ Отменено.\n\n"
            "Если передумаешь — пиши в любой момент!",
            reply_markup=kb.main_menu()
        )
        return
    
    # Проверка на пустое сообщение
    if len(text.strip()) < 3:
        await message.answer(
            "✍️ Напиши подробнее — хотя бы несколько слов 🙏",
            reply_markup=kb.cancel_keyboard()
        )
        return
    
    # Сохраняем сообщение в БД
    message_id = await db.create_support_message(
        user_id=user["id"],
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        message_text=text
    )
    
    await message.answer(
        "✅ <b>Сообщение отправлено!</b>\n\n"
        f"Твой ID тикета: #{message_id}\n\n"
        "Администратор ответит в ближайшее время.\n"
        "Уведомление придёт в этот чат 🔔",
        parse_mode="HTML",
        reply_markup=kb.main_menu()
    )
    
    # Проверяем историю — если это первое сообщение, показываем подсказку
    messages = await db.get_support_messages_by_user(message.from_user.id, limit=2)
    if len(messages) <= 1:
        await message.answer(
            "💡 <b>Совет:</b>\n\n"
            "Ты всегда можешь написать в поддержку снова.\n"
            "История переписки сохраняется.",
            parse_mode="HTML"
        )


# ─── User: View support history ───────────────────────────────────────────────

@router.message(F.text == "📋 История обращений")
async def view_support_history(message: Message, state: FSMContext):
    """Показать историю переписки с поддержкой."""
    await state.clear()
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return
    
    messages = await db.get_support_messages_by_user(message.from_user.id, limit=10)
    
    if not messages:
        await message.answer(
            "📋 <b>История обращений</b>\n\n"
            "Пока нет обращений в поддержку.\n\n"
            "Если есть вопрос или предложение — пиши!",
            parse_mode="HTML",
            reply_markup=kb.main_menu()
        )
        return
    
    # Формируем сообщение с историей
    text = "📋 <b>История обращений</b>\n\n"
    
    for msg in messages[:5]:  # Показываем последние 5
        status_emoji = {
            "new": "🆕",
            "in_progress": "⏳",
            "resolved": "✅",
            "closed": "🔒"
        }.get(msg["status"], "•")
        
        date_str = msg["created_at"][:16].replace("T", " ")
        preview = msg["message_text"][:50] + "..." if len(msg["message_text"]) > 50 else msg["message_text"]
        
        text += f"{status_emoji} <b>#{msg['id']}</b> — {date_str}\n"
        text += f"   {preview}\n"
        
        if msg.get("admin_reply"):
            reply_preview = msg["admin_reply"][:40] + "..." if len(msg["admin_reply"]) > 40 else msg["admin_reply"]
            text += f"   💬 Ответ: {reply_preview}\n"
        
        text += "\n"
    
    if len(messages) > 5:
        text += f"... и ещё {len(messages) - 5} обращений\n"
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb.main_menu()
    )


# ─── Callbacks: Support actions ───────────────────────────────────────────────

@router.callback_query(F.data == "cancel_support")
async def cancel_support_message(callback: CallbackQuery, state: FSMContext):
    """Отмена написания сообщения."""
    await state.clear()
    await callback.message.edit_text(
        "❌ Отменено.\n\n"
        "Если передумаешь — пиши в любой момент!",
        reply_markup=kb.main_menu()
    )
