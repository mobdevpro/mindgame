from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
import points_service as ps
from config import CHANNEL_ID, ADMIN_IDS
from states import OnboardingStates

router = Router()

ONBOARDING_STEPS = [
    (
        "🎮 <b>Добро пожаловать в игру осознанности!</b>\n\n"
        "Здесь твоя жизнь – это поле роста.\n"
        "Ты получаешь очки не за маски, а за честность с собой, "
        "осознанность и реальные действия."
    ),
    (
        "👁 <b>Шаг 1 – Замечай</b>\n\n"
        "Каждый раз, когда что-то тебя задело, раздражило или выбило "
        "из равновесия – это триггер.\n\n"
        "Зафиксируй его и получи очки. Ты уже не на автопилоте – "
        "ты наблюдаешь."
    ),
    (
        "⚡ <b>Очки за осознанность</b>\n\n"
        "📝 Запись триггера – очки\n"
        "💭 Назвал эмоцию – ещё очки\n"
        "💡 Нашёл вывод – ещё больше очков\n"
        "📔 Дневник каждый день – бонусы\n"
        "🔥 Серия дней подряд – мультипликатор"
    ),
    (
        "🎯 <b>Реальные действия = реальные награды</b>\n\n"
        "Из каждого триггера рождается действие.\n"
        "Из каждого действия – рост.\n\n"
        "Твои баллы – это не просто цифры. Их можно тратить на "
        "продукты и материалы автора."
    ),
]


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    # Parse referral code from start parameter
    args = message.text.split()
    referral_code = args[1] if len(args) > 1 else None

    referred_by_id = None
    if referral_code:
        async with __import__('aiosqlite').connect(__import__('config').DB_PATH) as conn:
            conn.row_factory = __import__('aiosqlite').Row
            async with conn.execute(
                "SELECT id FROM users WHERE referral_code = ?", (referral_code,)
            ) as cursor:
                ref_user = await cursor.fetchone()
                if ref_user:
                    referred_by_id = ref_user["id"]

    user = await db.get_user(message.from_user.id)
    is_new_user = user is None

    if not user:
        user = await db.create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
            last_name=message.from_user.last_name or "",
            language_code=message.from_user.language_code or "ru",
            referred_by=referred_by_id
        )

    # Award referral points to inviter when new user joins
    if is_new_user and referred_by_id and bot:
        try:
            inviter = await db.get_inviter_by_db_id(referred_by_id)
            if inviter:
                new_balance = await db.award_referral(
                    inviter["telegram_id"],
                    message.from_user.first_name or "Новый игрок"
                )
                await bot.send_message(
                    inviter["telegram_id"],
                    f"🎉 <b>По твоей реферальной ссылке зарегистрировался новый игрок!</b>\n\n"
                    f"👤 {message.from_user.first_name or 'Новый игрок'}\n"
                    f"💰 Тебе начислено <b>+50 баллов</b>\n"
                    f"Новый баланс: {new_balance}",
                    parse_mode="HTML"
                )
        except Exception:
            pass

    if user.get("onboarding_done"):
        await message.answer(
            f"С возвращением, {message.from_user.first_name}! 👋\n\n"
            f"Что фиксируем сегодня?",
            reply_markup=kb.main_menu()
        )
        await message.answer(
            "📱 Или открой полное приложение:",
            reply_markup=kb.webapp_inline_button()
        )
        return

    # Start onboarding
    for i, step_text in enumerate(ONBOARDING_STEPS):
        await message.answer(step_text, parse_mode="HTML")

    # Check subscription
    await ask_subscription(message, state, bot)


async def ask_subscription(message: Message, state: FSMContext, bot: Bot):
    await state.set_state(OnboardingStates.waiting_subscription)
    await message.answer(
        f"🔐 <b>Последний шаг</b>\n\n"
        f"Подпишись на канал {CHANNEL_ID} – там выходят материалы, "
        f"связанные с практикой.\n\n"
        f"После подписки получишь <b>50 стартовых баллов</b> 🎁",
        parse_mode="HTML",
        reply_markup=kb.subscription_keyboard(CHANNEL_ID)
    )


@router.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала запусти бота командой /start")
        return

    # Check subscription via Telegram API
    is_subscribed = await verify_subscription(bot, callback.from_user.id)

    if not is_subscribed:
        await callback.answer(
            "Похоже, ты ещё не подписался. Подпишись и нажми ещё раз! 👇",
            show_alert=True
        )
        return

    if user.get("is_subscribed"):
        # Already subscribed before – just go to menu
        await callback.message.edit_text("✅ Ты уже подписан!")
        await callback.message.answer(
            "Добро пожаловать обратно! 🎮",
            reply_markup=kb.main_menu()
        )
        await state.clear()
        return

    # Mark as subscribed + award points
    await db.update_user(
        callback.from_user.id,
        is_subscribed=1,
        onboarding_done=1
    )
    balance = await ps.award_subscription(callback.from_user.id)

    await callback.message.edit_text(
        f"✅ <b>Подписка подтверждена!</b>\n\n"
        f"🎁 Начислено 50 стартовых баллов\n"
        f"💰 Твой баланс: {balance} баллов\n\n"
        f"Игра началась! Зафиксируй свой первый триггер 👇",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "🎮 <b>Главное меню</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=kb.main_menu()
    )
    await callback.message.answer(
        "📱 Или открой полное приложение:",
        reply_markup=kb.webapp_inline_button()
    )
    await state.clear()
    await callback.answer()


async def verify_subscription(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        # If we can't check (e.g., bot not in channel), allow for local testing
        return True


@router.callback_query(F.data == "go_home")
async def go_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=kb.main_menu()
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 <b>Что умеет этот бот?</b>\n\n"
        "📝 <b>Записать триггер</b> – зафиксируй, что тебя задело\n"
        "📔 <b>Дневник</b> – ежедневная рефлексия\n"
        "📋 <b>Мои триггеры</b> – история наблюдений\n"
        "📊 <b>Прогресс</b> – баллы, уровень, достижения\n"
        "✅ <b>Чек-ин</b> – быстрое состояние прямо сейчас\n\n"
        "Каждое осознанное действие приносит очки! 🎮",
        parse_mode="HTML",
        reply_markup=kb.main_menu()
    )
