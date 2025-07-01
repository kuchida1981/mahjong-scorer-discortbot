import os

import discord
from discord.ext import commands

from app.discord_bot.commands import setup as setup_commands

# 環境変数からDiscordボットのトークンを取得
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# プレフィックスなしでスラッシュコマンドを使用
intents = discord.Intents.default()
intents.message_content = True  # メッセージの内容を読み取るためのインテントを有効にする
intents.members = True  # メンバー情報を取得するためのインテントを有効にする
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents)


# 起動時の処理
@bot.event
async def on_ready():  # pragma: no cover
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")  # pragma: no cover
    print("------")  # pragma: no cover
    # コマンドをセットアップ
    setup_commands(bot)
    # 起動時にスラッシュコマンドを同期
    await bot.tree.sync()  # pragma: no cover
    print("Slash commands synced.")  # pragma: no cover


# ボットの実行
if DISCORD_BOT_TOKEN:  # pragma: no cover
    bot.run(DISCORD_BOT_TOKEN)  # pragma: no cover
else:  # pragma: no cover
    print("DISCORD_BOT_TOKEN 環境変数が設定されていません。")  # pragma: no cover
