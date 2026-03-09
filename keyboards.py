from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

WEBAPP_URL = "https://vadbag.su/app"


def main_menu() -> ReplyKeyboardMarkup:
    from config import get_menu_setting
    builder = ReplyKeyboardBuilder()

    # Row 1: Записать триггер (always) + Дневник (optional)
    row1 = [KeyboardButton(text="📝 Записать триггер")]
    if get_menu_setting("show_diary"):
        row1.append(KeyboardButton(text="📔 Дневник"))
    builder.row(*row1)

    # Row 2: Мои триггеры + Мои задачи (both optional)
    row2 = []
    if get_menu_setting("show_triggers_list"):
        row2.append(KeyboardButton(text="📋 Мои триггеры"))
    if get_menu_setting("show_tasks"):
        row2.append(KeyboardButton(text="✅ Мои задачи"))
    if row2:
        builder.row(*row2)

    # Row 3: Мой прогресс + Быстрый чек-ин (both optional)
    row3 = []
    if get_menu_setting("show_progress"):
        row3.append(KeyboardButton(text="📊 Мой прогресс"))
    if get_menu_setting("show_checkin"):
        row3.append(KeyboardButton(text="✅ Быстрый чек-ин"))
    if row3:
        builder.row(*row3)

    # Row 4: Стоп + Настройки (both optional)
    row4 = []
    if get_menu_setting("show_stop"):
        row4.append(KeyboardButton(text="🛑 Стоп"))
    if get_menu_setting("show_settings"):
        row4.append(KeyboardButton(text="⚙️ Настройки"))
    if row4:
        builder.row(*row4)

    # Row 5: Магазин (optional)
    if get_menu_setting("show_shop"):
        builder.row(KeyboardButton(text="🛍 Магазин"))

    return builder.as_markup(resize_keyboard=True)


def subscription_keyboard(channel_id: str) -> InlineKeyboardMarkup:
    channel = channel_id.lstrip("@")
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📢 Подписаться на канал",
        url=f"https://t.me/{channel}"
    ))
    builder.row(InlineKeyboardButton(
        text="✅ Проверить подписку",
        callback_data="check_subscription"
    ))
    return builder.as_markup()


def skip_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Пропустить", callback_data="skip_step")
    builder.button(text="🏠 В меню", callback_data="go_home")
    return builder.as_markup()


def emotion_keyboard() -> InlineKeyboardMarkup:
    emotions = [
        ("😤 Злость", "anger"),
        ("😔 Грусть", "sadness"),
        ("😨 Страх", "fear"),
        ("😳 Стыд", "shame"),
        ("😟 Тревога", "anxiety"),
        ("😞 Обида", "resentment"),
        ("😤 Раздражение", "irritation"),
        ("😶 Онемение", "numbness"),
    ]
    builder = InlineKeyboardBuilder()
    for label, code in emotions:
        builder.button(text=label, callback_data=f"emotion:{code}")
    builder.button(text="⏭ Пропустить", callback_data="skip_step")
    builder.adjust(2)
    return builder.as_markup()


def intensity_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        emoji = "🔥" if i >= 8 else ("⚡" if i >= 5 else "💧")
        builder.button(text=f"{emoji} {i}", callback_data=f"intensity:{i}")
    builder.button(text="⏭ Пропустить", callback_data="skip_step")
    builder.adjust(5)
    return builder.as_markup()


def after_trigger_keyboard(trigger_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔍 Разобрать глубже",
        callback_data=f"reflect:{trigger_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="📝 Записать ещё",
        callback_data="new_trigger"
    ))
    builder.row(InlineKeyboardButton(
        text="🏠 В главное меню",
        callback_data="go_home"
    ))
    return builder.as_markup()


def triggers_list_keyboard(triggers: list, offset: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in triggers:
        short = t["raw_text"][:35] + "..." if len(t["raw_text"]) > 35 else t["raw_text"]
        emotion = f" {t['emotion_code']}" if t.get("emotion_code") else ""
        builder.row(InlineKeyboardButton(
            text=f"• {short}{emotion}",
            callback_data=f"view_trigger:{t['id']}"
        ))
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"triggers_page:{offset - 10}"))
    if len(triggers) == 10:
        nav.append(InlineKeyboardButton(text="Далее ➡️", callback_data=f"triggers_page:{offset + 10}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="go_home"))
    return builder.as_markup()


def trigger_detail_keyboard(trigger_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔍 Разобрать глубже",
        callback_data=f"reflect:{trigger_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ К списку",
        callback_data="show_triggers"
    ))
    return builder.as_markup()


def mood_keyboard() -> InlineKeyboardMarkup:
    moods = [
        ("😊 Хорошо", "good"),
        ("😐 Нейтрально", "neutral"),
        ("😔 Плохо", "bad"),
        ("😤 Напряжённо", "tense"),
        ("😴 Устало", "tired"),
        ("⚡ Энергично", "energetic"),
    ]
    builder = InlineKeyboardBuilder()
    for label, code in moods:
        builder.button(text=label, callback_data=f"mood:{code}")
    builder.adjust(2)
    return builder.as_markup()


def energy_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=f"energy:{i}")
    builder.button(text="⏭ Пропустить", callback_data="skip_diary_step")
    builder.adjust(5)
    return builder.as_markup()


def confirm_keyboard(yes_data: str, no_data: str = "go_home") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=yes_data)
    builder.button(text="❌ Нет", callback_data=no_data)
    return builder.as_markup()


def task_difficulty_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟢 Лёгкая (+5)", callback_data="task_diff:easy"))
    builder.row(InlineKeyboardButton(text="🟡 Средняя (+12)", callback_data="task_diff:medium"))
    builder.row(InlineKeyboardButton(text="🔴 Сложная (+30)", callback_data="task_diff:hard"))
    builder.row(InlineKeyboardButton(text="🔥 Дискомфортная, но нужная (+50)", callback_data="task_diff:uncomfortable"))
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="go_home"))
    return builder.as_markup()


def tasks_list_keyboard(tasks: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status_icons = {"new": "🆕", "in_progress": "⏳", "done": "✅", "cancelled": "❌"}
    for t in tasks:
        icon = status_icons.get(t["status"], "•")
        short = t["title"][:38] + "…" if len(t["title"]) > 38 else t["title"]
        builder.row(InlineKeyboardButton(
            text=f"{icon} {short}",
            callback_data=f"view_task:{t['id']}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Добавить задачу", callback_data="new_task"))
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="go_home"))
    return builder.as_markup()


def task_detail_keyboard(task_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status in ("new", "in_progress"):
        builder.row(InlineKeyboardButton(
            text="✅ Отметить выполненной",
            callback_data=f"task_done:{task_id}"
        ))
    if status == "new":
        builder.row(InlineKeyboardButton(
            text="⏳ Взять в работу",
            callback_data=f"task_start:{task_id}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ К списку", callback_data="show_tasks"))
    return builder.as_markup()


def stop_feeling_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, code in [
        ("😤 Злость/раздражение", "anger"),
        ("😨 Страх/тревога", "fear"),
        ("😔 Обида/грусть", "sadness"),
        ("😳 Стыд/вина", "shame"),
        ("😶 Онемение", "numbness"),
    ]:
        builder.row(InlineKeyboardButton(text=label, callback_data=f"stop_feel:{code}"))
    return builder.as_markup()


def stop_intensity_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=f"stop_int:{i}")
    builder.adjust(5)
    return builder.as_markup()


def stop_next_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Я готов(а) действовать осознанно", callback_data="stop_done"))
    builder.row(InlineKeyboardButton(text="📝 Записать как триггер", callback_data="new_trigger"))
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="go_home"))
    return builder.as_markup()


def webapp_inline_button() -> InlineKeyboardMarkup:
    """Inline-кнопка для открытия Mini App — надёжнее ReplyKeyboard на всех клиентах."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🎮 Открыть приложение",
        web_app=WebAppInfo(url=WEBAPP_URL)
    ))
    return builder.as_markup()
