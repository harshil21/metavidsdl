import asyncio
import re
import tempfile
from os import getenv
from pathlib import Path

import instaloader
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from telegram import Update  #upm package(python-telegram-bot)
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()


TOKEN = getenv("TOKEN", "")  # bot token
DEV_ID = getenv("DEV_ID", "")
USER = getenv("USER", "")
PASSWORD = getenv("PASSWORD", "")
PORT = 80

START_TEXT = (
    "This is a bot which will reply to messages which have an instagram "
    "reel link with a downloaded video."
)

app = FastAPI()


@app.get("/")
async def web_html(request: Request):
    return PlainTextResponse("Hello, meta video bot is running!")


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT)


async def help(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{START_TEXT} Just send a message with a reel link (max one link per message)"
    )


async def process_message(update: Update, _: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message.text
    short_code = re.search(r"(?<=reel\/)[^\/]+", message)
    if not short_code:
        return

    short_code = short_code.group(0)
    with tempfile.TemporaryDirectory() as tmpdirname:
        mp4 = download_video_from_url(short_code, tmpdirname)
        if not mp4:
            await update.message.reply_text("Error downloading video")
            return

        await update.effective_message.reply_video(mp4)


def download_video_from_url(short_code, tmpdirname) -> Path | None:
    loader = instaloader.Instaloader(
        download_video_thumbnails=False,
        dirname_pattern=tmpdirname + "/{target}",
    )
    loader.login(USER, PASSWORD)
    post = instaloader.Post.from_shortcode(loader.context, short_code)
    loader.download_post(post, target="reel")
    for file in (Path(tmpdirname) / "reel").iterdir():
        if file.suffix == ".mp4":  # get the downloaded file by its .mp4 suffix
            return file
    return None


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        DEV_ID, "An error occurred while processing an update: \n" + str(context.error)
    )


async def main() -> None:
    server = uvicorn.Server(
        config=uvicorn.Config(
            f"{Path(__file__).stem}:app",
            port=PORT,
            host="0.0.0.0",
            reload=True,
        )
    )
    tg_app = Application.builder().token(TOKEN).build()

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("help", help))
    tg_app.add_handler(MessageHandler(filters.TEXT, process_message, block=False))
    tg_app.add_error_handler(error_handler)

    async with tg_app:
        await tg_app.updater.start_polling()
        await tg_app.start()
        await server.serve()
        await tg_app.updater.stop()
        await tg_app.stop()


if __name__ == "__main__":
    asyncio.run(main())
