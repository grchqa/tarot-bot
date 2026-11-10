"""Карта дня: тёмная карточка с золотой рамкой (Pillow).
Название, короткий текст и блок «Напутствие дня». Ничего скачивать не нужно: всё рисуется кодом.
Шрифты те же, что в cardart.py (DejaVuSerif-Italic.ttf и DejaVuSerif-Bold.ttf).

Главное:
  CARDS                       - список карт дня (название, подводка, текст, напутствие)
  card_index_for(user_id)     - какая карта выпала этому человеку сегодня (по Москве).
                                В течение дня одна и та же, на следующий день другая,
                                пока не пройдёт вся колода, потом порядок перемешивается заново.
  render_day_card(idx, wm)    - JPEG-байты картинки (результат кэшируется)
"""

import functools
import io
import logging
import math
import os
import random
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 840, 1290
BRONZE = (190, 146, 92)
GOLD_LIGHT = (240, 214, 160)
GOLD_DARK = (170, 122, 68)
LEAD_COLOR = (226, 198, 148)
TEXT_COLOR = (232, 222, 206)
DARK = (16, 12, 10)
CW = 600  # ширина колонки с текстом

MSK = timezone(timedelta(hours=3), "MSK")

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [
    os.path.join(BASE, "fonts"),
    BASE,  # если файлы шрифтов лежат рядом, без папки
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
    "/Library/Fonts",
]

# --------------------------------------------------------------------------
# Карты дня. title - название, lead - подводка, body - текст (абзацы через пустую строку),
# hint - «Напутствие дня». Можно спокойно править и добавлять свои.
# --------------------------------------------------------------------------
CARDS = [
    {
        "title": "Тишина",
        "lead": "Ответ часто приходит не громче шёпота.",
        "body": "Мир вокруг шумит, и кажется, что нужно успеть услышать всех. Но самое важное звучит тогда, когда замолкаешь сам.\n\nОставь в сегодняшнем дне хотя бы несколько минут без телефона и чужих мнений.",
        "hint": "Послушай тишину. В ней уже есть то, что ты ищешь.",
    },
    {
        "title": "Первый шаг",
        "lead": "Большая дорога начинается с очень маленького движения.",
        "body": "Тебе не нужен весь план целиком. Достаточно увидеть следующий шаг и сделать его, пока сомнения не успели собраться с мыслями.\n\nДаже неидеальное начало лучше идеального ожидания.",
        "hint": "Сделай сегодня одно маленькое дело для своей мечты.",
    },
    {
        "title": "Доверие",
        "lead": "Не всё нужно проверять, чтобы оно оказалось правдой.",
        "body": "Ты тратишь много сил на то, чтобы держать всё под контролем. Жизнь умеет складываться и без твоего постоянного надзора.\n\nДоверие не наивность, а умение отдохнуть от тревоги.",
        "hint": "Разреши событиям идти своим ходом. Ты справишься с любым поворотом.",
    },
    {
        "title": "Границы",
        "lead": "Сказать «нет» одному значит сказать «да» себе.",
        "body": "Ты не обязан быть удобным для каждого. Забота о других не требует, чтобы ты исчезал сам.\n\nТам, где заканчиваются твои силы, начинаются твои границы, и они заслуживают уважения.",
        "hint": "Выбери одно «нет», которое давно просится наружу, и скажи его спокойно.",
    },
    {
        "title": "Терпение",
        "lead": "Зерно растёт и тогда, когда его не видно.",
        "body": "Результат пока не заметен, но это не значит, что ничего не происходит. Самые важные перемены созревают медленно, под землёй.\n\nНе дёргай росток, чтобы проверить, как он растёт.",
        "hint": "Продолжай идти ровно. Твоё время уже в пути.",
    },
    {
        "title": "Благодарность",
        "lead": "Заметить хорошее значит притянуть ещё больше хорошего.",
        "body": "Мы быстро привыкаем к тому, что есть, и видим лишь то, чего не хватает. Но стоит оглянуться, и находится много тёплого: люди, мгновения, маленькие удачи.",
        "hint": "Назови сегодня три вещи, за которые ты благодарен.",
    },
    {
        "title": "Выбор",
        "lead": "Перед тобой не одна дорога, а несколько.",
        "body": "Ты ждёшь знака, что правильно, а что нет. Но чаще всего ошибочных выборов не бывает, бывают выборы, которые ты потом наполняешь смыслом.\n\nПрислушайся, к какому варианту тянется сердце.",
        "hint": "Выбери то, после чего тебе легче дышать.",
    },
    {
        "title": "Перемены",
        "lead": "Ветер перемен не спрашивает, готов ли ты.",
        "body": "Что-то привычное меняет форму. Это может пугать, но вместе с этим освобождает место для нового.\n\nГибкое дерево не ломается на ветру, оно учится танцевать с ним.",
        "hint": "Встреть перемену с любопытством, а не с тревогой.",
    },
    {
        "title": "Дом",
        "lead": "Сила возвращается туда, где тебе спокойно.",
        "body": "Дом это не только стены. Это место, человек или занятие, рядом с которыми можно выдохнуть и стать собой.\n\nСегодня сделай что-то, что добавит тепла твоему личному месту силы.",
        "hint": "Позаботься о своём уголке покоя: он питает тебя.",
    },
    {
        "title": "Смелость",
        "lead": "Страх никуда не уходит, он просто идёт рядом.",
        "body": "Смелость не в том, чтобы ничего не бояться. Она в том, чтобы пойти, даже когда дрожат колени.\n\nТо, что ты откладываешь из-за страха, часто оказывается проще, чем казалось.",
        "hint": "Сделай шаг навстречу тому, что пугает, и убедись, что ты сильнее.",
    },
    {
        "title": "Отдых",
        "lead": "Пауза тоже часть пути.",
        "body": "Ты давно бежишь и не замечаешь усталости. Но без отдыха не рождаются ни идеи, ни радость, ни силы.\n\nПозволь себе замедлиться и не считай это слабостью.",
        "hint": "Подари себе сегодня час, в котором ты никому ничего не должен.",
    },
    {
        "title": "Интуиция",
        "lead": "Внутренний голос редко кричит, но почти никогда не ошибается.",
        "body": "Ты уже знаешь ответ, просто пока не доверяешь ему. Он приходит как тихое «да» или едва заметное «нет» где-то в глубине.\n\nУчись различать его среди шума мыслей.",
        "hint": "Первое, что подсказало сердце, достойно внимания.",
    },
    {
        "title": "Ясность",
        "lead": "Туман рассеивается, когда делаешь шаг вперёд.",
        "body": "Ты хочешь увидеть весь путь заранее, но ясность приходит по мере движения.\n\nЕсли что-то остаётся неясным, значит время ещё не пришло. Занимайся тем, что понятно уже сейчас.",
        "hint": "Сделай то, что очевидно. Остальное прояснится.",
    },
    {
        "title": "Прощение",
        "lead": "Тяжёлая ноша становится легче, когда её опускают.",
        "body": "Обида держит тебя на привязи у прошлого. Простить не значит оправдать, это значит больше не расплачиваться за чужие поступки собственным покоем.\n\nНачни с прощения себя.",
        "hint": "Позволь себе быть несовершенным и всё равно достойным любви.",
    },
    {
        "title": "Дорога",
        "lead": "Не важно, как быстро ты идёшь, важно, что ты идёшь.",
        "body": "Иногда кажется, что другие давно впереди. Но у каждого своя дорога, свои повороты и свой темп.\n\nСравнивай себя только с собой вчерашним, и ты заметишь, как далеко зашёл.",
        "hint": "Иди в своём ритме. Дорога знает, куда ведёт.",
    },
    {
        "title": "Встреча",
        "lead": "Нужный человек появляется, когда ты занят своей жизнью.",
        "body": "Не ищи встречи с напряжением. Живи, делай то, что любишь, оставайся открытым, и нужные люди найдут тебя сами.\n\nЛюбой разговор сегодня может оказаться неслучайным.",
        "hint": "Будь внимателен к людям рядом: среди них кто-то важный.",
    },
    {
        "title": "Рост",
        "lead": "Неудобство часто признак того, что ты растёшь.",
        "body": "Тесно в старой одежде не потому, что с тобой что-то не так. Ты просто стал больше прежних рамок.\n\nНе возвращайся в старое, учись жить в новом размере.",
        "hint": "Позволь себе быть тем, кем ты становишься.",
    },
    {
        "title": "Свет",
        "lead": "Даже одна свеча разгоняет тьму.",
        "body": "В самый трудный день рядом всегда есть что-то светлое: тёплое слово, красивое небо, чашка чая. Заметь это.\n\nСвет, который ты даёшь другим, возвращается к тебе.",
        "hint": "Сегодня стань для кого-то маленьким источником тепла.",
    },
    {
        "title": "Тень",
        "lead": "То, что ты прячешь, управляет тобой сильнее, чем то, что признаёшь.",
        "body": "У каждого есть качества, которые он стыдится показывать. Но именно в них часто скрыта сила.\n\nПосмотри на свои тёмные стороны без осуждения, и они перестанут быть врагами.",
        "hint": "Прими в себе то, что раньше отталкивал.",
    },
    {
        "title": "Баланс",
        "lead": "Равновесие это не неподвижность, а умение возвращаться.",
        "body": "Работа и отдых, давать и принимать, говорить и слушать. Если одна чаша перевешивает, жизнь начинает крениться.\n\nПроверь, чего сейчас слишком много, а чего не хватает.",
        "hint": "Верни в этот день то, чего тебе недоставало.",
    },
    {
        "title": "Простота",
        "lead": "Лишнее утяжеляет, нужное делает лёгким.",
        "body": "Ты усложняешь там, где можно сделать проще. Не каждое дело требует глубокого анализа и десяти вариантов.\n\nСпроси себя: что здесь по-настоящему важно?",
        "hint": "Убери сегодня одну лишнюю заботу из своего списка.",
    },
    {
        "title": "Радость",
        "lead": "Радость не награда за труд, а топливо для него.",
        "body": "Ты ждёшь, пока закончатся дела, чтобы позволить себе удовольствие. Но дела никогда не заканчиваются.\n\nМаленькая радость сегодня даёт больше сил, чем большая когда-нибудь потом.",
        "hint": "Сделай что-нибудь просто потому, что тебе это нравится.",
    },
    {
        "title": "Забота о себе",
        "lead": "Нельзя налить из пустого кувшина.",
        "body": "Ты привык заботиться о других и откладывать себя на потом. Но твои силы не бесконечны, им тоже нужна подпитка.\n\nЗабота о себе не эгоизм, а основа для всего остального.",
        "hint": "Спроси себя, что тебе нужно прямо сейчас, и исполни это.",
    },
    {
        "title": "Завершение",
        "lead": "Закрытая дверь освобождает руки для новой.",
        "body": "Что-то подходит к концу, и это естественно. Незавершённые дела тянут вниз, как открытые вкладки в голове.\n\nПоставь точку там, где история уже рассказана, и поблагодари её.",
        "hint": "Закончи сегодня одно давнее дело.",
    },
    {
        "title": "Начало",
        "lead": "Чистая страница пугает и вдохновляет одновременно.",
        "body": "Ты стоишь на пороге нового. Ничего ещё не решено, а значит возможно всё.\n\nНе тащи в начало багаж старых ожиданий. Дай новому шанс стать собой.",
        "hint": "Начни так, как будто у тебя всё получится.",
    },
    {
        "title": "Свобода",
        "lead": "Самые крепкие цепи те, что мы надели на себя сами.",
        "body": "Подумай, какие «надо» и «должен» ты носишь, хотя никто их не требует. Многие правила давно потеряли смысл.\n\nСвобода начинается с разрешения быть другим.",
        "hint": "Нарушь сегодня одно собственное ненужное правило.",
    },
    {
        "title": "Мудрость",
        "lead": "Опыт становится мудростью, когда его осмыслишь.",
        "body": "Всё, через что ты прошёл, чему-то тебя научило, даже самое болезненное. Оглянись и найди этот урок.\n\nТы знаешь больше, чем думаешь.",
        "hint": "Доверься тому, чему тебя научила жизнь.",
    },
    {
        "title": "Единство",
        "lead": "Вместе мы можем то, что не под силу одному.",
        "body": "Ты не обязан справляться со всем в одиночку. Просить о помощи это тоже умение.\n\nОбратись сегодня к тому, кто рядом, и позволь ему быть полезным.",
        "hint": "Не отказывайся от поддержки. Она делает сильнее.",
    },
    {
        "title": "Огонь",
        "lead": "Страсть это энергия, которой нужно русло.",
        "body": "В тебе горит желание что-то сделать, создать, изменить. Не гаси его сомнением, но и не давай сжечь себя дотла.\n\nНаправь огонь в дело, которое тебе дорого.",
        "hint": "Отдай сегодняшнюю энергию тому, что действительно важно.",
    },
    {
        "title": "Вода",
        "lead": "Вода обходит камни и всё равно достигает моря.",
        "body": "Если путь закрыт, не бейся о стену. Найди обход, подожди разлива, измени русло.\n\nГибкость не поражение, а способ дойти до цели.",
        "hint": "Будь как вода: мягким, но настойчивым.",
    },
]

_cache: dict = {}


# --------------------------------------------------------------------------
# Выбор карты
# --------------------------------------------------------------------------
def card_index_for(user_id: int, day=None) -> int:
    """Карта дня для человека: в течение дня одна и та же, завтра другая.
    Колода проходится целиком по кругу, порядок у каждого человека свой."""
    day = day or datetime.now(MSK).date()
    n = len(CARDS)
    order = list(range(n))
    random.Random(user_id * 7919 + day.toordinal() // n).shuffle(order)
    return order[day.toordinal() % n]


# --------------------------------------------------------------------------
# Рисование
# --------------------------------------------------------------------------
@functools.lru_cache(maxsize=64)
def _font(names, size):
    for d in FONT_DIRS:
        for n in names:
            path = os.path.join(d, n)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    logging.warning("Шрифт %s не найден: русский текст на картах будет квадратиками. "
                    "Положите файлы .ttf рядом с dayart.py или в папку fonts.", names[0])
    return ImageFont.load_default(size)


def _wrap(text, font, max_w):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if font.getlength(trial) <= max_w:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _background():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=_lerp((26, 20, 16), (13, 10, 9), y / (H - 1)))
    # тёплое свечение за текстом
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W * 0.12, H * 0.22, W * 0.88, H * 0.78], fill=(40, 26, 14))
    img = ImageChops.add(img, glow.filter(ImageFilter.GaussianBlur(160)))
    # зерно, как на старой бумаге
    noise = Image.effect_noise((W, H), 40).convert("RGB")
    img = Image.blend(img, noise, 0.035)
    # пылинки
    rng = random.Random(11)
    d = ImageDraw.Draw(img)
    for _ in range(260):
        x, y = rng.randint(0, W), rng.randint(0, H)
        r = rng.choice([1, 1, 1, 2])
        v = rng.randint(34, 58)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(v + 8, v, v - 8))
    # затемнение по краям
    vig = Image.new("L", (W, H), 110)
    ImageDraw.Draw(vig).ellipse([-W * 0.15, -H * 0.1, W * 1.15, H * 1.1], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(170))
    return Image.composite(img, Image.new("RGB", (W, H), (6, 4, 3)), vig)


def _star_pts(cx, cy, r_out, r_in, n):
    pts = []
    for i in range(n * 2):
        ang = -math.pi / 2 + i * math.pi / n
        rr = r_out if i % 2 == 0 else r_in
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return pts


def _diamond(d, cx, cy, r, fill=BRONZE, outline=None, width=2):
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=fill, outline=outline, width=width)


def _divider(d, cx, y, half=170):
    d.line([(cx - half, y), (cx - 22, y)], fill=BRONZE, width=2)
    d.line([(cx + 22, y), (cx + half, y)], fill=BRONZE, width=2)
    _diamond(d, cx, y, 8)
    _diamond(d, cx - half - 8, y, 3)
    _diamond(d, cx + half + 8, y, 3)


def _braid(d, horizontal, center, start, end, amp=8, wl=46, w=5):
    """Плетёный шнур: две волны, которые поочерёдно идут сверху и снизу."""
    half = wl / 2

    def pts(t0, t1, sign):
        out = []
        steps = 16
        for i in range(steps + 1):
            t = t0 + (t1 - t0) * i / steps
            off = sign * amp * math.sin(2 * math.pi * (t - start) / wl)
            out.append((t, center + off) if horizontal else (center + off, t))
        return out

    k = 0
    while start + k * half < end:
        t0 = start + k * half
        t1 = min(end, t0 + half)
        top, bottom = (1, -1) if k % 2 == 0 else (-1, 1)
        d.line(pts(t0, t1, bottom), fill=BRONZE, width=w, joint="curve")
        d.line(pts(t0, t1, top), fill=DARK, width=w + 5, joint="curve")
        d.line(pts(t0, t1, top), fill=BRONZE, width=w, joint="curve")
        k += 1


def _frame(img):
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, W - 24, H - 24], outline=BRONZE, width=3)
    d.rectangle([40, 40, W - 40, H - 40], outline=GOLD_DARK, width=1)
    d.rectangle([84, 84, W - 84, H - 84], outline=GOLD_DARK, width=1)
    d.rectangle([90, 90, W - 90, H - 90], outline=BRONZE, width=2)
    _braid(d, True, 62, 86, W - 86)
    _braid(d, True, H - 62, 86, W - 86)
    _braid(d, False, 62, 86, H - 86)
    _braid(d, False, W - 62, 86, H - 86)
    for cx, cy in [(62, 62), (W - 62, 62), (62, H - 62), (W - 62, H - 62)]:
        d.rectangle([cx - 25, cy - 25, cx + 25, cy + 25], fill=DARK, outline=BRONZE, width=2)
        _diamond(d, cx, cy, 15, fill=None, outline=BRONZE, width=2)
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=GOLD_LIGHT)


def _medallion(d, cx, cy):
    d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], outline=BRONZE, width=2)
    d.ellipse([cx - 33, cy - 33, cx + 33, cy + 33], outline=GOLD_DARK, width=1)
    d.polygon(_star_pts(cx, cy, 28, 10, 8), fill=GOLD_LIGHT)
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=DARK)
    for sx in (-1, 1):
        d.line([(cx + sx * 56, cy), (cx + sx * 190, cy)], fill=BRONZE, width=2)
        _diamond(d, cx + sx * 56, cy, 5)
        _diamond(d, cx + sx * 198, cy, 4)
        d.ellipse([cx + sx * 214 - 3, cy - 3, cx + sx * 214 + 3, cy + 3], fill=BRONZE)


def _bottom_ornament(d, cx, cy):
    for sx in (-1, 1):
        d.line([(cx + sx * 30, cy), (cx + sx * 150, cy)], fill=BRONZE, width=2)
        _diamond(d, cx + sx * 158, cy, 4)
    d.polygon(_star_pts(cx, cy, 16, 5, 4), fill=GOLD_LIGHT)


def _gold_text(img, lines, font, cx, y, lh, c_top=GOLD_LIGHT, c_bottom=GOLD_DARK, glow=True):
    """Текст с золотым градиентом и лёгким свечением."""
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    yy = y
    for ln in lines:
        md.text((cx, yy), ln, font=font, fill=255, anchor="ma")
        yy += lh
    if glow:
        g = mask.filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * 0.4))
        img.paste(Image.new("RGB", (W, H), GOLD_DARK), mask=g)
    y0, y1 = max(0, int(y) - 12), min(H, int(y + len(lines) * lh) + 12)
    grad = Image.new("RGB", (W, y1 - y0))
    gd = ImageDraw.Draw(grad)
    for i in range(y1 - y0):
        gd.line([(0, i), (W, i)], fill=_lerp(c_top, c_bottom, i / max(1, y1 - y0 - 1)))
    img.paste(grad, (0, y0), mask.crop((0, y0, W, y1)))


def _spaced(d, cx, y, text, font, fill, spacing=5):
    total = sum(font.getlength(ch) for ch in text) + spacing * (len(text) - 1)
    x = cx - total / 2
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill, anchor="la")
        x += font.getlength(ch) + spacing
    return total


IT = ("DejaVuSerif-Italic.ttf", "DejaVuSerif.ttf")
REG = ("DejaVuSerif.ttf", "DejaVuSerif-Italic.ttf")
BOLD = ("DejaVuSerif-Bold.ttf", "DejaVuSerif.ttf")
TOP_Y, BOTTOM_Y = 215, H - 175  # в этой полосе размещается текст


def _prepare(card, s):
    """Подбирает размеры шрифтов под масштаб s и считает высоту всех блоков."""
    for size in range(int(100 * s), 47, -4):
        f_title = _font(IT, size)
        t_lines = _wrap(card["title"], f_title, CW)
        fits = all(f_title.getlength(ln) <= CW for ln in t_lines)
        if fits and (len(t_lines) == 1 or (len(t_lines) == 2 and size <= 84)):
            break
    t_lh = int(size * 1.2)

    f_lead = _font(IT, int(36 * s))
    lead = _wrap(card["lead"], f_lead, CW)
    lead_lh = int(36 * s * 1.34)

    f_body = _font(REG, int(30 * s))
    paras = [_wrap(p, f_body, CW) for p in card["body"].split("\n\n")]
    body_lh = int(30 * s * 1.42)
    par_gap = int(18 * s)

    f_hdr = _font(BOLD, int(20 * s))
    f_hint = _font(IT, int(33 * s))
    hint = _wrap(card["hint"], f_hint, CW)
    hint_lh = int(33 * s * 1.36)

    gap = int(26 * s)
    total = (
        len(t_lines) * t_lh + gap + 16 + gap
        + len(lead) * lead_lh + gap + 16 + gap
        + sum(len(p) for p in paras) * body_lh + par_gap * (len(paras) - 1)
        + int(40 * s) + int(26 * s) + int(18 * s)
        + len(hint) * hint_lh
    )
    return dict(f_title=f_title, t_lines=t_lines, t_lh=t_lh, f_lead=f_lead, lead=lead, lead_lh=lead_lh,
                f_body=f_body, paras=paras, body_lh=body_lh, par_gap=par_gap, f_hdr=f_hdr,
                f_hint=f_hint, hint=hint, hint_lh=hint_lh, gap=gap, s=s), total


def _render(idx, watermark):
    card = CARDS[idx]
    s = 1.0
    layout, total = _prepare(card, s)
    while total > BOTTOM_Y - TOP_Y and s > 0.6:
        s -= 0.04
        layout, total = _prepare(card, s)

    L = layout
    img = _background()
    _frame(img)
    d = ImageDraw.Draw(img)
    cx = W // 2
    _medallion(d, cx, 152)
    _bottom_ornament(d, cx, H - 140)

    y = TOP_Y + max(0, (BOTTOM_Y - TOP_Y - total) // 2)
    _gold_text(img, L["t_lines"], L["f_title"], cx, y, L["t_lh"])
    y += len(L["t_lines"]) * L["t_lh"] + L["gap"]
    d = ImageDraw.Draw(img)
    _divider(d, cx, y + 8)
    y += 16 + L["gap"]

    for ln in L["lead"]:
        d.text((cx, y), ln, font=L["f_lead"], fill=LEAD_COLOR, anchor="ma")
        y += L["lead_lh"]
    y += L["gap"]
    _divider(d, cx, y + 8)
    y += 16 + L["gap"]

    for i, para in enumerate(L["paras"]):
        for ln in para:
            d.text((cx, y), ln, font=L["f_body"], fill=TEXT_COLOR, anchor="ma")
            y += L["body_lh"]
        if i < len(L["paras"]) - 1:
            y += L["par_gap"]

    y += int(40 * s)
    hdr_y = y + int(13 * s)
    hdr_w = _spaced(d, cx, y, "НАПУТСТВИЕ ДНЯ", L["f_hdr"], BRONZE)
    d.line([(cx - 300, hdr_y), (cx - hdr_w / 2 - 18, hdr_y)], fill=GOLD_DARK, width=1)
    d.line([(cx + hdr_w / 2 + 18, hdr_y), (cx + 300, hdr_y)], fill=GOLD_DARK, width=1)
    y += int(26 * s) + int(18 * s)
    _gold_text(img, L["hint"], L["f_hint"], cx, y, L["hint_lh"], c_top=GOLD_LIGHT, c_bottom=BRONZE, glow=False)

    if watermark:
        d = ImageDraw.Draw(img)
        f_wm = _font(IT, 22)
        d.text((cx, H - 112), watermark, font=f_wm, fill=BRONZE, anchor="mm")
    return img


def render_day_card(idx: int, watermark: str = "") -> bytes:
    """Возвращает JPEG-байты карточки. Результат кэшируется."""
    key = (idx, watermark)
    if key not in _cache:
        buf = io.BytesIO()
        _render(idx, watermark).save(buf, format="JPEG", quality=92)
        _cache[key] = buf.getvalue()
    return _cache[key]


def fit_scale(idx: int) -> float:
    """Для проверки: до какого масштаба пришлось уменьшить шрифты, чтобы текст поместился."""
    s = 1.0
    _, total = _prepare(CARDS[idx], s)
    while total > BOTTOM_Y - TOP_Y and s > 0.6:
        s -= 0.04
        _, total = _prepare(CARDS[idx], s)
    return round(s, 2)
