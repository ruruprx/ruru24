import os
import threading
import logging
import time
from flask import Flask
from discord.ext import commands, tasks
import discord
import asyncio
import random

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask アプリケーションと Discord Bot の初期化 ---
app = Flask(__name__)

# Intents の設定 (KeepAliveに必須ではありませんが、Botの接続に必要)
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Botの準備完了フラグ
bot_is_ready = False

# 荒らしメッセージのリスト
spam_messages = [
    "これは荒らしメッセージです!",
    "サーバーを混乱させます!",
    "大量のメッセージを送信します!",
    "止められないでしょう?",
    "楽しんでください!",
    "荒らしBotがやってきました!",
    "これはテストメッセージです。",
    "荒らしBotは強力です!",
    "サーバーを混乱させるために作成されました。",
    "このメッセージは荒らしBotからです。"
]

# 荒らしタスク
@tasks.loop(seconds=1)
async def spam_channel(channel: discord.TextChannel):
    if channel is not None:
        message = random.choice(spam_messages)
        try:
            await channel.send(message)
        except discord.errors.Forbidden:
            logging.warning(f"送信権限がないため、{channel.name}にメッセージを送信できませんでした。")
        except Exception as e:
            logging.error(f"メッセージ送信中にエラーが発生しました: {e}")

# --- Discord イベントハンドラ ---
@bot.event
async def on_ready():
    """BotがDiscordに正常に接続・ログインしたときに実行されます。"""
    global bot_is_ready
    bot_is_ready = True
    logging.info(f"Discord Bot ログイン完了。ユーザー: {bot.user}")
    await bot.change_presence(activity=discord.Game(name="稼働中 | !help"))

@bot.event
async def on_connect():
    """BotがDiscord APIに接続したときに実行されます。"""
    logging.info("Discord Bot 接続中...")

# --- KeepAlive/ヘルスチェック エンドポイント ---

@app.route("/")
def health_check():
    """
    Render/UptimeRobotからのヘルスチェックに応答します。
    Botが起動済み(bot_is_ready=True)なら 200 OK、そうでなければ 503 Service Unavailable を返します。
    """
    if bot_is_ready:
        logging.info("KeepAlive Check: OK (200)")
        return "Bot is running and ready!", 200
    else:
        logging.warning("KeepAlive Check: Not Ready (503)")
        return "Bot is starting up...", 503

# --- Discord Bot 実行ロジック ---

def start_bot():
    """Botの実行（ブロッキング処理）を開始します。"""
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logging.error("FATAL ERROR: DISCORD_TOKEN 環境変数が設定されていません。")
        return

    logging.info(f"DISCORD_TOKEN を読み込みました (Preview: {TOKEN[:5]}...)")
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        logging.error("致命的なエラー: DISCORD_TOKEN が不正です。トークンを確認してください。")
        global bot_is_ready
        bot_is_ready = False
    except Exception as e:
        logging.error(f"Bot 実行中に予期せぬエラーが発生しました: {e}")
        global bot_is_ready
        bot_is_ready = False

# --- 荒らしコマンド ---
@bot.command()
async def nuke(ctx, duration: int = 60):
    """指定された期間（秒）荒らしメッセージを送信します。"""
    if ctx.author.guild_permissions.administrator:
        spam_channel.start(ctx.channel, duration)
        await ctx.send(f"{ctx.channel.mention}で荒らしを開始しました。{duration}秒間続けます。")
        await asyncio.sleep(duration)
        spam_channel.stop()
        await ctx.send("荒らしを終了しました。")
    else:
        await ctx.send("このコマンドは管理者のみが使用できます。")

# --- メイン実行 (WebサーバーとBotの並行処理) ---

if __name__ == '__main__':
    # 1. Botの実行をバックグラウンドスレッドで開始
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()

    # 2. Flask Webサーバーを起動
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
