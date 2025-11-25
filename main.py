import os
import threading
import discord
from discord.ext import commands
from discord import app_commands, ui
from flask import Flask, jsonify
import logging
from typing import Optional

# ログ設定
logging.basicConfig(level=logging.INFO)

# --- 🚨 KeepAlive用: Flaskアプリの定義 ---
app = Flask(__name__)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
# Webhookとチケットシステムに必要
intents.guilds = True
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの設定
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    # 🚨 コマンド実行を許可するユーザーID
    BOT_OWNER_ID = int(os.environ.get("BOT_OWNER_ID", 0)) 
    if not DISCORD_BOT_TOKEN:
        logging.error("致命的なエラー: 'DISCORD_BOT_TOKEN' が設定されていません。")
except Exception:
    DISCORD_BOT_TOKEN = None
    BOT_OWNER_ID = 0

# --- 🧑‍💻 コマンド実行許可ユーザーID (ここに含まれるIDのみが /fakemessage, /ticket を実行可能) ---
ALLOWED_USER_IDS = [
    BOT_OWNER_ID,
    1420826924145442937,
]

# --- 🎫 チケットシステム設定 ---
CLOSED_TICKET_CATEGORY_NAME = "🔒｜クローズ済みチケット"
TICKET_PANEL_CONFIG = {} # {guild_id: {title, description, button_label, category_id, role_ids}}


# ----------------------------------------------------
# --- 🚨 コマンド実行制限チェック関数 🚨 ---
# ----------------------------------------------------

def is_allowed_user():
    """ALLOWED_USER_IDSに含まれるユーザーのみが実行を許可されるカスタムチェック"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in ALLOWED_USER_IDS:
            return True
        
        await interaction.response.send_message(
            "❌ あなたにはこのコマンドを実行する権限がありません。", 
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)

# ----------------------------------------------------
# --- 🎫 チケットシステムのView, Modal定義 ---
# ----------------------------------------------------

class CloseTicketView(ui.View):
    """チケットチャンネル内で、チャンネルをクローズするために使用するボタンを定義するView。"""
    def __init__(self, bot: commands.Bot, creator: discord.Member):
        super().__init__(timeout=None)
        self.bot = bot
        self.creator = creator 

    @ui.button(label="🔒 チケットをクローズ", style=discord.ButtonStyle.red, custom_id="close_ticket_button")
    async def close_ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.creator.id and not interaction.user.guild_permissions.administrator:
             await interaction.response.send_message("❌ チケットをクローズできるのは作成者か管理者のみです。", ephemeral=True)
             return
        await interaction.response.defer(thinking=True)
        channel = interaction.channel
        guild = interaction.guild
        closed_category = discord.utils.get(guild.categories, name=CLOSED_TICKET_CATEGORY_NAME)
        if not closed_category: 
            closed_category = await guild.create_category(CLOSED_TICKET_CATEGORY_NAME)
            
        await channel.edit(name=f"closed-{channel.name}", category=closed_category)
        await channel.set_permissions(self.creator, read_messages=False)
        await channel.set_permissions(guild.default_role, read_messages=False)
        await interaction.followup.send(f"🔒 チケットがクローズされました。チャンネルは {CLOSED_TICKET_CATEGORY_NAME} に移動されました。")


class TicketView(ui.View):
    """チケット作成ボタンと、それをクリックした後の処理を定義するView。"""
    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=None) 
        self.bot = bot
        self.guild_id = guild_id
        
        config = TICKET_PANEL_CONFIG.get(guild_id, {})
        button_label = config.get("button_label", "🎫 チケットを作成")
        
        self.clear_items()
        self.add_item(
            ui.Button(
                label=button_label, 
                style=discord.ButtonStyle.primary, 
                custom_id="create_ticket_button"
            )
        )

    @ui.button(label="PLACEHOLDER", style=discord.ButtonStyle.primary, custom_id="create_ticket_button")
    async def create_ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True) 
        guild = interaction.guild
        member = interaction.user
        
        config = TICKET_PANEL_CONFIG.get(guild.id)
        if not config:
            await interaction.followup.send("❌ チケットパネルが設定されていません。管理者に連絡してください。", ephemeral=True)
            return

        ticket_category = guild.get_channel(config["category_id"])
        
        if not ticket_category or not isinstance(ticket_category, discord.CategoryChannel):
            await interaction.followup.send("❌ 設定されたチケットカテゴリーが見つかりません。管理者に連絡してください。", ephemeral=True)
            return
            
        channel_name = f"ticket-{member.name.lower().replace(' ', '-')}"
        if discord.utils.get(ticket_category.channels, name=channel_name):
            await interaction.followup.send("⚠️ 既にチケットチャンネルがあります。既存のチャンネルを使用してください。", ephemeral=True)
            return

        # 権限の上書き設定
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
        # 閲覧可能ロールの設定を反映
        for role_id in config["role_ids"]:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)


        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=ticket_category,
            overwrites=overwrites
        )
        
        # チケット作成時のメッセージは固定
        await ticket_channel.send(
            f"{member.mention} さん、チケットを作成しました。**【問題を解決するために必要な情報を記述してください】**\n"
            "管理者が対応するまでしばらくお待ちください。"
        )
        close_view = CloseTicketView(self.bot, member)
        await ticket_channel.send(
            "問題を解決したい場合、下の **'🔒 チケットをクローズ'** ボタンを押してください。",
            view=close_view
        )
        await interaction.followup.send(f"✅ チケットを作成しました！ {ticket_channel.mention} に移動してください。", ephemeral=True)


class TicketSetupModal(ui.Modal, title="🎫 チケットパネル設定"):
    """チケットパネルの各種設定を受け付けるモーダル"""
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=300)
        self.bot = bot
        
    # --- 入力項目 ---
    
    panel_title = ui.TextInput(
        label="パネルのタイトル",
        default="サポートチケット",
        style=discord.TextStyle.short,
        required=True,
        max_length=100,
    )

    panel_description = ui.TextInput(
        label="パネルの説明",
        default="下のボタンを押してチケットを作成してください。",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )
    
    button_label = ui.TextInput(
        label="ボタンのラベル",
        default="🎫 チケットを作成",
        style=discord.TextStyle.short,
        required=True,
        max_length=80,
    )
    
    category_id = ui.TextInput(
        label="チケット作成カテゴリーID",
        placeholder="ここにカテゴリーIDをペーストしてください",
        style=discord.TextStyle.short,
        required=True,
        max_length=20,
    )
    
    role_ids = ui.TextInput(
        label="閲覧可能ロールID (カンマ区切り)",
        placeholder="対応ロールのIDをカンマ(,)で区切って入力 (任意)",
        style=discord.TextStyle.short,
        required=False,
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        guild = interaction.guild
        
        try:
            cat_id = int(self.category_id.value.strip())
            category = guild.get_channel(cat_id)
            if not category or not isinstance(category, discord.CategoryChannel):
                await interaction.followup.send("❌ 入力されたカテゴリーIDが無効です。", ephemeral=True)
                return
            
            role_id_list = []
            if self.role_ids.value.strip():
                for role_str in self.role_ids.value.split(','):
                    role_id_str = role_str.strip()
                    if role_id_str.isdigit():
                        role_id = int(role_id_str)
                        role = guild.get_role(role_id)
                        if role:
                            role_id_list.append(role_id)
                        else:
                            await interaction.followup.send(f"⚠️ ロールID `{role_id_str}` は見つかりませんでした。スキップします。", ephemeral=True)
        
        except ValueError:
            await interaction.followup.send("❌ IDの入力形式が不正です。数値のみを使用してください。", ephemeral=True)
            return

        global TICKET_PANEL_CONFIG
        TICKET_PANEL_CONFIG[guild.id] = {
            "title": self.panel_title.value.strip(),
            "description": self.panel_description.value.strip(),
            "button_label": self.button_label.value.strip(),
            "category_id": cat_id,
            "role_ids": role_id_list,
        }

        config = TICKET_PANEL_CONFIG[guild.id]
        embed = discord.Embed(
            title=config["title"],
            description=config["description"],
            color=discord.Color.blue()
        )
        
        await interaction.channel.send(embed=embed, view=TicketView(self.bot, guild.id))
        
        await interaction.followup.send("✅ チケットパネルをこのチャンネルに表示しました。", ephemeral=True)


# ----------------------------------------------------
# --- Discord イベント ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="/fakemessage & /ticket")
    )
    logging.info(f"Bot {bot.user} is ready!")
    
    # --- グループコマンドの登録 ---
    try:
        # 修正: TicketCommands クラスのインスタンスをツリーに追加する
        bot.tree.add_command(
            TicketCommands(name="ticket", description="チケットシステムを管理します。")
        )
        
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

# --- 🎫 チケットシステムコマンドのグループ定義 ---
class TicketCommands(app_commands.Group):
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # グループコマンド全体にALLOWED_USER_IDSを適用
        if interaction.user.id in ALLOWED_USER_IDS:
            return True
        await interaction.response.send_message("❌ あなたにはこのコマンドを実行する権限がありません。", ephemeral=True)
        return False
    
    # サブコマンドは 'async def' である必要があります
    @app_commands.command(name="create_panel", description="チケット作成パネルを設定し、現在のチャンネルに表示します。")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_panel(self, interaction: discord.Interaction):
        # 設定モーダルを表示する
        await interaction.response.send_modal(TicketSetupModal(bot))


# --- 管理コマンド (Fakemessage) ---

@bot.tree.command(name="fakemessage", description="指定ユーザーになりすましてメッセージを送信します (Webhookを使用)。")
@commands.has_permissions(manage_webhooks=True)
@is_allowed_user()
async def fakemessage_slash(interaction: discord.Interaction, user: discord.Member, content: str):
    await interaction.response.defer(ephemeral=True)
    channel = interaction.channel
    webhook = None

    try:
        webhooks = await channel.webhooks()
        for wh in webhooks:
            if wh.name == "Bot Fake Sender":
                webhook = wh
                break
        
        if webhook is None:
            webhook = await channel.create_webhook(name="Bot Fake Sender")

        await webhook.send(
            content=content,
            username=user.display_name,
            avatar_url=user.display_avatar.url
        )
        
        await interaction.followup.send(f"✅ **{user.display_name}** になりすましたメッセージを送信しました。", ephemeral=True)
        
    except discord.Forbidden:
        await interaction.followup.send("❌ BotにWebhookの管理権限がありません。", ephemeral=True)
    except Exception as e:
        logging.error(f"Fakemessage実行中にエラーが発生: {e}")
        await interaction.followup.send("予期せぬエラーが発生し、メッセージを送信できませんでした。", ephemeral=True)


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
            if not bot.intents.members or not bot.intents.message_content:
                 logging.warning("必要なインテント（Members, Message Content）が有効になっていません。Discord Developer Portalで確認してください。")
            bot.run(DISCORD_BOT_TOKEN)
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
