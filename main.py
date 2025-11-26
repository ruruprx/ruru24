import os
import threading
import discord
from discord.ext import commands
from discord import app_commands, ui
from flask import Flask, jsonify
import logging
from typing import Optional
import asyncio
import yt_dlp
import ffmpeg

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
    if not DISCORD_BOT_TOKEN:
        logging.error("致命的なエラー: 'DISCORD_BOT_TOKEN' が設定されていません。")
except Exception:
    DISCORD_BOT_TOKEN = None

# --- YTDL設定 (YouTubeダウンロードとストリーム用) ---
# ytdl-coreモジュールに依存するストリーミングソースを作成するヘルパークラス
class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',  # bind to IPv4
    }
    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        ydl = yt_dlp.YoutubeDL(cls.YTDL_OPTIONS)
        
        # yt-dlpによる情報抽出をスレッドプールで実行
        data = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=not stream))

        if 'entries' in data:
            # プレイリストまたは複数の結果がある場合は最初のものを取得
            data = data['entries'][0]

        # ストリーミングソースURLを取得
        filename = data['url'] if stream else ydl.prepare_filename(data)
        
        # discord.FFmpegPCMAudio でストリーミングを開始
        return cls(discord.FFmpegPCMAudio(filename, **cls.FFMPEG_OPTIONS), data=data)


# ----------------------------------------------------
# --- Discord イベント ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="/play & /stop")
    )
    logging.info(f"Bot {bot.user} is ready!")
    
    # --- スラッシュコマンドの登録 ---
    try:
        # MusicCommands クラスのインスタンスをツリーに追加する
        bot.tree.add_command(
            MusicCommands(name="music", description="音楽再生コマンド")
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
# --- 🎶 音楽再生コマンドのグループ定義 ---
# ----------------------------------------------------

class MusicCommands(app_commands.Group):
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # ボイスチャンネルに接続していない場合は、接続を試みる
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ 音楽を再生するには、先にボイスチャンネルに接続してください。", 
                ephemeral=True
            )
            return False
        return True

    @app_commands.command(name="play", description="YouTubeから音楽を検索して再生します。")
    async def play(self, interaction: discord.Interaction, search: str):
        # 即座に応答
        await interaction.response.defer(thinking=True)
        
        # ボイスクライアントを取得
        vc = interaction.guild.voice_client

        # ボイスチャンネルに接続
        if not vc:
            try:
                vc = await interaction.user.voice.channel.connect()
            except asyncio.TimeoutError:
                await interaction.followup.send("❌ ボイスチャンネルへの接続がタイムアウトしました。", ephemeral=True)
                return
            except discord.Forbidden:
                await interaction.followup.send("❌ ボイスチャンネルに接続する権限がありません。", ephemeral=True)
                return
        
        # 既に再生中の場合は停止
        if vc.is_playing():
            vc.stop()

        try:
            # YTDLSourceからストリーミングソースを作成
            player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
            vc.play(player, after=lambda e: logging.error(f'Player error: {e}') if e else None)
            
            await interaction.followup.send(f"▶️ **{player.title}** の再生を開始します！")

        except Exception as e:
            logging.error(f"音楽再生エラー: {e}")
            await interaction.followup.send(f"❌ 音楽の検索・再生中にエラーが発生しました: {e}", ephemeral=True)

    @app_commands.command(name="stop", description="現在の再生を停止し、ボイスチャンネルから切断します。")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        vc = interaction.guild.voice_client
        
        if not vc or not vc.is_connected():
            await interaction.followup.send("⚠️ Botはボイスチャンネルに接続されていません。", ephemeral=True)
            return

        if vc.is_playing():
            vc.stop() # 再生を停止
            
        await vc.disconnect() # チャンネルから切断
        await interaction.followup.send("⏹️ 再生を停止し、ボイスチャンネルから切断しました。")


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
