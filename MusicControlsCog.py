import os
import platform
import random
import datetime
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from SearchPlatforms import SearchPlatforms

def get_link_type(link):
    link_type = "video"

    # Youtube links
    if "youtu" in link:
        link_type = "youtube_video"
        if "list=" in link:
            link_type = "youtube_playlist"

    # Spotify Links
    if "spotify" in link:
        link_type = "spotify_song"
        if "/playlist/" in link or "/album/" in link:
            link_type = "spotify_playlist"

    # Apple Music / iTunes Links
    if "apple" in link:
        link_type = "apple_song"

    return link_type

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

def now_playing_embed(song):

    embed = discord.Embed(
        title="Now Playing",
        description=song.get("title"),
        colour=discord.Colour.blue()
    )
    embed.add_field(name="Added By", value=f"<@{song['user_id']}>")

    embed.add_field(name="Length", value=datetime.timedelta(seconds=song.get("duration") or 0))

    embed.set_thumbnail(url=song.get("thumbnail"))

    return embed

# In the Discord.py library a collection of commands are called 'Cogs',
# which means that this class is a 'Cog' containing all the music commands.
class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.announcement_channel = None
        self.searcher = SearchPlatforms(os.getenv("SPOTIPY_CLIENT_ID"), os.getenv("SPOTIPY_CLIENT_SECRET"))

    @app_commands.command(name="play", description="Play a Youtube / Spotify / Apple Music song or playlist")
    @app_commands.describe(link="A YouTube / Spotify / Apple Music link")
    async def parse_and_play(self, interaction: discord.Interaction, link: str):

        await interaction.response.defer()

        voice_client = await check_if_in_server(interaction)
        if voice_client is None:
            return

        link_type = get_link_type(link)

        random_chance = random.randint(1, 75)
        if random_chance == 50:
            link = "https://youtu.be/yU6gG-p5FZc?si=u58gj53pC3m5h3vq"
            link_type = "youtube_video"
            await interaction.followup.send("Congratulations, your link has been randomly selected to turn into Skin by Rag'n'Bone Man!")

        match link_type:
            case "youtube_video":
                song_info = await self.searcher.search_youtube_video(link)
            case "youtube_playlist":
                playlist_info = await self.searcher.search_youtube_playlist(link)
                print(playlist_info)
                playlist_songs = playlist_info.get("entries", [])
                for i, song in enumerate(playlist_songs):
                    not_last_song = (i != len(playlist_songs) - 1)
                    await self.add_to_queue(song, interaction, voice_client, not_last_song)
                await interaction.followup.send(
                    f"Added {len(playlist_songs)} songs from {playlist_info.get("title")} to the queue")
                return
            case "spotify_song":
                song_info = await self.searcher.search_spotify_video(link)
            case "spotify_playlist":
                playlist_info = await self.searcher.search_spotify_playlist(link)
                print(playlist_info)
                for i, song in enumerate(playlist_info):
                    not_last_song = (i != len(playlist_info) - 1)
                    await self.add_to_queue(song, interaction, voice_client, not_last_song)
                await interaction.followup.send(f"Added {len(playlist_info)} songs from a Spotify playlist to the queue")
                return
            case "apple_song":
                song_info = await self.searcher.search_apple_song(link)
            case _:
                await interaction.followup.send("Invalid link type.")
                return

        await self.add_to_queue(song_info, interaction, voice_client, False)
        await interaction.followup.send(f"Added to Queue: {song_info.get("title")}", ephemeral=True)

    @app_commands.command(name="pause", description="Pause the song")
    async def pause(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pausing...", ephemeral=True)

        voice_client = await(check_if_in_server(interaction))
        if voice_client is None:
            return

        voice_client.pause()

    @app_commands.command(name="resume", description="Resume the song")
    async def resume(self, interaction: discord.Interaction):
        await interaction.response.send_message("Resuming...", ephemeral=True)

        voice_client = await(check_if_in_server(interaction))
        if voice_client is None:
            return

        voice_client.resume()

    @app_commands.command(name="skip", description="Skip the current song and go to the next one in the queue")
    async def skip(self, interaction: discord.Interaction):

        await interaction.response.send_message("Skipping...", ephemeral=True)

        voice_client = await(check_if_in_server(interaction))
        if voice_client is None:
            await interaction.followup.send("The bot is not in a call.", ephemeral=True)
            return

        voice_client.stop()

    @app_commands.command(name="stop", description="Stop the current song and clear the queue")
    async def stop(self, interaction: discord.Interaction):

        voice_client = await(check_if_in_server(interaction))
        if voice_client is None:
            await interaction.followup.send("The bot is not in a call.")
            return

        voice_client.stop()
        self.queue.clear()

        await interaction.followup.send("Song has stopped and queue has been cleared.", ephemeral=True)

    @app_commands.command(name="leave", description="Leave the call.")
    async def disconnect(self, interaction: discord.Interaction):

        await interaction.response.defer()

        voice_client = await(check_if_in_server(interaction))
        if voice_client is None:
            await interaction.followup.send("The bot is not in a call.")
            return

        await voice_client.disconnect()

        await interaction.followup.send("I have left the call.")

    @app_commands.command(name="queue", description="See what's currently in the queue")
    async def see_current_queue(self, interaction: discord.Interaction):

        await interaction.response.defer()

        if len(self.queue) == 0:
            await interaction.followup.send("There is currently nothing in the queue.")
        elif len(self.queue) == 1:
            queue_songs = f"There is currently 1 song in the queue:\n\n"
            queue_songs += f"1) {self.queue[0].get('title')}"
            await interaction.followup.send(queue_songs)
        else:
            queue_songs = f"There are currently {len(self.queue)} songs in the queue:\n\n"
            for position, song in enumerate(self.queue):
                queue_songs += f"{position + 1}) {song.get('title')}\n"
            await interaction.followup.send(queue_songs)

    async def add_to_queue(self, song_info, interaction, voice_client, part_of_playlist):

        song = {
            "url": song_info.get("url"),
            "title": song_info.get("title", "Untitled"),
            "duration": song_info.get("duration"),
            "thumbnail": song_info.get("thumbnail"),
            "user_id": interaction.user.id
        }

        self.announcement_channel = interaction.channel
        self.queue.append(song)

        if not part_of_playlist:
            if not voice_client.is_playing() and not voice_client.is_paused():
                await self.next_song(interaction.guild)

    async def next_song(self, guild):

        voice_client = guild.voice_client

        if not voice_client:
            return

        if len(self.queue) == 0:
            if self.announcement_channel:
                await self.announcement_channel.send("All songs have now been played. Leaving call.")
            await voice_client.disconnect()
            return

        song = self.queue.pop(0)

        # If the song is from a playlist, it doesn't have the correct URL attached to it, so we need to convert it
        # before playback. This needs to be done here rather than on queue addition because otherwise the Youtube servers
        # could be called multiple times at once, which might result in an IP timeout.
        if "youtu" in song["url"]:
            audio_url = await self.searcher.search_youtube_video(song["url"])

            song["url"] = audio_url.get("url")

        ffmpeg_options = {
            'before_options': "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            'options': '-vn'
        }

        # The top source is if I have the FFMPEG exe stored in Windows,
        # and the other is if it's installed globally in my Raspberry Pi.
        if platform.system() == "Windows":
            source = discord.FFmpegOpusAudio(song['url'], **ffmpeg_options, executable="bin\\ffmpeg\\ffmpeg.exe")
        else:
            source = discord.FFmpegOpusAudio(song['url'], **ffmpeg_options, executable="ffmpeg")

        # After the song finishes, loop through this method again to get to the next song.
        def after_song(error):
            if error:
                print(f"Error while playing:{error}")
            asyncio.run_coroutine_threadsafe(self.next_song(guild), self.bot.loop)

        voice_client.play(source, after=after_song)

        if self.announcement_channel:
            embed = now_playing_embed(song)
            buttons = MusicControlButtons(self, guild)
            await self.announcement_channel.send(embed=embed, view=buttons)

class MusicControlButtons(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__()
        self.cog = cog
        self.guild = guild

    @discord.ui.button(label="Play/Pause", style=discord.ButtonStyle.green, emoji="⏯️")
    async def play_pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        voice_client = self.guild.voice_client

        if voice_client.is_paused():
            await self.cog.resume.callback(self.cog, interaction)
        else:
            await self.cog.pause.callback(self.cog, interaction)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.blurple, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.skip.callback(self.cog, interaction)

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))