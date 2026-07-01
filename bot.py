import json
import logging
import os
import random
import psutil
import re
import base64
import ast
import io
import math
import operator
import secrets
import string
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from uuid import uuid4

from telegram import Message, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# === РУССКИЕ КОМАНДЫ БЕЗ / ===
def extract_users_from_tokens(tokens: list[str] | None) -> list[str]:
    if not tokens:
        return []

    users: list[str] = []
    for token in tokens:
        cleaned = (token or "").strip().strip(",.;:!?()[]{}<>")
        if not cleaned:
            continue
        if cleaned.startswith("@"):
            cleaned = cleaned[1:]
        if re.fullmatch(r"[A-Za-z0-9_]{3,32}", cleaned):
            users.append(cleaned)

    return list(dict.fromkeys(users))


def get_mentioned_or_replied(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE | None = None,
) -> list[str]:
    msg = update.message
    if not msg:
        return []

    mentioned = get_mentioned_users(msg.text)
    mentioned.extend(extract_users_from_tokens(getattr(context, "args", None)))
    if mentioned:
        return list(dict.fromkeys(mentioned))

    if msg.reply_to_message and msg.reply_to_message.from_user:
        user = msg.reply_to_message.from_user
        return [user.username or str(user.id)]

    return []

async def handle_ru_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.strip().lower()
    user = msg.from_user
    if not user:
        return
    user_key = register_profile(user)
    chat_id = str(msg.chat_id)
    ensure_mops_chat(chat_id)
    remember_chat_user(chat_id, user_key)
    if await moderation_guard(update, context, chat_id, user_key):
        return

    ceremony_words = {
        "согласен",
        "согласна",
        "не согласен",
        "не согласна",
        "против",
        "отказываюсь",
    }
    if text in ceremony_words:
        pending_user = norm_user(msg.from_user.username or str(msg.from_user.id))
        _, pending = find_pending_marriage_for_user(chat_id, pending_user)
        if pending:
            return

    # === СКРЫТЫЕ КОМАНДЫ СОЗДАТЕЛЯ ===
    if text.startswith("фармила-прем "):
        await owner_grant_premium(update, context)
        return
    if text.startswith("фармила-монеты "):
        await owner_grant_coins(update, context)
        return
    if text.startswith("фармила-жалоба "):
        await owner_secret_report(update, context)
        return
    if text.startswith("фармила-мод "):
        await owner_mod_config(update, context)
        return

    # === КОМАНДЫ МОПСА ===
    if text in ['привет', 'пр', 'приве', 'хау', 'здорово', 'hi', 'hello']:
        await mops_greet(update, context)
        return
    if text in ['пока','уебывай жир', 'бай', 'до свидания', 'goodbye']:
        await mops_farewell(update, context)
        return
    if text in ['спасибо', 'благодарю', 'СПС Я АХУЕННЕН', 'thx', 'thanks']:
        await mops_thanks(update, context)
        return
    if text in ['шутка', 'анекдот', 'рассмеши']:
        await mops_joke(update, context)
        return
    if text in ['цитата', 'quote']:
        await mops_quote(update, context)
        return
    if text in ['факт', 'интересное', 'инфа']:
        await mops_fact(update, context)
        return
    if text in ['комплимент', 'похвали']:
        await mops_compliment(update, context)
        return
    if text in ['оскорбление', 'поругай']:
        await mops_insult(update, context)
        return
    if text in ['шар', 'ball', 'спрошу']:
        await mops_8ball(update, context)
        return
    if text in ['монетка', 'орел', 'решка']:
        await mops_coin(update, context)
        return
    if text in ['кубик', 'бросить']:
        await mops_dice(update, context)
        return
    if text in ['число', 'рандом', 'рандомное']:
        await mops_random(update, context)
        return
    if text in ['гороскоп', 'зодиак']:
        await mops_horoscope(update, context)
        return
    if text in ['погода', 'погодка'] or text.startswith(".погода ") or text.startswith("погода "):
        await mops_weather(update, context)
        return
    if text.startswith(".цена ") or text.startswith("цена "):
        await price_watch_add(update, context)
        return
    if text in {"цена список", ".цена список", "цены"}:
        await price_watch_list(update, context)
        return
    if text in {"цена сравнить", ".цена сравнить", "где дешевле"}:
        await price_watch_compare(update, context)
        return
    if text in {"цена лучшие", ".цена лучшие", "цена где лучше"}:
        await price_watch_best(update, context)
        return
    if text in ['помощь', 'help', 'команды', 'что ты умеешь']:
        await mops_farmila_help(update, context)
        return
    if text in {'ии', 'ai', 'нейро', 'умный помощник'}:
        await ai_help(update, context)
        return
    if text in {'фото', 'картинка', 'анализ фото', 'что на фото', 'vision', 'photo', 'ocr', 'распознай фото'}:
        await ai_analyze_photo(update, context)
        return
    if text in {'учеба', 'учёба', 'study', 'школа', 'предметы', 'учебные команды'}:
        await study_help(update, context)
        return
    if text in {'математика', 'алгебра', 'геометрия'}:
        await math_cmd(update, context)
        return
    if text in {'биология', 'био'}:
        await biology_cmd(update, context)
        return
    if text in {'информатика', 'инфа', 'программирование'}:
        await informatics_cmd(update, context)
        return
    if text in {'пищевое', 'пищевые технологии', 'повар', 'кондитер'}:
        await food_cmd(update, context)
        return
    if text in {'техкарта', 'технологическая карта'}:
        await foodcard_cmd(update, context)
        return
    if text in {'кбжу', 'калории'}:
        await nutrition_cmd(update, context)
        return
    if text in {'сайт', 'сайт команд', 'команды сайт'}:
        await site_cmd(update, context)
        return
    for prefix, handler in {
        'учеба ': study_cmd,
        'учёба ': study_cmd,
        'study ': study_cmd,
        'математика ': math_cmd,
        'алгебра ': math_cmd,
        'геометрия ': math_cmd,
        'биология ': biology_cmd,
        'био ': biology_cmd,
        'информатика ': informatics_cmd,
        'инфа ': informatics_cmd,
        'программирование ': informatics_cmd,
        'пищевое ': food_cmd,
        'пищевые технологии ': food_cmd,
        'повар ': food_cmd,
        'кондитер ': food_cmd,
        'техкарта ': foodcard_cmd,
        'технологическая карта ': foodcard_cmd,
        'кбжу ': nutrition_cmd,
        'калории ': nutrition_cmd,
        'пропорция ': proportion_cmd,
        'пропорции ': proportion_cmd,
        'пересчет рецепта ': scale_recipe_cmd,
        'пересчёт рецепта ': scale_recipe_cmd,
        'пересчитать рецепт ': scale_recipe_cmd,
        'рецепт пересчитать ': scale_recipe_cmd,
        'единицы ': unit_cmd,
        'конвертируй ': unit_cmd,
    }.items():
        if text.startswith(prefix):
            context.args = msg.text.strip()[len(prefix):].strip().split()
            await handler(update, context)
            return
    for prefix, handler in {
        'спроси ': ai_ask,
        'ии ': ai_ask,
        'ai ': ai_ask,
        'реши ': ai_ask,
        'задача ': ai_ask,
        'анализ ': ai_ask,
        'объясни ': ai_ask,
        'переведи ': ai_translate,
        'кратко ': ai_summary,
        'посчитай ': calc_cmd,
        'кальк ': calc_cmd,
        'выбери ': choose_cmd,
        'оцени ': rate_cmd,
        'заметка ': note_add_cmd,
        'напомни ': remind_cmd,
    }.items():
        if text.startswith(prefix):
            context.args = msg.text.strip()[len(prefix):].strip().split()
            await handler(update, context)
            return
    if text in {'заметки', 'мои заметки'}:
        await notes_cmd(update, context)
        return
    if text in {'очистить заметки', 'удалить заметки'}:
        await note_clear_cmd(update, context)
        return
    if text in {'правда', 'truth'}:
        await truth_cmd(update, context)
        return
    if text in {'действие', 'dare'}:
        await dare_cmd(update, context)
        return
    if text in {'слоты', 'казино', 'slots'}:
        await slots_cmd(update, context)
        return
    if text in {'монетка+', 'флип', 'coinflip'}:
        await coinflip_cmd(update, context)
        return
    if text in ['хоши', 'кошка', 'hoshi']:
        await hoshi_help(update, context)
        return
    if text in ['совет хоши', 'хоши совет', 'hoshi tip']:
        await hoshi_tip(update, context)
        return
    if text in ['хоши статус', 'статус хоши']:
        await hoshi_status(update, context)
        return
    if text in ['хоши вкл', 'вкл хоши']:
        await hoshi_on(update, context)
        return
    if text in ['хоши выкл', 'выкл хоши']:
        await hoshi_off(update, context)
        return
    if text in ['хоши баланс', 'баланс хоши']:
        await hoshi_balance(update, context)
        return
    if text in ['хоши квест', 'квест хоши']:
        await hoshi_quest(update, context)
        return

    # === ИГРОВЫЕ КОМАНДЫ ===
    game_commands = {
        'дуэль': duel, 'брак': brak, 'свадьба': brak,
        'развод': razvod, 'расставание': razvod,
        'альянс': alyans, 'союз': alyans,
        'враги': vragi, 'война': war,
        'принять': accept, 'согласен': accept,
        'отклонить': decline, 'отказ': decline,
        'выстрел': shot, 'стрель': shot,
        'баланс': balance, 'монеты': balance,
        'магазин': shop, 'кольца': rings,
        'моикольца': my_rings, 'кольцо': ring_exchange,
        'браки': braki, 'семьи': braki, 'союзы': soyuzy,
        'мойбрак': moisoyuz, 'моясемья': moisoyuz,
        'пвп': pvpstats, 'пвптоп': pvptop,
        'войнытоп': wartop, 'рейд': raid_start,
        'удар': raid_hit, 'слова': words_start,
        'стопслова': words_stop,
        'мопс': mops_status, 'мопсон': mops_on,
        'мопсофф': mops_off,
        'ежедневка': daily, 'награда': daily,
        'отношения': relation_status,
        'игры': mops_play,
        'мопсигра': mops_guess,
        'полечудес': polesudes_start,
        'морскойбой': battleship_start,
        'принятьобмен': accept_trade,
        'отклонитьобмен': decline_trade,
        'профиль': profile,
        'квест': quest_status,
        'рыбалка': fish,
        'лотобилет': lottery_buy,
        'лотерея': lottery_draw,
        'тренировкамопса': mops_train,
        'топигроков': top_players,
        'банк': bank,
        'ранг': rank,
        'мафия': mafia_create,
        'мафиявойти': mafia_join,
        'мафиястарт': mafia_start,
        'мафиястатус': mafia_status,
        'мафиястоп': mafia_stop,
        'викторина': quiz,
    }

    if text in game_commands:
        func = game_commands[text]
        no_args = [
            'принять', 'согласен', 'отклонить', 'отказ', 'выстрел', 'стрель',
            'баланс', 'монеты', 'магазин', 'кольца', 'моикольца', 'браки', 'семьи', 'союзы',
            'мойбрак', 'моясемья', 'пвптоп', 'войнытоп', 'рейд',
            'удар', 'слова', 'стопслова', 'мопс', 'ежедневка', 'награда',
            'отношения', 'игры', 'мопсигра', 'полечудес', 'морскойбой',
            'принятьобмен', 'отклонитьобмен', 'профиль', 'квест', 'рыбалка',
            'лотобилет', 'лотерея', 'тренировкамопса', 'топигроков', 'банк'
            , 'ранг', 'мафия', 'мафиявойти', 'мафиястарт', 'мафиястатус', 'мафиястоп', 'викторина'
        ]

        if text in no_args:
            await func(update, context)
            return

        mentioned = get_mentioned_or_replied(update, context)
        if not mentioned:
            await msg.reply_text(f"Напиши: {text} @user")
            return

        context.args = mentioned
        await func(update, context)
        return

    # Команды с аргументами
    if text.startswith("гвиар кто"):
        await gviar_who(update, context)
        return

    for cmd in ['дуэль ', 'брак ', 'свадьба ', 'развод ', 'расставание ', 'альянс ', 'союз ',
                'враги ', 'война ', 'кольцо ', 'купить ', 'пвп ', 'кто ', 'поцелуй ', 'обнять ',
                'обмен ', 'вклад ', 'снять ', 'передать ', 'мафияголос ', 'мафиязащита ', 'кнб ']:
        if text.startswith(cmd):
            rest = msg.text.strip()[len(cmd):].strip()
            if rest:
                mentioned = list(dict.fromkeys(re.findall(r'@(\w+)', rest)))
            else:
                mentioned = get_mentioned_or_replied(update, context)

            if not mentioned and cmd.strip() not in ['купить']:
                await msg.reply_text(f"{cmd.strip()} @user")
                return

            cmd_stripped = cmd.strip()
            if cmd_stripped == 'дуэль':
                context.args = mentioned
                await duel(update, context)
            elif cmd_stripped in ['брак', 'свадьба']:
                context.args = mentioned
                await brak(update, context)
            elif cmd_stripped in ['развод', 'расставание']:
                context.args = mentioned
                await razvod(update, context)
            elif cmd_stripped in ['альянс', 'союз']:
                context.args = mentioned
                await alyans(update, context)
            elif cmd_stripped == 'враги':
                context.args = mentioned
                await vragi(update, context)
            elif cmd_stripped == 'война':
                context.args = mentioned
                await war(update, context)
            elif cmd_stripped == 'кольцо':
                context.args = mentioned
                await ring_exchange(update, context)
            elif cmd_stripped == 'купить':
                context.args = [rest]
                await buy(update, context)
            elif cmd_stripped == 'пвп':
                context.args = mentioned
                await pvpstats(update, context)
            elif cmd_stripped == 'кто':
                await msg.reply_text("Используй формат: гвиар кто <вопрос>")
            elif cmd_stripped == 'поцелуй':
                context.args = mentioned
                await mops_kiss(update, context)
            elif cmd_stripped == 'обнять':
                context.args = mentioned
                await mops_hug(update, context)
            elif cmd_stripped == 'обмен':
                context.args = rest.split()
                await trade(update, context)
            elif cmd_stripped == 'вклад':
                context.args = rest.split()
                await deposit(update, context)
            elif cmd_stripped == 'снять':
                context.args = rest.split()
                await withdraw(update, context)
            elif cmd_stripped == 'передать':
                context.args = rest.split()
                await pay(update, context)
            elif cmd_stripped == 'мафияголос':
                context.args = rest.split()
                await mafia_vote(update, context)
            elif cmd_stripped == 'мафиязащита':
                context.args = rest.split()
                await mafia_protect(update, context)
            elif cmd_stripped == 'кнб':
                context.args = rest.split()
                await rps(update, context)
            return



def _fix_mojibake(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    try:
        # Fix strings like "ПСЂёвет" -> "Привет"
        candidate = text.encode("cp1251").decode("utf-8")
    except Exception:
        return text

    def score(s: str) -> int:
        return s.count("Р") + s.count("С") + s.count("Ѓ") + s.count("Џ")

    return candidate if score(candidate) < score(text) else text


_orig_reply_text = Message.reply_text


async def _reply_text_fixed(self, text, *args, **kwargs):
    if isinstance(text, str):
        text = _fix_mojibake(text)
    return await _orig_reply_text(self, text, *args, **kwargs)


Message.reply_text = _reply_text_fixed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = (
    os.getenv("DATA_DIR")
    or os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    or BASE_DIR
)
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "data.json")
DUEL_STATS_FILE = os.path.join(DATA_DIR, "duel_stats.json")
WAR_STATS_FILE = os.path.join(DATA_DIR, "war_stats.json")
WORD_GAME_FILE = os.path.join(DATA_DIR, "word_game.json")
RAID_FILE = os.path.join(DATA_DIR, "raid_state.json")
DAILY_FILE = os.path.join(DATA_DIR, "daily_rewards.json")
INVENTORY_FILE = os.path.join(DATA_DIR, "inventory.json")
MOPS_FILE = os.path.join(DATA_DIR, "mops_helper.json")
PROFILE_FILE = os.path.join(DATA_DIR, "profiles.json")
RELATION_FILE = os.path.join(DATA_DIR, "relations.json")
TRADE_FILE = os.path.join(DATA_DIR, "trade_state.json")
MINIGAME_FILE = os.path.join(DATA_DIR, "minigames.json")
REPORT_FILE = os.path.join(DATA_DIR, "mod_reports.json")
QUEST_FILE = os.path.join(DATA_DIR, "quests.json")
ACHIEV_FILE = os.path.join(DATA_DIR, "achievements.json")
LOTTERY_FILE = os.path.join(DATA_DIR, "lottery.json")
BANK_FILE = os.path.join(DATA_DIR, "bank.json")
XP_FILE = os.path.join(DATA_DIR, "xp.json")
MOD_STATE_FILE = os.path.join(DATA_DIR, "moderation_state.json")
PRICE_WATCH_FILE = os.path.join(DATA_DIR, "price_watch.json")
DONATE_LOG_FILE = os.path.join(DATA_DIR, "donate_log.json")
NOTES_FILE = os.path.join(DATA_DIR, "notes.json")

SHOP_ITEMS = {
    "sword": {"name": "Железный меч", "price": 120},
    "shield": {"name": "Щит стража", "price": 110},
    "potion": {"name": "Зелье лечения", "price": 60},
    "bomb": {"name": "Бомба", "price": 95},
    "amulet": {"name": "Амулет удачи", "price": 180},
    "ring": {"name": "Обручальное кольцо", "price": 150},
    "katana": {"name": "Катана ветра", "price": 260},
    "axe": {"name": "Секира грома", "price": 240},
    "spear": {"name": "Копье охотника", "price": 210},
    "crossbow": {"name": "Арбалет дозорного", "price": 230},
    "wand": {"name": "Жезл искр", "price": 280},
    "armor": {"name": "Латный доспех", "price": 300},
}

RING_CHOICES = {
    "ring_12k": {"name": "Кольцо 12 карат", "price": 120},
    "ring_18k": {"name": "Кольцо 18 карат", "price": 220},
    "ring_24k": {"name": "Кольцо 24 карат", "price": 350},
    "ring_silver": {"name": "Серебряное кольцо", "price": 80},
    "ring_rose": {"name": "Кольцо Розовый кварц", "price": 480},
    "ring_royal": {"name": "Королевское кольцо", "price": 700},
    "ring_diamond": {"name": "Кольцо с бриллиантом", "price": 1200},
    "ring_emerald": {"name": "Кольцо с изумрудом", "price": 950},
    "ring_sapphire": {"name": "Кольцо с сапфиром", "price": 880},
    "ring_ruby": {"name": "Кольцо с рубином", "price": 920},
    "ring_platinum": {"name": "Платиновое кольцо", "price": 1100},
    "ring_black_diamond": {"name": "Кольцо с чёрным бриллиантом", "price": 1600},
    "ring_crown": {"name": "Кольцо Корона", "price": 1450},
    "ring_eternity": {"name": "Вечное кольцо (бриллианты по кругу)", "price": 2200}
}

SHOP_ITEMS.update(RING_CHOICES)

marriages: dict[str, list[dict]] = {}
duel_stats: dict[str, dict[str, int]] = {}
war_stats: dict[str, dict[str, int]] = {}
duel_requests: dict[str, dict[str, str]] = {}
active_duels: dict[str, dict[str, str]] = {}
pending_marriages: dict[str, dict[str, str]] = {}
word_games: dict[str, dict] = {}
raid_states: dict[str, dict] = {}
daily_rewards: dict[str, dict] = {}
inventories: dict[str, dict[str, int]] = {}
mops_state: dict[str, dict] = {}
profiles: dict[str, dict] = {}
relations: dict[str, dict] = {}
trade_requests: dict[str, dict] = {}
minigames: dict[str, dict] = {}
mod_reports: dict[str, list[dict]] = {}
quests: dict[str, dict] = {}
achievements: dict[str, dict] = {}
lottery: dict[str, dict] = {}
bank_data: dict[str, dict] = {}
xp_data: dict[str, dict] = {}
mod_state: dict[str, dict] = {}
price_watch: dict[str, dict] = {}
donate_log: dict[str, list[dict]] = {}
notes_data: dict[str, list[dict]] = {}
mafia_games: dict[str, dict] = {}
BOT_STARTED_AT = datetime.now()
OWNER_USERNAME = "exsep"
OWNER_ID = 7238803158
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
COMMANDS_SITE_URL = (os.getenv("COMMANDS_SITE_URL") or "").strip()
AI_SYSTEM_PROMPT = (
    "Ты полезный Telegram-помощник Мопс-Фармила. Отвечай по-русски, ясно и аккуратно. "
    "Если решаешь задачу с фото или текстом, сначала распознай условие, затем дай решение "
    "по шагам и короткий итог. Если данных не хватает, честно скажи, что именно нужно уточнить. "
    "Хорошо помогай с математикой, биологией, информатикой и пищевыми технологиями: "
    "объясняй формулы, считай пропорции, техкарты, рецептуры, выход, себестоимость и КБЖУ. "
    "Не выдумывай факты и не обещай невозможного."
)


def is_owner(tg_user) -> bool:
    if not tg_user:
        return False
    uname = (tg_user.username or "").lower().strip("@")
    return tg_user.id == OWNER_ID or uname == OWNER_USERNAME


def is_privileged(tg_user) -> bool:
    return is_owner(tg_user)


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.warning("Cannot read %s: %s", path, e)
        return default


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_mentioned_users(text: str | None) -> list[str]:
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"@(\w+)", text)))


def ensure_stat_user(stats: dict[str, dict[str, int]], user: str) -> None:
    if user not in stats:
        stats[user] = {"wins": 0, "losses": 0, "draws": 0}


def duel_key(chat_id: str, challenger: str, target: str) -> str:
    return f"{chat_id}:{challenger}:{target}"


def find_request_for_target(chat_id: str, target: str) -> tuple[str, dict[str, str]] | tuple[None, None]:
    prefix = f"{chat_id}:"
    for key, req in duel_requests.items():
        if key.startswith(prefix) and req.get("target") == target:
            return key, req
    return None, None


def clear_duel_requests_for_pair(chat_id: str, user_a: str, user_b: str) -> None:
    keys = [
        duel_key(chat_id, user_a, user_b),
        duel_key(chat_id, user_b, user_a),
    ]
    for k in keys:
        duel_requests.pop(k, None)


def marriage_key(chat_id: str, user_a: str, user_b: str) -> str:
    first, second = sorted([user_a, user_b])
    return f"{chat_id}:{first}:{second}"


def norm_user(user: str | None) -> str:
    return (user or "").strip().lower()


def is_user_in_marriage(chat_id: str, user: str) -> bool:
    needle = norm_user(user)
    for m in marriages.get(chat_id, []):
        members = [norm_user(x) for x in m.get("members", [])]
        if m.get("type") == "marriage" and needle in members:
            return True
    return False


def find_pending_marriage_for_user(chat_id: str, user: str) -> tuple[str, dict[str, str]] | tuple[None, None]:
    prefix = f"{chat_id}:"
    user = norm_user(user)
    matched: list[tuple[str, dict[str, str]]] = []
    for key, data in pending_marriages.items():
        if not key.startswith(prefix):
            continue
        a = norm_user(data.get("a"))
        b = norm_user(data.get("b"))
        if user in (a, b):
            matched.append((key, data))

    if not matched:
        return None, None

    # If user has multiple pending proposals, choose the latest one.
    matched.sort(key=lambda item: float(item[1].get("created_at", "0")), reverse=True)
    return matched[0]


def clear_pending_marriages_for_users(chat_id: str, users: set[str]) -> None:
    users = {norm_user(u) for u in users}
    prefix = f"{chat_id}:"
    to_delete = []
    for key, data in pending_marriages.items():
        if not key.startswith(prefix):
            continue
        a = norm_user(data.get("a"))
        b = norm_user(data.get("b"))
        if a in users or b in users:
            to_delete.append(key)
    for key in to_delete:
        pending_marriages.pop(key, None)


def find_marriage_for_user(chat_id: str, user: str) -> tuple[int, dict] | tuple[None, None]:
    user = norm_user(user)
    records = marriages.get(chat_id, [])
    for idx, m in enumerate(records):
        members = [norm_user(x) for x in m.get("members", [])]
        if m.get("type") == "marriage" and user in members:
            return idx, m
    return None, None


def parse_iso_date(dt: str | None) -> datetime | None:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt)
    except Exception:
        return None


def resolve_ring_id(raw: str | None) -> str | None:
    token = (raw or "").strip().lower()

    aliases = {
        # Золотые кольца (старые)
        "12": "ring_12k",
        "12k": "ring_12k",
        "ring12": "ring_12k",
        "ring_12k": "ring_12k",
        "18": "ring_18k",
        "18k": "ring_18k",
        "ring18": "ring_18k",
        "ring_18k": "ring_18k",
        "24": "ring_24k",
        "24k": "ring_24k",
        "ring24": "ring_24k",
        "ring_24k": "ring_24k",
        "ring": "ring",

        # Новые позиции: драгоценные камни
        "diamond": "ring_diamond",
        "d": "ring_diamond",
        "ring_diamond": "ring_diamond",
        "emerald": "ring_emerald",
        "e": "ring_emerald",
        "ring_emerald": "ring_emerald",
        "sapphire": "ring_sapphire",
        "s": "ring_sapphire",
        "ring_sapphire": "ring_sapphire",
        "ruby": "ring_ruby",
        "r": "ring_ruby",
        "ring_ruby": "ring_ruby",

        # Новые позиции: премиум и необычные
        "platinum": "ring_platinum",
        "pt": "ring_platinum",
        "ring_platinum": "ring_platinum",
        "black_diamond": "ring_black_diamond",
        "bd": "ring_black_diamond",
        "ring_black_diamond": "ring_black_diamond",
        "crown": "ring_crown",
        "ring_crown": "ring_crown",
        "eternity": "ring_eternity",
        "et": "ring_eternity",
        "ring_eternity": "ring_eternity",
        "moonstone": "ring_moonstone",
        "ring_moonstone": "ring_moonstone",
        "tiger_eye": "ring_tiger_eye",
        "ring_tiger_eye": "ring_tiger_eye",
        "astrology": "ring_astrology",
        "ring_astrology": "ring_astrology",
        "dragon": "ring_dragon",
        "ring_dragon": "ring_dragon",
        "couple": "ring_couple_set",
        "set": "ring_couple_set",
        "ring_couple_set": "ring_couple_set",
    }

    ring_id = aliases.get(token)
    if ring_id and ring_id in SHOP_ITEMS:
        return ring_id
    return None



def pick_best_common_ring(inv_a: dict[str, int], inv_b: dict[str, int]) -> str | None:
    priority = [
    "ring_black_diamond", 
    "ring_diamond",
    "ring_platinum",
    "ring_crown",
    "ring_eternity",
    "ring_sapphire",
    "ring_emerald",
    "ring_ruby",
    "ring_moonstone",
    "ring_tiger_eye",
    "ring_astrology",
    "ring_dragon",
    "ring_couple_set",
    "ring_24k",
    "ring_18k",
    "ring_12k",
    "ring"
]

    for ring_id in priority:
        if int(inv_a.get(ring_id, 0)) > 0 and int(inv_b.get(ring_id, 0)) > 0:
            return ring_id
    return None


def total_rings(inv: dict[str, int]) -> int:
    return sum(
        int(qty)
        for item_id, qty in inv.items()
        if item_id == "ring" or item_id.startswith("ring_")
    )


def make_active_duel_key(chat_id: str, user_a: str, user_b: str) -> str:
    first, second = sorted([user_a, user_b])
    return f"{chat_id}:{first}:{second}"


def find_active_duel_for_user(chat_id: str, user: str) -> tuple[str, dict[str, str]] | tuple[None, None]:
    prefix = f"{chat_id}:"
    for key, duel in active_duels.items():
        if key.startswith(prefix) and user in (duel.get("a"), duel.get("b")):
            return key, duel
    return None, None


def normalize_word(word: str) -> str:
    return re.sub(r"[^a-zA-Zа-яА-ЯёЁ]", "", word).lower().replace("ё", "е")


def get_last_letter(word: str) -> str:
    skip = {"ь", "ъ", "ы"}
    for ch in reversed(word):
        if ch not in skip:
            return ch
    return ""


def get_user_key(username: str | None, user_id: int) -> str:
    return f"id:{user_id}"


def today_str() -> str:
    return datetime.now().date().isoformat()


def format_uptime(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0:
        return f"{days}д {hours}ч {minutes}м"
    return f"{hours}ч {minutes}м"


def ensure_mops_chat(chat_id: str) -> dict:
    chats = mops_state.setdefault("chats", {})
    chat_cfg = chats.setdefault(
        chat_id,
        {
            "enabled": True,
            "hoshi_enabled": True,
            "mops_reports_enabled": True,
            "report_interval_min": 300,  # 5 часов по умолчанию
            "last_sent": "",
            "last_scene": "",
            "last_report_ts": 0,
        },
    )
    try:
        interval = int(chat_cfg.get("report_interval_min", 300))
    except Exception:
        interval = 300
    chat_cfg["report_interval_min"] = max(60, min(1440, interval))
    return chat_cfg


def remember_chat_user(chat_id: str, user_key: str) -> None:
    users = mops_state.setdefault("chat_users", {})
    arr = users.setdefault(chat_id, [])
    if user_key not in arr:
        arr.append(user_key)
        users[chat_id] = arr[-500:]
        mops_state["chat_users"] = users
        save_json(MOPS_FILE, mops_state)


def ensure_mod_chat(chat_id: str) -> dict:
    chats = mod_state.setdefault("chats", {})
    cfg = chats.setdefault(
        chat_id,
        {
            "enabled": True,
            "flood_limit": 6,
            "flood_window_sec": 12,
            "mute_minutes": 10,
            "bad_words": ["скам", "фишинг", "докс", "наркот", "экстрем"],
            "warns": {},
            "banned": [],
            "activity": {},
        },
    )
    return cfg


def ensure_wallet(user: str) -> dict:
    return daily_rewards.setdefault(user, {"coins": 0, "streak": 0, "last_claim": ""})


def ensure_inventory(user: str) -> dict[str, int]:
    return inventories.setdefault(user, {})


def hp_bar(current_hp: int, max_hp: int = 100, width: int = 10) -> str:
    current_hp = max(0, min(max_hp, current_hp))
    filled = int(round((current_hp / max_hp) * width))
    return "❤️" * filled + "🖤" * (width - filled)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    ensure_mops_chat(chat_id)
    save_json(MOPS_FILE, mops_state)

    await update.message.reply_text(
        "Команды:\n"
        "/brak @user1 @user2 ... (2-67)\n"
        "/razvod [@user]\n"
        "/alyans @user1 @user2 ... (1-80)\n"
        "/vragi @user1 @user2\n"
        "/braki\n"
        "/soyuzy\n"
        "/moisoyuz\n\n"
        "/anniversary [@user]\n"
        "/rings\n"
        "/my_rings\n"
        "/ring_exchange [12k|18k|24k]\n\n"
        "PvP:\n"
        "/duel @user или /pvp @user\n"
        "/accept\n"
        "/decline\n"
        "/shot\n"
        "/pvpstats [@user]\n"
        "/pvptop\n"
        "/duel_help\n\n"
        "Война:\n"
        "/war @user\n"
        "/warstats [@user]\n"
        "/wartop\n\n"
        "Игра в слова:\n"
        "/words_start\n"
        "/word слово\n"
        "/words_status\n"
        "/words_stop\n\n"
        "Рейд и экономика:\n"
        "/raid_start\n"
        "/raid_hit\n"
        "/raid_status\n"
        "/raid_top\n"
        "/raid_help\n"
        "/daily\n"
        "/balance [@user]\n"
        "/eco_help\n\n"
        "Магазин:\n"
        "/shop\n"
        "/buy item_id [кол-во]\n"
        "/inventory [@user]\n\n"
        "AI-помощник:\n"
        "/ai — подсказка по AI-командам\n"
        "/ask вопрос\n"
        "/solve условие или ответом на фото\n"
        "/analyze фото\n"
        "/vision /photo /ocr — локальный анализ фото без ключа\n"
        "/summary текст\n"
        "/translate текст\n\n"
        "Учеба:\n"
        "/study\n"
        "/math 15% от 240\n"
        "/biology фотосинтез\n"
        "/informatics алгоритм\n"
        "/food брутто нетто\n"
        "/techcard 10 порций; мука 500 г 60 руб/кг\n"
        "/scale_recipe с 4 на 10; мука 500 г\n"
        "/proportion 500 750 120\n"
        "/nutrition 4 порции; мука 500 г\n"
        "/units 250 г в кг\n\n"
        "Ультра-команды:\n"
        "/calc 2*(5+3)\n"
        "/roll 2d6+1\n"
        "/choose пицца | суши | бургер\n"
        "/password 20\n"
        "/remind 10m текст\n"
        "/note_add текст\n"
        "/notes\n"
        "/truth /dare /slots /ship /rate /bomb"
    )

async def brak(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    proposer = register_profile(msg.from_user)
    mentioned = get_mentioned_or_replied(update, context)

    if len(mentioned) != 1:
        await msg.reply_text("Использование: /brak @user")
        return

    target = resolve_user_key_from_token(mentioned[0]) if mentioned else None
    if not target and msg.reply_to_message and msg.reply_to_message.from_user:
        target = register_profile(msg.reply_to_message.from_user)
    if not target:
        await msg.reply_text("Не удалось определить второго участника.")
        return
    if target == proposer:
        await msg.reply_text("Нельзя жениться на себе")
        return

    if is_user_in_marriage(chat_id, proposer) or is_user_in_marriage(chat_id, target):
        await msg.reply_text("Один из участников уже в браке")
        return

    inv_a = ensure_inventory(proposer)
    inv_b = ensure_inventory(target)
    if total_rings(inv_a) < 1 or total_rings(inv_b) < 1:
        await msg.reply_text(
            "Без колец брак заключить нельзя.\n"
            "У каждого участника должно быть хотя бы одно кольцо.\n"
            "Список колец: /rings\n"
            "Покупка: /buy ring_12k (или ring_18k / ring_24k)"
        )
        return

    # Clear stale/parallel requests for either participant to avoid wrong pairing.
    clear_pending_marriages_for_users(chat_id, {proposer, target})

    key = marriage_key(chat_id, proposer, target)
    if key in pending_marriages:
        await msg.reply_text("Приглашение на свадьбу уже отправлено")
        return

    pending_marriages[key] = {
        "chat_id": chat_id,
        "a": proposer,
        "b": target,
        "a_ok": "0",
        "b_ok": "0",
        "created_at": str(datetime.now().timestamp()),
    }
    await msg.reply_text(
        f"💌 {display_user(proposer)} зовет {display_user(target)} на свадьбу!\n\n"
        "Для церемонии оба участника должны написать в чат:\n"
        "согласен (или согласна)\n\n"
        "Если кто-то пишет: не согласен / не согласна — свадьба отменяется."
    )


async def marriage_ceremony_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return
    if msg.from_user and msg.from_user.is_bot:
        return

    text = (msg.text or "").strip().lower()
    chat_id = str(msg.chat_id)
    user = register_profile(msg.from_user)

    key, request = find_pending_marriage_for_user(chat_id, user)
    if not request:
        return

    a = norm_user(request.get("a"))
    b = norm_user(request.get("b"))

    agree_words = {"согласен", "согласна"}
    decline_words = {"не согласен", "не согласна", "против", "отказываюсь"}

    if text in decline_words:
        pending_marriages.pop(key, None)
        await msg.reply_text(
            f"💔 Церемония отменена.\n"
            f"{display_user(user)} не согласен(на) на брак."
        )
        return

    if text not in agree_words:
        return

    if user == a:
        request["a_ok"] = "1"
    elif user == b:
        request["b_ok"] = "1"
    else:
        return

    pending_marriages[key] = request
    a_ok = request.get("a_ok") == "1"
    b_ok = request.get("b_ok") == "1"

    if not (a_ok and b_ok):
        waiting_for = b if user == a else a
        await msg.reply_text(
            f"✅ @{user} сказал(а): «согласен/согласна».\n"
            f"Ждем ответ от @{waiting_for}."
        )
        return

    # Оба согласились — создаем брак.
    if is_user_in_marriage(chat_id, a) or is_user_in_marriage(chat_id, b):
        pending_marriages.pop(key, None)
        await msg.reply_text("Свадьба отменена: один из участников уже в браке.")
        return

    marriages.setdefault(chat_id, [])
    marriages[chat_id].append(
        {
            "type": "marriage",
            "members": [a, b],
            "date": datetime.now().isoformat(),
            "wedding_date": datetime.now().isoformat(),
            "rings_exchanged": False,
            "rings_date": "",
        }
    )
    save_json(DATA_FILE, marriages)
    pending_marriages.pop(key, None)
    await msg.reply_text(
        "💍✨ Торжественная церемония завершена!\n\n"
        f"@{a} и @{b} теперь официально в браке!\n"
        "Пусть ваш союз будет крепким, счастливым и долгим! ❤️\n\n"
        "💍 Обменяйтесь кольцами:\n"
        "/ring_exchange 12k\n"
        "/ring_exchange 18k\n"
        "/ring_exchange 24k"
    )


async def razvod(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    user = msg.from_user.username or str(msg.from_user.id)
    mentioned = get_mentioned_or_replied(update, context)

    if chat_id not in marriages:
        await msg.reply_text("Рќет бСЂаков")
        return

    if mentioned:
        target = mentioned[0]
        for m in list(marriages[chat_id]):
            if m.get("type") == "marriage" and target in m.get("members", []):
                marriages[chat_id].remove(m)
                save_json(DATA_FILE, marriages)
                await msg.reply_text(f"@{target} СЂазведен(а)")
                return
        await msg.reply_text("Рќе найдено")
        return

    found = False
    for m in list(marriages[chat_id]):
        if m.get("type") == "marriage" and user in m.get("members", []):
            marriages[chat_id].remove(m)
            found = True

    if found:
        save_json(DATA_FILE, marriages)
        await msg.reply_text("Р азвод выполнен")
    else:
        await msg.reply_text("Рўы не в бСЂаке")


async def anniversary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    caller = msg.from_user.username or str(msg.from_user.id)
    mentioned = get_mentioned_or_replied(update, context)
    user = mentioned[0] if mentioned else caller

    _, marriage = find_marriage_for_user(chat_id, user)
    if not marriage:
        await msg.reply_text("Брак не найден.")
        return

    members = marriage.get("members", [])
    partner = members[1] if members and members[0] == user and len(members) > 1 else (members[0] if members else "")
    wedding_dt = parse_iso_date(marriage.get("wedding_date") or marriage.get("date"))
    if not wedding_dt:
        await msg.reply_text("Дата свадьбы не найдена.")
        return

    today = datetime.now()
    days_together = (today.date() - wedding_dt.date()).days
    next_anniv = wedding_dt.replace(year=today.year)
    if next_anniv.date() < today.date():
        next_anniv = next_anniv.replace(year=today.year + 1)
    days_to_anniv = (next_anniv.date() - today.date()).days
    rings_status = "да" if marriage.get("rings_exchanged") else "нет"
    ring_type = marriage.get("ring_type", "")
    ring_label = SHOP_ITEMS.get(ring_type, {"name": ring_type}).get("name", ring_type) if ring_type else "не выбран"

    await msg.reply_text(
        f"💞 Пара: @{user} + @{partner}\n"
        f"Дата свадьбы: {wedding_dt.strftime('%d.%m.%Y')}\n"
        f"Вместе дней: {days_together}\n"
        f"До годовщины: {days_to_anniv} дней\n"
        f"Обмен кольцами: {rings_status}\n"
        f"Тип колец: {ring_label}"
    )


async def ring_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    user = msg.from_user.username or str(msg.from_user.id)

    idx, marriage = find_marriage_for_user(chat_id, user)
    if marriage is None:
        await msg.reply_text("Ты не состоишь в браке.")
        return

    members = marriage.get("members", [])
    if len(members) != 2:
        await msg.reply_text("Обмен кольцами доступен только для пары.")
        return

    a, b = members[0], members[1]
    inv_a = ensure_inventory(a)
    inv_b = ensure_inventory(b)
    requested_ring_id = resolve_ring_id(context.args[0]) if context.args else None
    ring_id = requested_ring_id or pick_best_common_ring(inv_a, inv_b)
    if not ring_id:
        await msg.reply_text(
            "Для обмена кольцами у обоих должен быть одинаковый тип кольца.\n"
            "Список типов: /rings\n"
            "Покупка: /buy ring_12k или /buy ring_18k или /buy ring_24k"
        )
        return

    ring_a = int(inv_a.get(ring_id, 0))
    ring_b = int(inv_b.get(ring_id, 0))
    if ring_a < 1 or ring_b < 1:
        await msg.reply_text(
            f"Для обмена кольцами типа `{ring_id}` у каждого должно быть минимум 1 кольцо.\n"
            "Список: /rings"
        )
        return

    inv_a[ring_id] = ring_a - 1
    inv_b[ring_id] = ring_b - 1
    marriage["rings_exchanged"] = True
    marriage["rings_date"] = datetime.now().isoformat()
    marriage["ring_type"] = ring_id
    marriages[chat_id][idx] = marriage

    save_json(DATA_FILE, marriages)
    save_json(INVENTORY_FILE, inventories)
    ring_name = SHOP_ITEMS.get(ring_id, {"name": ring_id}).get("name", ring_id)
    await msg.reply_text(
        "💍💍 Обмен кольцами состоялся!\n"
        f"Тип колец: {ring_name}\n"
        f"Поздравляем @{a} и @{b} с еще более крепким союзом!"
    )


async def rings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [
        "Варианты колец:",
        f"- ring_12k: {SHOP_ITEMS['ring_12k']['name']} ({SHOP_ITEMS['ring_12k']['price']} монет)",
        f"- ring_18k: {SHOP_ITEMS['ring_18k']['name']} ({SHOP_ITEMS['ring_18k']['price']} монет)",
        f"- ring_24k: {SHOP_ITEMS['ring_24k']['name']} ({SHOP_ITEMS['ring_24k']['price']} монет)",
        "",
        "Покупка:",
        "/buy ring_12k",
        "/buy ring_18k",
        "/buy ring_24k",
        "",
        "Обмен:",
        "/ring_exchange 12k",
        "/ring_exchange 18k",
        "/ring_exchange 24k",
    ]
    await update.message.reply_text("\n".join(lines))


async def my_rings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    caller = get_user_key(msg.from_user.username, msg.from_user.id)
    mentioned = get_mentioned_or_replied(update, context)
    user = mentioned[0] if mentioned else caller

    inv = ensure_inventory(user)
    ring_ids = ["ring_24k", "ring_18k", "ring_12k", "ring"]
    lines: list[str] = []
    total = 0

    for ring_id in ring_ids:
        qty = int(inv.get(ring_id, 0))
        if qty <= 0:
            continue
        total += qty
        ring_name = SHOP_ITEMS.get(ring_id, {"name": ring_id}).get("name", ring_id)
        lines.append(f"- {ring_name} ({ring_id}): x{qty}")

    if not lines:
        await msg.reply_text(f"У @{user} нет колец")
        return

    await msg.reply_text(f"Кольца @{user} (всего: {total}):\n" + "\n".join(lines))

async def alyans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    mentioned = get_mentioned_or_replied(update, context)
    actor = msg.from_user.username or str(msg.from_user.id)
    if len(mentioned) == 1 and mentioned[0] != actor:
        mentioned = [actor, mentioned[0]]

    if len(mentioned) < 1 or len(mentioned) > 80:
        await msg.reply_text("Альянс: 1-80 человек")
        return

    marriages.setdefault(chat_id, [])
    marriages[chat_id].append(
        {"type": "union", "members": mentioned, "date": datetime.now().isoformat()}
    )
    save_json(DATA_FILE, marriages)
    await msg.reply_text("Альянс: " + ", ".join([f"@{u}" for u in mentioned]))


async def vragi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    mentioned = get_mentioned_or_replied(update, context)
    actor = msg.from_user.username or str(msg.from_user.id)
    if len(mentioned) == 1 and mentioned[0] != actor:
        mentioned = [actor, mentioned[0]]

    if len(mentioned) < 2:
        await msg.reply_text("Использование: /vragi @user1 @user2")
        return

    marriages.setdefault(chat_id, [])
    marriages[chat_id].append(
        {"type": "enemies", "members": mentioned, "date": datetime.now().isoformat()}
    )
    save_json(DATA_FILE, marriages)
    await msg.reply_text("Враги: " + ", ".join([f"@{u}" for u in mentioned]))


async def braki(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    records = marriages.get(chat_id, [])

    lines = [f"{' и '.join([f'@{u}' for u in m['members']])}" for m in records if m.get("type") == "marriage"]
    if not lines:
        await msg.reply_text("Нет Браков")
        return
    await msg.reply_text("Браки:\n" + "\n".join(lines))


async def soyuzy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    records = marriages.get(chat_id, [])

    unions = [f"{', '.join([f'@{u}' for u in m['members']])}" for m in records if m.get("type") == "union"]
    enemies = [f"{', '.join([f'@{u}' for u in m['members']])}" for m in records if m.get("type") == "enemies"]

    if not unions and not enemies:
        await msg.reply_text("Нет союзов и врагов")
        return

    text = "Альянсы:\n" + ("\n".join(unions) if unions else "нет")
    text += "\n\nВраги:\n" + ("\n".join(enemies) if enemies else "нет")
    await msg.reply_text(text)


async def moisoyuz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    user = msg.from_user.username or str(msg.from_user.id)
    records = marriages.get(chat_id, [])

    lines = []
    for m in records:
        members = m.get("members", [])
        if user not in members:
            continue
        if m.get("type") == "marriage":
            lines.append("Брак: " + " и ".join([f"@{u}" for u in members]))
        elif m.get("type") == "union":
            lines.append("Альянс: " + ", ".join([f"@{u}" for u in members]))
        elif m.get("type") == "enemies":
            lines.append("Враги: " + ", ".join([f"@{u}" for u in members]))

    if not lines:
        await msg.reply_text("Ты нигде не состоишь")
        return
    await msg.reply_text(f"Список для @{user}:\n" + "\n".join(lines))


async def duel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    challenger = register_profile(msg.from_user)
    mentioned = get_mentioned_or_replied(update, context)

    if len(mentioned) != 1:
        await msg.reply_text("Использование: /duel @user")
        return

    target = resolve_user_key_from_token(mentioned[0]) if mentioned else None
    if not target and msg.reply_to_message and msg.reply_to_message.from_user:
        target = register_profile(msg.reply_to_message.from_user)
    if not target:
        await msg.reply_text("Не удалось определить пользователя.")
        return
    if target == challenger:
        await msg.reply_text("Нельзя вызвать себя на дуэль")
        return

    key = duel_key(chat_id, challenger, target)
    if key in duel_requests:
        await msg.reply_text("Вызов уже отправлен")
        return

    active_key = make_active_duel_key(chat_id, challenger, target)
    if active_key in active_duels:
        await msg.reply_text("Между этими игроками уже идет дуэль")
        return

    # Clear stale requests for the same pair so /duel can be resent cleanly.
    clear_duel_requests_for_pair(chat_id, challenger, target)

    duel_requests[key] = {"chat_id": chat_id, "challenger": challenger, "target": target}
    await msg.reply_text(
        f"{display_user(challenger)} вызывает {display_user(target)} на дуэль!\n"
        "Кликабельные команды:\n"
        "/accept - принять\n"
        "/decline - отклонить"
    )


async def accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    target = register_profile(msg.from_user)

    key, req = find_request_for_target(chat_id, target)
    if not req:
        await msg.reply_text("Для тебя нет активных дуэлей")
        return

    challenger = req["challenger"]
    clear_duel_requests_for_pair(chat_id, challenger, target)

    battle_key = make_active_duel_key(chat_id, challenger, target)
    first_turn = random.choice([challenger, target])
    active_duels[battle_key] = {
        "chat_id": chat_id,
        "a": challenger,
        "b": target,
        "turn": first_turn,
        "hp_a": 100,
        "hp_b": 100,
        "shots_done": 0,
    }

    await msg.reply_text(
        f"Дуэль началась: {display_user(challenger)} vs {display_user(target)}\n"
        f"Первый ход: {display_user(first_turn)}\n"
        f"HP {display_user(challenger)}: 100/100 {hp_bar(100)}\n"
        f"HP {display_user(target)}: 100/100 {hp_bar(100)}\n"
        "Команда выстрела: /shot"
    )


async def shot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    shooter = register_profile(msg.from_user)

    battle_key, duel_state = find_active_duel_for_user(chat_id, shooter)
    if not duel_state:
        await msg.reply_text("У тебя нет активной дуэли. Начни: /duel @user")
        return

    turn = duel_state.get("turn")
    if shooter != turn:
        await msg.reply_text(f"Сейчас ход не твой. Ходит: {display_user(turn)}")
        return

    a = duel_state.get("a")
    b = duel_state.get("b")
    opponent = b if shooter == a else a
    hp_a = int(duel_state.get("hp_a", 100))
    hp_b = int(duel_state.get("hp_b", 100))
    shots_done = int(duel_state.get("shots_done", 0))

    # У всех равные шансы: попадание 50/50.
    hit = random.random() < 0.5
    shots_done += 1

    if hit:
        damage = random.randint(18, 34)
        if shooter == a:
            hp_b = max(0, hp_b - damage)
        else:
            hp_a = max(0, hp_a - damage)
        shot_text = f"Попадание! {display_user(shooter)} нанес {damage} урона."
    else:
        shot_text = f"Промах! {display_user(shooter)} не попал."

    duel_state["hp_a"] = hp_a
    duel_state["hp_b"] = hp_b
    duel_state["shots_done"] = shots_done
    duel_state["turn"] = opponent
    active_duels[battle_key] = duel_state

    status_text = (
        f"{shot_text}\n"
        f"Выстрелы: {shots_done}\n"
        f"HP {display_user(a)}: {hp_a}/100 {hp_bar(hp_a)}\n"
        f"HP {display_user(b)}: {hp_b}/100 {hp_bar(hp_b)}"
    )

    # Завершение только если у одного из игроков закончилось HP.
    finished = hp_a <= 0 or hp_b <= 0
    if not finished:
        await reply_game(update, context, status_text + f"\nСледующий ход: {display_user(opponent)}\nКоманда: /shot", 120)
        return

    ensure_stat_user(duel_stats, a)
    ensure_stat_user(duel_stats, b)

    if hp_a == hp_b:
        duel_stats[a]["draws"] += 1
        duel_stats[b]["draws"] += 1
        result_text = "Итог дуэли: ничья."
    elif hp_a > hp_b:
        duel_stats[a]["wins"] += 1
        duel_stats[b]["losses"] += 1
        result_text = f"Итог дуэли: победил {display_user(a)}."
    else:
        duel_stats[b]["wins"] += 1
        duel_stats[a]["losses"] += 1
        result_text = f"Итог дуэли: победил {display_user(b)}."

    active_duels.pop(battle_key, None)
    save_json(DUEL_STATS_FILE, duel_stats)
    await reply_game(update, context, status_text + "\n" + result_text + "\nНовая дуэль: /duel @user", 150)


async def decline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    target = register_profile(msg.from_user)

    key, req = find_request_for_target(chat_id, target)
    if not req:
        await msg.reply_text("Для тебя нет активных дуэлей")
        return

    challenger = req["challenger"]
    clear_duel_requests_for_pair(chat_id, challenger, target)
    await msg.reply_text(f"{display_user(target)} отклонил(а) дуэль от {display_user(challenger)}")


async def duel_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Дуэли (кликабельно):\n"
        "/duel @user\n"
        "/accept\n"
        "/decline\n"
        "/shot\n"
        "/pvpstats [@user]\n"
        "/pvptop\n\n"
        "Правила:\n"
        "1) У каждого 100 HP\n"
        "2) Попадание / промах: 50/50\n"
        "3) При промахе ход переходит сопернику\n"
        "4) Дуэль идет до 0 HP у одного из игроков"
    )

async def pvpstats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    caller = msg.from_user.username or str(msg.from_user.id)
    mentioned = get_mentioned_or_replied(update, context)
    user = mentioned[0] if mentioned else caller

    ensure_stat_user(duel_stats, user)
    s = duel_stats[user]
    await msg.reply_text(
        f"PvP @{user}\n"
        f"Победы: {s['wins']}\n"
        f"Поражения: {s['losses']}\n"
        f"Ничья: {s['draws']}"
    )


async def pvptop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not duel_stats:
        await msg.reply_text("Пока нет PvP-данных")
        return

    ranking = sorted(
        duel_stats.items(),
        key=lambda item: (item[1].get("wins", 0), -item[1].get("losses", 0)),
        reverse=True,
    )[:10]

    lines = ["Рўоп PvP (по победам):"]
    for i, (user, s) in enumerate(ranking, start=1):
        lines.append(f"{i}. @{user} - W:{s.get('wins', 0)} L:{s.get('losses', 0)} D:{s.get('draws', 0)}")
    await msg.reply_text("\n".join(lines))


async def war(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    attacker = msg.from_user.username or str(msg.from_user.id)
    mentioned = get_mentioned_or_replied(update, context)

    if len(mentioned) != 1:
        await msg.reply_text("Использование: /war @user")
        return

    defender = mentioned[0]
    if defender == attacker:
        await msg.reply_text("Нельзя воевать с собой")
        return

    hp_a = 120
    hp_d = 120
    log_lines = [f"Война: @{attacker} vs @{defender}"]
    for round_num in range(1, 6):
        if hp_a <= 0 or hp_d <= 0:
            break
        dmg_a = random.randint(12, 35)
        dmg_d = random.randint(12, 35)
        hp_d -= dmg_a
        hp_a -= dmg_d
        log_lines.append(
            f"Р аунд {round_num}: @{attacker} -{dmg_a} HP вСЂага, @{defender} -{dmg_d} HP вСЂага | "
            f"HP: {max(hp_a,0)}:{max(hp_d,0)}"
        )

    ensure_stat_user(war_stats, attacker)
    ensure_stat_user(war_stats, defender)

    if hp_a == hp_d:
        war_stats[attacker]["draws"] += 1
        war_stats[defender]["draws"] += 1
        log_lines.append("Итог: ничья")
    elif hp_a > hp_d:
        war_stats[attacker]["wins"] += 1
        war_stats[defender]["losses"] += 1
        log_lines.append(f"Итог: победил @{attacker}")
    else:
        war_stats[defender]["wins"] += 1
        war_stats[attacker]["losses"] += 1
        log_lines.append(f"Итог: победил @{defender}")

    save_json(WAR_STATS_FILE, war_stats)
    await msg.reply_text("\n".join(log_lines))


async def warstats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    caller = msg.from_user.username or str(msg.from_user.id)
    mentioned = get_mentioned_or_replied(update, context)
    user = mentioned[0] if mentioned else caller

    ensure_stat_user(war_stats, user)
    s = war_stats[user]
    await msg.reply_text(
        f"Войны @{user}\n"
        f"Победы: {s['wins']}\n"
        f"Поражения: {s['losses']}\n"
        f"Ничья: {s['draws']}"
    )


async def wartop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not war_stats:
        await msg.reply_text("Пока нет данных по войнам")
        return

    ranking = sorted(
        war_stats.items(),
        key=lambda item: (item[1].get("wins", 0), -item[1].get("losses", 0)),
        reverse=True,
    )[:10]

    lines = ["Топ войн (по победам):"]
    for i, (user, s) in enumerate(ranking, start=1):
        lines.append(f"{i}. @{user} - W:{s.get('wins', 0)} L:{s.get('losses', 0)} D:{s.get('draws', 0)}")
    await msg.reply_text("\n".join(lines))


async def words_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)

    word_games[chat_id] = {
        "active": True,
        "last_letter": "",
        "used_words": [],
        "last_user": "",
    }
    save_json(WORD_GAME_FILE, word_games)
    await msg.reply_text("Игра в слова запущена. Пишите: /word слово")


async def word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    user = msg.from_user.username or str(msg.from_user.id)
    game = word_games.get(chat_id)

    if not game or not game.get("active"):
        await msg.reply_text("Сначала запусти игру: /words_start")
        return

    if not context.args:
        await msg.reply_text("Использование: /word слово")
        return

    raw_word = " ".join(context.args).strip()
    w = normalize_word(raw_word)
    if len(w) < 2:
        await msg.reply_text("Слово слишком короткое")
        return

    used_words = set(game.get("used_words", []))
    if w in used_words:
        await msg.reply_text("Это слово уже было")
        return

    required = game.get("last_letter", "")
    if required and not w.startswith(required):
        await msg.reply_text(f"Нужна буква: {required.upper()}")
        return

    last_user = game.get("last_user", "")
    if last_user == user:
        await msg.reply_text("Сейчас ход другого игрока")
        return

    used_words.add(w)
    next_letter = get_last_letter(w)

    game["used_words"] = sorted(list(used_words))
    game["last_letter"] = next_letter
    game["last_user"] = user
    word_games[chat_id] = game
    save_json(WORD_GAME_FILE, word_games)

    if next_letter:
        await msg.reply_text(f"Принято: {w}. Следующая буква: {next_letter.upper()}")
    else:
        await msg.reply_text(f"Принято: {w}. Следующая буква: ЛЮБАЯ")


async def words_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    game = word_games.get(chat_id)
    if not game or not game.get("active"):
        await msg.reply_text("Игра не запущена")
        return

    await msg.reply_text(
        "Игра активна\n"
        f"Слов использовано: {len(game.get('used_words', []))}\n"
        f"Текущая буква: {(game.get('last_letter') or 'любая').upper()}"
    )


async def words_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    game = word_games.get(chat_id)
    if not game or not game.get("active"):
        await msg.reply_text("Игра уже остановлена")
        return

    count_words = len(game.get("used_words", []))
    word_games[chat_id] = {
        "active": False,
        "last_letter": "",
        "used_words": [],
        "last_user": "",
    }
    save_json(WORD_GAME_FILE, word_games)
    await msg.reply_text(f"Игра остановлена. Всего слов: {count_words}")


async def raid_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    state = raid_states.get(chat_id, {})
    if state.get("active"):
        started = parse_iso_date(state.get("started_at"))
        if started and (datetime.now() - started).total_seconds() > 1800:
            state["active"] = False
        else:
            await msg.reply_text("Рейд уже идет. Используйте /raid_hit")
            return

    boss_names = ["Дракон", "Титан", "Лич", "Гидра", "Голем"]
    hp = random.randint(350, 4000)
    boss = random.choice(boss_names)
    raid_states[chat_id] = {"active": True, "boss": boss, "hp": hp, "max_hp": hp, "attackers": {}, "started_at": datetime.now().isoformat()}
    save_json(RAID_FILE, raid_states)
    await msg.reply_text(f"Рейд начался!\nБосс: {boss}\nHP: {hp}\nБейте босса: /raid_hit")


async def raid_hit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    state = raid_states.get(chat_id)
    if not state or not state.get("active"):
        await msg.reply_text("Сейчас нет активного рейда. Команда: /raid_start")
        return
    started = parse_iso_date(state.get("started_at"))
    if started and (datetime.now() - started).total_seconds() > 1800:
        state["active"] = False
        save_json(RAID_FILE, raid_states)
        await msg.reply_text("Рейд завершился по времени. Запустите новый: /raid_start")
        return

    user = register_profile(msg.from_user)
    damage = random.randint(25, 85)
    if random.random() < 0.15:
        damage = int(damage * 1.7)

    state["hp"] = max(0, int(state["hp"]) - damage)
    attackers = state.setdefault("attackers", {})
    attackers[user] = int(attackers.get(user, 0)) + damage

    if state["hp"] > 0:
        await msg.reply_text(
            f"{display_user(user)} нанес {damage} урона.\n"
            f"Босс {state['boss']} HP: {state['hp']}/{state['max_hp']}"
        )
        save_json(RAID_FILE, raid_states)
        return

    state["active"] = False
    top = sorted(attackers.items(), key=lambda x: x[1], reverse=True)[:5]
    lines = [f"Босс {state['boss']} повержен!"]
    if top:
        lines.append("Топ урона:")
        for i, (name, dmg) in enumerate(top, start=1):
            lines.append(f"{i}. {display_user(name)}: {dmg}")

    for name, dmg in attackers.items():
        reward = 10 + dmg // 20
        entry = daily_rewards.setdefault(name, {"coins": 0, "streak": 0, "last_claim": ""})
        entry["coins"] = int(entry.get("coins", 0)) + reward

    save_json(RAID_FILE, raid_states)
    save_json(DAILY_FILE, daily_rewards)
    await msg.reply_text("\n".join(lines) + "\nНаграды добавлены в баланс.")


async def raid_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    state = raid_states.get(chat_id)
    if not state or not state.get("active"):
        await msg.reply_text("Активного рейда нет.")
        return

    attackers = state.get("attackers", {})
    top = sorted(attackers.items(), key=lambda x: x[1], reverse=True)[:3]
    text = f"Босс: {state['boss']}\nHP: {state['hp']}/{state['max_hp']}"
    if top:
        text += "\nТоп урона:\n" + "\n".join([f"{i}. {display_user(u)}: {d}" for i, (u, d) in enumerate(top, 1)])
    await msg.reply_text(text)


async def raid_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    ranking = sorted(
        ((u, int(v.get("coins", 0))) for u, v in daily_rewards.items()),
        key=lambda x: x[1],
        reverse=True,
    )[:10]
    if not ranking:
        await msg.reply_text("Пока нет данных.")
        return

    lines = ["Топ по монетам:"]
    for i, (u, c) in enumerate(ranking, start=1):
        lines.append(f"{i}. @{u}: {c} монет")
    await msg.reply_text("\n".join(lines))


async def raid_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Рейд (кликабельно):\n"
        "/raid_start\n"
        "/raid_hit\n"
        "/raid_status\n"
        "/raid_top"
    )


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = register_profile(msg.from_user)
    entry = daily_rewards.setdefault(user, {"coins": 0, "streak": 0, "last_claim": ""})
    today = today_str()
    last = entry.get("last_claim", "")

    if last == today:
        await msg.reply_text(f"Сегодня уже получено.\nБаланс: {entry.get('coins', 0)} монет")
        return

    days_diff = 99
    if last:
        try:
            days_diff = (datetime.fromisoformat(today).date() - datetime.fromisoformat(last).date()).days
        except Exception:
            days_diff = 99

    if days_diff == 1:
        entry["streak"] = int(entry.get("streak", 0)) + 1
    else:
        entry["streak"] = 1

    reward = 50 + min(70, entry["streak"] * 5)
    entry["coins"] = int(entry.get("coins", 0)) + reward
    entry["last_claim"] = today
    daily_rewards[user] = entry
    save_json(DAILY_FILE, daily_rewards)
    lvl, _, up = grant_xp(user, 12)

    await msg.reply_text(
        f"Ежедневная награда: +{reward}\n"
        f"Серия: {entry['streak']} дней\n"
        f"Баланс: {entry['coins']} монет\n"
        + (f"Новый ранг: {xp_title(lvl)}" if up else "")
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    caller = register_profile(msg.from_user)
    mentioned = get_mentioned_or_replied(update, context)
    user = resolve_user_key_from_token(mentioned[0]) if mentioned else caller
    if not user:
        user = caller
    entry = daily_rewards.setdefault(user, {"coins": 0, "streak": 0, "last_claim": ""})
    await msg.reply_text(
        f"Баланс {display_user(user)}: {entry.get('coins', 0)} монет\n"
        f"Серия daily: {entry.get('streak', 0)}"
    )


async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["Магазин:"]
    for item_id, item in SHOP_ITEMS.items():
        lines.append(f"- {item_id}: {item['name']} ({item['price']} монет)")
    lines.append("Покупка: /buy item_id [кол-во]")
    await update.message.reply_text("\n".join(lines))


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = get_user_key(msg.from_user.username, msg.from_user.id)

    if not context.args:
        await msg.reply_text("Использование: /buy item_id [кол-во]")
        return

    item_id = context.args[0].lower().strip()
    item = SHOP_ITEMS.get(item_id)
    if not item:
        await msg.reply_text("Такого предмета нет. Список: /shop")
        return

    qty = 1
    if len(context.args) > 1:
        try:
            qty = int(context.args[1])
        except ValueError:
            await msg.reply_text("Количество должно быть числом")
            return

    if qty < 1 or qty > 99:
        await msg.reply_text("Количество: от 1 до 99")
        return

    cost = item["price"] * qty
    wallet = ensure_wallet(user)
    coins = int(wallet.get("coins", 0))
    if coins < cost:
        await msg.reply_text(f"Не хватает монет. Нужно: {cost}, у тебя: {coins}")
        return

    wallet["coins"] = coins - cost
    inv = ensure_inventory(user)
    inv[item_id] = int(inv.get(item_id, 0)) + qty

    save_json(DAILY_FILE, daily_rewards)
    save_json(INVENTORY_FILE, inventories)
    await msg.reply_text(
        f"Покупка успешна: {item['name']} x{qty}\n"
        f"Списано: {cost}\n"
        f"Баланс: {wallet['coins']}"
    )


async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    caller = get_user_key(msg.from_user.username, msg.from_user.id)
    mentioned = get_mentioned_or_replied(update, context)
    user = mentioned[0] if mentioned else caller

    inv = ensure_inventory(user)
    if not inv:
        await msg.reply_text(f"Инвентарь @{user} пуст")
        return

    lines = [f"Инвентарь @{user}:"]
    for item_id, qty in sorted(inv.items()):
        item = SHOP_ITEMS.get(item_id, {"name": item_id})
        lines.append(f"- {item['name']} ({item_id}): x{qty}")
    await msg.reply_text("\n".join(lines))


async def eco_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Экономика (кликабельно):\n"
        "/daily\n"
        "/balance [@user]\n"
        "/shop\n"
        "/buy item_id [кол-во]\n"
        "/inventory [@user]"
        "\n\n"
        "Мопс-Фармила:\n"
        "/mops_on\n"
        "/mops_off\n"
        "/mops_status"
    )


async def mops_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    cfg = ensure_mops_chat(chat_id)
    cfg["enabled"] = True
    save_json(MOPS_FILE, mops_state)
    await update.message.reply_text(
        "🐶 Мопс-Фармила включен.\n"
        "Буду писать ежедневный отчёт о стабильности бота."
    )


async def mops_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    cfg = ensure_mops_chat(chat_id)
    cfg["enabled"] = False
    save_json(MOPS_FILE, mops_state)
    await update.message.reply_text("🐶 Мопс-Фармила выключен для этого чата.")


async def mops_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    cfg = ensure_mops_chat(chat_id)
    uptime = format_uptime(datetime.now() - BOT_STARTED_AT)
    status = "включен" if cfg.get("enabled") else "выключен"
    last_sent = cfg.get("last_sent") or "еще не отправлялся"
    await update.message.reply_text(
        f"🐶 Мопс-Фармила: {status}\n"
        f"Аптайм: {uptime}\n"
        f"Последний отчёт: {last_sent}\n"
        f"Интервал отчёта: {cfg.get('report_interval_min', 300)} мин"
    )


async def reports_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = ensure_mops_chat(str(update.effective_chat.id))
    await update.message.reply_text(
        "📡 Настройки отчётов:\n"
        f"Мопс: {'вкл' if cfg.get('mops_reports_enabled', True) else 'выкл'}\n"
        f"Интервал: {cfg.get('report_interval_min', 300)} мин\n"
        "Готовые режимы: 60, 300, 720, 1440\n"
        "Команда: /reports_interval <минуты>"
    )


async def reports_set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    cfg = ensure_mops_chat(str(msg.chat_id))
    if not context.args or not str(context.args[0]).isdigit():
        await msg.reply_text("Формат: /reports_interval 60|300|720|1440 (или любое число 60..1440)")
        return
    val = int(context.args[0])
    if val < 60 or val > 1440:
        await msg.reply_text("Допустимо: от 60 до 1440 минут.")
        return
    cfg["report_interval_min"] = val
    save_json(MOPS_FILE, mops_state)
    await msg.reply_text(f"Интервал отчёта обновлён: каждые {val} мин.")


async def reports_interval_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Раз в 1 час", callback_data="repint:60"), InlineKeyboardButton("Раз в 5 часов", callback_data="repint:300")],
            [InlineKeyboardButton("Раз в 12 часов", callback_data="repint:720"), InlineKeyboardButton("Раз в 24 часа", callback_data="repint:1440")],
        ]
    )
    await update.message.reply_text("Выбери интервал отчётов:", reply_markup=kb)


async def reports_interval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data.startswith("repint:"):
        return
    await q.answer()
    val = int(q.data.split(":", 1)[1])
    cfg = ensure_mops_chat(str(q.message.chat_id))
    cfg["report_interval_min"] = max(60, min(1440, val))
    save_json(MOPS_FILE, mops_state)
    await q.message.reply_text(f"Интервал отчётов установлен: {cfg['report_interval_min']} мин.")


async def donate_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⭐ Stars", callback_data="dpanel:stars"), InlineKeyboardButton("🎁 Premium", callback_data="dpanel:premium")],
            [InlineKeyboardButton("🚀 Boost", callback_data="dpanel:boost"), InlineKeyboardButton("📊 Моя отметка", callback_data="dpanel:note")],
            [InlineKeyboardButton("🔗 Открыть @PremiumBot", url="https://t.me/PremiumBot")],
        ]
    )
    await update.message.reply_text(
        "💎 Донат и поддержка:\n"
        "1) Telegram Stars: отправка через встроенные платежи бота (если подключишь платежного провайдера)\n"
        "2) Telegram Premium/Stars через @PremiumBot вручную (как внешний шлюз)\n"
        "Ссылка: https://t.me/PremiumBot\n\n"
        "Команды:\n"
        "/donate_stars — как отправить Stars\n"
        "/donate_premium — как подарить Premium",
        reply_markup=kb,
    )


async def donate_stars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "⭐ Как поддержать звездами:\n"
        "1) Открой @PremiumBot\n"
        "2) Выбери Stars\n"
        "3) Отправь на нужный аккаунт/кошелек\n"
        "4) В боте потом отметь донат командой /donate_note <сумма>"
    )


async def donate_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎁 Как подарить Telegram Premium:\n"
        "1) Открой @PremiumBot\n"
        "2) Выбери Premium Gift\n"
        "3) Отправь подарок\n"
        "4) Для учета в рейтинге доната используй /donate_note premium"
    )


async def donate_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    note = " ".join(context.args or []).strip()
    if not note:
        await msg.reply_text("Формат: /donate_note <сумма|premium|комментарий>")
        return
    key = str(msg.chat_id)
    rows = donate_log.setdefault(key, [])
    rows.append(
        {
            "user": register_profile(msg.from_user),
            "note": note,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
    )
    donate_log[key] = rows[-500:]
    save_json(DONATE_LOG_FILE, donate_log)
    await msg.reply_text(f"Спасибо за поддержку! Отметка доната записана: {note}")


async def donate_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data.startswith("dpanel:"):
        return
    await q.answer()
    mode = q.data.split(":", 1)[1]
    if mode == "stars":
        await q.message.reply_text("⭐ Поддержка Stars: /donate_stars")
        return
    if mode == "premium":
        await q.message.reply_text("🎁 Подарок Premium: /donate_premium")
        return
    if mode == "boost":
        await q.message.reply_text("🚀 Буст: можешь отправить Stars/Premium через @PremiumBot и отметить: /donate_note boost")
        return
    await q.message.reply_text("📝 Отметка доната: /donate_note <сумма|premium|комментарий>")


async def donate_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not is_owner(msg.from_user):
        await msg.reply_text("Команда только для владельца.")
        return
    key = str(msg.chat_id)
    rows = donate_log.get(key, [])
    if not rows:
        await msg.reply_text("Донат-лог пуст.")
        return
    users = {}
    for r in rows:
        u = r.get("user", "")
        users[u] = users.get(u, 0) + 1
    top = sorted(users.items(), key=lambda x: x[1], reverse=True)[:10]
    lines = [f"Донат-отметок: {len(rows)}", "Топ по отметкам:"]
    for i, (u, c) in enumerate(top, 1):
        lines.append(f"{i}. {display_user(u)} — {c}")
    await msg.reply_text("\n".join(lines))


async def channel_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📣 Шаблон для Telegram-канала с командами:\n\n"
        "1) Приветствие:\n"
        "Добро пожаловать в канал Мопса-Фармилы. Здесь все команды и примеры.\n\n"
        "2) Экономика:\n"
        "/daily, /balance, /shop, /buy, /inventory, /pay\n"
        "Пример: /buy ring_12k 1\n\n"
        "3) Брак и отношения:\n"
        "/brak @user, /relation, .отн статус @user, .отн действия @user\n\n"
        "4) Игры:\n"
        "/mops_guess, /quiz, /rps, /mafia_create\n\n"
        "5) Умные команды:\n"
        ".погода Москва, /q, /price_watch_add <ссылка>\n\n"
        "6) Отчеты:\n"
        "/reports_status, /reports_buttons, /reports_interval 300\n\n"
        "Скопируй это в посты канала и дополняй по мере обновлений."
    )

# === МОПС-ФАРМИЛА ФУНКЦИИ ===

MOPS_GREETINGS = ["Привет! 🐶", "Здорово!", "Приветики!", "Хау!", "Привет, друг!"]
MOPS_FAREWELLS = ["Пока! 🐶", "До свидания!", "Бай!", "Увидимся!"]
MOPS_THANKS = ["Пожалуйста! 🐶", "Рад помочь!", "Обращайся!"]
MOPS_JOKES = ["Почему программист ушёл? Потому что не получил массив.", "Что сказал ноль восьмёрке? Классный ремень!", "Штирлиц выстрелил вслепую. Слепая упала."]
MOPS_QUOTES = ["«Всё будет хорошо» — неизвестный оптимист.", "«Работа не волк, но в лес не убежит».", "«Лучше поздно, чем никогда»."]
MOPS_FACTS = ["Пчёлы умеют различать человеческие лица.", "Осьминоги имеют три сердца.", "Бабочки пробуют вкус ногами.", "Венера вращается в обратную сторону."]
MOPS_COMPLIMENTS = ["Ты молодец! 🌟", "Ты потрясающий! 🔥", "У тебя всё получится! 💪", "Ты лучший! ❤️"]
MOPS_INSULTS = ["Ты как печалька, только хуже.", "Ты конечно молодец, но не очень.", "Твой код — это искусство... неизвестного художника."]
MOPS_8BALL = ["Да", "Нет", "Возможно", "Спроси позже", "Определённо да", "Лучше не надо"]
MOPS_HOROSCOPES = {"aries": "Овен: Сегодня день активных действий!", "taurus": "Телец: Время для отдыха.", "gemini": "Близнецы: Общение принесёт удачу.", "cancer": "Рак: Семья важна сегодня.", "leo": "Лев: Вас ждёт признание!", "virgo": "Дева: Детали решат всё.", "libra": "Весы: Гармония в отношениях.", "scorpio": "Скорпион: Тайны раскроются.", "sagittarius": "Стрелец: Приключения ждут!", "capricorn": "Козерог: Работа принесёт плоды.", "aquarius": "Водолей: Неожиданные идеи.", "pisces": "Рыбы: Творчество на высоте."}
MOPS_WEATHER = ["Солнечно, +25°C ☀️", "Облачно, +18°C ☁️", "Дождь, +15°C 🌧", "Снег, -5°C ❄️"]
HOSHI_TIPS = [
    "Хоши советует: сохраняй монеты в банке, чтобы капали проценты.",
    "Хоши напоминает: ежедневка дает серию, не пропускай.",
    "Хоши: перед дуэлью загляни в инвентарь и купи полезные предметы.",
    "Хоши: квест дня можно закрыть через рыбалку, игры и тренировки.",
]
HOSHI_SCENES = [
    "🐱 Хоши шепчет Мопсу-Фармиле: «Сегодня без багов, только победы». 🐶",
    "🐶 Мопс-Фармила спорит с Хоши, кто быстрее закроет квест дня.",
    "🐱 Хоши принесла удачу в рейд. Мопс-Фармила доволен.",
    "🐶 Мопс-Фармила и 🐱 Хоши устроили мини-совет: «Фармим красиво и честно».",
]

async def mops_greet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(MOPS_GREETINGS))

async def mops_farewell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(MOPS_FAREWELLS))

async def mops_thanks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(MOPS_THANKS))

async def mops_joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(MOPS_JOKES))

async def mops_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(MOPS_QUOTES))

async def mops_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(MOPS_FACTS))

async def mops_compliment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(MOPS_COMPLIMENTS))

async def mops_insult(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(MOPS_INSULTS))

async def mops_8ball(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"🔮 {random.choice(MOPS_8BALL)}")

async def mops_coin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"🪙 {random.choice(['Орёл', 'Решка'])}")

async def mops_dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"🎲 Выпало: {random.randint(1, 6)}")

async def mops_random(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"🎲 Число: {random.randint(1, 100)}")

async def mops_horoscope(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sign = random.choice(list(MOPS_HOROSCOPES.keys()))
    await update.message.reply_text(f"♈️ {sign.capitalize()}: {MOPS_HOROSCOPES[sign]}")

def _http_get_json(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Mops-Farmila Bot)", "Accept-Language": "ru-RU,ru;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    return json.loads(raw) if raw else {}


def _city_weather_text(city: str) -> str:
    quoted_city = urllib.parse.quote(city.strip())
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={quoted_city}&count=1&language=ru&format=json"
    geo = _http_get_json(geo_url, timeout=10)
    rows = geo.get("results") or []
    if not rows:
        return ""
    row = rows[0]
    lat = row.get("latitude")
    lon = row.get("longitude")
    cname = row.get("name") or city
    country = row.get("country") or ""
    wx_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,weather_code&timezone=auto"
    )
    wx = _http_get_json(wx_url, timeout=10)
    cur = wx.get("current") or {}
    code = int(cur.get("weather_code", -1))
    codes = {0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность", 3: "пасмурно", 45: "туман", 61: "дождь", 71: "снег", 95: "гроза"}
    return (
        f"🌤 Погода в {cname}{(', ' + country) if country else ''}:\n"
        f"Температура: {cur.get('temperature_2m', '?')}°C\n"
        f"Ощущается: {cur.get('apparent_temperature', '?')}°C\n"
        f"Ветер: {cur.get('wind_speed_10m', '?')} км/ч\n"
        f"Состояние: {codes.get(code, 'уточняется')}"
    )


async def mops_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    city = " ".join(context.args or []).strip()
    raw = (msg.text or "").strip()
    if not city and raw:
        cleaned = re.sub(r"^[.!/]+", "", raw).strip()
        low = cleaned.lower()
        for pref in ("погода", "weather"):
            if low.startswith(pref):
                city = cleaned[len(pref):].strip(" :-,()[]{}")
                break
    if city:
        try:
            text = _city_weather_text(city)
            if text:
                await msg.reply_text(text)
                return
        except Exception:
            pass
        await msg.reply_text(f"Не удалось получить погоду для «{city}».")
        return
    await msg.reply_text("Формат: .погода <город> или /weather <город>")


async def quote_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    src = msg.reply_to_message
    text = ""
    author = "Пользователь"
    if src:
        text = (src.text or src.caption or "").strip()
        if src.from_user:
            author = src.from_user.full_name or src.from_user.username or author
    if not text:
        text = " ".join(context.args or []).strip()
        if msg.from_user:
            author = msg.from_user.full_name or msg.from_user.username or author
    if not text:
        await msg.reply_text("Используй /q ответом на сообщение или /q <текст>")
        return
    header = f"💬 {author}\n"
    payload = header + text
    if len(payload) <= 3800:
        await msg.reply_text(payload)
        return
    # Для очень длинных сообщений отправляем в частях.
    await msg.reply_text(header + text[:3500] + "…")
    rest = text[3500:]
    while rest:
        chunk = rest[:3500]
        rest = rest[3500:]
        await msg.reply_text(chunk)


def _fetch_html(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def _extract_price_rub(html: str) -> int | None:
    if not html:
        return None
    patterns = [
        r'"price"\s*:\s*"?(\\d{2,9})"?',
        r'"priceValue"\s*:\s*"?(\\d{2,9})"?',
        r'content="(\\d{2,9})"[^>]*product:price:amount',
        r'(\\d{2,3}(?:\\s\\d{3})+)\\s*₽',
        r'(\\d{2,9})\\s*руб',
    ]
    for p in patterns:
        m = re.search(p, html, flags=re.IGNORECASE)
        if not m:
            continue
        raw = re.sub(r"\\D", "", m.group(1))
        if raw.isdigit():
            val = int(raw)
            if 10 <= val <= 10_000_000:
                return val
    return None


def _extract_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return "Товар"
    return re.sub(r"\\s+", " ", m.group(1)).strip()[:120] or "Товар"


def _market_name(url: str) -> str:
    u = (url or "").lower()
    if "wildberries" in u or "wb.ru" in u:
        return "Wildberries"
    if "ozon" in u:
        return "Ozon"
    if "market.yandex" in u or "yandex.market" in u:
        return "Яндекс.Маркет"
    return "Маркетплейс"


def _snapshot_price(url: str) -> tuple[str, int | None]:
    html = _fetch_html(url)
    return _extract_title(html), _extract_price_rub(html)


def _norm_product_title(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"\b(купить|цена|ozon|wildberries|яндекс\\.маркет|yandex market|маркетплейс)\b", " ", t)
    t = re.sub(r"[^a-zа-я0-9]+", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    parts = t.split()[:8]
    return " ".join(parts)


async def price_watch_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    raw = " ".join(context.args or []).strip()
    if not raw and msg and msg.text:
        m = re.search(r"https?://\\S+", msg.text)
        raw = m.group(0) if m else ""
    if not raw.startswith("http"):
        await msg.reply_text("Формат: /price_watch_add <ссылка_на_товар>")
        return
    try:
        title, price = _snapshot_price(raw)
    except Exception:
        await msg.reply_text("Не удалось прочитать страницу товара. Проверь ссылку.")
        return
    wid = uuid4().hex[:8]
    price_watch[wid] = {
        "chat_id": str(msg.chat_id),
        "user_id": str(msg.from_user.id),
        "url": raw,
        "market": _market_name(raw),
        "title": title,
        "group_key": _norm_product_title(title),
        "last_price": int(price or 0),
        "created_at": int(time.time()),
        "last_check": 0,
        "target_price": 0,
        "target_hit_notified": False,
    }
    save_json(PRICE_WATCH_FILE, price_watch)
    await msg.reply_text(f"✅ Слежка добавлена [{wid}]\n{title}\nМаркет: {_market_name(raw)}\nЦена: {price or '?'} ₽")


async def price_watch_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    lines = ["Слежки за ценой:"]
    count = 0
    for wid, w in price_watch.items():
        if str(w.get("chat_id")) != str(msg.chat_id):
            continue
        count += 1
        lp = int(w.get("last_price", 0))
        tgt = int(w.get("target_price", 0))
        ttxt = f", цель ≤ {tgt} ₽" if tgt > 0 else ""
        lines.append(f"[{wid}] {w.get('market','')} | {w.get('title','Товар')} | {lp if lp else '?'} ₽{ttxt}")
    if count == 0:
        await msg.reply_text("Активных слежек нет.")
        return
    await msg.reply_text("\n".join(lines[:40]))


async def price_watch_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not context.args:
        await msg.reply_text("Формат: /price_watch_remove <id>")
        return
    wid = context.args[0].strip()
    row = price_watch.get(wid)
    if not row:
        await msg.reply_text("ID слежки не найден.")
        return
    if str(row.get("chat_id")) != str(msg.chat_id):
        await msg.reply_text("Эта слежка из другого чата.")
        return
    price_watch.pop(wid, None)
    save_json(PRICE_WATCH_FILE, price_watch)
    await msg.reply_text(f"🗑 Слежка [{wid}] удалена.")


async def run_price_watch_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    now_ts = int(time.time())
    changed = False
    for wid, w in list(price_watch.items()):
        if now_ts - int(w.get("last_check", 0)) < 900:
            continue
        url = str(w.get("url", ""))
        if not url.startswith("http"):
            continue
        try:
            title, price = _snapshot_price(url)
        except Exception:
            continue
        old = int(w.get("last_price", 0))
        new = int(price or 0)
        w["last_check"] = now_ts
        if title:
            w["title"] = title
        if new > 0 and old > 0 and new != old:
            diff = new - old
            arrow = "⬇️" if diff < 0 else "⬆️"
            txt = (
                f"{arrow} Цена изменилась [{wid}]\n"
                f"{w.get('title','Товар')}\n"
                f"{w.get('market','Маркет')}\n"
                f"Было: {old} ₽\nСтало: {new} ₽\n"
                f"Разница: {diff:+d} ₽\n{url}"
            )
            try:
                await context.bot.send_message(chat_id=int(w.get("chat_id")), text=txt)
            except Exception:
                pass
        target = int(w.get("target_price", 0))
        hit_sent = bool(w.get("target_hit_notified", False))
        if target > 0 and new > 0:
            if new <= target and not hit_sent:
                try:
                    await context.bot.send_message(
                        chat_id=int(w.get("chat_id")),
                        text=(
                            f"🎯 Цена достигла цели [{wid}]\n"
                            f"{w.get('title','Товар')}\n"
                            f"Текущая: {new} ₽, цель: {target} ₽\n{url}"
                        ),
                    )
                except Exception:
                    pass
                w["target_hit_notified"] = True
            elif new > target:
                w["target_hit_notified"] = False
        if new > 0:
            w["last_price"] = new
            w["group_key"] = _norm_product_title(w.get("title", ""))
        price_watch[wid] = w
        changed = True
    if changed:
        save_json(PRICE_WATCH_FILE, price_watch)


async def price_watch_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_price_watch_job(context)
    await update.message.reply_text("Проверка цен выполнена.")


async def price_watch_compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    rows = []
    for wid, w in price_watch.items():
        if str(w.get("chat_id")) != str(msg.chat_id):
            continue
        p = int(w.get("last_price", 0))
        if p > 0:
            rows.append((p, wid, w))
    if len(rows) < 2:
        await msg.reply_text("Для сравнения нужно минимум 2 слежки с распознанной ценой.")
        return
    rows.sort(key=lambda x: x[0])
    cheap = rows[0]
    exp = rows[-1]
    await msg.reply_text(
        "Сравнение цен по текущим слежкам:\n"
        f"✅ Дешевле всего: [{cheap[1]}] {cheap[2].get('market','')} — {cheap[0]} ₽\n"
        f"❗ Дороже всего: [{exp[1]}] {exp[2].get('market','')} — {exp[0]} ₽"
    )


async def price_watch_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if len(context.args or []) < 2:
        await msg.reply_text("Формат: /price_watch_target <id> <цена>")
        return
    wid = str(context.args[0]).strip()
    if not str(context.args[1]).isdigit():
        await msg.reply_text("Цена должна быть числом.")
        return
    target = int(context.args[1])
    row = price_watch.get(wid)
    if not row:
        await msg.reply_text("ID слежки не найден.")
        return
    if str(row.get("chat_id")) != str(msg.chat_id):
        await msg.reply_text("Эта слежка из другого чата.")
        return
    row["target_price"] = max(0, target)
    row["target_hit_notified"] = False
    price_watch[wid] = row
    save_json(PRICE_WATCH_FILE, price_watch)
    await msg.reply_text(f"Цель для [{wid}] установлена: ≤ {target} ₽")


async def price_watch_best(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    groups: dict[str, list[tuple[int, str, dict]]] = {}
    for wid, w in price_watch.items():
        if str(w.get("chat_id")) != str(msg.chat_id):
            continue
        p = int(w.get("last_price", 0))
        if p <= 0:
            continue
        gk = str(w.get("group_key", "") or _norm_product_title(w.get("title", "")))
        if not gk:
            continue
        groups.setdefault(gk, []).append((p, wid, w))
    if not groups:
        await msg.reply_text("Недостаточно данных для сравнения по одинаковым товарам.")
        return
    lines = ["Где дешевле по похожим товарам:"]
    shown = 0
    for gk, arr in groups.items():
        if len(arr) < 2:
            continue
        arr.sort(key=lambda x: x[0])
        cheap = arr[0]
        exp = arr[-1]
        if cheap[0] == exp[0]:
            continue
        lines.append(
            f"• {gk}\n"
            f"дешевле: {cheap[2].get('market','')} {cheap[0]} ₽ [{cheap[1]}]\n"
            f"дороже: {exp[2].get('market','')} {exp[0]} ₽ [{exp[1]}]"
        )
        shown += 1
        if shown >= 10:
            break
    if shown == 0:
        await msg.reply_text("Пока нет групп с разницей цен между маркетами.")
        return
    await msg.reply_text("\n".join(lines))


async def hoshi_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🐱 Хоши умеет:\n"
        "/hoshi_tip — полезный совет\n"
        "/hoshi_on — включить Хоши в чате\n"
        "/hoshi_off — выключить Хоши в чате\n"
        "/hoshi_status — статус Хоши\n"
        "Без слеша: хоши, хоши совет, хоши баланс, хоши квест, хоши вкл, хоши выкл"
    )


async def hoshi_tip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(random.choice(HOSHI_TIPS))


async def hoshi_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    w = ensure_wallet_key(user_key)
    b = ensure_bank(user_key)
    await msg.reply_text(
        f"🐱 Хоши-отчет:\n"
        f"Кошелек: {w.get('coins', 0)}\n"
        f"Банк: {b.get('deposit', 0)}\n"
        f"Совет: держи часть монет в банке для процентов."
    )


async def hoshi_quest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    q = ensure_quest(user_key)
    left = max(0, int(q.get("target", 5)) - int(q.get("progress", 0)))
    await msg.reply_text(
        f"🐱 Хоши по квесту:\n"
        f"Прогресс: {q.get('progress', 0)}/{q.get('target', 5)}\n"
        f"Осталось: {left}\n"
        f"Быстрый путь: рыбалка, лотерея, тренировка мопса."
    )


async def hoshi_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    cfg = ensure_mops_chat(chat_id)
    cfg["hoshi_enabled"] = True
    save_json(MOPS_FILE, mops_state)
    await update.message.reply_text("🐱 Хоши включена для этого чата.")


async def hoshi_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    cfg = ensure_mops_chat(chat_id)
    cfg["hoshi_enabled"] = False
    save_json(MOPS_FILE, mops_state)
    await update.message.reply_text("🐱 Хоши выключена для этого чата.")


async def hoshi_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    cfg = ensure_mops_chat(chat_id)
    st = "включена" if cfg.get("hoshi_enabled", True) else "выключена"
    await update.message.reply_text(f"🐱 Хоши: {st}")

async def mops_love(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"❤️ Любовь: {random.randint(1, 100)}%")


async def gviar_who(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    raw = (msg.text or "").strip()
    question = raw[len("гвиар кто"):].strip(" ?")
    if not question:
        await msg.reply_text("Формат: гвиар кто <вопрос>")
        return
    users = mops_state.setdefault("chat_users", {}).get(chat_id, [])
    if not users:
        await msg.reply_text("Пока мало данных по участникам чата.")
        return
    pool = [u for u in users if u != register_profile(msg.from_user)]
    if not pool:
        pool = users
    picked = random.choice(pool)
    await msg.reply_text(f"Гвиар кто {question}?\nОтвет: {display_user(picked)}")


def _ai_is_ready() -> bool:
    return bool(OPENAI_API_KEY)


SAFE_MATH_NAMES = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "pi": math.pi,
    "e": math.e,
}
SAFE_AST_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_math(expr: str) -> float:
    expr = expr.replace(",", ".").replace("^", "**")
    tree = ast.parse(expr, mode="eval")

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_AST_OPS:
            return SAFE_AST_OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_AST_OPS:
            return SAFE_AST_OPS[type(node.op)](walk(node.operand))
        if isinstance(node, ast.Name) and node.id in SAFE_MATH_NAMES:
            return SAFE_MATH_NAMES[node.id]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in SAFE_MATH_NAMES:
            fn = SAFE_MATH_NAMES[node.func.id]
            if not callable(fn):
                raise ValueError("Это не функция")
            return fn(*[walk(arg) for arg in node.args])
        raise ValueError("Можно использовать только числа, + - * / // % ** и функции sqrt/sin/cos/tan/log")

    return walk(tree)


def _normalize_x_expr(expr: str) -> str:
    expr = expr.lower().replace(" ", "").replace(",", ".").replace("^", "**").replace("х", "x")
    expr = expr.replace("x2", "x**2")
    expr = re.sub(r"(\d|\))x", r"\1*x", expr)
    expr = re.sub(r"x(\d|\()", r"x*\1", expr)
    return expr


def _format_number(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value:.10g}" if isinstance(value, float) else str(value)


def _try_solve_linear(text: str) -> str | None:
    compact = _normalize_x_expr(text)
    if "=" not in compact or "x" not in compact:
        return None
    left, right = compact.split("=", 1)
    try:
        f0 = _safe_eval_math(left.replace("x", "(0)")) - _safe_eval_math(right.replace("x", "(0)"))
        f1 = _safe_eval_math(left.replace("x", "(1)")) - _safe_eval_math(right.replace("x", "(1)"))
        a = f1 - f0
        b = f0
        if abs(a) < 1e-12:
            return "Уравнение не похоже на линейное или имеет бесконечно много/нет решений."
        x = -b / a
        return f"Решение линейного уравнения:\n1. Переносим всё в одну сторону.\n2. Получаем коэффициенты a={_format_number(a)}, b={_format_number(b)}.\n3. x = -b / a = {_format_number(x)}"
    except Exception:
        return None


def _try_solve_quadratic(text: str) -> str | None:
    compact = _normalize_x_expr(text)
    if "=" in compact:
        left, right = compact.split("=", 1)
    else:
        left, right = compact, "0"
    if "x**2" not in left + right and "x2" not in left + right:
        return None
    compact_left = left
    compact_right = right
    try:
        def f(v):
            return _safe_eval_math(compact_left.replace("x", f"({v})")) - _safe_eval_math(compact_right.replace("x", f"({v})"))

        c = f(0)
        y1 = f(1)
        yn1 = f(-1)
        a = (y1 + yn1 - 2 * c) / 2
        b = y1 - a - c
        d = b * b - 4 * a * c
        if abs(a) < 1e-12:
            return _try_solve_linear(text)
        lines = [
            "Квадратное уравнение:",
            f"a={_format_number(a)}, b={_format_number(b)}, c={_format_number(c)}",
            f"D = b*b - 4ac = {_format_number(d)}",
        ]
        if d < 0:
            lines.append("Дискриминант меньше 0, действительных корней нет.")
        elif abs(d) < 1e-12:
            x = -b / (2 * a)
            lines.append(f"Один корень: x = {_format_number(x)}")
        else:
            root = math.sqrt(d)
            x1 = (-b + root) / (2 * a)
            x2 = (-b - root) / (2 * a)
            lines.append(f"x1 = {_format_number(x1)}")
            lines.append(f"x2 = {_format_number(x2)}")
        return "\n".join(lines)
    except Exception:
        return None


def _local_summary(text: str, max_sentences: int = 4) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return "Не вижу текста для краткого пересказа."
    picked = sentences[:max_sentences]
    return "Кратко:\n" + "\n".join(f"• {s}" for s in picked)


def _local_translate(text: str) -> str:
    ru_to_en = {
        "привет": "hello",
        "пока": "bye",
        "спасибо": "thank you",
        "любовь": "love",
        "задача": "task",
        "решение": "solution",
        "помощь": "help",
    }
    en_to_ru = {v: k for k, v in ru_to_en.items()}
    words = re.findall(r"[A-Za-zА-Яа-яЁё]+|[^A-Za-zА-Яа-яЁё]+", text)
    has_cyr = bool(re.search(r"[А-Яа-яЁё]", text))
    dictionary = ru_to_en if has_cyr else en_to_ru
    converted = []
    changed = False
    for word in words:
        key = word.lower()
        if key in dictionary:
            converted.append(dictionary[key])
            changed = True
        else:
            converted.append(word)
    if changed:
        return "Черновой перевод без внешнего API:\n" + "".join(converted)
    return "Без внешнего AI-ключа у меня есть только мини-словарь. Для точного перевода напиши короче или используй локальные команды."


STUDY_TOPICS = {
    "math": {
        "title": "Математика",
        "aliases": ("матем", "алгеб", "геометр", "процент", "уравнен", "формул", "дискриминант"),
        "items": [
            (
                ("дискриминант", "квадрат", "квадратное"),
                "Квадратное уравнение: ax^2 + bx + c = 0.\n"
                "D = b^2 - 4ac. Если D > 0, корня два: x1,2 = (-b +/- sqrt(D)) / 2a. "
                "Если D = 0, корень один: x = -b / 2a. Если D < 0, действительных корней нет.",
            ),
            (
                ("линейное", "линейн", "уравнение"),
                "Линейное уравнение приводится к виду ax + b = 0. Решение: x = -b / a, если a не равно 0.",
            ),
            (
                ("процент", "проценты", "%"),
                "Проценты: p% от числа A = A * p / 100. Если число выросло с A до B, рост в процентах = (B - A) / A * 100%.",
            ),
            (
                ("пропорц", "отношение"),
                "Пропорция: если a соответствует b, а c соответствует x, то x = b * c / a. "
                "Для рецептов это основной коэффициент пересчета.",
            ),
            (
                ("площадь круга", "круг", "окружность"),
                "Круг: площадь S = pi * r^2, длина окружности C = 2 * pi * r. Диаметр d = 2r.",
            ),
            (
                ("треугольник", "пифагор"),
                "Прямоугольный треугольник: a^2 + b^2 = c^2. Площадь обычного треугольника: S = a * h / 2.",
            ),
            (
                ("производная", "дифференц"),
                "Производная показывает скорость изменения функции. База: (x^n)' = n*x^(n-1), (sin x)' = cos x, (cos x)' = -sin x.",
            ),
        ],
    },
    "biology": {
        "title": "Биология",
        "aliases": ("биолог", "клетк", "днк", "рнк", "фотосинт", "митоз", "мейоз", "экосистем"),
        "items": [
            (
                ("клетка", "органоид"),
                "Клетка - базовая единица живого. Мембрана отделяет клетку, цитоплазма содержит органоиды, "
                "ядро хранит ДНК, митохондрии дают энергию, рибосомы собирают белки.",
            ),
            (
                ("фотосинтез", "хлорофилл"),
                "Фотосинтез: растения используют свет, CO2 и воду, чтобы получить глюкозу и кислород. "
                "Упрощенно: 6CO2 + 6H2O -> C6H12O6 + 6O2 при участии света и хлорофилла.",
            ),
            (
                ("митоз",),
                "Митоз - деление клетки, при котором из одной клетки получаются две генетически одинаковые. "
                "Нужен для роста, обновления тканей и бесполого размножения.",
            ),
            (
                ("мейоз",),
                "Мейоз - деление, при котором образуются половые клетки с половинным набором хромосом. "
                "Он создает генетическое разнообразие.",
            ),
            (
                ("днк", "ген", "хромосом"),
                "ДНК хранит наследственную информацию. Ген - участок ДНК, связанный с признаком или молекулой РНК/белка. "
                "Хромосомы - компактно упакованная ДНК с белками.",
            ),
            (
                ("рнк", "белок", "трансляц", "транскрипц"),
                "Схема реализации наследственной информации: ДНК -> РНК -> белок. "
                "Транскрипция делает РНК по ДНК, трансляция собирает белок по матричной РНК.",
            ),
            (
                ("экосистем", "цепь питания", "пирамида"),
                "Экосистема включает живые организмы и среду. В цепях питания энергия идет от продуцентов к консументам и редуцентам.",
            ),
            (
                ("пищевар", "фермент"),
                "Пищеварение расщепляет пищу до веществ, которые организм может усвоить. Ферменты ускоряют реакции: амилаза - углеводы, протеазы - белки, липазы - жиры.",
            ),
        ],
    },
    "informatics": {
        "title": "Информатика",
        "aliases": ("информ", "программ", "алгоритм", "python", "код", "сеть", "sql", "двоич"),
        "items": [
            (
                ("алгоритм",),
                "Алгоритм - точное описание шагов для решения задачи. Хороший алгоритм конечен, понятен исполнителю и дает ожидаемый результат.",
            ),
            (
                ("переменная", "тип данных"),
                "Переменная хранит значение. Частые типы: int - целые числа, float - дробные, str - строки, bool - истина/ложь, list - список.",
            ),
            (
                ("цикл", "for", "while"),
                "Цикл повторяет действия. for удобен для перебора элементов, while работает, пока условие истинно.",
            ),
            (
                ("условие", "if", "else"),
                "Условный оператор выбирает ветку выполнения: if проверяет условие, elif добавляет вариант, else срабатывает иначе.",
            ),
            (
                ("функция",),
                "Функция - именованный блок кода. Она помогает не повторяться: принимает аргументы, выполняет действия и может возвращать результат.",
            ),
            (
                ("двоич", "бит", "байт"),
                "Бит - 0 или 1. Байт = 8 бит. В двоичной системе разряды идут степенями 2: 1011b = 8 + 2 + 1 = 11.",
            ),
            (
                ("сеть", "ip", "tcp", "http"),
                "IP-адрес помогает найти устройство в сети. TCP надежно доставляет данные, HTTP используется для веб-запросов.",
            ),
            (
                ("sql", "база данных", "таблица"),
                "SQL работает с таблицами. SELECT читает данные, INSERT добавляет, UPDATE меняет, DELETE удаляет. "
                "WHERE задает условие отбора.",
            ),
            (
                ("безопас", "пароль", "хэш"),
                "Безопасность: используй длинные уникальные пароли, 2FA, не храни пароли открытым текстом. "
                "Хэш - односторонний отпечаток данных.",
            ),
        ],
    },
    "food": {
        "title": "Пищевые технологии",
        "aliases": ("пищ", "повар", "кондитер", "рецепт", "техкарт", "технолог", "кбжу", "себестоим"),
        "items": [
            (
                ("техкарта", "технологическая карта"),
                "Техкарта обычно содержит название блюда, выход, количество порций, сырье брутто/нетто, технологию приготовления, "
                "условия подачи, себестоимость и показатели качества.",
            ),
            (
                ("брутто", "нетто", "отход"),
                "Брутто - масса продукта до обработки. Нетто - после обработки. Отходы в процентах: нетто = брутто * (1 - отходы/100).",
            ),
            (
                ("выход", "порц"),
                "Выход - масса готового блюда или изделия. Для пересчета рецепта используй коэффициент: новый выход / старый выход.",
            ),
            (
                ("себестоимость", "калькуляц"),
                "Себестоимость порции = сумма стоимости ингредиентов / количество порций. "
                "Если цена дана за кг, стоимость ингредиента = масса в кг * цена за кг.",
            ),
            (
                ("дрожж", "тесто"),
                "Дрожжевое тесто любит теплую среду, но не перегрев. Соль не кладут прямо на дрожжи. "
                "Сильная мука лучше держит газ, а расстойка нужна для объема.",
            ),
            (
                ("бисквит",),
                "Бисквит держится на воздухе во взбитых яйцах. Вмешивай муку аккуратно, форму не смазывай высоко по стенкам, "
                "первые 20 минут духовку лучше не открывать.",
            ),
            (
                ("крем", "ганаш", "сливки"),
                "Для стабильного крема важны жирность, температура и пропорции. Ганаш: чем больше шоколада относительно сливок, тем плотнее текстура.",
            ),
            (
                ("карамель",),
                "Карамель требует чистой посуды и контроля температуры. Сахар легко горит, а горячая карамель опасна: работай сухой лопаткой и осторожно.",
            ),
            (
                ("санитар", "хассп", "haccp"),
                "Пищевая безопасность: чистые руки и инвентарь, разделение сырого и готового, контроль температуры хранения, маркировка сроков.",
            ),
        ],
    },
}

NUTRITION_DB = {
    "flour": {"name": "мука пшеничная", "kcal": 364, "p": 10.3, "f": 1.1, "c": 70.6, "aliases": ("мука", "пшеничная мука")},
    "sugar": {"name": "сахар", "kcal": 398, "p": 0, "f": 0, "c": 99.7, "aliases": ("сахар", "сахарная пудра", "пудра")},
    "butter": {"name": "масло сливочное", "kcal": 748, "p": 0.5, "f": 82.5, "c": 0.8, "aliases": ("масло сливочное", "сливочное масло", "масло")},
    "oil": {"name": "масло растительное", "kcal": 899, "p": 0, "f": 99.9, "c": 0, "aliases": ("растительное масло", "масло растительное", "подсолнечное масло")},
    "egg": {"name": "яйцо", "kcal": 157, "p": 12.7, "f": 10.9, "c": 0.7, "aliases": ("яйцо", "яйца", "яиц")},
    "milk": {"name": "молоко", "kcal": 60, "p": 3.0, "f": 3.2, "c": 4.7, "aliases": ("молоко",)},
    "cream": {"name": "сливки", "kcal": 337, "p": 2.2, "f": 33.0, "c": 3.2, "aliases": ("сливки",)},
    "sour_cream": {"name": "сметана", "kcal": 206, "p": 2.8, "f": 20.0, "c": 3.2, "aliases": ("сметана",)},
    "cottage_cheese": {"name": "творог", "kcal": 159, "p": 16.7, "f": 9.0, "c": 2.0, "aliases": ("творог",)},
    "cheese": {"name": "сыр", "kcal": 350, "p": 24.0, "f": 27.0, "c": 2.0, "aliases": ("сыр",)},
    "chocolate": {"name": "шоколад", "kcal": 546, "p": 4.9, "f": 31.0, "c": 61.0, "aliases": ("шоколад",)},
    "cocoa": {"name": "какао", "kcal": 289, "p": 24.3, "f": 15.0, "c": 10.2, "aliases": ("какао", "какао порошок")},
    "honey": {"name": "мед", "kcal": 329, "p": 0.8, "f": 0, "c": 81.5, "aliases": ("мед", "мёд")},
    "banana": {"name": "банан", "kcal": 96, "p": 1.5, "f": 0.5, "c": 21.0, "aliases": ("банан", "бананы")},
    "apple": {"name": "яблоко", "kcal": 47, "p": 0.4, "f": 0.4, "c": 9.8, "aliases": ("яблоко", "яблоки")},
    "potato": {"name": "картофель", "kcal": 77, "p": 2.0, "f": 0.4, "c": 16.3, "aliases": ("картофель", "картошка")},
    "rice": {"name": "рис сухой", "kcal": 344, "p": 6.7, "f": 0.7, "c": 78.9, "aliases": ("рис",)},
    "chicken": {"name": "курица", "kcal": 190, "p": 16.0, "f": 14.0, "c": 0, "aliases": ("курица", "куриное филе", "филе куриное")},
    "beef": {"name": "говядина", "kcal": 187, "p": 18.9, "f": 12.4, "c": 0, "aliases": ("говядина",)},
    "pork": {"name": "свинина", "kcal": 259, "p": 16.0, "f": 21.6, "c": 0, "aliases": ("свинина",)},
    "fish": {"name": "рыба", "kcal": 120, "p": 20.0, "f": 4.0, "c": 0, "aliases": ("рыба", "филе рыбы")},
    "yeast": {"name": "дрожжи сухие", "kcal": 325, "p": 40.4, "f": 7.6, "c": 41.2, "aliases": ("дрожжи", "сухие дрожжи")},
    "salt": {"name": "соль", "kcal": 0, "p": 0, "f": 0, "c": 0, "aliases": ("соль",)},
    "water": {"name": "вода", "kcal": 0, "p": 0, "f": 0, "c": 0, "aliases": ("вода",)},
}

UNIT_FACTORS = {
    "мг": ("mass", 0.001),
    "г": ("mass", 1.0),
    "кг": ("mass", 1000.0),
    "мл": ("volume", 1.0),
    "л": ("volume", 1000.0),
    "ч.л": ("volume", 5.0),
    "ст.л": ("volume", 15.0),
    "стакан": ("volume", 250.0),
}

UNIT_ALIASES = {
    "mg": "мг",
    "g": "г",
    "gram": "г",
    "grams": "г",
    "kg": "кг",
    "ml": "мл",
    "milliliter": "мл",
    "l": "л",
    "liter": "л",
    "литр": "л",
    "литра": "л",
    "литров": "л",
    "грамм": "г",
    "грамма": "г",
    "граммов": "г",
    "килограмм": "кг",
    "килограмма": "кг",
    "килограммов": "кг",
    "чайнл": "ч.л",
    "чайнаяложка": "ч.л",
    "чайныхложек": "ч.л",
    "столоваяложка": "ст.л",
    "столовыхложек": "ст.л",
    "стакана": "стакан",
    "стаканов": "стакан",
}


def _num(raw: str) -> float:
    return float(str(raw).replace(",", "."))


def _pretty_amount(value: float, unit: str = "") -> str:
    if abs(value - round(value)) < 1e-9:
        number = str(int(round(value)))
    else:
        number = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{number} {unit}".strip()


def _normalize_unit(raw: str | None) -> str:
    unit = (raw or "").lower().replace("ё", "е").strip()
    unit = unit.replace(" ", "")
    unit = unit.strip(".")
    if unit in {"чл", "ч.л", "ч.л."}:
        return "ч.л"
    if unit in {"стл", "ст.л", "ст.л."}:
        return "ст.л"
    if unit in {"кг", "г", "мг", "л", "мл", "шт"}:
        return unit
    if unit in {"яйцо", "яйца", "яиц"}:
        return "шт"
    return UNIT_ALIASES.get(unit, unit)


def _normalize_food_name(name: str) -> str:
    return re.sub(r"[^a-zа-я0-9% ]+", " ", name.lower().replace("ё", "е")).strip()


def _find_food_key(name: str) -> str | None:
    clean = _normalize_food_name(name)
    for key, item in NUTRITION_DB.items():
        for alias in item["aliases"]:
            if _normalize_food_name(alias) in clean:
                return key
    return None


def _extract_servings(text: str, default: float = 1.0) -> float:
    patterns = [
        r"(?:на|для)\s*(\d+(?:[.,]\d+)?)\s*(?:порц|порции|порций|шт|издел)",
        r"(\d+(?:[.,]\d+)?)\s*(?:порц|порции|порций|шт|издел)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return max(_num(match.group(1)), 0.001)
    return default


def _parse_ingredient_part(part: str) -> dict | None:
    raw = re.sub(r"^[\s\-•*]+", "", part.strip())
    if not raw:
        return None
    low = raw.lower()
    if re.search(r"\b(порц|порции|порций|выход|итого|себестоимость)\b", low) and not re.search(r"\d+\s*(?:кг|г|мг|л|мл|шт|яйц)", low):
        return None
    qty_matches = list(re.finditer(r"(\d+(?:[.,]\d+)?)\s*(кг|г|мг|л|мл|шт|яйцо|яйца|яиц)\b", raw, re.IGNORECASE))
    if not qty_matches:
        return None
    qty_match = qty_matches[-1]
    name = raw[: qty_match.start()].strip(" ,:-")
    if not name:
        return None
    amount = _num(qty_match.group(1))
    unit = _normalize_unit(qty_match.group(2))
    tail = raw[qty_match.end():]
    price = None
    price_unit = None
    price_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:р|руб|₽)?\s*(?:/|за\s+1\s*)\s*(кг|г|л|мл|шт)\b",
        tail,
        re.IGNORECASE,
    )
    if not price_match:
        price_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:р|руб|₽)\b", tail, re.IGNORECASE)
    if price_match:
        price = _num(price_match.group(1))
        price_unit = _normalize_unit(price_match.group(2) if price_match.lastindex and price_match.lastindex >= 2 else None)
    return {"name": name, "amount": amount, "unit": unit, "price": price, "price_unit": price_unit}


def _parse_ingredients(text: str) -> list[dict]:
    normalized = text.replace("\r", "\n")
    chunks = [p.strip() for p in re.split(r"[;\n]+", normalized) if p.strip()]
    items: list[dict] = []
    for chunk in chunks:
        item = _parse_ingredient_part(chunk)
        if item:
            items.append(item)
    return items


def _amount_to_base(amount: float, unit: str) -> tuple[float, str] | tuple[None, None]:
    unit = _normalize_unit(unit)
    if unit == "кг":
        return amount, "кг"
    if unit == "г":
        return amount / 1000, "кг"
    if unit == "мг":
        return amount / 1_000_000, "кг"
    if unit == "л":
        return amount, "л"
    if unit == "мл":
        return amount / 1000, "л"
    if unit == "шт":
        return amount, "шт"
    return None, None


def _amount_to_grams(item: dict) -> float | None:
    amount = float(item["amount"])
    unit = _normalize_unit(item["unit"])
    key = _find_food_key(item["name"])
    if unit == "кг":
        return amount * 1000
    if unit == "г":
        return amount
    if unit == "мг":
        return amount / 1000
    if unit == "л":
        return amount * 1000
    if unit == "мл":
        return amount
    if unit == "шт" and key == "egg":
        return amount * 50
    return None


def _ingredient_cost(item: dict) -> float | None:
    price = item.get("price")
    if price is None:
        return None
    amount = float(item["amount"])
    unit = _normalize_unit(item["unit"])
    price_unit = _normalize_unit(item.get("price_unit"))
    if not price_unit:
        if unit in {"кг", "г", "мг"}:
            price_unit = "кг"
        elif unit in {"л", "мл"}:
            price_unit = "л"
        else:
            price_unit = "шт"
    if price_unit in {"кг", "г", "мг"} and unit in {"кг", "г", "мг"}:
        grams = _amount_to_grams(item) or 0
        price_per_g = price / (1000 if price_unit == "кг" else 1 if price_unit == "г" else 0.001)
        return grams * price_per_g
    if price_unit in {"л", "мл"} and unit in {"л", "мл"}:
        ml = amount * 1000 if unit == "л" else amount
        price_per_ml = price / (1000 if price_unit == "л" else 1)
        return ml * price_per_ml
    if price_unit == "шт" and unit == "шт":
        return amount * price
    return None


def _study_topic_answer(subject: str, text: str) -> str | None:
    data = STUDY_TOPICS.get(subject)
    if not data:
        return None
    clean = text.lower().replace("ё", "е")
    for keywords, answer in data["items"]:
        if any(keyword in clean for keyword in keywords):
            return f"{data['title']}:\n{answer}"
    return None


def _detect_study_subject(text: str) -> str | None:
    clean = text.lower().replace("ё", "е")
    for subject, data in STUDY_TOPICS.items():
        if any(alias in clean for alias in data["aliases"]):
            return subject
    return None


def _try_percentage(text: str) -> str | None:
    clean = text.lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*от\s*(\d+(?:\.\d+)?)", clean)
    if match:
        p, value = _num(match.group(1)), _num(match.group(2))
        return f"{_pretty_amount(p)}% от {_pretty_amount(value)} = {_pretty_amount(value * p / 100)}"
    match = re.search(r"(?:рост|изменени[ея]|на сколько процентов).*?(\d+(?:\.\d+)?).*?(\d+(?:\.\d+)?)", clean)
    if match:
        old, new = _num(match.group(1)), _num(match.group(2))
        if abs(old) < 1e-12:
            return "Не могу посчитать процент изменения: первое число равно 0."
        return f"Изменение с {_pretty_amount(old)} до {_pretty_amount(new)} = {_pretty_amount((new - old) / old * 100)}%"
    match = re.search(r"(\d+(?:\.\d+)?)\s+это\s+(\d+(?:\.\d+)?)\s*%", clean)
    if match:
        part, p = _num(match.group(1)), _num(match.group(2))
        if abs(p) < 1e-12:
            return "Процент не должен быть 0."
        return f"Если {_pretty_amount(part)} - это {_pretty_amount(p)}%, то 100% = {_pretty_amount(part * 100 / p)}"
    return None


def _try_proportion(text: str) -> str | None:
    nums = [_num(x) for x in re.findall(r"\d+(?:[.,]\d+)?", text)]
    if len(nums) < 3:
        return None
    a, c, b = nums[0], nums[1], nums[2]
    if abs(a) < 1e-12:
        return "В пропорции первое число не должно быть 0."
    x = b * c / a
    return (
        "Пропорция:\n"
        f"если {_pretty_amount(a)} соответствует {_pretty_amount(b)}, "
        f"то для {_pretty_amount(c)} получится x = {_pretty_amount(b)} * {_pretty_amount(c)} / {_pretty_amount(a)} = {_pretty_amount(x)}"
    )


def _local_math_answer(text: str) -> str | None:
    clean = text.strip()
    if not clean:
        return None
    percent = _try_percentage(clean)
    if percent:
        return percent
    if "пропорц" in clean.lower():
        prop = _try_proportion(clean)
        if prop:
            return prop
    quad = _try_solve_quadratic(clean)
    if quad:
        return quad
    linear = _try_solve_linear(clean)
    if linear:
        return linear
    math_like = re.fullmatch(r"[0-9\s+\-*/().,%^a-zA-Z_]+", clean)
    if math_like and re.search(r"\d", clean):
        try:
            return f"Ответ: {_format_number(_safe_eval_math(clean))}"
        except Exception:
            pass
    return _study_topic_answer("math", clean)


def _local_study_answer(text: str, subject: str | None = None) -> str | None:
    clean = text.strip()
    if not clean:
        return None
    if subject == "math":
        return _local_math_answer(clean)
    if subject:
        return _study_topic_answer(subject, clean)
    math_answer = _local_math_answer(clean)
    if math_answer:
        return math_answer
    detected = _detect_study_subject(clean)
    if detected:
        return _study_topic_answer(detected, clean)
    for candidate in ("biology", "informatics", "food"):
        answer = _study_topic_answer(candidate, clean)
        if answer:
            return answer
    return None


def _study_examples_text() -> str:
    return (
        "Учебные команды:\n"
        "/study вопрос - общий учебный помощник\n"
        "/math 15% от 240 или /math x^2-5x+6=0\n"
        "/biology фотосинтез\n"
        "/informatics двоичная система\n"
        "/food брутто нетто отходы\n"
        "/techcard 10 порций; мука 500 г 60 руб/кг; сахар 200 г 90 руб/кг\n"
        "/scale_recipe с 4 на 10; мука 500 г; сахар 200 г\n"
        "/proportion 500 750 120\n"
        "/nutrition 4 порции; мука 500 г; сахар 150 г; яйцо 3 шт\n"
        "/units 250 г в кг\n\n"
        "Без слеша тоже работает: «математика ...», «биология ...», «информатика ...», "
        "«техкарта ...», «пропорции ...», «кбжу ...», «единицы ...»."
    )


def _local_ai_answer(text: str, mode: str = "ask") -> str:
    clean = text.strip()
    if not clean:
        return "Напиши текст вопроса или задачи."
    study = _local_study_answer(clean)
    if study:
        return study
    quad = _try_solve_quadratic(clean)
    if quad:
        return quad
    linear = _try_solve_linear(clean)
    if linear:
        return linear
    math_like = re.fullmatch(r"[0-9\s+\-*/().,%^]+", clean)
    if math_like:
        try:
            return f"Ответ: {_format_number(_safe_eval_math(clean))}"
        except Exception as e:
            return f"Не смог посчитать выражение: {e}"
    if mode == "summary":
        return _local_summary(clean)
    if mode == "translate":
        return _local_translate(clean)
    if mode == "solve":
        return (
            "Я могу решить без API простые выражения, линейные и квадратные уравнения.\n"
            "Пример: /solve 2x+5=17 или /solve x^2-5x+6=0\n\n"
            f"Твоё условие вижу так: {clean}"
        )
    return (
        "Работаю в автономном режиме без OpenAI-ключа.\n"
        "Могу считать, решать простые уравнения, делать краткий пересказ, переводить по мини-словарю, "
        "вести заметки, напоминания и игры.\n\n"
        "Для полноценного анализа фото нужен любой vision-AI ключ, но бот и без него запускается 24/7."
    )


def _openai_chat_request(messages: list[dict], max_tokens: int = 1200) -> str:
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.25,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{OPENAI_BASE_URL}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    answer = json.loads(raw)["choices"][0]["message"]["content"]
    return (answer or "").strip()


async def _run_blocking(func, *args):
    try:
        import asyncio
        return await asyncio.to_thread(func, *args)
    except AttributeError:
        return func(*args)


def _limit_telegram_text(text: str, limit: int = 3900) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 80].rstrip() + "\n\n...ответ получился длинным, сократил под лимит Telegram."


async def _ai_reply(update: Update, messages: list[dict], wait_text: str = "Думаю...") -> None:
    msg = update.message
    if not msg:
        return
    if not _ai_is_ready():
        user_parts = [m.get("content", "") for m in messages if m.get("role") == "user"]
        text_parts = []
        for part in user_parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, list):
                text_parts.extend(item.get("text", "") for item in part if isinstance(item, dict))
        await msg.reply_text(_limit_telegram_text(_local_ai_answer("\n".join(text_parts))))
        return
    status = await msg.reply_text(wait_text)
    try:
        answer = await _run_blocking(_openai_chat_request, messages)
    except Exception as e:
        logger.exception("AI request failed: %s", e)
        await status.edit_text("Не смог получить ответ от AI. Проверь OPENAI_API_KEY, OPENAI_MODEL и интернет на сервере.")
        return
    if not answer:
        await status.edit_text("AI вернул пустой ответ. Попробуй переформулировать вопрос.")
        return
    await status.edit_text(_limit_telegram_text(answer))


def _message_arg_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    if context.args:
        return " ".join(context.args).strip()
    msg = update.message
    if not msg:
        return ""
    text = msg.caption or msg.text or ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


async def ai_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "AI-команды:\n"
        "/ask вопрос — спросить что угодно\n"
        "/solve условие — решить задачу по тексту\n"
        "/summary текст — сделать краткое резюме\n"
        "/translate текст — перевести на русский/английский\n"
        "/analyze — ответом на фото или с подписью к фото\n"
        "/vision, /photo, /ocr — локальный анализ фото без OpenAI-ключа\n"
        "/study — учебные команды: математика, биология, информатика, пищевые технологии\n\n"
        "Без OPENAI_API_KEY бот всё равно работает: считает, решает простые уравнения, "
        "делает краткий пересказ, анализирует качество/тип фото и отвечает локальным режимом.\n\n"
        "Без слеша тоже можно: «реши ...», «спроси ...», «анализ ...», «переведи ...», «кратко ...».\n"
        "Фото с подписью «реши», «задача» или «анализ» бот разберёт сам."
    )


async def study_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(_study_examples_text())


async def _study_subject_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    subject: str | None,
    title: str,
) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text(_study_examples_text())
        return
    local = _local_study_answer(text, subject)
    if local:
        await update.message.reply_text(_limit_telegram_text(local))
        return
    if not _ai_is_ready():
        await update.message.reply_text(
            _limit_telegram_text(
                f"Локально не нашёл точный ответ по теме «{title}».\n"
                "Попробуй спросить короче или по ключевым словам. Примеры:\n\n"
                + _study_examples_text()
            )
        )
        return
    messages = [
        {
            "role": "system",
            "content": (
                AI_SYSTEM_PROMPT
                + f"\nСейчас отвечай как учебный помощник по теме «{title}». "
                "Дай понятное объяснение, формулы или алгоритм решения, затем короткий итог."
            ),
        },
        {"role": "user", "content": text},
    ]
    await _ai_reply(update, messages, f"Разбираю тему «{title}»...")


async def study_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _study_subject_cmd(update, context, None, "учеба")


async def math_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _study_subject_cmd(update, context, "math", "математика")


async def biology_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _study_subject_cmd(update, context, "biology", "биология")


async def informatics_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _study_subject_cmd(update, context, "informatics", "информатика")


async def food_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _study_subject_cmd(update, context, "food", "пищевые технологии")


async def proportion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text(
            "Формат: /proportion 500 750 120\n"
            "Это значит: если на 500 г основы нужно 120 г ингредиента, то сколько нужно на 750 г."
        )
        return
    answer = _try_proportion(text)
    if not answer:
        await update.message.reply_text("Не вижу 3 числа. Пример: /proportion 500 750 120")
        return
    await update.message.reply_text(answer)


async def unit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text("Формат: /units 250 г в кг или /units 2 ст.л в мл")
        return
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*([a-zа-я.]+)\s*(?:в|to|->|=)\s*([a-zа-я.]+)", text.lower())
    if not match:
        await update.message.reply_text("Не понял конвертацию. Пример: /units 250 г в кг")
        return
    value = _num(match.group(1))
    src = _normalize_unit(match.group(2))
    dst = _normalize_unit(match.group(3))
    if src not in UNIT_FACTORS or dst not in UNIT_FACTORS:
        await update.message.reply_text("Знаю единицы: мг, г, кг, мл, л, ч.л, ст.л, стакан.")
        return
    src_kind, src_factor = UNIT_FACTORS[src]
    dst_kind, dst_factor = UNIT_FACTORS[dst]
    if src_kind != dst_kind:
        await update.message.reply_text("Нельзя честно перевести массу в объем без плотности продукта.")
        return
    result = value * src_factor / dst_factor
    await update.message.reply_text(f"{_pretty_amount(value, src)} = {_pretty_amount(result, dst)}")


async def scale_recipe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text("Формат: /scale_recipe с 4 на 10; мука 500 г; сахар 200 г")
        return
    clean = text.lower().replace(",", ".")
    match = re.search(r"(?:с|из)\s*(\d+(?:\.\d+)?)\s*(?:порц\w*)?\s*(?:на|до|->|=>)\s*(\d+(?:\.\d+)?)", clean)
    if match:
        old_count, new_count = _num(match.group(1)), _num(match.group(2))
        recipe_text = text[match.end():]
    else:
        first_part = re.split(r"[;\n]", clean, maxsplit=1)[0]
        nums = re.findall(r"\d+(?:\.\d+)?", first_part)
        if len(nums) < 2:
            await update.message.reply_text("Укажи старое и новое количество: /scale_recipe с 4 на 10; мука 500 г")
            return
        old_count, new_count = _num(nums[0]), _num(nums[1])
        original_parts = re.split(r"[;\n]", text, maxsplit=1)
        recipe_text = original_parts[1] if len(original_parts) > 1 else ""
    if old_count <= 0 or new_count <= 0:
        await update.message.reply_text("Количество порций должно быть больше 0.")
        return
    coef = new_count / old_count
    items = _parse_ingredients(recipe_text)
    lines = [
        "Пересчет рецепта:",
        f"Было: {_pretty_amount(old_count)} порц., стало: {_pretty_amount(new_count)} порц.",
        f"Коэффициент: {_pretty_amount(coef)}",
    ]
    if not items:
        lines.append("Ингредиенты не распознаны. Умножай каждую норму на этот коэффициент.")
        await update.message.reply_text("\n".join(lines))
        return
    lines.append("Новые нормы:")
    for item in items:
        new_amount = float(item["amount"]) * coef
        lines.append(f"- {item['name']}: {_pretty_amount(float(item['amount']), item['unit'])} -> {_pretty_amount(new_amount, item['unit'])}")
    await update.message.reply_text(_limit_telegram_text("\n".join(lines)))


async def foodcard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text(
            "Формат: /techcard 10 порций; мука 500 г 60 руб/кг; сахар 200 г 90 руб/кг; яйцо 3 шт 12 руб/шт"
        )
        return
    servings = _extract_servings(text, default=1.0)
    items = _parse_ingredients(text)
    if not items:
        await update.message.reply_text("Не распознал ингредиенты. Разделяй их точкой с запятой: мука 500 г; сахар 200 г")
        return
    total_cost = 0.0
    has_cost = False
    mass_g = 0.0
    volume_ml = 0.0
    pieces = 0.0
    lines = [
        "Технологическая карта (черновой расчет):",
        f"Порций: {_pretty_amount(servings)}",
        "Сырье:",
    ]
    for item in items:
        per_portion = float(item["amount"]) / servings
        cost = _ingredient_cost(item)
        cost_text = ""
        if cost is not None:
            total_cost += cost
            has_cost = True
            cost_text = f", стоимость {_pretty_amount(cost, 'руб')}"
        unit = _normalize_unit(item["unit"])
        if unit in {"кг", "г", "мг"}:
            grams = _amount_to_grams(item) or 0
            mass_g += grams
        elif unit in {"л", "мл"}:
            volume_ml += float(item["amount"]) * (1000 if unit == "л" else 1)
        elif unit == "шт":
            pieces += float(item["amount"])
        lines.append(
            f"- {item['name']}: брутто/нетто {_pretty_amount(float(item['amount']), item['unit'])}, "
            f"на порцию {_pretty_amount(per_portion, item['unit'])}{cost_text}"
        )
    totals = []
    if mass_g:
        totals.append(f"масса сырья {_pretty_amount(mass_g, 'г')}")
    if volume_ml:
        totals.append(f"объем {_pretty_amount(volume_ml, 'мл')}")
    if pieces:
        totals.append(f"штучные продукты {_pretty_amount(pieces, 'шт')}")
    if totals:
        lines.append("Итого: " + ", ".join(totals))
    if has_cost:
        lines.append(f"Себестоимость всего: {_pretty_amount(total_cost, 'руб')}")
        lines.append(f"Себестоимость порции: {_pretty_amount(total_cost / servings, 'руб')}")
    else:
        lines.append("Цены не указаны, себестоимость не считалась.")
    lines.append("Если есть отходы, укажи их отдельно: брутто и нетто могут отличаться после обработки.")
    await update.message.reply_text(_limit_telegram_text("\n".join(lines)))


async def nutrition_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text("Формат: /nutrition 4 порции; мука 500 г; сахар 150 г; яйцо 3 шт")
        return
    servings = _extract_servings(text, default=1.0)
    items = _parse_ingredients(text)
    if not items:
        await update.message.reply_text("Не распознал ингредиенты. Пример: /nutrition 2 порции; молоко 300 мл; яйцо 2 шт")
        return
    totals = {"kcal": 0.0, "p": 0.0, "f": 0.0, "c": 0.0, "grams": 0.0}
    unknown = []
    lines = [f"КБЖУ, черновой расчет на {_pretty_amount(servings)} порц.:"]
    for item in items:
        key = _find_food_key(item["name"])
        grams = _amount_to_grams(item)
        if not key or grams is None:
            unknown.append(item["name"])
            continue
        ref = NUTRITION_DB[key]
        factor = grams / 100
        kcal = ref["kcal"] * factor
        p = ref["p"] * factor
        f = ref["f"] * factor
        c = ref["c"] * factor
        totals["kcal"] += kcal
        totals["p"] += p
        totals["f"] += f
        totals["c"] += c
        totals["grams"] += grams
        lines.append(f"- {item['name']} ({_pretty_amount(grams, 'г')}): {_pretty_amount(kcal, 'ккал')}")
    lines.append(
        "Итого: "
        f"{_pretty_amount(totals['kcal'], 'ккал')}, "
        f"Б {_pretty_amount(totals['p'], 'г')}, "
        f"Ж {_pretty_amount(totals['f'], 'г')}, "
        f"У {_pretty_amount(totals['c'], 'г')}"
    )
    lines.append(
        "На порцию: "
        f"{_pretty_amount(totals['kcal'] / servings, 'ккал')}, "
        f"Б {_pretty_amount(totals['p'] / servings, 'г')}, "
        f"Ж {_pretty_amount(totals['f'] / servings, 'г')}, "
        f"У {_pretty_amount(totals['c'] / servings, 'г')}"
    )
    if unknown:
        lines.append("Не нашел в локальной базе: " + ", ".join(dict.fromkeys(unknown)) + ". Их можно посчитать через /ask при включенном AI.")
    await update.message.reply_text(_limit_telegram_text("\n".join(lines)))


async def ai_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text("Напиши вопрос: /ask как решить квадратное уравнение?")
        return
    if not _ai_is_ready():
        await update.message.reply_text(_limit_telegram_text(_local_ai_answer(text, "ask")))
        return
    messages = [
        {"role": "system", "content": AI_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    await _ai_reply(update, messages, "Думаю над ответом...")


async def ai_solve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        msg = update.message
        if msg and ((msg.photo) or (msg.reply_to_message and msg.reply_to_message.photo)):
            await ai_analyze_photo(update, context)
            return
        await update.message.reply_text("Пришли условие после /solve или ответь командой /solve на фото с задачей.")
        return
    if not _ai_is_ready():
        await update.message.reply_text(_limit_telegram_text(_local_ai_answer(text, "solve")))
        return
    messages = [
        {"role": "system", "content": AI_SYSTEM_PROMPT},
        {"role": "user", "content": "Реши задачу подробно, но без лишней воды:\n" + text},
    ]
    await _ai_reply(update, messages, "Решаю задачу...")


async def ai_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text("Пришли текст после /summary.")
        return
    if not _ai_is_ready():
        await update.message.reply_text(_limit_telegram_text(_local_ai_answer(text, "summary")))
        return
    messages = [
        {"role": "system", "content": AI_SYSTEM_PROMPT},
        {"role": "user", "content": "Сделай краткое и полезное резюме:\n" + text},
    ]
    await _ai_reply(update, messages, "Сжимаю до главного...")


async def ai_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text("Пришли текст после /translate.")
        return
    if not _ai_is_ready():
        await update.message.reply_text(_limit_telegram_text(_local_ai_answer(text, "translate")))
        return
    messages = [
        {"role": "system", "content": AI_SYSTEM_PROMPT},
        {"role": "user", "content": "Переведи текст. Если он на русском — на английский, иначе на русский:\n" + text},
    ]
    await _ai_reply(update, messages, "Перевожу...")


async def _photo_bytes_from_message(msg: Message, context: ContextTypes.DEFAULT_TYPE) -> bytes | None:
    source = msg
    if not source.photo and source.reply_to_message and source.reply_to_message.photo:
        source = source.reply_to_message
    if not source.photo:
        return None
    photo = source.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    data = await tg_file.download_as_bytearray()
    return bytes(data)


def _color_name(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    if mx < 45:
        return "черный"
    if mn > 215:
        return "белый"
    if mx - mn < 24:
        return "серый"
    if r > 180 and g > 160 and b < 110:
        return "желтый/золотистый"
    if r > 150 and g > 80 and b < 90:
        return "оранжево-коричневый"
    if r > g * 1.25 and r > b * 1.25:
        return "красный"
    if g > r * 1.15 and g > b * 1.15:
        return "зеленый"
    if b > r * 1.15 and b > g * 1.15:
        return "синий"
    if r > 120 and b > 120 and g < 120:
        return "фиолетовый/розовый"
    return "смешанный"


def _local_photo_analysis(image_bytes: bytes, question: str = "") -> str:
    try:
        from PIL import Image, ImageFilter, ImageOps, ImageStat
    except Exception:
        return (
            "Фото получил, но локальный анализ недоступен: не установлен Pillow.\n"
            "На Railway он уже есть в requirements.txt как Pillow."
        )

    try:
        img = Image.open(io.BytesIO(image_bytes))
        fmt = img.format or "unknown"
        exif = img.getexif()
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        return f"Фото получил, но не смог открыть изображение локально: {e}"

    width, height = img.size
    ratio = width / max(height, 1)
    orientation = "горизонтальное" if ratio > 1.15 else "вертикальное" if ratio < 0.87 else "почти квадратное"

    thumb = img.copy()
    thumb.thumbnail((320, 320))
    gray = ImageOps.grayscale(thumb)
    stat = ImageStat.Stat(gray)
    brightness = float(stat.mean[0])
    contrast = float(stat.stddev[0])
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_mean = float(ImageStat.Stat(edges).mean[0])

    pixels = list(gray.getdata())
    total = max(len(pixels), 1)
    dark_ratio = sum(1 for p in pixels if p < 70) / total
    light_ratio = sum(1 for p in pixels if p > 220) / total
    mid_ratio = 1 - dark_ratio - light_ratio

    color_thumb = thumb.copy()
    color_thumb.thumbnail((96, 96))
    colors = color_thumb.convert("P", palette=Image.Palette.ADAPTIVE, colors=6).convert("RGB").getcolors(96 * 96)
    colors = sorted(colors or [], reverse=True)[:5]
    palette = []
    for count, rgb in colors:
        share = count / max(color_thumb.size[0] * color_thumb.size[1], 1) * 100
        palette.append(f"{_color_name(rgb)} {share:.0f}%")

    rgb_stat = ImageStat.Stat(color_thumb)
    means = rgb_stat.mean
    saturation_samples = []
    warm_pixels = 0
    for r, g, b in color_thumb.getdata():
        mx, mn = max(r, g, b), min(r, g, b)
        saturation_samples.append(0 if mx == 0 else (mx - mn) / mx)
        if r > 110 and g > 55 and b < 115 and r >= g >= b * 0.55:
            warm_pixels += 1
    saturation = sum(saturation_samples) / max(len(saturation_samples), 1)
    warm_ratio = warm_pixels / max(len(saturation_samples), 1)

    row_dark_hits = 0
    col_dark_hits = 0
    tw, th = gray.size
    for y in range(th):
        row = [gray.getpixel((x, y)) for x in range(tw)]
        if 0.04 < (sum(1 for p in row if p < 95) / max(tw, 1)) < 0.55:
            row_dark_hits += 1
    for x in range(tw):
        col = [gray.getpixel((x, y)) for y in range(th)]
        if 0.04 < (sum(1 for p in col if p < 95) / max(th, 1)) < 0.55:
            col_dark_hits += 1
    row_score = row_dark_hits / max(th, 1)
    col_score = col_dark_hits / max(tw, 1)

    question_low = question.lower()
    question_wants_text = any(word in question_low for word in ("текст", "задач", "реш", "формул", "ocr", "распознай"))
    guesses = []
    looks_like_light_text = (light_ratio > 0.72 and dark_ratio > 0.003) or (
        question_wants_text and light_ratio > 0.85 and edge_mean > 2
    )
    if looks_like_light_text:
        guesses.append("похоже на светлый лист, тетрадь, документ или скрин с небольшим текстом")
    if light_ratio > 0.55 and dark_ratio > 0.018 and edge_mean > 6:
        guesses.append("похоже на лист, тетрадь, документ или скрин с текстом")
    if light_ratio > 0.45 and row_score > 0.25 and col_score > 0.14:
        guesses.append("могут быть таблица, схема, чек-лист или задание")
    if edge_mean > 18 and contrast > 48 and saturation < 0.22:
        guesses.append("много мелких контрастных деталей: вероятен текст, код, формулы или интерфейс")
    if saturation > 0.33 and warm_ratio > 0.22 and light_ratio < 0.55:
        guesses.append("есть теплые пищевые оттенки: возможно еда, выпечка или ингредиенты")
    if saturation > 0.38 and edge_mean < 16 and mid_ratio > 0.55:
        guesses.append("похоже на обычное фото предмета или сцены")
    if dark_ratio > 0.40:
        guesses.append("снимок темный, деталей может быть мало")
    if edge_mean < 5 and contrast < 32 and not looks_like_light_text:
        guesses.append("картинка выглядит мягкой или размытой")
    if not guesses:
        guesses.append("тип фото определить трудно, но базовые параметры посчитаны")

    tips = []
    if brightness < 75:
        tips.append("добавь света или пересними ближе к окну")
    elif brightness > 220:
        tips.append("слишком светло: часть деталей может теряться")
    if edge_mean < 5 and not looks_like_light_text:
        tips.append("фото может быть размытым, попробуй снять резче")
    if question_wants_text or light_ratio > 0.55:
        tips.append("для задач и текста лучше снимать ровно сверху, без наклона, чтобы весь лист попадал в кадр")

    ocr_note = (
        "Честно: без OpenAI/vision-ключа я не распознаю текст с фото как полноценный OCR. "
        "Зато могу понять качество/тип изображения и подсказать, что видно по структуре. "
        "Если пришлешь текст задачи сообщением, я решу ее полностью."
    )

    exif_note = ""
    if exif:
        date_raw = exif.get(36867) or exif.get(306)
        if date_raw:
            exif_note = f"\nEXIF дата: {date_raw}"

    lines = [
        "Локальный анализ фото без OpenAI:",
        f"Файл: {fmt}, размер {width}x{height}, {orientation}.{exif_note}",
        f"Свет: {brightness:.0f}/255, контраст: {contrast:.0f}/255, детализация: {edge_mean:.1f}/255.",
        f"Темных зон: {dark_ratio * 100:.0f}%, светлых зон: {light_ratio * 100:.0f}%.",
        "Палитра: " + (", ".join(palette) if palette else "не определилась"),
        "Что могу предположить:",
        *[f"- {guess}" for guess in guesses[:4]],
    ]
    if tips:
        lines.extend(["Что улучшить для распознавания:", *[f"- {tip}" for tip in tips[:3]]])
    lines.append(ocr_note)
    return "\n".join(lines)


async def ai_analyze_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    image_bytes = await _photo_bytes_from_message(msg, context)
    if not image_bytes:
        await msg.reply_text("Пришли фото с подписью /analyze или ответь /analyze на фото.")
        return
    question = _message_arg_text(update, context) or msg.caption or "Проанализируй фото. Если там задача, реши её по шагам."
    if not _ai_is_ready():
        await msg.reply_text(_limit_telegram_text(_local_photo_analysis(image_bytes, question)))
        return
    b64 = base64.b64encode(image_bytes).decode("ascii")
    messages = [
        {"role": "system", "content": AI_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        },
    ]
    await _ai_reply(update, messages, "Смотрю фото и разбираю...")


async def ai_photo_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.photo:
        return
    caption = (msg.caption or "").strip().lower()
    trigger_words = (
        "реши",
        "задача",
        "анализ",
        "проанализируй",
        "что на фото",
        "фото",
        "картинка",
        "распознай",
        "ocr",
        "текст",
        "формула",
        "техкарта",
        "кбжу",
    )
    is_private = bool(update.effective_chat and update.effective_chat.type == "private")
    if not any(word in caption for word in trigger_words) and not (is_private and not caption):
        return
    await ai_analyze_photo(update, context)


async def calc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    expr = _message_arg_text(update, context)
    if not expr:
        await update.message.reply_text("Формат: /calc 2*(5+3) или /calc sqrt(144)")
        return
    try:
        await update.message.reply_text(f"Ответ: {_format_number(_safe_eval_math(expr))}")
    except Exception as e:
        await update.message.reply_text(f"Не смог посчитать: {e}")


async def roll_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = (_message_arg_text(update, context) or "1d6").lower().replace(" ", "")
    match = re.fullmatch(r"(\d{1,2})?d(\d{1,5})([+-]\d{1,5})?", raw)
    if not match:
        await update.message.reply_text("Формат: /roll d20, /roll 2d6, /roll 3d10+2")
        return
    count = int(match.group(1) or 1)
    sides = int(match.group(2))
    mod = int(match.group(3) or 0)
    if count > 30 or sides < 2 or sides > 100000:
        await update.message.reply_text("Разумный лимит: до 30 кубов, стороны от 2 до 100000.")
        return
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + mod
    mod_text = f" {mod:+d}" if mod else ""
    await update.message.reply_text(f"🎲 {raw}: {rolls}{mod_text}\nИтого: {total}")


async def choose_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    options = [x.strip() for x in re.split(r"[|,;]", text) if x.strip()]
    if len(options) < 2:
        await update.message.reply_text("Формат: /choose пицца | суши | бургер")
        return
    await update.message.reply_text(f"Выбор: {random.choice(options)}")


async def password_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = _message_arg_text(update, context)
    try:
        length = int(raw) if raw else 16
    except ValueError:
        length = 16
    length = max(8, min(64, length))
    alphabet = string.ascii_letters + string.digits + "!@#$%&*_-+="
    pwd = "".join(secrets.choice(alphabet) for _ in range(length))
    await update.message.reply_text(f"Пароль на {length} символов:\n`{pwd}`", parse_mode="Markdown")


async def remind_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data or {}
    try:
        await context.bot.send_message(chat_id=data["chat_id"], text=f"⏰ Напоминание: {data['text']}")
    except Exception as e:
        logger.warning("Reminder failed: %s", e)


def _parse_duration_seconds(raw: str) -> int | None:
    raw = raw.lower().strip()
    match = re.fullmatch(r"(\d+)([smhdсмчд]?)", raw)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    mult = 1
    if unit in {"m", "м"}:
        mult = 60
    elif unit in {"h", "ч"}:
        mult = 3600
    elif unit in {"d", "д"}:
        mult = 86400
    return value * mult


async def remind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text("Формат: /remind 10m проверить чай или /remind 1h созвон")
        return
    parts = text.split(maxsplit=1)
    seconds = _parse_duration_seconds(parts[0])
    if not seconds or len(parts) < 2:
        await update.message.reply_text("Формат: /remind 10m текст. Единицы: s/m/h/d или с/м/ч/д.")
        return
    if seconds < 5 or seconds > 14 * 86400:
        await update.message.reply_text("Напоминание можно поставить от 5 секунд до 14 дней.")
        return
    if not context.job_queue:
        await update.message.reply_text("Job queue недоступен, напоминания сейчас выключены.")
        return
    context.job_queue.run_once(
        remind_job,
        when=seconds,
        data={"chat_id": update.effective_chat.id, "text": parts[1]},
        name=f"remind_{update.effective_chat.id}_{int(time.time())}",
    )
    await update.message.reply_text(f"⏰ Готово, напомню через {parts[0]}.")


def _notes_key(update: Update) -> str:
    return f"{update.effective_chat.id}:{update.effective_user.id}"


async def note_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    if not text:
        await update.message.reply_text("Формат: /note_add текст заметки")
        return
    key = _notes_key(update)
    notes = notes_data.setdefault(key, [])
    notes.append({"text": text[:1000], "created": datetime.now().strftime("%Y-%m-%d %H:%M")})
    if len(notes) > 30:
        del notes[:-30]
    save_json(NOTES_FILE, notes_data)
    await update.message.reply_text(f"Заметка сохранена. Всего заметок: {len(notes)}")


async def notes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    notes = notes_data.get(_notes_key(update), [])
    if not notes:
        await update.message.reply_text("Заметок пока нет. Добавь: /note_add текст")
        return
    lines = ["Твои заметки:"]
    for i, item in enumerate(notes, 1):
        lines.append(f"{i}. {item.get('text', '')} ({item.get('created', '')})")
    await update.message.reply_text(_limit_telegram_text("\n".join(lines)))


async def note_clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    notes_data.pop(_notes_key(update), None)
    save_json(NOTES_FILE, notes_data)
    await update.message.reply_text("Заметки очищены.")


TRUTHS = [
    "Какая твоя самая странная привычка?",
    "Что ты давно откладываешь?",
    "Кого из чата ты бы взял(а) в команду на квест?",
    "Какой факт о тебе мало кто знает?",
]
DARES = [
    "Напиши комплимент последнему активному участнику.",
    "Поставь себе смешной статус на 10 минут.",
    "Расскажи мини-историю в 3 предложениях.",
    "Отправь стикер, который описывает твой день.",
]


async def truth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Правда: " + random.choice(TRUTHS))


async def dare_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Действие: " + random.choice(DARES))


async def slots_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    icons = ["🍒", "🍋", "💎", "7️⃣", "⭐", "🍀"]
    spin = [random.choice(icons) for _ in range(3)]
    if len(set(spin)) == 1:
        result = "Джекпот!"
    elif len(set(spin)) == 2:
        result = "Почти, есть пара."
    else:
        result = "Не повезло, крути ещё."
    await update.message.reply_text(" | ".join(spin) + f"\n{result}")


async def coinflip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🪙 " + random.choice(["Орёл", "Решка", "Ребро, невероятно."]))


async def rate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context) or "это"
    await update.message.reply_text(f"Оценка «{text}»: {random.randint(1, 100)}/100")


async def ship_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _message_arg_text(update, context)
    names = [x.strip("@ ,;") for x in text.split() if x.strip("@ ,;")]
    if len(names) < 2:
        names = get_mentioned_or_replied(update, context)
    if len(names) < 2:
        await update.message.reply_text("Формат: /ship @user1 @user2")
        return
    score = random.randint(1, 100)
    await update.message.reply_text(f"Совместимость {names[0]} + {names[1]}: {score}%")


async def bomb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    seconds = random.randint(3, 9)
    await update.message.reply_text(f"💣 Бомба обезврежена за {seconds} сек. Код: {random.randint(1000, 9999)}")


async def site_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return
    site_path = os.path.join(BASE_DIR, "site", "index.html")
    if COMMANDS_SITE_URL:
        await msg.reply_text(f"Сайт команд: {COMMANDS_SITE_URL}")
    if os.path.exists(site_path):
        with open(site_path, "rb") as f:
            await msg.reply_document(
                document=f,
                filename="mops-farmila-commands.html",
                caption="Сайт со всеми командами бота. Открой HTML-файл в браузере.",
            )
        return
    if not COMMANDS_SITE_URL:
        await msg.reply_text("Файл сайта не найден. В репозитории должен быть site/index.html.")

async def mops_kiss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await rp_action(update, context, "поцеловал(а)", 10)

async def mops_hug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await rp_action(update, context, "обнял(а)", 8)

async def mops_farmila_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🐶 Мопс-Фармила:\n\n"
        "Привет: /hello или просто «привет»\n"
        "Пока: /bye или «пока»\n"
        "Спасибо: /thanks или «спасибо»\n\n"
        "AI-помощник:\n"
        "/ai — помощь по AI\n"
        "/ask вопрос — ответить на вопрос\n"
        "/solve условие — решить задачу\n"
        "/analyze — анализ фото ответом на фото\n"
        "/vision /photo /ocr — локальный анализ фото без OpenAI\n"
        "/summary текст — кратко пересказать\n"
        "/translate текст — перевести\n\n"
        "Учеба и профессии:\n"
        "/study — учебная справка\n"
        "/math — математика, проценты, уравнения\n"
        "/biology — биология\n"
        "/informatics — информатика и программирование\n"
        "/food — пищевые технологии\n"
        "/techcard — техкарта и себестоимость\n"
        "/scale_recipe — пересчет рецепта\n"
        "/proportion — пропорции\n"
        "/nutrition — КБЖУ\n"
        "/units — перевод единиц\n\n"
        "Ультра-команды:\n"
        "/calc — калькулятор\n"
        "/roll — кубики d20/2d6\n"
        "/choose — выбрать вариант\n"
        "/password — пароль\n"
        "/remind — напоминание\n"
        "/note_add /notes /note_clear — заметки\n"
        "/truth /dare /slots /ship /rate /bomb — игры\n\n"
        "Развлечения:\n"
        "/joke — шутка\n"
        "/quote — цитата\n"
        "/fact — факт\n"
        "/compliment — похвалить\n"
        "/insult — поругать\n"
        "/ball — да/нет\n"
        "/coin — орел/решка\n"
        "/d6 — кубик 1-6\n"
        "/random — число\n"
        "/horoscope — гороскоп\n\n"
        "Управление:\n"
        "/mops_on /mops_off /mops_status"
    )

async def mops_daily_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chats = mops_state.setdefault("chats", {})
    now_ts = int(time.time())
    uptime = format_uptime(datetime.now() - BOT_STARTED_AT)

    for chat_id, cfg in chats.items():
        if not cfg.get("enabled", True):
            continue
        if not cfg.get("mops_reports_enabled", True):
            continue
        interval_min = int(cfg.get("report_interval_min", 300))
        last_ts = int(cfg.get("last_report_ts", 0) or 0)
        if last_ts > 0 and (now_ts - last_ts) < interval_min * 60:
            continue
        try:
            await context.bot.send_message(
                chat_id=int(chat_id),
                text=(
                    "🐶 Мопс-Фармила на связи.\n"
                    "✅ Бот работает стабильно.\n"
                    f"⏱ Аптайм: {uptime}\n"
                    "Если что-то пойдёт не так, просто напишите команду /mops_status."
                ),
            )
            cfg["last_sent"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            cfg["last_report_ts"] = now_ts
        except Exception as e:
            logger.warning("Mops daily message failed for chat %s: %s", chat_id, e)

    save_json(MOPS_FILE, mops_state)


async def hoshi_scene_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chats = mops_state.setdefault("chats", {})
    now_hour = datetime.now().strftime("%Y-%m-%d %H")
    for chat_id, cfg in chats.items():
        if not cfg.get("enabled", True):
            continue
        if not cfg.get("hoshi_enabled", True):
            continue
        if cfg.get("last_scene") == now_hour:
            continue
        # Ненавязчиво: с вероятностью 30% раз в час.
        if random.random() > 0.3:
            continue
        try:
            await context.bot.send_message(chat_id=int(chat_id), text=random.choice(HOSHI_SCENES))
            cfg["last_scene"] = now_hour
        except Exception as e:
            logger.warning("Hoshi scene failed for chat %s: %s", chat_id, e)
    save_json(MOPS_FILE, mops_state)


async def bot_added_greeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat:
        return
    chat_id = str(chat.id)
    ensure_mops_chat(chat_id)
    save_json(MOPS_FILE, mops_state)
    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                "Привет, я Мопс-Фармила.\n"
                "Коротко: рейды, дуэли, брак/отношения, экономика, мини-игры, квесты, обмен предметами.\n"
                "Быстрый старт: /start\n"
                "Текст-команды тоже работают, например: баланс, браки, рейд, рыбалка."
            ),
        )
    except Exception:
        return


def _user_id_key(user_id: int) -> str:
    return f"id:{user_id}"


def register_profile(tg_user) -> str:
    key = _user_id_key(tg_user.id)
    profile = profiles.setdefault(key, {"username": "", "first_name": ""})
    profile["username"] = (tg_user.username or profile.get("username") or "").lower()
    profile["first_name"] = tg_user.first_name or profile.get("first_name") or ""
    profiles[key] = profile
    save_json(PROFILE_FILE, profiles)
    return key


def display_user(user_key: str) -> str:
    p = profiles.get(user_key, {})
    uname = p.get("username", "")
    return f"@{uname}" if uname else (p.get("first_name") or user_key.replace("id:", "id"))


def ensure_wallet_key(user_key: str) -> dict:
    return daily_rewards.setdefault(user_key, {"coins": 0, "streak": 0, "last_claim": ""})


def resolve_user_key_from_token(token: str) -> str | None:
    token = norm_user(token)
    if token.startswith("id:"):
        return token
    if token.isdigit():
        return f"id:{token}"
    for key, p in profiles.items():
        if norm_user(p.get("username")) == token:
            return key
    return None


def schedule_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, seconds: int = 90) -> None:
    if context.job_queue:
        context.job_queue.run_once(
            delete_message_job,
            when=seconds,
            data={"chat_id": chat_id, "message_id": message_id},
            name=f"autodel:{chat_id}:{message_id}",
        )


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data or {}
    try:
        await context.bot.delete_message(chat_id=data.get("chat_id"), message_id=data.get("message_id"))
    except Exception:
        return


async def reply_game(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, ttl: int = 120) -> None:
    sent = await update.message.reply_text(text)
    schedule_delete(context, sent.chat_id, sent.message_id, ttl)
    schedule_delete(context, update.message.chat_id, update.message.message_id, ttl)


def relation_title(days: int, level: int) -> str:
    if days >= 365 and level >= 18:
        return "Легендарная пара"
    if days >= 180 and level >= 12:
        return "Золотая пара"
    if days >= 90 and level >= 8:
        return "Сильная пара"
    if level >= 5:
        return "Влюбленные"
    return "Новая пара"


async def relation_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    user_key = register_profile(msg.from_user)
    idx, m = find_marriage_for_user(chat_id, user_key)
    if idx is None or not m:
        await msg.reply_text("Вы не в браке.")
        return
    rel_key = marriage_key(chat_id, m["members"][0], m["members"][1])
    rel = relations.setdefault(rel_key, {"xp": 0, "level": 1, "created": datetime.now().isoformat()})
    dt = parse_iso_date(m.get("created")) or datetime.now()
    days = max(1, (datetime.now().date() - dt.date()).days + 1)
    title = relation_title(days, int(rel.get("level", 1)))
    await msg.reply_text(
        f"Статус пары: {title}\n"
        f"Уровень: {rel.get('level', 1)}\n"
        f"XP: {rel.get('xp', 0)}\n"
        f"Вместе: {days} дн."
    )
    save_json(RELATION_FILE, relations)


async def rp_action(update: Update, context: ContextTypes.DEFAULT_TYPE, verb: str, xp: int = 8) -> None:
    msg = update.message
    actor = register_profile(msg.from_user)
    mentioned = get_mentioned_or_replied(update, context)
    target_key = None
    if mentioned:
        target_key = resolve_user_key_from_token(mentioned[0])
    if not target_key and msg.reply_to_message and msg.reply_to_message.from_user:
        target_key = register_profile(msg.reply_to_message.from_user)
    if not target_key:
        await msg.reply_text(f"Использование: {verb} @user или ответом на сообщение.")
        return
    chat_id = str(msg.chat_id)
    idx, m = find_marriage_for_user(chat_id, actor)
    if idx is not None and m and target_key in m.get("members", []):
        rel_key = marriage_key(chat_id, m["members"][0], m["members"][1])
        rel = relations.setdefault(rel_key, {"xp": 0, "level": 1, "created": datetime.now().isoformat()})
        rel["xp"] = int(rel.get("xp", 0)) + xp
        if rel["xp"] >= int(rel.get("level", 1)) * 60:
            rel["xp"] = 0
            rel["level"] = int(rel.get("level", 1)) + 1
        save_json(RELATION_FILE, relations)
    await msg.reply_text(f"{display_user(actor)} {verb} {display_user(target_key)}")


async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    actor = register_profile(msg.from_user)
    mentioned = get_mentioned_or_replied(update, context)
    if len(context.args) < 2:
        await msg.reply_text("Использование: /trade @user item_id [кол-во]")
        return
    target = resolve_user_key_from_token(mentioned[0]) if mentioned else None
    if not target:
        await msg.reply_text("Укажи получателя через @ или ответ.")
        return
    item_id = context.args[-2].lower()
    qty = int(context.args[-1]) if context.args[-1].isdigit() else 1
    inv = ensure_inventory(actor)
    if int(inv.get(item_id, 0)) < qty:
        await msg.reply_text("Не хватает предметов для обмена.")
        return
    tid = f"{msg.chat_id}:{actor}:{target}:{uuid4().hex[:8]}"
    trade_requests[tid] = {"from": actor, "to": target, "item": item_id, "qty": qty, "chat_id": str(msg.chat_id)}
    save_json(TRADE_FILE, trade_requests)
    await msg.reply_text(
        f"Запрос обмена отправлен: {display_user(actor)} -> {display_user(target)}\n"
        f"{item_id} x{qty}\n/accept_trade или /decline_trade"
    )


def _find_trade_for_user(chat_id: str, user_key: str) -> tuple[str, dict] | tuple[None, None]:
    for k, t in trade_requests.items():
        if t.get("chat_id") == chat_id and t.get("to") == user_key:
            return k, t
    return None, None


async def accept_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = register_profile(msg.from_user)
    key, tr = _find_trade_for_user(str(msg.chat_id), user)
    if not tr:
        await msg.reply_text("Нет активных запросов обмена.")
        return
    giver = tr["from"]
    item_id = tr["item"]
    qty = int(tr.get("qty", 1))
    inv_from = ensure_inventory(giver)
    if int(inv_from.get(item_id, 0)) < qty:
        trade_requests.pop(key, None)
        save_json(TRADE_FILE, trade_requests)
        await msg.reply_text("Обмен отменен: у отправителя уже нет предмета.")
        return
    inv_from[item_id] = int(inv_from.get(item_id, 0)) - qty
    if inv_from[item_id] <= 0:
        inv_from.pop(item_id, None)
    inv_to = ensure_inventory(user)
    inv_to[item_id] = int(inv_to.get(item_id, 0)) + qty
    trade_requests.pop(key, None)
    save_json(TRADE_FILE, trade_requests)
    save_json(INVENTORY_FILE, inventories)
    await msg.reply_text(f"Обмен выполнен: {display_user(giver)} передал {item_id} x{qty} для {display_user(user)}")


async def decline_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = register_profile(msg.from_user)
    key, tr = _find_trade_for_user(str(msg.chat_id), user)
    if not tr:
        await msg.reply_text("Нет активных запросов обмена.")
        return
    trade_requests.pop(key, None)
    save_json(TRADE_FILE, trade_requests)
    await msg.reply_text("Обмен отклонен.")


async def mops_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Мини-игры: polesudes_start, battleship_start, мопсигра, кнб <камень|ножницы|бумага>, викторина")


async def rps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not context.args:
        await msg.reply_text("Формат: кнб камень|ножницы|бумага")
        return
    choice = context.args[0].lower()
    opts = ["камень", "ножницы", "бумага"]
    if choice not in opts:
        await msg.reply_text("Выбери: камень, ножницы или бумага.")
        return
    bot = random.choice(opts)
    win = (choice == "камень" and bot == "ножницы") or (choice == "ножницы" and bot == "бумага") or (choice == "бумага" and bot == "камень")
    if choice == bot:
        res = "Ничья."
    elif win:
        res = "Ты победил!"
    else:
        res = "Победа бота."
    await reply_game(update, context, f"Ты: {choice}\nБот: {bot}\n{res}", 90)


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    qs = [
        ("Сколько дней в неделе?", "7"),
        ("Столица Франции?", "париж"),
        ("2+2*2 = ?", "6"),
    ]
    q, a = random.choice(qs)
    minigames[str(msg.chat_id)] = {"type": "quiz", "q": q, "a": a, "active": True}
    save_json(MINIGAME_FILE, minigames)
    await reply_game(update, context, f"Викторина: {q}\nОтветь сообщением: ответ <текст>", 120)


async def mops_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    secret = random.randint(1, 10)
    guess = random.randint(1, 10)
    text = f"Мопс загадал {secret}. Твой бросок: {guess}. " + ("Победа!" if secret == guess else "Почти!")
    await reply_game(update, context, text, 60)


async def polesudes_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    words = ["фармила", "кольцо", "рейд", "бот", "дуэль", "мопс"]
    answer = random.choice(words)
    chat_id = str(update.message.chat_id)
    minigames[chat_id] = {"type": "wheel", "answer": answer, "open": ["_" for _ in answer], "active": True}
    save_json(MINIGAME_FILE, minigames)
    await reply_game(update, context, "Поле чудес началось! Пиши: буква <символ> или слово <слово>", 120)


async def game_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return
    chat_id = str(msg.chat_id)
    game = minigames.get(chat_id, {})
    if game.get("type") == "quiz" and game.get("active"):
        text = msg.text.strip().lower()
        if text.startswith("ответ "):
            ans = text.split(" ", 1)[1].strip().lower()
            ok = ans == str(game.get("a", "")).lower()
            game["active"] = False
            minigames[chat_id] = game
            save_json(MINIGAME_FILE, minigames)
            await reply_game(update, context, "Верно! +10 XP" if ok else f"Неверно. Правильный ответ: {game.get('a')}", 90)
            if ok:
                grant_xp(register_profile(msg.from_user), 10)
        return
    if game.get("type") != "wheel" or not game.get("active"):
        return
    text = msg.text.strip().lower()
    if text.startswith("буква "):
        ch = text.split(" ", 1)[1][:1]
        ans = game["answer"]
        open_mask = game["open"]
        hit = False
        for i, c in enumerate(ans):
            if c == ch:
                open_mask[i] = ch
                hit = True
        game["open"] = open_mask
        if "_" not in open_mask:
            game["active"] = False
            await reply_game(update, context, f"Слово разгадано: {ans}", 90)
        else:
            await reply_game(update, context, ("Есть!" if hit else "Нет такой буквы.") + f" {' '.join(open_mask)}", 90)
    elif text.startswith("слово "):
        val = text.split(" ", 1)[1].strip()
        if val == game["answer"]:
            game["active"] = False
            await reply_game(update, context, f"Верно! Слово: {val}", 90)
        else:
            await reply_game(update, context, "Неверно, пробуй еще.", 90)
    minigames[chat_id] = game
    save_json(MINIGAME_FILE, minigames)


async def battleship_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = random.randint(1, 9)
    chat_id = str(update.message.chat_id)
    minigames[chat_id] = {"type": "sea", "target": target, "active": True, "tries": 4}
    save_json(MINIGAME_FILE, minigames)
    await reply_game(update, context, "Морской бой: угадай клетку 1-9 командой: выстрел <число>", 120)


async def sea_shot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    game = minigames.get(chat_id, {})
    if game.get("type") != "sea" or not game.get("active"):
        return
    text = msg.text.strip().lower()
    if not text.startswith("выстрел "):
        return
    part = text.split(" ", 1)[1]
    if not part.isdigit():
        await reply_game(update, context, "Нужно число 1-9.", 60)
        return
    val = int(part)
    game["tries"] = int(game.get("tries", 4)) - 1
    if val == int(game["target"]):
        game["active"] = False
        await reply_game(update, context, "Попадание! Корабль потоплен.", 90)
    elif game["tries"] <= 0:
        game["active"] = False
        await reply_game(update, context, f"Бой окончен. Корабль был в клетке {game['target']}.", 90)
    else:
        await reply_game(update, context, f"Мимо. Осталось попыток: {game['tries']}", 90)
    minigames[chat_id] = game
    save_json(MINIGAME_FILE, minigames)


def ensure_mafia(chat_id: str) -> dict:
    return mafia_games.setdefault(
        chat_id,
        {
            "active": False,
            "started": False,
            "players": [],
            "roles": {},
            "alive": [],
            "votes": {},
            "protected": "",
            "round": 0,
            "host": "",
        },
    )


async def mafia_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    g = ensure_mafia(chat_id)
    if g.get("active"):
        await msg.reply_text("Мафия уже создана. Войти: мафиявойти")
        return
    host = register_profile(msg.from_user)
    g.update({"active": True, "started": False, "players": [host], "roles": {}, "alive": [host], "votes": {}, "round": 0, "host": host})
    mafia_games[chat_id] = g
    await reply_game(update, context, "Игра Мафия создана. Пишите: мафиявойти. Старт: мафиястарт", 180)


async def mafia_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    g = ensure_mafia(chat_id)
    if not g.get("active"):
        await msg.reply_text("Сначала создайте игру: мафия")
        return
    if g.get("started"):
        await msg.reply_text("Игра уже началась.")
        return
    user_key = register_profile(msg.from_user)
    if user_key not in g["players"]:
        g["players"].append(user_key)
        g["alive"].append(user_key)
    mafia_games[chat_id] = g
    await msg.reply_text(f"{display_user(user_key)} вошел в игру. Участников: {len(g['players'])}")


async def mafia_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    g = ensure_mafia(chat_id)
    if not g.get("active"):
        await msg.reply_text("Нет активной комнаты. Команда: мафия")
        return
    if g.get("started"):
        await msg.reply_text("Игра уже идет.")
        return
    players = list(dict.fromkeys(g.get("players", [])))
    if len(players) < 4:
        await msg.reply_text("Для старта нужно минимум 4 игрока.")
        return
    random.shuffle(players)
    mafia_count = 1 if len(players) < 7 else 2
    mafias = set(players[:mafia_count])
    prostitute = players[mafia_count] if len(players) >= 5 else ""
    roles = {}
    for p in players:
        if p in mafias:
            roles[p] = "мафия"
        elif prostitute and p == prostitute:
            roles[p] = "проститутка"
        else:
            roles[p] = "мирный"
    g["roles"] = roles
    g["started"] = True
    g["alive"] = players[:]
    g["votes"] = {}
    g["round"] = 1
    mafia_games[chat_id] = g
    for p in players:
        role = roles[p]
        txt = f"Твоя роль в Мафии: {role}."
        try:
            uid = int(p.replace("id:", ""))
            await context.bot.send_message(chat_id=uid, text=txt)
        except Exception:
            continue
    await reply_game(update, context, "Мафия началась. Голосование: мафияголос @user. Роль проститутка: мафиязащита @user", 180)


async def mafia_protect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    g = ensure_mafia(chat_id)
    if not g.get("active") or not g.get("started"):
        await msg.reply_text("Мафия не запущена.")
        return
    actor = register_profile(msg.from_user)
    if g.get("roles", {}).get(actor) != "проститутка":
        await msg.reply_text("Эта команда доступна только роли проститутка.")
        return
    if actor not in g.get("alive", []):
        await msg.reply_text("Ты выбыл из игры.")
        return
    if not context.args:
        await msg.reply_text("Формат: мафиязащита @user")
        return
    target = resolve_user_key_from_token(context.args[0].lstrip("@"))
    if not target or target not in g.get("alive", []):
        await msg.reply_text("Цель не найдена среди живых.")
        return
    g["protected"] = target
    mafia_games[chat_id] = g
    await msg.reply_text(f"Защита активна на этот раунд: {display_user(target)}")


async def mafia_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    g = ensure_mafia(chat_id)
    if not g.get("active") or not g.get("started"):
        await msg.reply_text("Мафия не запущена.")
        return
    voter = register_profile(msg.from_user)
    if voter not in g.get("alive", []):
        await msg.reply_text("Ты выбыл из игры.")
        return
    if not context.args:
        await msg.reply_text("Формат: мафияголос @user")
        return
    target = resolve_user_key_from_token(context.args[0].lstrip("@"))
    if not target or target not in g.get("alive", []):
        await msg.reply_text("Цель не найдена среди живых.")
        return
    g["votes"][voter] = target
    mafia_games[chat_id] = g
    alive = g.get("alive", [])
    if len(g["votes"]) < len(alive):
        await msg.reply_text(f"Голос принят. {len(g['votes'])}/{len(alive)}")
        return
    counts = {}
    for _, t in g["votes"].items():
        counts[t] = counts.get(t, 0) + 1
    kicked = max(counts.items(), key=lambda x: x[1])[0]
    protected = g.get("protected", "")
    if protected and kicked == protected:
        g["votes"] = {}
        g["protected"] = ""
        g["round"] = int(g.get("round", 1)) + 1
        mafia_games[chat_id] = g
        await reply_game(update, context, f"{display_user(kicked)} был(а) под защитой и остался(ась) в игре. Раунд {g['round']}.", 180)
        return
    if kicked in g["alive"]:
        g["alive"].remove(kicked)
    g["votes"] = {}
    g["protected"] = ""
    mafia_alive = [u for u in g["alive"] if g["roles"].get(u) == "мафия"]
    civ_alive = [u for u in g["alive"] if g["roles"].get(u) != "мафия"]
    if not mafia_alive:
        for u in g.get("players", []):
            grant_xp(u, 8)
        g["active"] = False
        g["started"] = False
        await reply_game(update, context, f"Голосование: выбыл {display_user(kicked)}. Победа мирных!", 180)
    elif len(mafia_alive) >= len(civ_alive):
        g["active"] = False
        g["started"] = False
        await reply_game(update, context, f"Голосование: выбыл {display_user(kicked)}. Победа мафии!", 180)
    else:
        g["round"] = int(g.get("round", 1)) + 1
        await reply_game(update, context, f"Голосование: выбыл {display_user(kicked)}. Раунд {g['round']}.", 180)
    mafia_games[chat_id] = g


async def mafia_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    g = ensure_mafia(str(msg.chat_id))
    if not g.get("active"):
        await msg.reply_text("Мафия не создана.")
        return
    await msg.reply_text(
        f"Мафия: {'идет' if g.get('started') else 'лобби'}\n"
        f"Игроков: {len(g.get('players', []))}\n"
        f"Живых: {len(g.get('alive', []))}\n"
        f"Раунд: {g.get('round', 0)}"
    )


async def mafia_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat_id = str(msg.chat_id)
    g = ensure_mafia(chat_id)
    if not g.get("active"):
        await msg.reply_text("Мафия уже остановлена.")
        return
    mafia_games[chat_id] = {"active": False, "started": False, "players": [], "roles": {}, "alive": [], "votes": {}, "protected": "", "round": 0, "host": ""}
    await msg.reply_text("Игра Мафия остановлена.")


async def report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await mops_daily_job(context)


async def owner_grant_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not is_owner(msg.from_user):
        return
    mentioned = get_mentioned_or_replied(update, context)
    target = resolve_user_key_from_token(mentioned[0]) if mentioned else None
    if not target and msg.reply_to_message and msg.reply_to_message.from_user:
        target = register_profile(msg.reply_to_message.from_user)
    if not target:
        await msg.reply_text("Формат: фармила-прем @user")
        return
    p = profiles.setdefault(target, {"username": "", "first_name": ""})
    p["premium"] = True
    profiles[target] = p
    save_json(PROFILE_FILE, profiles)
    await msg.reply_text(f"Премиум Мопса выдан: {display_user(target)}")


async def owner_grant_coins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not is_owner(msg.from_user):
        return
    parts = msg.text.strip().split()
    if len(parts) < 3:
        await msg.reply_text("Формат: фармила-монеты @user 1000")
        return
    target = resolve_user_key_from_token(parts[1].lstrip("@"))
    if not target:
        await msg.reply_text("Не найден пользователь.")
        return
    try:
        amount = int(parts[2])
    except ValueError:
        await msg.reply_text("Сумма должна быть числом.")
        return
    if amount <= 0:
        await msg.reply_text("Сумма должна быть больше 0.")
        return
    w = ensure_wallet_key(target)
    w["coins"] = int(w.get("coins", 0)) + amount
    daily_rewards[target] = w
    save_json(DAILY_FILE, daily_rewards)
    await msg.reply_text(f"Начислено {amount} монет для {display_user(target)}. Баланс: {w['coins']}")


async def owner_secret_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not is_owner(msg.from_user):
        return
    # Безопасная версия: фиксируем жалобу в боте и оповещаем чат, без спама в поддержку.
    parts = msg.text.strip().split(maxsplit=2)
    if len(parts) < 2:
        await msg.reply_text("Формат: фармила-жалоба @user причина")
        return
    target = resolve_user_key_from_token(parts[1].lstrip("@"))
    reason = parts[2] if len(parts) > 2 else "подозрение на нарушение"
    if not target:
        await msg.reply_text("Не найден пользователь.")
        return
    chat_id = str(msg.chat_id)
    lst = mod_reports.setdefault(chat_id, [])
    lst.append(
        {
            "target": target,
            "reason": reason,
            "by": register_profile(msg.from_user),
            "created_at": datetime.now().isoformat(),
        }
    )
    save_json(REPORT_FILE, mod_reports)
    await msg.reply_text(
        f"Жалоба записана в журнал модерации:\n"
        f"Пользователь: {display_user(target)}\n"
        f"Причина: {reason}"
    )


async def owner_mod_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not is_owner(msg.from_user):
        return
    parts = (msg.text or "").split()
    chat_id = str(msg.chat_id)
    cfg = ensure_mod_chat(chat_id)
    if len(parts) < 2:
        await msg.reply_text("фармила-мод статус|вкл|выкл|лимит 7|мут 10|+слово xxx|-слово xxx")
        return
    cmd = parts[1].lower()
    if cmd == "статус":
        await msg.reply_text(
            f"Модерация: {'вкл' if cfg.get('enabled') else 'выкл'}\n"
            f"Лимит флуда: {cfg.get('flood_limit')}/{cfg.get('flood_window_sec')}сек\n"
            f"Мут: {cfg.get('mute_minutes')} мин\n"
            f"Стоп-слов: {len(cfg.get('bad_words', []))}"
        )
    elif cmd == "вкл":
        cfg["enabled"] = True
    elif cmd == "выкл":
        cfg["enabled"] = False
    elif cmd == "лимит" and len(parts) > 2 and parts[2].isdigit():
        cfg["flood_limit"] = max(3, min(20, int(parts[2])))
    elif cmd == "мут" and len(parts) > 2 and parts[2].isdigit():
        cfg["mute_minutes"] = max(1, min(1440, int(parts[2])))
    elif cmd.startswith("+слово") and len(parts) > 2:
        w = parts[2].lower()
        arr = cfg.setdefault("bad_words", [])
        if w not in arr:
            arr.append(w)
    elif cmd.startswith("-слово") and len(parts) > 2:
        w = parts[2].lower()
        cfg["bad_words"] = [x for x in cfg.get("bad_words", []) if x != w]
    mod_state.setdefault("chats", {})[chat_id] = cfg
    save_json(MOD_STATE_FILE, mod_state)
    if cmd != "статус":
        await msg.reply_text("Настройки модерации обновлены.")


async def moderation_guard(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: str, user_key: str) -> bool:
    msg = update.message
    if not msg or not msg.text:
        return False
    if is_privileged(msg.from_user):
        return False
    cfg = ensure_mod_chat(chat_id)
    if not cfg.get("enabled", True):
        return False

    if user_key in cfg.get("banned", []):
        try:
            await msg.delete()
        except Exception:
            pass
        return True

    text = (msg.text or "").lower()
    warns = cfg.setdefault("warns", {})
    activity = cfg.setdefault("activity", {})
    now_ts = int(datetime.now().timestamp())
    arr = activity.setdefault(user_key, [])
    arr.append(now_ts)
    window = int(cfg.get("flood_window_sec", 12))
    arr = [x for x in arr if now_ts - x <= window]
    activity[user_key] = arr

    bad_hit = any(w in text for w in cfg.get("bad_words", []))
    flood_hit = len(arr) >= int(cfg.get("flood_limit", 6))
    if not bad_hit and not flood_hit:
        mod_state.setdefault("chats", {})[chat_id] = cfg
        save_json(MOD_STATE_FILE, mod_state)
        return False

    warns[user_key] = int(warns.get(user_key, 0)) + 1
    try:
        await msg.delete()
    except Exception:
        pass

    if warns[user_key] >= 3:
        mute_minutes = int(cfg.get("mute_minutes", 10))
        try:
            until = datetime.now() + timedelta(minutes=mute_minutes)
            await context.bot.restrict_chat_member(
                chat_id=msg.chat_id,
                user_id=msg.from_user.id,
                permissions={"can_send_messages": False},
                until_date=until,
            )
        except Exception:
            pass
        warns[user_key] = 0
        try:
            await msg.reply_text(f"{display_user(user_key)} получил авто-мут на {mute_minutes} мин.")
        except Exception:
            pass
    mod_state.setdefault("chats", {})[chat_id] = cfg
    save_json(MOD_STATE_FILE, mod_state)
    return True


def ensure_quest(user_key: str) -> dict:
    q = quests.setdefault(user_key, {"date": "", "target": 5, "progress": 0, "done": False})
    td = today_str()
    if q.get("date") != td:
        q = {"date": td, "target": random.randint(4, 9), "progress": 0, "done": False}
        quests[user_key] = q
    return q


def touch_progress(user_key: str, step: int = 1) -> None:
    q = ensure_quest(user_key)
    if q.get("done"):
        return
    q["progress"] = int(q.get("progress", 0)) + step
    if q["progress"] >= int(q.get("target", 5)):
        q["done"] = True
        wallet = ensure_wallet_key(user_key)
        reward = 120
        wallet["coins"] = int(wallet.get("coins", 0)) + reward
        daily_rewards[user_key] = wallet
        ach = achievements.setdefault(user_key, {"quest_done": 0, "fish": 0, "wins": 0, "lottery": 0})
        ach["quest_done"] = int(ach.get("quest_done", 0)) + 1
    quests[user_key] = q
    save_json(QUEST_FILE, quests)
    save_json(DAILY_FILE, daily_rewards)
    save_json(ACHIEV_FILE, achievements)


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    w = ensure_wallet_key(user_key)
    inv = ensure_inventory(user_key)
    q = ensure_quest(user_key)
    ach = achievements.setdefault(user_key, {"quest_done": 0, "fish": 0, "wins": 0, "lottery": 0})
    x = ensure_xp(user_key)
    lvl = int(x.get("level", 1))
    await msg.reply_text(
        f"Профиль {display_user(user_key)}\n"
        f"Монеты: {w.get('coins', 0)}\n"
        f"Ранг: {xp_title(lvl)} ({lvl} ур.)\n"
        f"Инвентарь: {sum(int(v) for v in inv.values())} предметов\n"
        f"Квест дня: {q.get('progress', 0)}/{q.get('target', 5)}\n"
        f"Достижения: квесты {ach.get('quest_done',0)}, рыба {ach.get('fish',0)}, лотерея {ach.get('lottery',0)}"
    )


async def quest_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    q = ensure_quest(user_key)
    await msg.reply_text(
        f"Квест дня: сделать {q['target']} активностей.\n"
        f"Прогресс: {q['progress']}/{q['target']}\n"
        f"Статус: {'выполнен' if q.get('done') else 'в процессе'}"
    )
    save_json(QUEST_FILE, quests)


async def fish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    catches = [
        ("карась", 14, 22),
        ("щука", 26, 42),
        ("сом", 35, 55),
        ("золотая рыбка", 0, 120),
    ]
    name, mn, mx = random.choice(catches)
    reward = random.randint(mn, mx)
    wallet = ensure_wallet_key(user_key)
    wallet["coins"] = int(wallet.get("coins", 0)) + reward
    daily_rewards[user_key] = wallet
    inv = ensure_inventory(user_key)
    fish_key = f"fish_{name.replace(' ', '_')}"
    inv[fish_key] = int(inv.get(fish_key, 0)) + 1
    ach = achievements.setdefault(user_key, {"quest_done": 0, "fish": 0, "wins": 0, "lottery": 0})
    ach["fish"] = int(ach.get("fish", 0)) + 1
    grant_xp(user_key, 7)
    touch_progress(user_key, 1)
    save_json(DAILY_FILE, daily_rewards)
    save_json(INVENTORY_FILE, inventories)
    save_json(ACHIEV_FILE, achievements)
    await reply_game(update, context, f"Улов: {name}. +{reward} монет.", 90)


async def lottery_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    price = 50
    w = ensure_wallet_key(user_key)
    if int(w.get("coins", 0)) < price:
        await msg.reply_text("Не хватает 50 монет на билет.")
        return
    w["coins"] = int(w.get("coins", 0)) - price
    ticket = random.randint(1000, 9999)
    rec = lottery.setdefault(user_key, {"tickets": [], "wins": 0})
    rec["tickets"].append(ticket)
    daily_rewards[user_key] = w
    lottery[user_key] = rec
    touch_progress(user_key, 1)
    save_json(DAILY_FILE, daily_rewards)
    save_json(LOTTERY_FILE, lottery)
    await msg.reply_text(f"Билет куплен: #{ticket}. Розыгрыш: /lottery_draw")


async def lottery_draw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    rec = lottery.setdefault(user_key, {"tickets": [], "wins": 0})
    if not rec.get("tickets"):
        await msg.reply_text("У вас нет билетов.")
        return
    winning = random.randint(1000, 9999)
    prize = 0
    if winning in rec["tickets"]:
        prize = 700
    elif any((t % 100) == (winning % 100) for t in rec["tickets"]):
        prize = 140
    rec["tickets"] = []
    if prize:
        w = ensure_wallet_key(user_key)
        w["coins"] = int(w.get("coins", 0)) + prize
        daily_rewards[user_key] = w
        rec["wins"] = int(rec.get("wins", 0)) + 1
        ach = achievements.setdefault(user_key, {"quest_done": 0, "fish": 0, "wins": 0, "lottery": 0})
        ach["lottery"] = int(ach.get("lottery", 0)) + 1
        save_json(ACHIEV_FILE, achievements)
        await msg.reply_text(f"Выигрыш! Номер #{winning}. Приз: +{prize} монет.")
    else:
        await msg.reply_text(f"Номер #{winning}. В этот раз без приза.")
    lottery[user_key] = rec
    touch_progress(user_key, 1)
    save_json(LOTTERY_FILE, lottery)
    save_json(DAILY_FILE, daily_rewards)


async def mops_train(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    p = profiles.setdefault(user_key, {"username": "", "first_name": ""})
    lvl = int(p.get("mops_level", 1))
    xp = int(p.get("mops_xp", 0)) + random.randint(8, 16)
    need = lvl * 40
    up = False
    if xp >= need:
        xp -= need
        lvl += 1
        up = True
    p["mops_level"] = lvl
    p["mops_xp"] = xp
    profiles[user_key] = p
    grant_xp(user_key, 10)
    touch_progress(user_key, 1)
    save_json(PROFILE_FILE, profiles)
    await msg.reply_text(
        f"Тренировка Мопса завершена.\nУровень: {lvl}\nXP: {xp}/{lvl*40}\n"
        + ("Новый уровень!" if up else "")
    )


async def top_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    ranking = sorted(
        ((u, int(v.get("coins", 0))) for u, v in daily_rewards.items()),
        key=lambda x: x[1],
        reverse=True,
    )[:10]
    if not ranking:
        await msg.reply_text("Топ пока пуст.")
        return
    lines = ["Топ игроков:"]
    for i, (u, c) in enumerate(ranking, 1):
        lines.append(f"{i}. {display_user(u)} - {c} монет")
    await msg.reply_text("\n".join(lines))


def ensure_bank(user_key: str) -> dict:
    return bank_data.setdefault(user_key, {"deposit": 0, "updated": today_str()})


def ensure_xp(user_key: str) -> dict:
    return xp_data.setdefault(user_key, {"xp": 0, "level": 1})


def xp_title(level: int) -> str:
    if level >= 40:
        return "Легенда Фармилы"
    if level >= 30:
        return "Повелитель рейдов"
    if level >= 20:
        return "Элита чата"
    if level >= 12:
        return "Опытный герой"
    if level >= 6:
        return "Боец"
    return "Новичок"


def grant_xp(user_key: str, amount: int) -> tuple[int, int, bool]:
    rec = ensure_xp(user_key)
    lvl = int(rec.get("level", 1))
    xp = int(rec.get("xp", 0)) + max(0, amount)
    need = lvl * 55
    uplevel = False
    while xp >= need:
        xp -= need
        lvl += 1
        need = lvl * 55
        uplevel = True
    rec["xp"] = xp
    rec["level"] = lvl
    xp_data[user_key] = rec
    save_json(XP_FILE, xp_data)
    return lvl, xp, uplevel


async def bank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    rec = ensure_bank(user_key)
    await msg.reply_text(f"Банк {display_user(user_key)}: {rec.get('deposit', 0)} монет")


async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    if not context.args or not context.args[0].isdigit():
        await msg.reply_text("Формат: /deposit 100")
        return
    amount = int(context.args[0])
    if amount <= 0:
        await msg.reply_text("Сумма должна быть больше 0.")
        return
    w = ensure_wallet_key(user_key)
    if int(w.get("coins", 0)) < amount:
        await msg.reply_text("Недостаточно монет.")
        return
    w["coins"] = int(w.get("coins", 0)) - amount
    rec = ensure_bank(user_key)
    rec["deposit"] = int(rec.get("deposit", 0)) + amount
    rec["updated"] = today_str()
    daily_rewards[user_key] = w
    bank_data[user_key] = rec
    save_json(DAILY_FILE, daily_rewards)
    save_json(BANK_FILE, bank_data)
    await msg.reply_text(f"Вклад пополнен на {amount}. В банке: {rec['deposit']}")


async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    if not context.args or not context.args[0].isdigit():
        await msg.reply_text("Формат: /withdraw 100")
        return
    amount = int(context.args[0])
    rec = ensure_bank(user_key)
    if amount <= 0 or int(rec.get("deposit", 0)) < amount:
        await msg.reply_text("Недостаточно средств на вкладе.")
        return
    rec["deposit"] = int(rec.get("deposit", 0)) - amount
    w = ensure_wallet_key(user_key)
    w["coins"] = int(w.get("coins", 0)) + amount
    bank_data[user_key] = rec
    daily_rewards[user_key] = w
    save_json(BANK_FILE, bank_data)
    save_json(DAILY_FILE, daily_rewards)
    await msg.reply_text(f"Снято {amount}. Баланс: {w['coins']}")


async def bank_interest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    changed = False
    td = today_str()
    for user_key, rec in bank_data.items():
        if rec.get("updated") == td:
            continue
        dep = int(rec.get("deposit", 0))
        if dep <= 0:
            rec["updated"] = td
            continue
        add = max(1, dep // 100)
        rec["deposit"] = dep + add
        rec["updated"] = td
        bank_data[user_key] = rec
        changed = True
    if changed:
        save_json(BANK_FILE, bank_data)


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    sender = register_profile(msg.from_user)
    if len(context.args) < 2:
        await msg.reply_text("Формат: /pay @user 100")
        return
    target = resolve_user_key_from_token(context.args[0].lstrip("@"))
    if not target or target == sender:
        await msg.reply_text("Некорректный получатель.")
        return
    if not context.args[1].isdigit():
        await msg.reply_text("Сумма должна быть числом.")
        return
    amount = int(context.args[1])
    if amount <= 0:
        await msg.reply_text("Сумма должна быть больше 0.")
        return
    ws = ensure_wallet_key(sender)
    if int(ws.get("coins", 0)) < amount:
        await msg.reply_text("Недостаточно монет.")
        return
    wt = ensure_wallet_key(target)
    ws["coins"] = int(ws.get("coins", 0)) - amount
    wt["coins"] = int(wt.get("coins", 0)) + amount
    daily_rewards[sender] = ws
    daily_rewards[target] = wt
    save_json(DAILY_FILE, daily_rewards)
    grant_xp(sender, 5)
    await msg.reply_text(f"Перевод выполнен: {display_user(sender)} -> {display_user(target)} : {amount} монет")


async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_key = register_profile(msg.from_user)
    rec = ensure_xp(user_key)
    lvl = int(rec.get("level", 1))
    xp = int(rec.get("xp", 0))
    await msg.reply_text(f"Ранг: {xp_title(lvl)}\nУровень: {lvl}\nXP: {xp}/{lvl*55}")


async def ban_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not is_privileged(msg.from_user):
        return
    if not context.args:
        await msg.reply_text("Формат: /ban_player @user")
        return
    target = resolve_user_key_from_token(context.args[0].lstrip("@"))
    if not target:
        await msg.reply_text("Пользователь не найден.")
        return
    cfg = ensure_mod_chat(str(msg.chat_id))
    banned = cfg.setdefault("banned", [])
    if target not in banned:
        banned.append(target)
    mod_state.setdefault("chats", {})[str(msg.chat_id)] = cfg
    save_json(MOD_STATE_FILE, mod_state)
    await msg.reply_text(f"{display_user(target)} добавлен в локальный бан-лист бота.")


async def unban_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not is_privileged(msg.from_user):
        return
    if not context.args:
        await msg.reply_text("Формат: /unban_player @user")
        return
    target = resolve_user_key_from_token(context.args[0].lstrip("@"))
    if not target:
        await msg.reply_text("Пользователь не найден.")
        return
    cfg = ensure_mod_chat(str(msg.chat_id))
    cfg["banned"] = [x for x in cfg.get("banned", []) if x != target]
    mod_state.setdefault("chats", {})[str(msg.chat_id)] = cfg
    save_json(MOD_STATE_FILE, mod_state)
    await msg.reply_text(f"{display_user(target)} удален из локального бан-листа бота.")



def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(ChatMemberHandler(bot_added_greeting, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("brak", brak))
    app.add_handler(CommandHandler("razvod", razvod))
    app.add_handler(CommandHandler("alyans", alyans))
    app.add_handler(CommandHandler("vragi", vragi))
    app.add_handler(CommandHandler("braki", braki))
    app.add_handler(CommandHandler("soyuzy", soyuzy))
    app.add_handler(CommandHandler("moisoyuz", moisoyuz))
    app.add_handler(CommandHandler("anniversary", anniversary))
    app.add_handler(CommandHandler("rings", rings))
    app.add_handler(CommandHandler("my_rings", my_rings))
    app.add_handler(CommandHandler("myrings", my_rings))
    app.add_handler(CommandHandler("ring_exchange", ring_exchange))
    app.add_handler(CommandHandler("duel", duel))
    app.add_handler(CommandHandler("pvp", duel))
    app.add_handler(CommandHandler("accept", accept))
    app.add_handler(CommandHandler("decline", decline))
    app.add_handler(CommandHandler("shot", shot))
    app.add_handler(CommandHandler("duel_help", duel_help))
    app.add_handler(CommandHandler("pvpstats", pvpstats))
    app.add_handler(CommandHandler("pvptop", pvptop))
    app.add_handler(CommandHandler("war", war))
    app.add_handler(CommandHandler("voyna", war))
    app.add_handler(CommandHandler("warstats", warstats_cmd))
    app.add_handler(CommandHandler("wartop", wartop))
    app.add_handler(CommandHandler("words_start", words_start))
    app.add_handler(CommandHandler("word", word))
    app.add_handler(CommandHandler("words_status", words_status))
    app.add_handler(CommandHandler("words_stop", words_stop))
    app.add_handler(CommandHandler("raid_start", raid_start))
    app.add_handler(CommandHandler("raid_hit", raid_hit))
    app.add_handler(CommandHandler("raid_status", raid_status))
    app.add_handler(CommandHandler("raid_top", raid_top))
    app.add_handler(CommandHandler("raid_help", raid_help))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("inventory", inventory))
    app.add_handler(CommandHandler("trade", trade))
    app.add_handler(CommandHandler("accept_trade", accept_trade))
    app.add_handler(CommandHandler("decline_trade", decline_trade))
    app.add_handler(CommandHandler("relation", relation_status))
    app.add_handler(CommandHandler("relations", relation_status))
    app.add_handler(CommandHandler("mops_play", mops_play))
    app.add_handler(CommandHandler("mops_guess", mops_guess))
    app.add_handler(CommandHandler("polesudes_start", polesudes_start))
    app.add_handler(CommandHandler("battleship_start", battleship_start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("quest", quest_status))
    app.add_handler(CommandHandler("fish", fish))
    app.add_handler(CommandHandler("lottery_buy", lottery_buy))
    app.add_handler(CommandHandler("lottery_draw", lottery_draw))
    app.add_handler(CommandHandler("mops_train", mops_train))
    app.add_handler(CommandHandler("top_players", top_players))
    app.add_handler(CommandHandler("bank", bank))
    app.add_handler(CommandHandler("deposit", deposit))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("rank", rank))
    app.add_handler(CommandHandler("ban_player", ban_player))
    app.add_handler(CommandHandler("unban_player", unban_player))
    app.add_handler(CommandHandler("mxp", owner_grant_premium))
    app.add_handler(CommandHandler("mxc", owner_grant_coins))
    app.add_handler(CommandHandler("mxr", owner_secret_report))
    app.add_handler(CommandHandler("eco_help", eco_help))
    app.add_handler(CommandHandler("mops_on", mops_on))
    app.add_handler(CommandHandler("mops_off", mops_off))
    app.add_handler(CommandHandler("mops_status", mops_status))
    app.add_handler(CommandHandler("reports_status", reports_status))
    app.add_handler(CommandHandler("reports_interval", reports_set_interval))
    app.add_handler(CommandHandler("reports_buttons", reports_interval_buttons))
    app.add_handler(CommandHandler("donate", donate_info))
    app.add_handler(CommandHandler("donate_stars", donate_stars))
    app.add_handler(CommandHandler("donate_premium", donate_premium))
    app.add_handler(CommandHandler("donate_note", donate_note))
    app.add_handler(CommandHandler("donate_stats", donate_stats))
    app.add_handler(CommandHandler("channel_guide", channel_guide))
    app.add_handler(CommandHandler("hoshi_help", hoshi_help))
    app.add_handler(CommandHandler("hoshi_tip", hoshi_tip))
    app.add_handler(CommandHandler("hoshi_on", hoshi_on))
    app.add_handler(CommandHandler("hoshi_off", hoshi_off))
    app.add_handler(CommandHandler("hoshi_status", hoshi_status))
    app.add_handler(CommandHandler("hoshi_balance", hoshi_balance))
    app.add_handler(CommandHandler("hoshi_quest", hoshi_quest))
    app.add_handler(CommandHandler("mafia_create", mafia_create))
    app.add_handler(CommandHandler("mafia_join", mafia_join))
    app.add_handler(CommandHandler("mafia_start", mafia_start))
    app.add_handler(CommandHandler("mafia_vote", mafia_vote))
    app.add_handler(CommandHandler("mafia_protect", mafia_protect))
    app.add_handler(CommandHandler("mafia_status", mafia_status))
    app.add_handler(CommandHandler("mafia_stop", mafia_stop))
    app.add_handler(CommandHandler("rps", rps))
    app.add_handler(CommandHandler("quiz", quiz))

    # Мопс-Фармила slash-команды только в ASCII.
    app.add_handler(CommandHandler("mops_help", mops_farmila_help))
    app.add_handler(CommandHandler("help_mops", mops_farmila_help))
    app.add_handler(CommandHandler("ai", ai_help))
    app.add_handler(CommandHandler("ai_help", ai_help))
    app.add_handler(CommandHandler("ask", ai_ask))
    app.add_handler(CommandHandler("solve", ai_solve))
    app.add_handler(CommandHandler("analyze", ai_analyze_photo))
    app.add_handler(CommandHandler("vision", ai_analyze_photo))
    app.add_handler(CommandHandler("photo", ai_analyze_photo))
    app.add_handler(CommandHandler("ocr", ai_analyze_photo))
    app.add_handler(CommandHandler("summary", ai_summary))
    app.add_handler(CommandHandler("translate", ai_translate))
    app.add_handler(CommandHandler("study", study_cmd))
    app.add_handler(CommandHandler("study_help", study_help))
    app.add_handler(CommandHandler("learn", study_cmd))
    app.add_handler(CommandHandler("school", study_cmd))
    app.add_handler(CommandHandler("math", math_cmd))
    app.add_handler(CommandHandler("algebra", math_cmd))
    app.add_handler(CommandHandler("geometry", math_cmd))
    app.add_handler(CommandHandler("biology", biology_cmd))
    app.add_handler(CommandHandler("bio", biology_cmd))
    app.add_handler(CommandHandler("informatics", informatics_cmd))
    app.add_handler(CommandHandler("programming", informatics_cmd))
    app.add_handler(CommandHandler("food", food_cmd))
    app.add_handler(CommandHandler("cook", food_cmd))
    app.add_handler(CommandHandler("pastry", food_cmd))
    app.add_handler(CommandHandler("techcard", foodcard_cmd))
    app.add_handler(CommandHandler("foodcard", foodcard_cmd))
    app.add_handler(CommandHandler("scale_recipe", scale_recipe_cmd))
    app.add_handler(CommandHandler("recipe_scale", scale_recipe_cmd))
    app.add_handler(CommandHandler("proportion", proportion_cmd))
    app.add_handler(CommandHandler("nutrition", nutrition_cmd))
    app.add_handler(CommandHandler("kbju", nutrition_cmd))
    app.add_handler(CommandHandler("calories", nutrition_cmd))
    app.add_handler(CommandHandler("units", unit_cmd))
    app.add_handler(CommandHandler("convert", unit_cmd))
    app.add_handler(CommandHandler("calc", calc_cmd))
    app.add_handler(CommandHandler("roll", roll_cmd))
    app.add_handler(CommandHandler("choose", choose_cmd))
    app.add_handler(CommandHandler("password", password_cmd))
    app.add_handler(CommandHandler("remind", remind_cmd))
    app.add_handler(CommandHandler("site", site_cmd))
    app.add_handler(CommandHandler("commands_site", site_cmd))
    app.add_handler(CommandHandler("note_add", note_add_cmd))
    app.add_handler(CommandHandler("notes", notes_cmd))
    app.add_handler(CommandHandler("note_clear", note_clear_cmd))
    app.add_handler(CommandHandler("truth", truth_cmd))
    app.add_handler(CommandHandler("dare", dare_cmd))
    app.add_handler(CommandHandler("slots", slots_cmd))
    app.add_handler(CommandHandler("coinflip", coinflip_cmd))
    app.add_handler(CommandHandler("rate", rate_cmd))
    app.add_handler(CommandHandler("ship", ship_cmd))
    app.add_handler(CommandHandler("bomb", bomb_cmd))
    app.add_handler(CommandHandler("hello", mops_greet))
    app.add_handler(CommandHandler("bye", mops_farewell))
    app.add_handler(CommandHandler("thanks", mops_thanks))
    app.add_handler(CommandHandler("joke", mops_joke))
    app.add_handler(CommandHandler("quote", mops_quote))
    app.add_handler(CommandHandler("fact", mops_fact))
    app.add_handler(CommandHandler("compliment", mops_compliment))
    app.add_handler(CommandHandler("insult", mops_insult))
    app.add_handler(CommandHandler("ball", mops_8ball))
    app.add_handler(CommandHandler("coin", mops_coin))
    app.add_handler(CommandHandler("d6", mops_dice))
    app.add_handler(CommandHandler("random", mops_random))
    app.add_handler(CommandHandler("horoscope", mops_horoscope))
    app.add_handler(CommandHandler("weather", mops_weather))
    app.add_handler(CommandHandler("q", quote_sticker))
    app.add_handler(CommandHandler("price_watch_add", price_watch_add))
    app.add_handler(CommandHandler("price_watch_list", price_watch_list))
    app.add_handler(CommandHandler("price_watch_remove", price_watch_remove))
    app.add_handler(CommandHandler("price_watch_check", price_watch_check))
    app.add_handler(CommandHandler("price_watch_compare", price_watch_compare))
    app.add_handler(CommandHandler("price_watch_target", price_watch_target))
    app.add_handler(CallbackQueryHandler(reports_interval_callback, pattern=r"^repint:"))
    app.add_handler(CallbackQueryHandler(donate_panel_callback, pattern=r"^dpanel:"))
    app.add_handler(CommandHandler("price_watch_best", price_watch_best))
    app.add_handler(CommandHandler("love", mops_love))
    app.add_handler(CommandHandler("kiss", mops_kiss))
    app.add_handler(CommandHandler("hug", mops_hug))
    mega_aliases = {
        "help": start, "menu": start, "guide": start, "manual": start, "info": start,
        "bal": balance, "wallet": balance, "money": balance, "coins": balance, "cash": balance,
        "store": shop, "market": shop, "mall": shop, "buyitem": buy, "purchase": buy,
        "inv": inventory, "bag": inventory, "items": inventory, "backpack": inventory, "stock": inventory,
        "claim": daily, "bonus": daily, "dailybonus": daily, "dly": daily, "reward": daily,
        "payto": pay, "gift": pay, "tip": pay, "send": pay, "transfer": pay,
        "banking": bank, "bankstatus": bank, "dep": deposit, "wd": withdraw, "take": withdraw,
        "xp": rank, "level": rank, "lvl": rank, "rating": rank, "profilexp": rank,
        "marry": brak, "marriage": brak, "wedding": brak, "divorce": razvod, "split": razvod,
        "myunion": moisoyuz, "marriages": braki, "alliances": soyuzy, "ringx": ring_exchange, "myrings2": my_rings,
        "fight": duel, "battle": duel, "challenge": duel, "acceptduel": accept, "declineduel": decline,
        "pvphelp": duel_help, "pvprank": pvpstats, "pvptop2": pvptop, "shoot": shot, "warstart": war,
        "raid": raid_start, "raidgo": raid_start, "hit": raid_hit, "raidhit": raid_hit, "raidstatus2": raid_status,
        "raidrank": raid_top, "raidinfo": raid_help, "warrank": wartop, "warstat": warstats_cmd, "voyna2": war,
        "words": words_start, "wordgame": words_start, "wordadd": word, "wordstat": words_status, "wordend": words_stop,
        "game": mops_play, "guess": mops_guess, "wheel": polesudes_start, "sea": battleship_start, "bship": battleship_start,
        "quizgame": quiz, "rpsgame": rps, "maf": mafia_create, "mafjoin": mafia_join, "mafstart": mafia_start,
        "mafvote": mafia_vote, "mafstatus": mafia_status, "mafstop": mafia_stop, "mafprotect": mafia_protect,
        "hello": mops_greet, "bye": mops_farewell, "thanks": mops_thanks, "joke": mops_joke, "fact": mops_fact,
        "quote": mops_quote, "compliment": mops_compliment, "insult": mops_insult, "ball": mops_8ball, "coin": mops_coin,
        "dice": mops_dice, "rand": mops_random, "horo": mops_horoscope, "meteo": mops_weather, "wx": mops_weather,
        "hoshi": hoshi_help, "hoshitip": hoshi_tip, "hoshion": hoshi_on, "hoshioff": hoshi_off, "hoshistatus": hoshi_status,
        "hoshibal": hoshi_balance, "hoshiquest": hoshi_quest, "mopson": mops_on, "mopsoff": mops_off, "mopsstate": mops_status,
        "reports": reports_status, "reportstatus": reports_status, "reportint": reports_set_interval, "reportbtn": reports_interval_buttons,
        "priceadd": price_watch_add, "pricelist": price_watch_list, "priceremove": price_watch_remove,
        "pricecheck": price_watch_check, "pricecompare": price_watch_compare, "pricebest": price_watch_best, "pricetarget": price_watch_target,
        "donateinfo": donate_info, "stars": donate_stars, "premium": donate_premium, "donatenote": donate_note,
        "ai": ai_help, "ask": ai_ask, "solve": ai_solve, "analyze": ai_analyze_photo,
        "summary": ai_summary, "translate": ai_translate,
        "math": calc_cmd, "calculator": calc_cmd, "dice2": roll_cmd, "pick": choose_cmd,
        "pass": password_cmd, "pwd": password_cmd, "timer": remind_cmd,
        "website": site_cmd, "cmdsite": site_cmd, "commandsite": site_cmd,
        "note": note_add_cmd, "notelist": notes_cmd, "noteclear": note_clear_cmd,
        "tod": truth_cmd, "casino": slots_cmd, "flip": coinflip_cmd,
        "compat": ship_cmd, "lovecheck": ship_cmd, "boom": bomb_cmd,
    }
    for acmd, afn in mega_aliases.items():
        app.add_handler(CommandHandler(acmd, afn))

    # 100+ безопасных алиасов команд
    extra_aliases = {
        "help": start, "menu": start, "commands": start, "guide": start, "manual": start,
        "bal": balance, "money": balance, "coins": balance, "wallet": balance, "cash": balance,
        "store": shop, "market": shop, "mall": shop, "buyitem": buy, "purchase": buy,
        "inv": inventory, "bag": inventory, "items": inventory, "backpack": inventory, "mystuff": inventory,
        "dly": daily, "bonus": daily, "claim": daily, "claimdaily": daily,
        "payto": pay, "send": pay, "gift": pay, "tip": pay, "transfer": pay,
        "banking": bank, "bankstatus": bank, "dep": deposit, "wd": withdraw, "withdrawal": withdraw,
        "xp": rank, "lvl": rank, "level": rank, "rating": rank, "profilexp": rank,
        "marry": brak, "marriage": brak, "wedding": brak, "split": razvod, "divorce": razvod,
        "marriages": braki, "alliances": soyuzy, "myunion": moisoyuz, "anniv": anniversary,
        "myrings": my_rings, "ringshop": rings, "ringx": ring_exchange, "ringtrade": ring_exchange,
        "fight": duel, "battle": duel, "challenge": duel, "acceptduel": accept, "declineduel": decline,
        "pvphelp": duel_help, "pvprank": pvpstats, "pvpleaders": pvptop, "shoot": shot,
        "raid": raid_start, "raidgo": raid_start, "hit": raid_hit, "raidhit": raid_hit,
        "raidstat": raid_status, "raidrank": raid_top, "raidinfo": raid_help,
        "warstart": war, "warstat": warstats_cmd, "warleaders": wartop,
        "words": words_start, "wordgame": words_start, "wordadd": word, "wordstat": words_status, "wordstop": words_stop,
        "guess": mops_guess, "guessgame": mops_guess, "game": mops_play,
        "sea": battleship_start, "bship": battleship_start, "wheel": polesudes_start,
        "quizgame": quiz, "rpsgame": rps, "maf": mafia_create, "mafjoin": mafia_join,
        "mafstart": mafia_start, "mafvote": mafia_vote, "mafstatus": mafia_status, "mafstop": mafia_stop,
        "hoshi": hoshi_help, "hoshihelp": hoshi_help, "hoshitip": hoshi_tip, "hoshion": hoshi_on, "hoshioff": hoshi_off,
        "hoshistatus": hoshi_status, "hoshibalance": hoshi_balance, "hoshiquest": hoshi_quest,
        "hello": mops_greet, "bye": mops_farewell, "thanks": mops_thanks,
        "joke": mops_joke, "fact": mops_fact, "quote": mops_quote, "compliment": mops_compliment, "insult": mops_insult,
        "ball": mops_8ball, "coin": mops_coin, "dice": mops_dice, "rand": mops_random, "horo": mops_horoscope,
        "weather": mops_weather, "meteo": mops_weather,
        "priceadd": price_watch_add, "pricelist": price_watch_list, "priceremove": price_watch_remove,
        "pricecheck": price_watch_check, "pricecompare": price_watch_compare, "pricebest": price_watch_best,
        "pricetarget": price_watch_target,
        "search": mops_quote, "ping": mops_status, "status": mops_status,
        "reports": reports_status, "reportstatus": reports_status, "reportinterval": reports_set_interval,
        "mopson": mops_on, "mopsoff": mops_off, "mopsstate": mops_status,
        "ai": ai_help, "ask": ai_ask, "solve": ai_solve, "analyze": ai_analyze_photo,
        "summary": ai_summary, "translate": ai_translate,
        "math": calc_cmd, "calculator": calc_cmd, "pick": choose_cmd, "choice": choose_cmd,
        "pass": password_cmd, "pwd": password_cmd, "timer": remind_cmd,
        "website": site_cmd, "cmdsite": site_cmd, "commandsite": site_cmd,
        "note": note_add_cmd, "notelist": notes_cmd, "noteclear": note_clear_cmd,
        "tod": truth_cmd, "casino": slots_cmd, "flip": coinflip_cmd,
        "compat": ship_cmd, "lovecheck": ship_cmd, "boom": bomb_cmd,
    }
    for alias_cmd, handler_fn in extra_aliases.items():
        app.add_handler(CommandHandler(alias_cmd, handler_fn))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, game_input), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sea_shot), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, marriage_ceremony_text), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ru_commands), group=1)
    app.add_handler(MessageHandler(filters.PHOTO, ai_photo_auto), group=1)
    return app


def main() -> None:
    global marriages, duel_stats, war_stats, word_games, raid_states, daily_rewards, inventories, mops_state, profiles, relations, trade_requests, minigames, mod_reports, quests, achievements, lottery, bank_data, xp_data, mod_state, price_watch, donate_log, notes_data
    marriages = load_json(DATA_FILE, {})
    duel_stats = load_json(DUEL_STATS_FILE, {})
    war_stats = load_json(WAR_STATS_FILE, {})
    word_games = load_json(WORD_GAME_FILE, {})
    raid_states = load_json(RAID_FILE, {})
    daily_rewards = load_json(DAILY_FILE, {})
    inventories = load_json(INVENTORY_FILE, {})
    mops_state = load_json(MOPS_FILE, {"chats": {}})
    profiles = load_json(PROFILE_FILE, {})
    relations = load_json(RELATION_FILE, {})
    trade_requests = load_json(TRADE_FILE, {})
    minigames = load_json(MINIGAME_FILE, {})
    mod_reports = load_json(REPORT_FILE, {})
    quests = load_json(QUEST_FILE, {})
    achievements = load_json(ACHIEV_FILE, {})
    lottery = load_json(LOTTERY_FILE, {})
    bank_data = load_json(BANK_FILE, {})
    xp_data = load_json(XP_FILE, {})
    mod_state = load_json(MOD_STATE_FILE, {})
    price_watch = load_json(PRICE_WATCH_FILE, {})
    donate_log = load_json(DONATE_LOG_FILE, {})
    notes_data = load_json(NOTES_FILE, {})

    token = (os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Set BOT_TOKEN (or TELEGRAM_BOT_TOKEN) in environment")

    app = build_application(token)
    if app.job_queue:
        # Проверяем каждый час, но в чат отправляем только 1 раз в сутки.
        app.job_queue.run_repeating(report_job, interval=3600, first=15, name="mops_daily")
        app.job_queue.run_repeating(bank_interest_job, interval=3600, first=30, name="bank_interest")
        app.job_queue.run_repeating(hoshi_scene_job, interval=3600, first=45, name="hoshi_scene")
        app.job_queue.run_repeating(run_price_watch_job, interval=900, first=60, name="price_watch")
    logger.info("Bot is running in polling mode")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


