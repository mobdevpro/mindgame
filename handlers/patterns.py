"""
Handlers for pattern analysis feature.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
import pattern_service as ps
from states import PatternStates

router = Router()


# ─── Pattern analysis command ─────────────────────────────────────────────────

@router.message(F.text == "🧩 Найти паттерны")
async def start_pattern_analysis(message: Message, state: FSMContext):
    """Запуск анализа паттернов."""
    await state.clear()
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запусти бота командой /start")
        return
    
    # Проверяем можно ли запустить анализ
    can_analyze, reason = await ps.can_analyze_patterns(user["id"])
    
    if not can_analyze:
        # Проверяем есть ли предыдущий результат
        last_result = await ps.get_pattern_result(user["id"])
        
        if last_result:
            # Показываем последний результат
            text = ps.format_pattern_message(last_result)
            text += f"\n⚠️ {reason}"
            
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=kb.pattern_result_keyboard(
                    last_result["analysis_id"],
                    last_result["is_processed"]
                )
            )
        else:
            # Показываем ошибку
            await message.answer(
                f"⚠️ {reason}",
                reply_markup=kb.main_menu()
            )
        return
    
    # Запускаем анализ
    loading_message = await message.answer(
        "🤖 <b>AI анализирует ваши триггеры...</b>\n\n"
        "Это займёт 5-10 секунд ⏳",
        parse_mode="HTML"
    )
    
    try:
        result = await ps.run_pattern_analysis(user["id"])
        
        await loading_message.delete()
        
        if not result["ok"]:
            await message.answer(
                f"❌ {result.get('error', 'Ошибка анализа')}",
                reply_markup=kb.main_menu()
            )
            return
        
        # Формируем сообщение с результатом
        analysis_result = result["result"]
        analysis_id = result["analysis_id"]
        
        # Сохраняем в state для последующего использования
        await state.update_data(analysis_id=analysis_id)
        
        text = ps.format_pattern_message({
            "analysis_id": analysis_id,
            "pattern_chain": analysis_result.get("pattern_chain", []),
            "core_belief": analysis_result.get("core_belief", ""),
            "confidence": analysis_result.get("confidence", 0),
            "recommendation": analysis_result.get("recommendation", ""),
            "is_processed": False
        })
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb.pattern_result_keyboard(analysis_id, False)
        )
        
    except Exception as e:
        import logging
        logging.error(f"Pattern analysis error: {e}")
        
        await loading_message.delete()
        await message.answer(
            "❌ Произошла ошибка при анализе. Попробуйте позже.",
            reply_markup=kb.main_menu()
        )


# ─── Callbacks: Process pattern ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("process_pattern:"))
async def on_process_pattern(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет проработать паттерн."""
    analysis_id = int(callback.data.split(":")[1])
    
    # Получаем результат
    result = await ps.get_pattern_result(callback.from_user.id)
    
    if not result or result["analysis_id"] != analysis_id:
        await callback.answer("Результат не найден", show_alert=True)
        return
    
    if result["is_processed"]:
        await callback.answer("Уже проработано", show_alert=True)
        return
    
    # Показываем подтверждение
    await state.set_state(PatternStates.waiting_process_confirm)
    await state.update_data(analysis_id=analysis_id)
    
    await callback.message.edit_text(
        result["text"] if "text" in result else ps.format_pattern_message(result) +
        "\n\n💡 <b>Проработка паттерна</b>\n\n"
        "Это упражнение поможет интегрировать инсайт.\n\n"
        "Вы получите +10 баллов за проработку.\n\n"
        "Продолжить?",
        parse_mode="HTML",
        reply_markup=kb.confirm_keyboard(
            yes_data=f"confirm_process:{analysis_id}",
            no_data="cancel_process"
        )
    )


@router.callback_query(F.data.startswith("confirm_process:"))
async def on_confirm_process(callback: CallbackQuery, state: FSMContext):
    """Подтверждение проработки паттерна."""
    analysis_id = int(callback.data.split(":")[1])
    
    # Награждаем баллами
    result = await ps.mark_pattern_processed(analysis_id, callback.from_user.id)
    
    if result["ok"]:
        await callback.message.edit_text(
            f"✅ <b>Паттерн проработан!</b>\n\n"
            f"🎉 +{result['points']} баллов\n"
            f"💰 Баланс: {result['balance']}\n\n"
            "Инсайт интегрирован. Возвращайтесь через неделю за новым анализом!",
            parse_mode="HTML",
            reply_markup=kb.main_menu()
        )
    else:
        await callback.answer("Ошибка при проработке", show_alert=True)


@router.callback_query(F.data == "cancel_process")
async def on_cancel_process(callback: CallbackQuery):
    """Отмена проработки паттерна."""
    await callback.message.edit_text(
        "❌ Проработка отменена.\n\n"
        "Возвращайтесь когда будете готовы!",
        reply_markup=kb.main_menu()
    )


# ─── Callback: Remind later ───────────────────────────────────────────────────

@router.callback_query(F.data == "remind_pattern_week")
async def on_remind_pattern(callback: CallbackQuery):
    """Напомнить о паттерне через неделю."""
    # TODO: Добавить напоминание в scheduler
    await callback.answer("Напомню через неделю! ⏰", show_alert=True)


# ─── Callback: View clusters ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("view_clusters:"))
async def on_view_clusters(callback: CallbackQuery):
    """Показать кластеры триггеров."""
    user_id = callback.from_user.id
    clusters = await db.get_trigger_clusters(user_id)
    
    if not clusters:
        await callback.answer("Кластеры не найдены", show_alert=True)
        return
    
    text = "🧩 <b>Кластеры триггеров</b>\n\n"
    
    for cluster in clusters[:5]:  # Максимум 5
        level_icon = {1: "📍", 2: "🔍", 3: "💎"}.get(cluster["cluster_level"], "•")
        text += f"{level_icon} <b>{cluster['cluster_theme']}</b>\n"
        text += f"   Триггеров: {len(eval(cluster['trigger_ids']))}\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.back_to_patterns_keyboard()
    )
