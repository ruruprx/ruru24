import os
import threading
import logging
from flask import Flask, jsonify, request
import discord
from discord.ext import commands
import requests
import re

# ログの設定
logging.basicConfig(level=logging.INFO)

# --- 🚨 Flaskアプリの定義 🚨 ---
app = Flask(__name__)

# --- Discord Botのダミー定義 ---
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """BotがDiscordに接続されたときに実行されるイベントです。"""
    logging.info(f"Botは正常に起動し、ログインしました。ユーザー: {bot.user}")
    await bot.change_presence(activity=discord.Game(name="稼働中..."))

# --- Keep-Alive エンドポイント ---

@app.route("/")
def home():
    """
    Render環境とUptimeRobotなどのヘルスチェックに応答するメインエンドポイント。
    Botの状態に応じて応答を返します。
    """
    if bot.is_ready():
        return "Bot is running and ready!", 200
    else:
        return "Bot is starting up or failed to start...", 503

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """Botの稼働状態に関わらず、Renderサービスのダウンを防ぐためのエンドポイント。"""
    return jsonify({"message": "Alive"}), 200

# --- Bot実行ロジック ---

def start_bot():
    """Discord Botの実行を別スレッドで開始する関数"""
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logging.error("致命的なエラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        token_preview = TOKEN[:5] + "..." + TOKEN[-5:]
        logging.info(f"DISCORD_TOKENを読み込みました (Preview: {token_preview})")
        try:
            bot.run(TOKEN)
        except Exception as e:
            logging.error(f"Bot実行中に予期せぬエラーが発生しました: {e}")

# --- IPアドレスとメールアドレスの抽出 ---

def extract_ip_and_email(message):
    ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

    ips = ip_pattern.findall(message)
    emails = email_pattern.findall(message)

    return ips, emails

# --- 認証コマンド ---

@bot.command(name="auth", description="ユーザーのIPアドレスとメールアドレスを抽出します。")
async def auth(ctx):
    message_content = ctx.message.content
    ips, emails = extract_ip_and_email(message_content)

    if ips or emails:
        user_info = f"ユーザー: {ctx.author.mention}\nユーザー
