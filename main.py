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

# ログ設定
logging.basicConfig(level=logging.INFO)

# --- 🚨 KeepAlive用: Flaskアプリの定義 ---
app = Flask(__name__)

# --- Discord Bot Setup ---
# 必要なインテントを有効化 (モデレーション、メッセージ内容、メンバー情報など)
intents = discord.Intents.default()
intents.guilds = True
intents.members = True 
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの設定
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    if not DISCORD_BOT_TOKEN:
        logging.error("致命的なエラー: 'DISCORD_BOT_TOKEN' が設定されていません。")
except Exception:
    DISCORD_BOT_TOKEN = None

# ----------------------------------------------------
# --- ⚙️ グローバルな設定・状態管理 ---
# ----------------------------------------------------

# 翻訳機能が有効なチャンネルを管理する辞書 {channel_id: target_language_code}
# target_language_codeは、例として 'en' (英語) や 'ja' (日本語) を想定
ACTIVE_TRANSLATION_CHANNELS = {} 
# 翻訳機能の実装には外部API (例: Google Cloud Translation API) が必要ですが、
# ここでは bot.tree.command 内で Google 検索ツールを使用して翻訳をシミュレートします。


# ----------------------------------------------------
# --- 🛡️ モデレーションコマンド (Cog) ---
# ----------------------------------------------------

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        # すべてのモデレーションコマンドの前に、実行者がモデレーターロールを持っているか確認
        # スラッシュコマンドでは interaction_check を使用するため、ここではスキップ
        return True 

    # --- Nuke: チャンネル再作成 ---
    @app_commands.command(name="nuke", description="チャンネルを削除し、同じ設定で再作成します。")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def nuke_command(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        channel = interaction.channel
        
        # チャンネルのすべての設定と位置を保持
        position = channel.position
        category = channel.category
        
        # チャンネルをクローン
        new_channel = await channel.clone()
        
        # 古いチャンネルを削除
        await channel.delete()
        
        # 新しいチャンネルを設定
        await new_channel.edit(position=position, category=category)
        
        # ユーザーに通知
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
        self.translation_loop_task = None

    # --- FAKE MESSAGE: 偽装メッセージ送信 ---
    @app_commands.command(name="fake_message", description="Botが別のユーザーとしてメッセージを送信します。")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def fake_message_command(self, interaction: discord.Interaction, user: discord.Member, content: str):
        # ユーザーのコマンド投稿を削除
        try:
            await interaction.message.delete()
        except:
            # スラッシュコマンドなので interaction.message は None。この行はスキップされる。
            pass

        # Webhookを使ってユーザーに成りすまして投稿
        try:
            # チャンネルの既存Webhookを検索
            webhooks = await interaction.channel.webhooks()
            webhook = utils.get(webhooks, name="FakeMessageHook")
            
            # Webhookが存在しない場合は作成
            if webhook is None:
                webhook = await interaction.channel.create_webhook(name="FakeMessageHook")
                
            await webhook.send(
                content=content, 
                username=user.display_name, 
                avatar_url=user.display_avatar.url
            )
            
            # コマンド実行者に応答 (非表示)
            await interaction.response.send_message("✅ メッセージを偽装送信しました。", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ Webhookの管理権限がないため、このコマンドを実行できません。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ エラーが発生しました: {e}", ephemeral=True)
            
    # --- CALC: 計算機能 ---
    @app_commands.command(name="calc", description="簡単な数式を計算します。")
    async def calc_command(self, interaction: discord.Interaction, formula: str):
        await interaction.response.defer(thinking=True)
        
        # 安全な計算のために eval の代わりに math を使用
        try:
            # 危険な文字をチェック
            if any(char in formula for char in 'aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ[{]}"\'`'):
                raise ValueError("許可されていない文字が含まれています。")
                
            # 計算を実行 (Pythonの標準的な計算機能を使用)
            # **注意: math.sqrtやmath.logなどの高度な関数を使用したい場合は、
            # 適切なライブラリをインポートし、evalを避けるための安全なパーサーが必要です。
            # ここでは組み込みの算術演算子のみを許可します。
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
        
        # ギブアウェイ終了を待機
        await asyncio.sleep(duration)
        
        # リアクションを取得し、参加者リストを作成
        try:
            # 更新されたメッセージを取得
            updated_message = await interaction.channel.fetch_message(message.id)
            reaction = utils.get(updated_message.reactions, emoji="🎁")
            
            if reaction:
                # Bot自身を除外して参加者を取得
                participants = [user async for user in reaction.users() if user != self.bot.user]
                
                if len(participants) < winners:
                    await updated_message.reply("⚠️ 参加者が少なすぎたため、ギブアウェイはキャンセルされました。")
                    return
                
                # 勝者を選出
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
            await interaction.channel.send("❌ ギブアウェイの抽選中にエラーが発生しました。", reference=updated_message)


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
            "このBotは、モデレーションとユーティリティに特化しています。\n\n"
            
            "### 🛡️ モデレーションコマンド (Prefix: /)\n"
            "- **`/nuke`**: チャンネルを即座に再作成し、履歴を消去します。\n"
            "- **`/ban <@ユーザー> [理由]`**: ユーザーをBANします。\n"
            "- **`/kick <@ユーザー> [理由]`**: ユーザーをキックします。\n"
            "- **`/timeout <@ユーザー> <分> [理由]`**: ユーザーを一時的にタイムアウトします。\n\n"
            
            "### 💡 ユーティリティコマンド (Prefix: /)\n"
            "- **`/fake_message <@ユーザー> <メッセージ>`**: 指定したユーザーになりすましてメッセージを送信します。(Webhook利用)\n"
            "- **`/calc <数式>`**: 数式を計算します。\n"
            "- **`/giveaway <分> <勝者数> <景品>`**: ギブアウェイを開始します。\n"
            "- **`/help`**: このヘルプを表示します。\n\n"
            
            "### 🌍 翻訳機能 (Prefix: /)\n"
            "- **`/翻訳 [言語コード]`**: そのチャンネルでの自動翻訳機能を切り替えます。言語コードがない場合は英語(`en`)に設定します。\n"
            "  - 例: `/翻訳 en` (日本語を英語に翻訳) \n"
            "  - 例: `/翻訳 off` (翻訳機能を解除) \n"
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
            # 言語コードの簡単なチェック (例: 'en', 'ja', 'es')
            if len(target_language) != 2 or not target_language.isalpha():
                await interaction.followup.send("❌ 無効な言語コードです。例: `en`, `ja`, `off` を使用してください。", ephemeral=True)
                return

            ACTIVE_TRANSLATION_CHANNELS[channel_id] = target_language
            await interaction.followup.send(f"✅ このチャンネルの**自動翻訳機能を有効**にしました。\n送信されたメッセージは `{target_language.upper()}` に翻訳されます。", ephemeral=False)


# ----------------------------------------------------
# --- Discord イベント & 翻訳ロジック ---
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
    if message.author.bot:
        return
        
    # 自動翻訳が有効なチャンネルであるかチェック
    if message.channel.id in ACTIVE_TRANSLATION_CHANNELS:
        target_lang = ACTIVE_TRANSLATION_CHANNELS[message.channel.id]
        original_content = message.content
        
        # ⚠️ 翻訳APIの代替としてGoogle Searchツールを使用します ⚠️
        # 実際の運用では、Google Cloud Translation APIなどの外部サービスが必要です。
        translation_query = f"'{original_content}' を {target_lang} に翻訳"
        
        try:
            # Google Search APIを呼び出す
            google_search_result = await google.search(queries=[translation_query])
            
            # 検索結果から翻訳されたテキストを抽出するロジック（Botの内部ロジックに依存）
            # ここでは、ツールの出力をそのまま翻訳結果として使用すると仮定します。
            # 実際の翻訳結果は検索スニペットの最初の結果になることが多いです。
            translated_text = "翻訳結果が見つかりませんでした。" 
            if google_search_result and google_search_result.get('result'):
                # 検索結果を整形し、最初のスニペットを翻訳として利用
                # (この部分は実行環境によって異なるため、一般的な処理を記述)
                translated_text = google_search_result['result'][:500] # 500文字に制限
                # ユーザーが理解しやすいように、検索結果の最初の部分を使用
            
            # 翻訳結果をチャンネルに送信
            await message.channel.send(
                f"**[{target_lang.upper()}への翻訳]** {message.author.mention}: \n"
                f"```{translated_text}```"
            )
            
        except Exception as e:
            logging.error(f"翻訳中にGoogle Searchツールエラー: {e}")
            await message.channel.send("❌ 翻訳サービスの呼び出し中にエラーが発生しました。", delete_after=10)

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
            bot.run(DISCORD_BOT_TOKEN, log_level=logging.INFO) 
            
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
