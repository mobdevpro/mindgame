from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db

router = Router()


# ─── Entry points ─────────────────────────────────────────────────────────────

@router.message(F.text == "🛍 Магазин")
@router.callback_query(F.data == "show_shop")
async def show_shop(update, state: FSMContext):
    is_callback = isinstance(update, CallbackQuery)
    msg = update.message if is_callback else update
    uid = update.from_user.id

    user = await db.get_user(uid)
    if not user:
        text = "Сначала запусти бота командой /start"
        if is_callback:
            await msg.answer(text)
        else:
            await update.answer(text)
        if is_callback:
            await update.answer()
        return

    balance = user.get("points_balance", 0)
    header = (
        f"🛍 <b>Магазин</b>\n\n"
        f"💰 Твой баланс: <b>{balance} баллов</b>\n\n"
        f"🚧 <b>Магазин в разработке!</b>\n\n"
        f"Скоро здесь появятся:\n"
        f"• 📱 Цифровые материалы\n"
        f"• 🎙 Консультации\n"
        f"• 📚 Курсы\n"
        f"• 🎁 Мерч\n\n"
        f"Следи за обновлениями! 👀"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])

    if is_callback:
        await msg.edit_text(header, parse_mode="HTML", reply_markup=kb)
        await update.answer()
    else:
        await update.answer(header, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "shop_my_purchases")
async def shop_my_purchases_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛒 <b>Мои покупки</b>\n\n"
        f"Покупок пока нет.\n\n"
        f"Магазин скоро откроется! 🚧",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu_cb(callback: CallbackQuery, state: FSMContext):
    from keyboards import main_menu_keyboard
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()
