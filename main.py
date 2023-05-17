from os import getenv
from typing import Any, Dict, Union

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, BotCommand
from aiogram.utils.token import TokenValidationError, validate_token
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    TokenBasedRequestHandler,
    setup_application,
)
from aiohttp.web import run_app
from aiohttp.web_app import Application
from aiohttp.web_request import Request
from aiohttp.web_response import json_response
from dotenv import load_dotenv

from sub_bot import form_router

load_dotenv()

main_router = Router()

BASE_URL = getenv("BASE_URL")
MAIN_BOT_TOKEN = getenv("MAIN_TOKEN")

WEB_SERVER_HOST = "localhost"
WEB_SERVER_PORT = 8000
MAIN_BOT_PATH = "/webhook/main"
OTHER_BOTS_PATH = "/webhook/bot/{bot_token}"

OTHER_BOTS_URL = f"{BASE_URL}{OTHER_BOTS_PATH}"


def is_bot_token(value: str) -> Union[bool, Dict[str, Any]]:
    try:
        validate_token(value)
    except TokenValidationError:
        return False
    return True


@main_router.message(Command(commands=["add"], magic=F.args.func(is_bot_token)))
async def command_add_bot(message: Message, command: CommandObject, bot: Bot) -> Any:
    new_bot = Bot(token=command.args, session=bot.session)
    try:
        bot_user = await new_bot.get_me()
    except TelegramUnauthorizedError:
        return message.answer("Invalid token")
    await new_bot.delete_webhook(drop_pending_updates=True)
    await new_bot.set_webhook(OTHER_BOTS_URL.format(bot_token=command.args))
    commands = [BotCommand(command="help", description="Yordam kerakmi?")]
    await new_bot.set_my_commands(commands)

    return await message.answer(f"Bot @{bot_user.username} successful added")


@main_router.message()
async def welcome_bot(message: Message):
    return await message.answer(message.text)


async def on_startup(dispatcher: Dispatcher, bot: Bot):
    await bot.set_webhook(f"{BASE_URL}{MAIN_BOT_PATH}")


async def check_data_handler(request: Request):
    bot: Bot = request.app["bot"]
    data = await request.json()
    new_token = data['token']
    new_bot = Bot(token=new_token, session=bot.session)
    try:
        bot_user = await new_bot.get_me()
    except TelegramUnauthorizedError:
        return json_response({'error': "invalid token"}, status=400)
    await new_bot.delete_webhook(drop_pending_updates=True)

    await new_bot.set_webhook(OTHER_BOTS_URL.format(bot_token=new_token))
    commands = [BotCommand(command="help", description="Yordam kerakmi?")]
    await new_bot.set_my_commands(commands)

    return json_response({'msg': f'Bot @{bot_user.username} successful added'}, status=400)


def main():
    session = AiohttpSession()
    bot_settings = {"session": session, "parse_mode": "HTML"}
    bot = Bot(MAIN_BOT_TOKEN, **bot_settings)

    main_dispatcher = Dispatcher()
    main_dispatcher.include_router(main_router)
    main_dispatcher.startup.register(on_startup)

    multibot_dispatcher = Dispatcher()
    multibot_dispatcher.include_router(form_router)

    app = Application()
    app["bot"] = bot
    app.router.add_post("/add", check_data_handler)
    SimpleRequestHandler(dispatcher=main_dispatcher, bot=bot).register(app, path=MAIN_BOT_PATH)
    TokenBasedRequestHandler(
        dispatcher=multibot_dispatcher,
        bot_settings=bot_settings,
    ).register(app, path=OTHER_BOTS_PATH)

    setup_application(app, main_dispatcher, bot=bot)
    setup_application(app, multibot_dispatcher)

    run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


if __name__ == "__main__":
    main()
