"""
Бот "Карта дня" для Telegram (aiogram 3).

Экран остаётся чистым: внизу одна кнопка «🔮 Карта дня», остальное в меню команд («/» у поля ввода).

  /card     - карта дня (то же, что кнопка), картинка + кнопка «Поделиться»
  /spread   - расклад на 3 карты (только премиум)
  /premium  - про премиум
  /remind   - утреннее напоминание «карта готова»: /remind (вкл/выкл) или /remind 08:30 (время по Москве)

Рядом должны лежать cardart.py (рисует карточки) и папка fonts/.

Переменные окружения:
  BOT_TOKEN  - токен от @BotFather (обязательно)
  ADMIN_ID   - ваш Telegram ID, чтобы выдавать премиум вручную (необязательно)
"""

import asyncio
import logging
import os
import random
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from cardart import render_card

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", "bot.db")

REFERRAL_DAYS = 1            # дней премиума тому, кто пригласил друга
DEFAULT_REMIND_TIME = "09:00"  # время напоминания по умолчанию (по Москве)
REMIND_WINDOW_MIN = 180      # если бот был выключен и опоздал больше чем на 3 часа, напоминание пропускаем
MSK = timezone(timedelta(hours=3))

BOT_USERNAME = ""  # заполняется при запуске

BTN_CARD = "🔮 Карта дня"

# Одна-единственная кнопка внизу экрана
KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_CARD)]],
    resize_keyboard=True,
)

MENU_COMMANDS = [
    BotCommand(command="card", description="Карта дня"),
    BotCommand(command="spread", description="Расклад на 3 карты (премиум)"),
    BotCommand(command="premium", description="Премиум"),
    BotCommand(command="remind", description="Утреннее напоминание"),
]

# Тексты утренних напоминаний. Саму карту в них не раскрываем, только что она готова.
REMIND_TEXTS = [
    "🔮 Ваша карта дня готова и ждёт вас.",
    "✨ Карта на сегодня уже выбрана. Загляните, что она говорит.",
    "🌅 Доброе утро! Ваша карта дня уже ждёт.",
    "🃏 Карта дня готова. Откроете?",
]

# --------------------------------------------------------------------------
# Колода: (название, эмодзи, предсказание). ПОРЯДОК ВАЖЕН: он совпадает с рисунками в cardart.py.
# Тексты можно спокойно менять, а вот порядок и количество (22) лучше не трогать.
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
        premium_until TEXT,
        remind INTEGER DEFAULT 1,
        remind_time TEXT DEFAULT '09:00',
        last_reminded TEXT
    )
    """
)
# Если таблица осталась от старой версии бота, добавляем недостающие столбцы
_cols = {r["name"] for r in db.execute("PRAGMA table_info(users)")}
for _col, _ddl in [
    ("remind", "INTEGER DEFAULT 1"),
    ("remind_time", "TEXT DEFAULT '09:00'"),
    ("last_reminded", "TEXT"),
]:
    if _col not in _cols:
        db.execute(f"ALTER TABLE users ADD COLUMN {_col} {_ddl}")
db.commit()


def now_msk() -> datetime:
    return datetime.now(MSK)


def register_user(user_id: int, username: str | None) -> bool:
    """Регистрирует пользователя. Возвращает True, если он зашёл впервые."""
    cur = db.execute(
        "INSERT OR IGNORE INTO users (user_id, username, created_at, last_reminded) VALUES (?, ?, ?, ?)",
        # last_reminded = сегодня, чтобы новичку не прилетело напоминание сразу после /start
        (user_id, username, datetime.now().isoformat(), now_msk().date().isoformat()),
    )
    is_new = cur.rowcount == 1
    db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    db.commit()
    return is_new


def user_exists(user_id: int) -> bool:
    return db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone() is not None


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
# Карты и картинки
# --------------------------------------------------------------------------
def card_index_of_the_day(user_id: int) -> int:
    # Один и тот же человек в течение суток всегда получает одну карту
    rng = random.Random(f"{user_id}-{now_msk().date().isoformat()}")
    return rng.randrange(len(CARDS))


async def card_image(idx: int, filename: str) -> BufferedInputFile:
    name, _emoji, text = CARDS[idx]
    data = await asyncio.to_thread(render_card, idx, name, text, f"@{BOT_USERNAME}")
    return BufferedInputFile(data, filename=filename)


def share_keyboard(user_id: int, name: str, emoji: str) -> InlineKeyboardMarkup:
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    text = f"Моя карта дня: {name} {emoji}. А какая у тебя? 🔮"
    url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(text, safe='')}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📤 Поделиться", url=url)]]
    )


# --------------------------------------------------------------------------
# Утренние напоминания
# --------------------------------------------------------------------------
async def run_reminders_once(bot: Bot) -> int:
    """Один проход: отправляет напоминание тем, у кого пришло время. Возвращает число отправленных."""
    now = now_msk()
    today = now.date().isoformat()
    cur_min = now.hour * 60 + now.minute
    rows = db.execute(
        "SELECT user_id, remind_time FROM users "
        "WHERE remind = 1 AND (last_reminded IS NULL OR last_reminded != ?)",
        (today,),
    ).fetchall()

    sent = 0
    for row in rows:
        try:
            h, m = map(int, (row["remind_time"] or DEFAULT_REMIND_TIME).split(":"))
        except ValueError:
            continue
        diff = cur_min - (h * 60 + m)
        if not (0 <= diff <= REMIND_WINDOW_MIN):
            continue

        uid = row["user_id"]
        try:
            await bot.send_message(uid, random.choice(REMIND_TEXTS))
            sent += 1
        except TelegramForbiddenError:
            # Человек заблокировал бота: больше не беспокоим
            db.execute("UPDATE users SET remind = 0 WHERE user_id = ?", (uid,))
            db.commit()
            continue
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            continue
        except TelegramBadRequest:
            pass  # чат недоступен, просто отметим как обработанного на сегодня
        db.execute("UPDATE users SET last_reminded = ? WHERE user_id = ?", (today, uid))
        db.commit()
        await asyncio.sleep(0.05)  # не превышаем лимит Telegram (около 30 сообщений в секунду)
    return sent


async def reminder_loop(bot: Bot):
    while True:
        try:
            await run_reminders_once(bot)
        except Exception:
            logging.exception("Ошибка в рассылке напоминаний")
        await asyncio.sleep(30)


# --------------------------------------------------------------------------
# Хендлеры
# --------------------------------------------------------------------------
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot):
    user_id = message.from_user.id
    is_new = register_user(user_id, message.from_user.username)

    # Реферальная ссылка: /start ref_123456
    arg = command.args or ""
    if is_new and arg.startswith("ref_") and arg[4:].isdigit():
        inviter = int(arg[4:])
        if inviter != user_id and user_exists(inviter):
            until = grant_premium(inviter, REFERRAL_DAYS)
            try:
                await bot.send_message(
                    inviter,
                    f"🎉 По вашей ссылке зашёл друг! Премиум продлён до {until:%d.%m.%Y}.",
                )
            except (TelegramForbiddenError, TelegramBadRequest):
                pass

    await message.answer(
        "Привет! Я достаю для вас карту дня 🔮\n\n"
        "Нажмите кнопку внизу. Каждое утро в 9:00 по Москве напомню, что карта готова "
        "(выключить: /remind).\n\n"
        "Бот создан для развлечения.",
        reply_markup=KEYBOARD,
    )


@dp.message(Command("card"))
@dp.message(F.text == BTN_CARD)
async def send_card(message: Message):
    user_id = message.from_user.id
    register_user(user_id, message.from_user.username)
    idx = card_index_of_the_day(user_id)
    name, emoji, text = CARDS[idx]
    caption = f"{emoji} <b>{name}</b>"
    try:
        photo = await card_image(idx, f"card_{idx}.jpg")
        await message.answer_photo(
            photo, caption=caption, parse_mode="HTML",
            reply_markup=share_keyboard(user_id, name, emoji),
        )
    except Exception:
        # Если с картинкой что-то пошло не так, отправляем обычный текст
        logging.exception("Не удалось отправить картинку")
        await message.answer(
            f"{emoji} <b>{name}</b>\n\n{text}",
            parse_mode="HTML",
            reply_markup=share_keyboard(user_id, name, emoji),
        )


@dp.message(Command("spread"))
async def send_spread(message: Message):
    register_user(message.from_user.id, message.from_user.username)
    if not is_premium(message.from_user.id):
        await message.answer("✨ Расклад на три карты есть в премиуме: /premium")
        return

    labels = ["Прошлое", "Настоящее", "Будущее"]
    picked = random.sample(range(len(CARDS)), 3)
    try:
        media = [
            InputMediaPhoto(media=await card_image(idx, f"spread_{i}.jpg"))
            for i, idx in enumerate(picked)
        ]
        await message.answer_media_group(media)
    except Exception:
        logging.exception("Не удалось отправить альбом")

    parts = []
    for label, idx in zip(labels, picked):
        name, emoji, text = CARDS[idx]
        parts.append(f"{emoji} <b>{label}: {name}</b>\n{text}")
    await message.answer("\n\n".join(parts), parse_mode="HTML")


@dp.message(Command("premium"))
async def premium_info(message: Message):
    register_user(message.from_user.id, message.from_user.username)
    if is_premium(message.from_user.id):
        row = db.execute(
            "SELECT premium_until FROM users WHERE user_id = ?", (message.from_user.id,)
        ).fetchone()
        until = datetime.fromisoformat(row["premium_until"]).strftime("%d.%m.%Y")
        await message.answer(f"💎 Премиум активен до {until}.")
        return

    await message.answer(
        "💎 <b>Премиум</b>: расклад на три карты, новые расклады и утренние прогнозы (скоро).\n\n"
        f"Бесплатно: делитесь картой дня, за каждого нового друга +{REFERRAL_DAYS} день.\n\n"
        "Оплата появится позже.",
        parse_mode="HTML",
    )
    # TODO: сюда добавится кнопка оплаты (Telegram Stars / ЮKassa).
    # После успешной оплаты вызвать: grant_premium(user_id, 30)


@dp.message(Command("remind"))
async def cmd_remind(message: Message, command: CommandObject):
    """/remind - включить или выключить, /remind 08:30 - задать время (по Москве)."""
    user_id = message.from_user.id
    register_user(user_id, message.from_user.username)
    arg = (command.args or "").strip()

    if arg:
        m = re.fullmatch(r"([01]?\d|2[0-3])[:.]([0-5]\d)", arg)
        if not m:
            await message.answer("Укажите время так: /remind 08:30 (по Москве)")
            return
        t = f"{int(m.group(1)):02d}:{m.group(2)}"
        # если время сегодня уже прошло, не шлём напоминание сегодня
        now = now_msk()
        already_passed = (now.hour * 60 + now.minute) >= (int(m.group(1)) * 60 + int(m.group(2)))
        db.execute(
            "UPDATE users SET remind = 1, remind_time = ?, last_reminded = ? WHERE user_id = ?",
            (t, now.date().isoformat() if already_passed else None, user_id),
        )
        db.commit()
        await message.answer(f"🔔 Буду напоминать каждое утро в {t} по Москве.")
        return

    row = db.execute("SELECT remind, remind_time FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if row["remind"]:
        db.execute("UPDATE users SET remind = 0 WHERE user_id = ?", (user_id,))
        db.commit()
        await message.answer("🔕 Напоминания выключены. Включить снова: /remind")
    else:
        db.execute("UPDATE users SET remind = 1 WHERE user_id = ?", (user_id,))
        db.commit()
        await message.answer(
            f"🔔 Напоминания включены: каждое утро в {row['remind_time'] or DEFAULT_REMIND_TIME} по Москве.\n"
            "Другое время: /remind 08:30"
        )


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
    await message.answer("Нажмите кнопку внизу 👇", reply_markup=KEYBOARD)


# --------------------------------------------------------------------------
async def main():
    global BOT_USERNAME
    if not BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Добавьте токен в переменные окружения.")
    logging.basicConfig(level=logging.INFO)
    bot = Bot(BOT_TOKEN)
    BOT_USERNAME = (await bot.get_me()).username
    await bot.set_my_commands(MENU_COMMANDS)
    reminder_task = asyncio.create_task(reminder_loop(bot))  # noqa: F841 (держим ссылку)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
