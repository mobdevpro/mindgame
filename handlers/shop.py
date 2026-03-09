from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db

router = Router()


def shop_catalog_keyboard(products: list, user_purchases: list) -> object:
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    purchased_ids = {p["product_id"] for p in user_purchases}
    buttons = []
    for p in products:
        is_bought = p["id"] in purchased_ids
        label = f"{'✅' if is_bought else '🛒'} {p['title']} — {p['price_points']} ⭐"
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"shop_item:{p['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="📦 Мои покупки", callback_data="shop_my_purchases")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shop_item_keyboard(product_id: int, can_buy: bool, already_bought: bool) -> object:
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    if already_bought:
        buttons.append([InlineKeyboardButton(text="✅ Уже куплено", callback_data="noop")])
    elif can_buy:
        buttons.append([InlineKeyboardButton(text="💳 Купить", callback_data=f"shop_buy:{product_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="❌ Недостаточно баллов", callback_data="noop")])
    buttons.append([InlineKeyboardButton(text="🔙 Магазин", callback_data="show_shop")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def purchases_keyboard() -> object:
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 В магазин", callback_data="show_shop")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])


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

    products = await db.get_products(active_only=True)
    purchases = await db.get_user_purchases(user["id"])

    balance = user.get("points_balance", 0)
    header = (
        f"🛍 <b>Магазин</b>\n\n"
        f"💰 Твой баланс: <b>{balance} баллов</b>\n\n"
    )

    if not products:
        header += "Товары скоро появятся. Следи за обновлениями! 👀"
        kb = purchases_keyboard()
    else:
        header += f"Доступно товаров: {len(products)}\nВыбери товар:"
        kb = shop_catalog_keyboard(products, purchases)

    if is_callback:
        await msg.edit_text(header, parse_mode="HTML", reply_markup=kb)
        await update.answer()
    else:
        await update.answer(header, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("shop_item:"))
async def shop_item(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])
    uid = callback.from_user.id

    product = await db.get_product(product_id)
    if not product:
        await callback.answer("Товар не найден")
        return

    user = await db.get_user(uid)
    purchases = await db.get_user_purchases(user["id"])
    purchased_ids = {p["product_id"] for p in purchases}

    balance = user.get("points_balance", 0)
    price = product.get("price_points", 0)
    already_bought = product_id in purchased_ids
    can_buy = balance >= price and not already_bought

    category_labels = {
        "digital": "📱 Цифровой",
        "consultation": "🎙 Консультация",
        "course": "📚 Курс",
        "merch": "🎁 Мерч",
    }
    cat = category_labels.get(product.get("category", "digital"), "📦 Товар")

    text = (
        f"🛒 <b>{product['title']}</b>\n\n"
        f"{product.get('description', '')}\n\n"
        f"Категория: {cat}\n"
        f"Цена: <b>{price} ⭐ баллов</b>\n"
        f"Твой баланс: {balance} ⭐\n"
    )
    if already_bought:
        text += "\n✅ <i>Ты уже приобрёл этот товар.</i>"
    elif not can_buy:
        need = price - balance
        text += f"\n❌ <i>Не хватает {need} баллов. Продолжай практики!</i>"

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=shop_item_keyboard(product_id, can_buy, already_bought)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop_buy:"))
async def shop_buy(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])
    uid = callback.from_user.id

    result = await db.buy_product(uid, product_id)

    if not result["ok"]:
        error = result.get("error", "Ошибка")
        msgs = {
            "not_found": "Товар не найден или недоступен.",
            "no_stock": "Товар закончился.",
            "insufficient_funds": f"Недостаточно баллов. Нужно {result.get('need', '?')}, у тебя {result.get('balance', '?')}.",
        }
        await callback.answer(msgs.get(error, error), show_alert=True)
        return

    product = result["product"]
    await callback.message.edit_text(
        f"🎉 <b>Покупка успешна!</b>\n\n"
        f"✅ <b>{product['title']}</b>\n\n"
        f"💸 Потрачено: {result['spent']} баллов\n"
        f"💰 Остаток: {result['balance']} баллов\n\n"
        f"<i>Спасибо за покупку! Мы свяжемся с тобой по поводу получения.</i>",
        parse_mode="HTML",
        reply_markup=purchases_keyboard()
    )
    await callback.answer("🎉 Куплено!")


@router.callback_query(F.data == "shop_my_purchases")
async def shop_my_purchases(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    user = await db.get_user(uid)
    if not user:
        await callback.answer("Ошибка")
        return

    purchases = await db.get_user_purchases(user["id"])

    if not purchases:
        text = (
            "📦 <b>Мои покупки</b>\n\n"
            "Ты ещё ничего не покупал.\n"
            "Зарабатывай баллы за практики и трать их в магазине! 🛍"
        )
    else:
        lines = [f"📦 <b>Мои покупки</b> ({len(purchases)}):\n"]
        for pu in purchases:
            lines.append(
                f"• <b>{pu['title']}</b> — {pu['points_amount']} ⭐\n"
                f"  <i>{str(pu['created_at'])[:10]}</i>"
            )
        text = "\n".join(lines)

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=purchases_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu_cb(callback: CallbackQuery, state: FSMContext):
    from keyboards import main_menu_keyboard
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()
