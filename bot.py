"""
Бот "Карта дня" для Telegram (aiogram 3).

Что умеет:
  🔮 Карта дня        - бесплатно, одна и та же карта в течение суток
  ✨ Расклад на 3     - только для премиум (прошлое / настоящее / будущее)
  💎 Премиум          - описание подписки (оплата пока заглушка)

Настройки берутся из переменных окружения:
  BOT_TOKEN  - токен от @BotFather (обязательно)
  ADMIN_ID   - ваш Telegram ID, чтобы выдавать премиум вручную (необязательно)
"""

import asyncio
import logging
import os
import random
import sqlite3
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", "bot.db")

BTN_CARD = "🔮 Карта дня"
BTN_SPREAD = "✨ Расклад на 3 карты"
BTN_PREMIUM = "💎 Премиум"

KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_CARD)],
        [KeyboardButton(text=BTN_SPREAD), KeyboardButton(text=BTN_PREMIUM)],
    ],
    resize_keyboard=True,
)

DISCLAIMER = "Бот создан для развлечения и вдохновения, а не как прогноз или совет."

# --------------------------------------------------------------------------
# Колода: (название, эмодзи, предсказание). Тексты можно спокойно менять.
# --------------------------------------------------------------------------
CARDS = [
    ("Шут", "🃏", "Сегодня хороший день, чтобы начать что-то новое. Не бойтесь выглядеть неопытным: лёгкость сейчас важнее плана."),
    ("Маг", "🪄", "У вас есть всё нужное для задуманного. Хватит ждать подходящего момента, он уже наступил."),
    ("Жрица", "🌙", "Прислушайтесь к интуиции. Ответ, который вы ищете, уже где-то внутри, просто не торопитесь с выводами."),
    ("Императрица", "🌿", "День тепла и щедрости. Позаботьтесь о себе и о близких, и это вернётся к вам с избытком."),
    ("Император", "👑", "Время навести порядок. Чёткие границы и спокойная твёрдость сегодня сработают лучше любых уговоров."),
    ("Жрец", "📜", "Совет от опытного человека придётся кстати. Не стесняйтесь спросить, как поступил бы тот, кому вы доверяете."),
    ("Влюблённые", "💞", "Сегодня важен выбор сердцем. Решение, в котором вы честны с собой, окажется верным."),
    ("Колесница", "🏇", "Двигайтесь вперёд уверенно. Если держать курс, обстоятельства сами подстроятся под вас."),
    ("Сила", "🦁", "Мягкость сильнее напора. Терпение и доброжелательность помогут справиться с тем, что обычно раздражает."),
    ("Отшельник", "🕯️", "Хороший день для тишины и размышлений. Чуть меньше шума вокруг, и многое станет понятно."),
    ("Колесо фортуны", "🎡", "Что-то меняется, и перемены к лучшему. Будьте готовы поймать неожиданную возможность."),
    ("Справедливость", "⚖️", "Сегодня всё расставится по местам. Поступайте честно, и итог вас устроит."),
    ("Повешенный", "🙃", "Взгляните на ситуацию с другой стороны. Пауза сейчас не потеря времени, а подготовка к рывку."),
    ("Перемены", "🦋", "Старое отпускает место новому. Не держитесь за то, что уже отслужило своё."),
    ("Умеренность", "⏳", "Золотая середина - ваш главный союзник. Не спешите и не тормозите, держите ровный ритм."),
    ("Искушение", "🔥", "Заметьте, что именно вас сегодня манит или держит. Осознанность вернёт вам свободу выбора."),
    ("Башня", "⚡", "Возможна неожиданная встряска, но она убирает лишнее. После неё станет легче дышать."),
    ("Звезда", "⭐", "День надежды. Мечты сегодня ближе, чем кажется, сделайте один маленький шаг к ним."),
    ("Луна", "🌕", "Не всё сегодня ясно, и это нормально. Отложите важные решения до вечера или до утра."),
    ("Солнце", "☀️", "Отличный день. Радость, успех и тёплые новости, позвольте себе насладиться ими."),
    ("Суд", "🎺", "Время подвести итоги и простить себя за старое. Вы готовы к новому этапу."),
    ("Мир", "🌍", "Что-то важное завершается удачно. Отметьте это, вы действительно многое сделали."),
]

# --------------------------------------------------------------------------
# База данных
# --------------------------------------------------------------------------
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
db.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        created_at TEXT,
        premium_until TEXT
    )
    """
)
db.commit()


def register_user(user_id: int, username: str | None) -> None:
    db.execute(
        "INSERT OR IGNORE INTO users (user_id, username, created_at) VALUES (?, ?, ?)",
        (user_id, username, datetime.now().isoformat()),
    )
    db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    db.commit()


def is_premium(user_id: int) -> bool:
    row = db.execute(
        "SELECT premium_until FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not row or not row["premium_until"]:
        return False
    return datetime.fromisoformat(row["premium_until"]) > datetime.now()


def grant_premium(user_id: int, days: int) -> datetime:
    """Выдать или продлить премиум. Когда подключите оплату, вызывайте это после успешного платежа."""
    row = db.execute(
        "SELECT premium_until FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    start = datetime.now()
    if row and row["premium_until"]:
        current = datetime.fromisoformat(row["premium_until"])
        if current > start:
            start = current
    until = start + timedelta(days=days)
    db.execute(
        "INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)",
        (user_id, datetime.now().isoformat()),
    )
    db.execute(
        "UPDATE users SET premium_until = ? WHERE user_id = ?", (until.isoformat(), user_id)
    )
    db.commit()
    return until


# --------------------------------------------------------------------------
# Логика карт
# --------------------------------------------------------------------------
def card_of_the_day(user_id: int):
    # Один и тот же человек в течение суток всегда получает одну карту
    rng = random.Random(f"{user_id}-{date.today().isoformat()}")
    return rng.choice(CARDS)


def three_card_spread():
    return random.sample(CARDS, 3)


# --------------------------------------------------------------------------
# Хендлеры
# --------------------------------------------------------------------------
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    register_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "Привет! Я достаю для вас карту дня 🔮\n\n"
        "Нажмите кнопку ниже и узнайте, что сегодня говорят карты. "
        "Приходите завтра, у каждого дня своя карта.\n\n"
        f"{DISCLAIMER}",
        reply_markup=KEYBOARD,
    )


@dp.message(Command("card"))
@dp.message(F.text == BTN_CARD)
async def send_card(message: Message):
    register_user(message.from_user.id, message.from_user.username)
    name, emoji, text = card_of_the_day(message.from_user.id)
    await message.answer(
        f"{emoji} <b>Ваша карта дня: {name}</b>\n\n{text}\n\n"
        "Хотите глубже? Расклад на три карты доступен в премиуме 💎",
        parse_mode="HTML",
    )


@dp.message(Command("spread"))
@dp.message(F.text == BTN_SPREAD)
async def send_spread(message: Message):
    register_user(message.from_user.id, message.from_user.username)
    if not is_premium(message.from_user.id):
        await message.answer(
            "✨ Расклад на три карты (прошлое, настоящее, будущее) доступен в премиуме.\n"
            "Нажмите «💎 Премиум», чтобы узнать подробности."
        )
        return

    labels = ["Прошлое", "Настоящее", "Будущее"]
    parts = []
    for label, (name, emoji, text) in zip(labels, three_card_spread()):
        parts.append(f"{emoji} <b>{label}: {name}</b>\n{text}")
    await message.answer("\n\n".join(parts), parse_mode="HTML")


@dp.message(Command("premium"))
@dp.message(F.text == BTN_PREMIUM)
async def premium_info(message: Message):
    register_user(message.from_user.id, message.from_user.username)
    if is_premium(message.from_user.id):
        row = db.execute(
            "SELECT premium_until FROM users WHERE user_id = ?", (message.from_user.id,)
        ).fetchone()
        until = datetime.fromisoformat(row["premium_until"]).strftime("%d.%m.%Y")
        await message.answer(f"💎 У вас премиум до {until}. Спасибо, что вы с нами!")
        return

    await message.answer(
        "💎 <b>Премиум</b>\n\n"
        "• расклад на три карты: прошлое, настоящее, будущее\n"
        "• больше раскладов (скоро)\n"
        "• персональный утренний прогноз (скоро)\n\n"
        "Оплата пока не подключена, но скоро здесь появится кнопка подписки.",
        parse_mode="HTML",
    )
    # TODO: сюда добавится кнопка оплаты (Telegram Stars / ЮKassa).
    # После успешной оплаты вызвать: grant_premium(user_id, 30)


@dp.message(Command("grant"))
async def admin_grant(message: Message):
    """Выдать премиум вручную для теста: /grant 123456789 30"""
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("Формат: /grant <user_id> <дней>")
        return
    until = grant_premium(int(parts[1]), int(parts[2]))
    await message.answer(f"Премиум для {parts[1]} выдан до {until:%d.%m.%Y}")


@dp.message(Command("id"))
async def show_id(message: Message):
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")


@dp.message()
async def fallback(message: Message):
    await message.answer("Нажмите кнопку ниже 👇", reply_markup=KEYBOARD)


# --------------------------------------------------------------------------
async def main():
    if not BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Добавьте токен в переменные окружения.")
    logging.basicConfig(level=logging.INFO)
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
