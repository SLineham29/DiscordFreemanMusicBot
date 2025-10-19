import os
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
from dotenv import load_dotenv
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()
token = os.getenv("BOT_TOKEN")
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")

client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

queue = []
announcement_channel = None
ytdl_options = {
    "format": "bestaudio[ext=webm][acodec=opus]/bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "source_address": "0.0.0.0",
    "socket_timeout": 10,
    "retries": 3,
    "skip_unavailable_fragments": True,
    "youtube_include_dash_manifest": False,
    "extract_flat": False,
}

# This makes an async loop to run the YouTube searcher in a new thread.
async def search_youtube(query, ytdl_options):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: extract(query, ytdl_options))

# This actually looks through YouTube for the video.
def extract(query, ytdl_options):
    with yt_dlp.YoutubeDL(ytdl_options) as ytdl:
        result = ytdl.extract_info(query, download=False)
    return result

# This is basically the bots permissions, it can send messages and join voice channels.
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def check_if_in_server(interaction):
    # This checks if the user is currently in a voice channel, and if not, then don't play the music.
    try:
        voice_channel = interaction.user.voice.channel
    except:
        await interaction.followup.send("Go into a voice channel before trying to play anything.")
        return None

    # This checks if the bot is currently connected to a voice channel
    voice_client = interaction.guild.voice_client

    # If it's not, connect to the one where the user is, else if the user is in a different channel, go to that.
    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)
    return voice_client

@bot.tree.command(name="play_youtube", description="Play a Youtube song or video or add it to the queue")
@app_commands.describe(link="A YouTube link")
async def playYoutube(interaction: discord.Interaction, link: str):
    global queue, announcement_channel, ytdl_options
    
    await interaction.response.defer()
    
    voice_client = await check_if_in_server(interaction)
    if voice_client is None:
        return

    info = await search_youtube(link, ytdl_options)

    await play(info, interaction, voice_client)

@bot.tree.command(name='play_spotify', description="Play a Spotify song or add it to the queue")
@app_commands.describe(link="A Spotify link")
async def playSpotify(interaction: discord.Interaction, link: str):
    global queue, announcement_channel, ytdl_options

    await interaction.response.defer()

    voice_client = await check_if_in_server(interaction)
    if voice_client is None:
        return

    song_by_link = sp.track(link)
    song_name = song_by_link['name']

    ytdl_search_options = {
        **ytdl_options,
        "default_search": "ytsearch"
    }

    results = await search_youtube(song_name, ytdl_search_options)
    videos = results.get("entries", [])

    if not videos:
        await interaction.followup.send(f"Could not any videos with name: {song_name}")
        return
    
    song = videos[0]

    await play(song, interaction, voice_client)

async def play(song_info, interaction, voice_client):

    global announcement_channel

    song = {
        "url": song_info.get("url"),
        "title": song_info.get("title", "Untitled")
    }
    
    announcement_channel = interaction.channel
    queue.append(song)
    
    await interaction.followup.send(f"Added to Queue: {song['title']}")
    
    if not voice_client.is_playing() and not voice_client.is_paused():
        await next_song(interaction.guild)

@bot.tree.command(name="pause", description="Pause the song")
async def pause(interaction: discord.Interaction):
    await interaction.response.defer()

    voice_client = await(check_if_in_server(interaction))
    if voice_client is None:
        return
    
    voice_client.pause()

    await interaction.followup.send("Song is paused")

@bot.tree.command(name="resume", description="Resume the song")
async def resume(interaction: discord.Interaction):
    await interaction.response.send_message("Resuming...")

    voice_client = await(check_if_in_server(interaction))
    if voice_client is None:
        return
    
    voice_client.resume()
    
@bot.tree.command(name="skip", description="Skip the current song and go to the next one in the queue")
async def skip(interaction: discord.Interaction):
    await interaction.response.send_message("Skipping...")

    voice_client = await(check_if_in_server(interaction))
    if voice_client is None:
        await interaction.followup.send("The bot is not in a call.")
        return
    
    await next_song(interaction.guild)

@bot.tree.command(name="stop", description="Clear the queue and leave the call")
async def stop(interaction: discord.Interaction):
    global queue
	
    await interaction.response.defer()

    voice_client = await(check_if_in_server(interaction))
    if voice_client is None:
        await interaction.followup.send("The bot is not in a call.")
        return
    
    queue.clear()
    await voice_client.disconnect()

    await interaction.followup.send("Song has stopped and queue has been cleared.")
    
async def next_song(guild):
    global queue, announcement_channel
    voice_client = guild.voice_client    
    
    if len(queue) == 0:
        await announcement_channel.send("All songs have now been played. Leaving call.")
        await voice_client.disconnect()
        return
		
    song = queue.pop(0)
    
    if not voice_client:
        return
    
    ffmpeg_options = {
        'before_options': "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        'options': '-vn'
    }
    
    # The top source is if I have the FFMPEG exe stored in Windows, 
    # and the other is if it's installed globally in my Raspberry Pi.
    source = discord.FFmpegOpusAudio(song['url'], **ffmpeg_options, executable="bin\\ffmpeg\\ffmpeg.exe")
    #source = discord.FFmpegOpusAudio(song['url'], **ffmpeg_options, executable="ffmpeg")
    
    def after_song():
        asyncio.run_coroutine_threadsafe(next_song(guild), bot.loop)
    
    voice_client.play(source, after=after_song)
    
    if announcement_channel:
        await announcement_channel.send(f"Now Playing: {song['title']}")
    
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print('------')
    
bot.run(token)
