import os
import threading
import discord
from discord.ext import commands
from discord import app_commands, utils, ui
from flask import Flask, jsonify
import logging
import math
import time
import random
import asyncio
# --- 変更点 ---
import openai
from openai import OpenAI
# --------------

# ログ設定
logging.basicConfig(level=logging.INFO)

# --- 🚨 KeepAlive用: Flaskアプリの定義 ---
app = Flask(__name__)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.guilds = True
intents.members = True 
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの設定
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") # 🚨 新しいAPIキー
    
    if not DISCORD_BOT_TOKEN:
        logging.error("致命的なエラー: 'DISCORD_BOT_TOKEN' が設定されていません。")
    
    # OpenAIクライアントの初期化
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logging.info("OpenAI Client initialized.")
    else:
        openai_client = None
        logging.warning("OPENAI_API_KEY not found. Translation feature will be limited.")

except Exception as e:
    DISCORD_BOT_TOKEN = None
    openai_client = None
    logging.error(f"初期設定中にエラー: {e}")


# ----------------------------------------------------
# --- ⚙️ グローバルな設定・状態管理 ---
# ----------------------------------------------------

# 翻訳機能が有効なチャンネルを管理する辞書 {channel_id: target_language_code}
# 例: {123456789: 'en'}
ACTIVE_TRANSLATION_CHANNELS = {} 


# ----------------------------------------------------
# --- 🛡️ モデレーションコマンド (Cog) ---
# ----------------------------------------------------

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Nuke: チャンネル再作成 ---
    @app_commands.command(name="nuke", description="チャンネルを削除し、同じ設定で再作成します。")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def nuke_command(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        channel = interaction.channel
        
        position = channel.position
        category = channel.category
        
        new_channel = await channel.clone()
        await channel.delete()
        
        await new_channel.edit(position=position, category=category)
        
        await interaction.followup.send(
            f"✅ チャンネル **#{new_channel.name}** を核爆弾で吹き飛ばし、再構築しました。",
            ephemeral=False
        )
        await new_channel.send(f"このチャンネルは {interaction.user.mention} によって再構築されました。")
        
    # --- BAN: ユーザーBAN ---
    @app_commands.command(name="ban", description="指定したユーザーをサーバーからBANします。")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        if member.bot:
            await interaction.followup.send("❌ BotをBANすることはできません。", ephemeral=True)
            return
            
        try:
            await member.ban(reason=reason)
            await interaction.followup.send(f"🔨 {member.mention} をサーバーからBANしました。\n理由: `{reason}`")
        except discord.Forbidden:
            await interaction.followup.send("❌ 権限がないため、このユーザーをBANできません。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ BAN中に予期せぬエラーが発生しました: {e}", ephemeral=True)

    # --- KICK: ユーザーKICK ---
    @app_commands.command(name="kick", description="指定したユーザーをサーバーからキックします。")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        if member.bot:
            await interaction.followup.send("❌ Botをキックすることはできません。", ephemeral=True)
            return

        try:
            await member.kick(reason=reason)
            await interaction.followup.send(f"👟 {member.mention} をサーバーからキックしました。\n理由: `{reason}`")
        except discord.Forbidden:
            await interaction.followup.send("❌ 権限がないため、このユーザーをキックできません。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ キック中に予期せぬエラーが発生しました: {e}", ephemeral=True)

    # --- TIMEOUT: ユーザータイムアウト (ミュート) ---
    @app_commands.command(name="timeout", description="指定したユーザーを一時的にタイムアウト（ミュート）します。")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout_command(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "理由なし"):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        if member.bot:
            await interaction.followup.send("❌ Botにタイムアウトを適用することはできません。", ephemeral=True)
            return
            
        try:
            duration = utils.timedelta(minutes=minutes)
            await member.timeout(duration, reason=reason)
            await interaction.followup.send(f"🔇 {member.mention} に `{minutes}分` のタイムアウトを適用しました。\n理由: `{reason}`")
        except discord.Forbidden:
            await interaction.followup.send("❌ 権限がないため、このユーザーにタイムアウトを適用できません。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ タイムアウト中に予期せぬエラーが発生しました: {e}", ephemeral=True)

# ----------------------------------------------------
# --- 💡 ユーティリティコマンド (Cog) ---
# ----------------------------------------------------

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- FAKE MESSAGE: 偽装メッセージ送信 ---
    @app_commands.command(name="fake_message", description="Botが別のユーザーとしてメッセージを送信します。")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def fake_message_command(self, interaction: discord.Interaction, user: discord.Member, content: str):
        
        # Webhookを使ってユーザーに成りすまして投稿
        try:
            webhooks = await interaction.channel.webhooks()
            webhook = utils.get(webhooks, name="FakeMessageHook")
            
            if webhook is None:
                webhook = await interaction.channel.create_webhook(name="FakeMessageHook")
                
            await webhook.send(
                content=content, 
                username=user.display_name, 
                avatar_url=user.display_avatar.url
            )
            
            await interaction.response.send_message("✅ メッセージを偽装送信しました。", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ Webhookの管理権限がないため、このコマンドを実行できません。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ エラーが発生しました: {e}", ephemeral=True)
            
    # --- CALC: 計算機能 ---
    @app_commands.command(name="calc", description="簡単な数式を計算します。")
    async def calc_command(self, interaction: discord.Interaction, formula: str):
        await interaction.response.defer(thinking=True)
        
        try:
            # 危険な文字をチェック
            allowed_chars = "0123456789.+-*/() "
            if any(char not in allowed_chars for char in formula):
                 raise ValueError("許可されていない文字が含まれています。演算子は + - * / () のみ使用可能です。")
                
            # 計算を実行
            result = eval(formula) 
            
            embed = discord.Embed(
                title="🧮 計算結果",
                color=discord.Color.blue()
            )
            embed.add_field(name="数式", value=f"`{formula}`", inline=False)
            embed.add_field(name="結果", value=f"**`{result}`**", inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 無効な数式です。計算できませんでした。\nエラー: `{e}`", ephemeral=True)

    # --- GIVEAWAY: ギブアウェイ機能 ---
    @app_commands.command(name="giveaway", description="ギブアウェイを開始します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_command(self, interaction: discord.Interaction, minutes: int, winners: int, prize: str):
        await interaction.response.defer(thinking=True)
        
        duration = minutes * 60
        end_time = int(time.time()) + duration
        
        embed = discord.Embed(
            title=f"🎉 GIVEAWAY: {prize} 🎉",
            description=f"リアクションで参加してください！\n終了まで: **<t:{end_time}:R>** ({minutes}分後)\n勝者数: **{winners}名**\n主催者: {interaction.user.mention}",
            color=discord.Color.gold()
        )
        message = await interaction.channel.send(embed=embed)
        await message.add_reaction("🎁") # 参加用リアクション

        await interaction.followup.send("✅ ギブアウェイを開始しました！", ephemeral=True)
        
        await asyncio.sleep(duration)
        
        try:
            updated_message = await interaction.channel.fetch_message(message.id)
            reaction = utils.get(updated_message.reactions, emoji="🎁")
            
            participants = []
            if reaction:
                participants = [user async for user in reaction.users() if user != self.bot.user]
                
            if len(participants) < winners:
                await updated_message.reply(f"⚠️ 参加者が少なかった（{len(participants)}名）ため、ギブアウェイはキャンセルされました。")
                return
            
            winners_list = random.sample(participants, winners)
            winner_mentions = ", ".join([w.mention for w in winners_list])
            
            final_embed = discord.Embed(
                title=f"🏆 GIVEAWAY終了: {prize} 🏆",
                description=f"勝者は... {winner_mentions} です！おめでとうございます！",
                color=discord.Color.green()
            )
            await updated_message.reply(content=f"おめでとうございます！{winner_mentions}！", embed=final_embed)
            
        except Exception as e:
            logging.error(f"ギブアウェイ抽選中にエラー: {e}")
            await interaction.channel.send("❌ ギブアウェイの抽選中にエラーが発生しました。", reference=message)


# ----------------------------------------------------
# --- 🌍 翻訳機能とHelp (Cog) ---
# ----------------------------------------------------

class TranslationAndHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    # --- HELP: ヘルプコマンド ---
    @app_commands.command(name="help", description="Botの機能とコマンドリストを表示します。")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        help_text = (
            "## 🤖 Bot 機能一覧\n\n"
            "このBotは、**モデレーション**と**ユーティリティ**に特化しています。\n\n"
            
            "### 🛡️ モデレーションコマンド (Prefix: /)\n"
            "- **`/nuke`**: チャンネルを即座に再作成し、履歴を消去します。*（権限: チャンネル管理）*\n"
            "- **`/ban <@ユーザー> [理由]`**: ユーザーをBANします。*（権限: メンバーBAN）*\n"
            "- **`/kick <@ユーザー> [理由]`**: ユーザーをキックします。*（権限: メンバーKick）*\n"
            "- **`/timeout <@ユーザー> <分> [理由]`**: ユーザーを一時的にタイムアウトします。*（権限: メンバー管理）*\n\n"
            
            "### 💡 ユーティリティコマンド (Prefix: /)\n"
            "- **`/fake_message <@ユーザー> <メッセージ>`**: 指定したユーザーになりすましてメッセージを送信します。*（権限: Webhook管理）*\n"
            "- **`/calc <数式>`**: 簡単な数式を計算します。\n"
            "- **`/giveaway <分> <勝者数> <景品>`**: ギブアウェイを開始します。*（権限: サーバー管理）*\n\n"
            
            "### 🌍 翻訳機能 (Prefix: /)\n"
            "- **`/翻訳 [言語コード]`**: そのチャンネルでの**自動翻訳機能**を切り替えます。\n"
            "  - 例: `/翻訳 en` (メッセージを英語に翻訳)\n"
            "  - 例: `/翻訳 off` (翻訳機能を解除)\n"
            "  - 💡 **注意**: 翻訳には**ChatGPT (OpenAI) API**を使用します。\n"
        )
        
        embed = discord.Embed(
            title="✨ Bot コマンドヘルプ",
            description=help_text,
            color=discord.Color.purple()
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

    # --- TRANSLATE: 翻訳機能のオン/オフ ---
    @app_commands.command(name="翻訳", description="そのチャンネルでの自動翻訳をON/OFFします。")
    async def translate_toggle_command(self, interaction: discord.Interaction, target_language: str = "en"):
        await interaction.response.defer(thinking=True, ephemeral=True)
        channel_id = interaction.channel_id
        
        target_language = target_language.lower()
        
        if target_language in ["off", "解除"]:
            if channel_id in ACTIVE_TRANSLATION_CHANNELS:
                del ACTIVE_TRANSLATION_CHANNELS[channel_id]
                await interaction.followup.send("❌ このチャンネルの**自動翻訳機能を解除**しました。", ephemeral=False)
            else:
                await interaction.followup.send("⚠️ このチャンネルでは自動翻訳機能は有効になっていません。", ephemeral=True)
        else:
            if not openai_client:
                await interaction.followup.send("❌ OpenAI APIキーが設定されていません。翻訳機能は利用できません。", ephemeral=False)
                return

            ACTIVE_TRANSLATION_CHANNELS[channel_id] = target_language
            await interaction.followup.send(f"✅ このチャンネルの**自動翻訳機能を有効**にしました。\n送信されたメッセージは `{target_language.upper()}` に翻訳されます。\n💡 **翻訳にはChatGPTを使用します。**", ephemeral=False)


# ----------------------------------------------------
# --- Discord イベント & 翻訳ロジック (OpenAI使用) ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="/help で機能一覧")
    )
    logging.info(f"Bot {bot.user} is ready!")
    
    # Cogの登録
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(Utility(bot))
    await bot.add_cog(TranslationAndHelp(bot))
    
    # スラッシュコマンドの同期
    try:
        synced = await bot.tree.sync()
        logging.info(f"スラッシュコマンドを同期しました。登録数: {len(synced)} 件")
    except Exception as e:
        logging.error(f"スラッシュコマンドの同期中にエラーが発生しました: {e}")


@bot.event
async def on_message(message):
    """メッセージイベント (翻訳機能の実行場所)"""
    if message.author.bot or message.content.startswith('/'): # スラッシュコマンドは無視
        return
        
    if message.channel.id in ACTIVE_TRANSLATION_CHANNELS:
        target_lang = ACTIVE_TRANSLATION_CHANNELS[message.channel.id]
        
        if not openai_client:
            await message.channel.send(
                f"**[{target_lang.upper()}への翻訳]** {message.author.mention}: \n"
                f"⚠️ **OpenAI APIキーが未設定**のため、翻訳は実行できません。",
                delete_after=20
            )
            await bot.process_commands(message)
            return

        try:
            # 翻訳を非同期で実行
            response = await asyncio.to_thread(
                openai_client.chat.completions.create,
                model="gpt-3.5-turbo", # 翻訳に適した高速モデル
                messages=[
                    {"role": "system", "content": f"あなたは優秀な翻訳家です。ユーザーのメッセージを'{target_lang}'にのみ翻訳してください。翻訳結果以外の情報は一切含めないでください。"},
                    {"role": "user", "content": message.content}
                ],
                temperature=0.0
            )
            
            translated_text = response.choices[0].message.content.strip()
            
            # 翻訳結果をチャンネルに送信
            await message.channel.send(
                f"**[{target_lang.upper()}への翻訳]** {message.author.mention}: \n"
                f"```{translated_text}```"
            )
            
        except openai.AuthenticationError:
            await message.channel.send(f"❌ OpenAI APIキーの認証に失敗しました。キーを確認してください。", delete_after=15)
        except openai.APIError as e:
            logging.error(f"OpenAI APIエラー: {e}")
            await message.channel.send(f"❌ 翻訳中にAPIエラーが発生しました。", delete_after=15)
        except Exception as e:
            logging.error(f"翻訳中に予期せぬエラー: {e}")
            await message.channel.send(f"❌ 翻訳中にエラーが発生しました。", delete_after=15)

    # コマンドの処理を続ける
    await bot.process_commands(message)


# ----------------------------------------------------
# --- Render/Uptime Robot対応: KeepAlive Server ---
# ----------------------------------------------------

def start_bot():
    """Discord Botの実行を別スレッドで開始する"""
    global DISCORD_BOT_TOKEN
    if not DISCORD_BOT_TOKEN:
        logging.error("Botの実行をスキップ: トークンが設定されていません。")
    else:
        logging.info("Discord Botを起動中...")
        try:
            bot.run(DISCORD_BOT_TOKEN, log_handler=None) 
            
        except discord.errors.LoginFailure:
            logging.error("ログイン失敗: Discord Bot Tokenが無効です。")
        except Exception as e:
            logging.error(f"予期せぬエラーが発生しました: {e}")

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
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    return jsonify({"message": "Alive"}), 200
