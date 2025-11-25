import os
import threading
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask, jsonify
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)

# --- 🚨 KeepAlive用: Flaskアプリの定義 ---
app = Flask(__name__)

# --- Discord Bot Setup ---
# Webhook管理とメッセージ内容の意図が必要です
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True 

# スラッシュコマンドメインなので、プレフィックスはシンプルに
bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの設定
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    # 誰でも使えるようにするため、ALLOWED_USER_IDの設定は不要
    if not DISCORD_BOT_TOKEN:
        logging.error("致命的なエラー: 'DISCORD_BOT_TOKEN' が設定されていません。")
except Exception:
    DISCORD_BOT_TOKEN = None

# ----------------------------------------------------
# --- Discord イベント ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="/fakemessage")
    )
    logging.info(f"Bot {bot.user} is ready!")
    
    # スラッシュコマンドの同期
    try:
        synced = await bot.tree.sync()
        logging.info(f"スラッシュコマンドを同期しました。登録数: {len(synced)} 件")
    except Exception as e:
        logging.error(f"スラッシュコマンドの同期中にエラーが発生しました: {e}")

@bot.event
async def on_message(message):
    """メッセージイベントはスラッシュコマンド実行に影響を与えないよう、最低限の処理のみ"""
    if message.author.bot:
        return
    await bot.process_commands(message)

# ----------------------------------------------------
# --- スラッシュコマンドの定義 ---
# ----------------------------------------------------

@bot.tree.command(name="fakemessage", description="指定ユーザーになりすましてメッセージを送信します (Webhookを使用)。")
@app_commands.describe(user="なりすますユーザー", content="送信するメッセージ内容")
# 権限チェックはDiscord標準のWebhook管理権限に依存します
@commands.has_permissions(manage_webhooks=True) 
async def fakemessage_slash(interaction: discord.Interaction, user: discord.Member, content: str):
    
    # 🚨 警告: このコマンドは、BotがWebhookを作成・管理できるチャンネルで、
    # 実行者が「Webhookの管理」権限を持っている場合に実行可能です。
    
    await interaction.response.defer(ephemeral=True)
    channel = interaction.channel
    webhook = None

    try:
        # 1. 既存のWebhookを探す
        webhooks = await channel.webhooks()
        for wh in webhooks:
            if wh.name == "Bot Fake Sender":
                webhook = wh
                break
        
        # 2. 既存のWebhookがなければ作成する
        if webhook is None:
            # Bot自体にWebhook作成権限が必要です
            webhook = await channel.create_webhook(name="Bot Fake Sender")

        # 3. Webhook経由でメッセージを送信
        await webhook.send(
            content=content,
            username=user.display_name,
            avatar_url=user.display_avatar.url
        )
        
        # 4. 実行者に応答
        await interaction.followup.send(f"✅ **{user.display_name}** になりすましたメッセージを送信しました。", ephemeral=True)
        
    except discord.Forbidden:
        await interaction.followup.send("❌ Botまたは実行者にWebhookの管理/メッセージ送信権限がありません。", ephemeral=True)
    except Exception as e:
        logging.error(f"Fakemessage実行中にエラーが発生: {e}")
        await interaction.followup.send("予期せぬエラーが発生し、メッセージを送信できませんでした。", ephemeral=True)

# ----------------------------------------------------
# --- Render/Uptime Robot対応: KeepAlive Server ---
# ----------------------------------------------------

def start_bot():
    """Discord Botの実行を別スレッドで開始する"""
    if DISCORD_BOT_TOKEN:
        logging.info("Discord Botを起動中...")
        try:
            bot.run(DISCORD_BOT_TOKEN)
        except discord.errors.LoginFailure:
            logging.error("ログイン失敗: Discord Bot Tokenが無効です。")
        except Exception as e:
            logging.error(f"Bot実行中に予期せぬエラーが発生しました: {e}")
    else:
        logging.error("Botの実行をスキップ: トークンが設定されていません。")


# Flaskサーバーが起動されると同時にBotを別スレッドで起動する
bot_thread = threading.Thread(target=start_bot)
bot_thread.start()

@app.route("/")
def home():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    if bot.is_ready():
        return "Bot is running and ready!"
    else:
        return "Bot is starting up or failed to start...", 503

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント (より明示的なエンドポイント)"""
    return jsonify({"message": "Alive"}), 200

