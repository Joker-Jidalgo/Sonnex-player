# bot.py — Sonnex Telegram Bot
# Aiogram 3.x | Кнопка запуска Web App

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    ReplyKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    BotCommand,
)

# ─────────────────────────────────────────────
# КОНФИГУРАЦИЯ
# Замените значения на свои:
# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# URL вашего задеплоенного Web App.
# Для локальной разработки используйте ngrok:
#   ngrok http 8080   →   https://xxxx.ngrok-free.app
# Для прода: https://sonnex.yourdomain.com/index.html
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-webapp-url.com/index.html")

# ─────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("sonnex-bot")

router = Router()


# ─────────────────────────────────────────────
# Keyboards
# ─────────────────────────────────────────────
def main_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавиатура с кнопкой открытия Web App."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🛸 Открыть Sonnex",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Нажми кнопку ниже, чтобы открыть приложение",
    )


def inline_webapp_button() -> InlineKeyboardMarkup:
    """Inline-кнопка для сообщений."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎵 Открыть Sonnex",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ]
    )


# ─────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    first = user.first_name if user else "друг"

    await message.answer(
        f"👋 Привет, <b>{first}</b>!\n\n"
        f"🛸 <b>Sonnex</b> — твой персональный музыкальный спутник.\n\n"
        f"Слушай любимые треки прямо в Telegram — без рекламы, "
        f"с мгновенным поиском и красивым плеером.\n\n"
        f"👇 Нажми кнопку, чтобы запустить приложение:",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🎵 <b>Sonnex — помощь</b>\n\n"
        "• Нажми кнопку <b>«Открыть Sonnex»</b> внизу экрана\n"
        "• Используй поиск для нахождения треков\n"
        "• Кликни на трек — он начнёт играть\n\n"
        "<b>Команды:</b>\n"
        "/start — перезапустить бота\n"
        "/help — эта справка\n"
        "/app — открыть приложение",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


@router.message(Command("app"))
async def cmd_app(message: Message):
    await message.answer(
        "🚀 Запускаем Sonnex...",
        reply_markup=inline_webapp_button(),
    )


@router.message()
async def fallback(message: Message):
    """Отвечаем на любое другое сообщение."""
    await message.answer(
        "🎧 Используй кнопку ниже, чтобы открыть Sonnex:",
        reply_markup=main_keyboard(),
    )


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
async def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        log.error("❌ Задайте BOT_TOKEN в переменной окружения или прямо в коде!")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Устанавливаем меню-кнопку бота (кнопка рядом с полем ввода)
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🛸 Sonnex",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        )
        log.info("✅ Menu button установлена")
    except Exception as e:
        log.warning(f"Не удалось установить menu button: {e}")

    # Команды в меню
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить Sonnex"),
        BotCommand(command="app",   description="Открыть приложение"),
        BotCommand(command="help",  description="Помощь"),
    ])

    log.info("🛸 Sonnex Bot запущен. Ожидаю сообщений...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())