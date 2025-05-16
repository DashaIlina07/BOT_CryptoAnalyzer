import os
import asyncio
import requests
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile

from dotenv import load_dotenv, find_dotenv

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

# загрузка токена из .env
load_dotenv(find_dotenv())
bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher()

# путь к файлу логов
LOG_FILE = "resources/command_logs.txt"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot_database.db")
engine = create_engine(DATABASE_URL)
Base = declarative_base()
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    language = Column(String(2), default='ru')
    is_active = Column(Boolean, default=True)
    first_seen = Column(DateTime, default=func.now())
    last_activity = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"


Base.metadata.create_all(engine)


# функция для получения/создания пользователя
async def get_or_create_user(user_id, username=None, full_name=None):
    session = Session()
    try:
        user = session.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            user = User(
                telegram_id=user_id,
                username=username,
                full_name=full_name
            )
            session.add(user)
            session.commit()
        return user
    finally:
        session.close()


# функция для обновления времени последней активности
async def update_user_activity(user_id):
    session = Session()
    try:
        user = session.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.last_activity = func.now()
            session.commit()
    finally:
        session.close()


# функция для логирования команд
async def log_command(message: types.Message, command: str):
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    full_name = message.from_user.full_name or "No name"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # обновление информации о пользователе в бд
    await get_or_create_user(user_id, username, full_name)
    await update_user_activity(user_id)

    log_entry = f"[{timestamp}] User ID: {user_id}, Username: @{username}, Name: {full_name}, Command: {command}\n"

    # создание директории для лога
    os.makedirs(os.path.dirname(LOG_FILE) if os.path.dirname(LOG_FILE) else '.', exist_ok=True)

    # запись информации в файл
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)


# популярные токены
popular_tokens = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'SOL': 'solana',
    'BNB': 'binancecoin',
    'DOGE': 'dogecoin'
}

# словари с переводами для интерфейса бота
translations = {
    'ru': {
        "welcome": "👋 Привет! Я крипто-бот. Помогу узнать курсы, построить графики и рассчитать позиции.\n\n"
                   "Нажми кнопку ниже или введи /menu для списка команд.",
        "open_menu": "📋 Открыть меню",
        "menu_title": "📋 Меню команд:",
        "menu_crypto": "/crypto — курсы самых популярных криптовалют.",
        "menu_calc": "/calc <цена_входа> <плечо> <баланс> — калькулятор позиции.",
        "menu_chart": "/chart — выбор коина и его график.",
        "menu_faq": "/faq — часто задаваемые вопросы и ответы на них.",
        "menu_help": "/help — помощь",
        "menu_language": "/language — изменить язык интерфейса.",
        "crypto_prices": "💱 Актуальные курсы:",
        "error": "Ошибка: {}",
        "calc_usage": "Используй: /calc <вход> <плечо> <баланс>",
        "position_size": "📈 Размер позиции: {}",
        "liquidation_price": "⚠️ Ликвидация: {:.2f}",
        "faq_select": "❓ Выберите вопрос:",
        "question_not_found": "Вопрос не найден.",
        "about_bot": "ℹ️ <b>О боте</b>\n"
                     "Я — крипто-бот, помогаю следить за курсами популярных токенов, строить графики и рассчитывать позиции.",
        "why_bot": "🚀 <b>Зачем нужен бот?</b>\n"
                   "- Быстро узнать текущий курс BTC, ETH, SOL и др.\n"
                   "- Построить 7-дневный график цены.\n"
                   "- Рассчитать размер позиции и цену ликвидации с любым плечом.",
        "calc_help": "🧮 <b>Как работает /calc?</b>\n"
                     "Отправьте <code>/calc &lt;цена_входа&gt; &lt;плечо&gt; &lt;баланс&gt;</code>:\n"
                     "• <b>цена_входа</b> — цена, по которой вы вошли (например, 20000)\n"
                     "• <b>плечо</b> — желаемое кредитное плечо (например, 10)\n"
                     "• <b>баланс</b> — ваш депозит в USD (например, 100)\n"
                     "Бот вернёт размер позиции и цену ликвидации.",
        "select_token": "Выбери токен для графика:",
        "chart_caption": "📈 График {} за 7 дней",
        "description": "🧾 Описание:",
        "chart_error": "Ошибка при получении данных: {}",
        "hello_response": "И тебе привет!",
        "bye_response": "До встречи!",
        "unknown_command": "Не понял 😅 Напиши /menu для списка команд.",
        "select_language": "🌐 Выберите язык интерфейса:",
        "language_ru": "🇷🇺 Русский",
        "language_en": "🇬🇧 English",
        "language_changed": "🇷🇺 Язык интерфейса изменен на русский"
    },
    'en': {
        "welcome": "👋 Hello! I'm a crypto bot. I'll help you check rates, build charts and calculate positions.\n\n"
                   "Press the button below or type /menu for a list of commands.",
        "open_menu": "📋 Open menu",
        "menu_title": "📋 Command menu:",
        "menu_crypto": "/crypto — rates of the most popular cryptocurrencies.",
        "menu_calc": "/calc <entry_price> <leverage> <balance> — position calculator.",
        "menu_chart": "/chart — select a coin and see its chart.",
        "menu_faq": "/faq — frequently asked questions and answers.",
        "menu_help": "/help — help",
        "menu_language": "/language — change interface language.",
        "crypto_prices": "💱 Current rates:",
        "error": "Error: {}",
        "calc_usage": "Usage: /calc <entry> <leverage> <balance>",
        "position_size": "📈 Position size: {}",
        "liquidation_price": "⚠️ Liquidation: {:.2f}",
        "faq_select": "❓ Select a question:",
        "question_not_found": "Question not found.",
        "about_bot": "ℹ️ <b>About the bot</b>\n"
                     "I'm a crypto bot, helping you track popular token rates, build charts and calculate positions.",
        "why_bot": "🚀 <b>Why use this bot?</b>\n"
                   "- Quickly check current BTC, ETH, SOL rates and more.\n"
                   "- Build a 7-day price chart.\n"
                   "- Calculate position size and liquidation price with any leverage.",
        "calc_help": "🧮 <b>How does /calc work?</b>\n"
                     "Send <code>/calc &lt;entry_price&gt; &lt;leverage&gt; &lt;balance&gt;</code>:\n"
                     "• <b>entry_price</b> — price at which you entered (e.g., 20000)\n"
                     "• <b>leverage</b> — desired leverage (e.g., 10)\n"
                     "• <b>balance</b> — your deposit in USD (e.g., 100)\n"
                     "The bot will return position size and liquidation price.",
        "select_token": "Select a token for the chart:",
        "chart_caption": "📈 {} chart for 7 days",
        "description": "🧾 Description:",
        "chart_error": "Error getting data: {}",
        "hello_response": "Hello to you too!",
        "bye_response": "See you later!",
        "unknown_command": "I don't understand 😅 Type /menu for a list of commands.",
        "select_language": "🌐 Select interface language:",
        "language_ru": "🇷🇺 Русский",
        "language_en": "🇬🇧 English",
        "language_changed": "🇬🇧 Interface language changed to English"
    }
}

# переводы для команды FAQ
faq_data = {
    'ru': {
        "q1": {
            "question": "Что такое криптовалюта?",
            "answer": "Криптовалюта — это разновидность цифровой валюты, не имеющей физического воплощения и единого центра, который бы ее контролировал. Работает в так называемом «блокчейне» или цепочке блоков с информацией."
        },
        "q2": {
            "question": "Что такое блокчейн?",
            "answer": "Блокчейн (от англ. block — «блок, модуль» и chain — «цепочка») — это непрерывная цепочка блоков с данными. Каждый из блоков содержит информацию и ссылку на предыдущий. Это помогает, например, проследить историю покупок и продаж актива."
        },
        "q3": {
            "question": "Что такое майнинг?",
            "answer": "Майнинг — это процесс добычи криптовалют с помощью вычислительных устройств, решающих задачи для подтверждения транзакций. Майнеры получают награду за добавление блоков в блокчейн, что обеспечивает безопасность сети."
        },
        "q4": {
            "question": "Что такое токены и их типы?",
            "answer": "Токен — цифровой актив на основе блокчейна. В отличие от коина, токен не имеет собственного блокчейна. Типы токенов: альткоин, стейблкоин, токен управления, невзаимозаменяемый токен (NFT)."
        }
    },
    'en': {
        "q1": {
            "question": "What is cryptocurrency?",
            "answer": "Cryptocurrency is a type of digital currency that has no physical form and no single controlling center. It operates in a so-called 'blockchain' or chain of blocks with information."
        },
        "q2": {
            "question": "What is blockchain?",
            "answer": "Blockchain is a continuous chain of data blocks. Each block contains information and a reference to the previous one. This helps, for example, to trace the history of purchases and sales of an asset."
        },
        "q3": {
            "question": "What is mining?",
            "answer": "Mining is the process of obtaining cryptocurrencies using computing devices that solve problems to confirm transactions. Miners receive rewards for adding blocks to the blockchain, which ensures network security."
        },
        "q4": {
            "question": "What are tokens and their types?",
            "answer": "A token is a blockchain-based digital asset. Unlike a coin, a token does not have its own blockchain. Token types: altcoin, stablecoin, governance token, non-fungible token (NFT)."
        }
    }
}


# получение языка пользователя из бд
async def get_user_language(user_id):
    session = Session()
    try:
        user = session.query(User).filter(User.telegram_id == user_id).first()
        if user:
            return user.language
        return 'ru'  # дефолтный язык
    finally:
        session.close()


# установка языка пользователя в бд
async def set_user_language(user_id, language):
    session = Session()
    try:
        user = session.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.language = language
            session.commit()
    finally:
        session.close()


# Получение курсов криптовалют
def get_crypto_price(symbols=('bitcoin', 'ethereum', 'tether'), currency='usd'):
    url = "https://api.coingecko.com/api/v3/simple/price"
    response = requests.get(url, params={'ids': ','.join(symbols), 'vs_currencies': currency})
    data = response.json()

    result = []
    for symbol in symbols:
        price = data.get(symbol, {}).get(currency)
        if price:
            result.append(f"{symbol.upper()}: {price} {currency.upper()}")
    return '\n'.join(result)


# Калькулятор позиции и ликвидации
def calculate_position(entry_price: float, leverage: float, balance: float):
    position_size = balance * leverage
    liquidation_price = entry_price - (entry_price * (1 / leverage)) if leverage != 0 else 0
    return {
        "position_size": position_size,
        "liquidation_price": liquidation_price
    }


# История цены и график
def get_price_history(symbol='bitcoin', currency='usd', days=7):
    url = f'https://api.coingecko.com/api/v3/coins/{symbol}/market_chart'
    params = {'vs_currency': currency, 'days': days}
    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()
    return [(x[0], x[1]) for x in data['prices']]


def generate_price_chart(symbol='bitcoin', currency='usd', lang='ru'):
    history = get_price_history(symbol, currency)
    timestamps = [datetime.fromtimestamp(ts / 1000).strftime('%b %d') for ts, _ in history]
    prices = [price for _, price in history]

    plt.figure(figsize=(8, 4))
    plt.plot(timestamps, prices, label=f"{symbol.upper()}", color='blue')
    plt.xticks(rotation=45)

    # заголовок графика на основе выбранного языка
    title = f"{symbol.upper()} Цена за 7 дней" if lang == 'ru' else f"{symbol.upper()} Price for 7 days"
    x_label = "Дата" if lang == 'ru' else "Date"
    y_label = f"Цена в {currency.upper()}" if lang == 'ru' else f"Price in {currency.upper()}"

    plt.title(title)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.tight_layout()
    plt.grid(True)
    plt.legend()

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf


# Получение описания токена
def get_token_description(symbol='bitcoin', lang='ru'):
    url = f"https://api.coingecko.com/api/v3/coins/{symbol}"
    res = requests.get(url, params={"localization": "true"})
    res.raise_for_status()
    data = res.json()

    desc = data.get("description", {}).get(lang) or data.get("description", {}).get("en", "")
    return desc.strip()[
           :1000] + "..." if desc else "Описание недоступно." if lang == 'ru' else "Description not available."


# Хендлеры

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await log_command(message, "/start")
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    full_name = message.from_user.full_name or "No name"

    # создаем или получаем запись пользователя
    await get_or_create_user(user_id, username, full_name)

    lang = await get_user_language(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translations[lang]["open_menu"], callback_data="open_menu")]
        ]
    )
    await message.answer(
        translations[lang]["welcome"],
        reply_markup=keyboard
    )


@dp.message(Command("menu"))
async def menu_cmd(message: types.Message):
    await log_command(message, "/menu")
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    await message.answer(
        f"{translations[lang]['menu_title']}\n"
        f"{translations[lang]['menu_crypto']}\n"
        f"{translations[lang]['menu_calc']}\n"
        f"{translations[lang]['menu_chart']}\n"
        f"{translations[lang]['menu_faq']}\n"
        f"{translations[lang]['menu_help']}\n"
        f"{translations[lang]['menu_language']}"
    )


@dp.message(Command("crypto"))
async def crypto_cmd(message: types.Message):
    await log_command(message, message.text)  # логируем полную команду с аргументами
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    try:
        parts = message.text.split()
        tokens = [t.lower() for t in parts[1:]] if len(parts) > 1 else ['bitcoin', 'ethereum', 'tether']
        prices = get_crypto_price(tokens)
        await message.answer(f"{translations[lang]['crypto_prices']}\n{prices}")
    except Exception as e:
        await message.answer(translations[lang]['error'].format(str(e)))


@dp.message(Command("calc"))
async def calc_cmd(message: types.Message):
    await log_command(message, message.text)
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    try:
        parts = message.text.split()
        if len(parts) != 4:
            raise ValueError(translations[lang]['calc_usage'])
        entry = float(parts[1])
        leverage = float(parts[2])
        balance = float(parts[3])
        result = calculate_position(entry, leverage, balance)
        await message.answer(
            f"{translations[lang]['position_size'].format(result['position_size'])}\n"
            f"{translations[lang]['liquidation_price'].format(result['liquidation_price'])}"
        )
    except Exception as e:
        await message.answer(translations[lang]['error'].format(str(e)))


@dp.message(Command("faq"))
async def faq_cmd(message: types.Message):
    await log_command(message, "/faq")
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    buttons = [
        [InlineKeyboardButton(text=faq_data[lang][qid]["question"], callback_data=f"faq_{qid}")]
        for qid in faq_data[lang]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(translations[lang]["faq_select"], reply_markup=keyboard)


@dp.callback_query(lambda c: c.data.startswith("faq_"))
async def answer_faq(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "No username"
    full_name = callback.from_user.full_name or "No name"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Обновление активности пользователя
    await update_user_activity(user_id)

    lang = await get_user_language(user_id)

    # логируем callback-запросы
    log_entry = f"[{timestamp}] User ID: {user_id}, Username: @{username}, Name: {full_name}, Callback: {callback.data}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)

    qid = callback.data.split("_", 1)[1]
    faq = faq_data[lang].get(qid)
    if faq:
        await callback.message.answer(f"📌 *{faq['question']}*\n\n{faq['answer']}", parse_mode="Markdown")
    else:
        await callback.message.answer(translations[lang]["question_not_found"])
    await callback.answer()


@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await log_command(message, "/help")
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translations[lang]["open_menu"], callback_data="open_menu")]
        ]
    )

    await message.answer(
        f"{translations[lang]['about_bot']}\n\n"
        f"{translations[lang]['why_bot']}\n\n"
        f"{translations[lang]['calc_help']}",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@dp.callback_query(lambda c: c.data == "open_menu")
async def open_menu_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "No username"
    full_name = callback.from_user.full_name or "No name"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Обновление активности пользователя
    await update_user_activity(user_id)

    # логируем callback-запросы
    log_entry = f"[{timestamp}] User ID: {user_id}, Username: @{username}, Name: {full_name}, Callback: open_menu\n"
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)

    await menu_cmd(callback.message)
    await callback.answer()


@dp.message(Command("chart"))
async def chart_menu(message: types.Message):
    await log_command(message, "/chart")
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"chart_{token}")]
        for name, token in popular_tokens.items()
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(translations[lang]["select_token"], reply_markup=keyboard)


@dp.callback_query(lambda c: c.data.startswith("chart_"))
async def send_chart(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "No username"
    full_name = callback.from_user.full_name or "No name"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # обновление активности пользователя
    await update_user_activity(user_id)

    lang = await get_user_language(user_id)

    # логирование callback-запросов с выбором графика
    log_entry = f"[{timestamp}] User ID: {user_id}, Username: @{username}, Name: {full_name}, Callback: {callback.data}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)

    token = callback.data.split("_", 1)[1]
    try:
        chart_buf = generate_price_chart(token, lang=lang)
        desc = get_token_description(token, lang)

        photo = BufferedInputFile(chart_buf.read(), filename=f"{token}.png")
        await callback.message.answer_photo(
            photo=photo,
            caption=translations[lang]["chart_caption"].format(token.upper())
        )
        await callback.message.answer(f"{translations[lang]['description']}\n{desc}")
        await callback.answer()
    except Exception as e:
        await callback.message.answer(translations[lang]["chart_error"].format(str(e)))


@dp.message(Command("language"))
async def language_cmd(message: types.Message):
    await log_command(message, "/language")
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translations[lang]["language_ru"], callback_data="lang_ru")],
            [InlineKeyboardButton(text=translations[lang]["language_en"], callback_data="lang_en")]
        ]
    )
    await message.answer(translations[lang]["select_language"], reply_markup=keyboard)


@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "No username"
    full_name = callback.from_user.full_name or "No name"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # получаем выбранный язык
    selected_lang = callback.data.split("_", 1)[1]

    # сохранение предпочтений пользователя в бд
    await set_user_language(user_id, selected_lang)
    await update_user_activity(user_id)

    # логируем выбор языка
    log_entry = f"[{timestamp}] User ID: {user_id}, Username: @{username}, Name: {full_name}, Set language: {selected_lang}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)

    # подтверждение на выбранном языке
    await callback.message.answer(translations[selected_lang]["language_changed"])
    await callback.answer()


@dp.message()
async def echo_handler(message: types.Message):
    # логируем обычные сообщения
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    full_name = message.from_user.full_name or "No name"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # обновление информации о пользователе в бд
    await get_or_create_user(user_id, username, full_name)
    await update_user_activity(user_id)

    lang = await get_user_language(user_id)

    log_entry = f"[{timestamp}] User ID: {user_id}, Username: @{username}, Name: {full_name}, Message: {message.text}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)

    text = message.text.lower()
    if text in ['привет', 'приветик', 'hello', 'hi', 'хэлоу']:
        await message.answer(translations[lang]["hello_response"])
    elif text in ['пока', 'до свидания', 'bye', 'пакеда']:
        await message.answer(translations[lang]["bye_response"])
    else:
        await message.answer(translations[lang]["unknown_command"])


async def main():
    log_dir = os.path.dirname(LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)
    # создание файла логов, если его неь
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("Telegram Bot Command Log \n\n")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())