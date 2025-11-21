import os
import threading
import logging
from flask import Flask, jsonify, request, redirect
import discord
from discord.ext import commands
import time  # Botの準備完了を待つために使用します
import json
import asyncio
from ninFlaskV8 import start
import v8path
from asyncEAGM import EAGM

# ログの設定
# デプロイ時に発生するログを明確にするため、基本設定を行います
logging.basicConfig(level=logging.INFO)

# --- 🚨 Flaskアプリの定義 🚨 ---
app = Flask(__name__)

# --- Discord Botの初期設定 ---
# Botのステータス（準備完了かどうか）をチェックするために、Botインスタンスが必要です。
# Botのコアロジック（コマンドなど）は、このコードでは省略しています。
intents = discord.Intents.default()
# KeepAlive機能だけであれば、メッセージやギルドのインテントは必須ではありませんが、
# 正常な動作確認のため含めておきます。
intents.messages = True
intents.guilds = True
intents.message_content = True

# Botインスタンスを作成
bot = commands.Bot(command_prefix="!", intents=intents)

# BotがDiscordへの接続と初期化を完了したかどうかを判定するフラグ
# bot.is_ready()を使いますが、念のため初期値を用意
bot_is_ready = False

@bot.event
async def on_ready():
    """BotがDiscordに接続されたときに実行されます。"""
    global bot_is_ready
    bot_is_ready = True
    logging.info(f"Bot successfully logged in as: {bot.user}")
    # 接続後、Botが実行中であることを示すステータスを設定します
    await bot.change_presence(activity=discord.Game(name="稼働中..."))

# --- KeepAlive/ヘルスチェック エンドポイント ---

@app.route("/")
@app.route("/health")
def home():
    """
    Render環境や外部監視サービス(UptimeRobot)からのメインのヘルスチェックに応答します。
    Botの準備ができていれば200 OK、そうでなければ503 Service Unavailableを返します。
    """
    if bot_is_ready:
        # Botがログインを完了し、稼働準備ができている場合
        return "Bot is running and ready!", 200
    else:
        # Botがまだ起動中、または起動に失敗した場合
        # 503を返すことで、Renderに「起動に時間がかかっている」ことを伝え、
        # すぐに再起動ループに入るのを防ぎます（ただし、最終的には200を返す必要があります）。
        return "Bot is starting up or failed to start...", 503

# --- Discord Bot実行ロジック ---

def start_bot():
    """Discord Botの実行を別スレッドで開始する関数"""
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        # 環境変数がない場合は致命的なエラーとして処理を終了
        logging.error("FATAL ERROR: 'DISCORD_TOKEN' environment variable is not set.")
        return
    else:
        # トークンは機密情報なので、ログには一部のみ表示
        logging.info(f"DISCORD_TOKEN loaded (Preview: {TOKEN[:5]}...)")
        try:
            # Botの実行（これはブロッキングコールです）
            # ここでBotがDiscordに接続し、イベントを待ち受けます
            bot.run(TOKEN)
        except Exception as e:
            logging.error(f"Unexpected error during Bot run: {e}")
            global bot_is_ready
            bot_is_ready = False  # 失敗した場合はフラグをリセット

# --- スラッシュコマンドの定義 ---

@bot.tree.command(name="button", description="認証ボタンの表示")
async def panel_au(interaction: discord.Interaction, ロール: discord.Role, タイトル: str = "こんにちは！", 説明: str = "リンクボタンから登録して認証完了"):
    if not interaction.guild:
        await interaction.response.send_message("DMでは使えません", ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("管理者しか使えません", ephemeral=True)
        return

    button = discord.ui.Button(label="登録リンク", style=discord.ButtonStyle.primary, url=authurl + f"&state={(hex(interaction.guild_id)).upper()[2:]}")
    view = discord.ui.View()
    view.add_item(button)
    await interaction.response.send_message("made by ```.taka.``` thankyou for running!", ephemeral=True)
    json.dump({"role": str(ロール.id)}, open(os.path.join(serverdata_folder_path, f"{interaction.guild.id}.json"), "w"))

    try:
        await interaction.channel.send(view=view, embed=discord.Embed(title=タイトル, description=説明, color=discord.Colour.blue()))
    except Exception as e:
        print(e)

@bot.tree.command(name="call", description='認証したユーザーをサーバーに追加します (管理者用)')
async def call(interaction: discord.Interaction, data_server_id: str = None):
    if not interaction.guild:
        await interaction.response.send_message("DMでは使用できません", ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("このコマンドは管理者のみが使用できます", ephemeral=True)
        return

    try:
        with open(usadata_path, 'r', encoding='utf-8') as f:
            all_user_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        await interaction.response.send_message("登録されているユーザーデータはありません")
        return

    target_user_path = ""
    if not data_server_id:
        target_user_path = os.path.join(serverdata_folder_path, f"{interaction.guild_id}.json")

    elif data_server_id == "all":
        target_user_path = usadata_path

    else:
        target_user_path = os.path.join(serverdata_folder_path, f"{data_server_id}.json")

    try:
        with open(target_user_path, 'r', encoding='utf-8') as f:
            users_to_add = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        await interaction.response.send_message("登録されているユーザーデータはありません")
        return

    await interaction.response.send_message("登録されたユーザーを追加中です...")

    stats = {
        "added": 0,
        "already_joined": 0,
        "invalid_token": 0,
        "rate_limited": 0,
        "max_guilds_or_bad_request": 0,
        "unknown_error": 0
    }

    user_ids_to_process = list(users_to_add.keys())

    for user_id in user_ids_to_process:
        access_token = all_user_data.get(user_id)

        if not access_token:
            if user_id in users_to_add:
