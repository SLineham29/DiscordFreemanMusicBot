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
    link_type = "query"
    link = link.lower()

    # YouTube links
    if "youtu" in link:
        if "list=" in link:
            return "youtube_playlist"
        return "youtube_video"

    # Spotify Links
    if "spotify" in link:
        if "/playlist/" in link:
            return "spotify_playlist"
        elif "/album/" in link:
            return "spotify_album"
        else:
            return "spotify_song"

    # Apple Music / iTunes Links
    # Just in case someone looks for a YouTube video with the word "apple" in it, there's an extra check for the song ID.
    if "apple" in link and "i=" in link:
        return "apple_song"

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
    embed.add_field(name="By", value=song.get("artist", "Unknown"), inline=False)
    embed.add_field(name="Added By", value=f"<@{song['user_id']}>")
    embed.add_field(name="Length", value=datetime.timedelta(seconds=song.get("duration") or 0))
    embed.set_thumbnail(url=song.get("thumbnail"))
    return embed

def added_to_queue_embed(song):
    embed = discord.Embed(
        title="Added to Queue",
        description=song.get("title"),
        colour=discord.Colour.brand_green()
    )
    return embed

def added_album_to_queue_embed(album):
    embed = discord.Embed(
        title="Added an Album to the Queue",
        description=f"{album.get('title')} by {album.get('artist')}",
        colour=discord.Colour.brand_green()
    )
    embed.add_field(name="Song Count", value=f"{album.get('track_count')}")
    embed.set_thumbnail(url=album.get("thumbnail"))
    return embed

def see_queue_embed(queue):
    if len(queue) == 0:
        embed = discord.Embed(
            title="There is currently nothing in the queue.",
            colour=discord.Colour.brand_red()
        )
        return embed
    elif len(queue) == 1:
        embed = discord.Embed(
            title="There is currently 1 song in the queue:",
            colour=discord.Colour.blue()
        )
    else:
        embed = discord.Embed(
            title=f"There are currently {len(queue)} songs in the queue:",
            colour=discord.Colour.blue()
        )

    for position, song in enumerate(queue):
        embed.add_field(name=f"{position + 1})", value=f"{song.get('title')} - {song.get('artist')}", inline=False)
    return embed

# In the Discord.py library a collection of commands are called 'Cogs',
# which means that this class is a 'Cog' containing all the music commands.
class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.announcement_channel = None
        self.searcher = SearchPlatforms(os.getenv("SPOTIPY_CLIENT_ID"), os.getenv("SPOTIPY_CLIENT_SECRET"))

    @app_commands.command(name="play", description="Play a Youtube / Spotify / Apple Music song, video, or playlist")
    @app_commands.describe(link="A YouTube / Spotify / Apple Music link, or YouTube search query")
    async def parse_and_play(self, interaction: discord.Interaction, link: str):

        await interaction.response.defer()
        self.announcement_channel = interaction.channel

        voice_client = await check_if_in_server(interaction)
        if voice_client is None:
            return

        link_type = get_link_type(link)
        link_is_decoded = True

        random_chance = random.randint(1, 75)
        if random_chance == 50:
            link = "https://youtu.be/yU6gG-p5FZc?si=u58gj53pC3m5h3vq"
            link_type = "youtube_video"
            await self.announcement_channel.send("Congratulations, your link has been randomly selected to turn into Skin by Rag'n'Bone Man!")

        match link_type:
            case "query":
                song_info = await self.searcher.search_youtube_with_query(link)
            case "youtube_video":
                song_info = await self.searcher.search_youtube_video(link)
            case "youtube_playlist":
                playlist_info = await self.searcher.search_youtube_playlist(link)
                playlist_songs = playlist_info.get("entries", [])
                for i, song in enumerate(playlist_songs):
                    not_last_song = (i != len(playlist_songs) - 1)
                    await self.add_to_queue(song, interaction, voice_client, True, not_last_song, False)
                await interaction.followup.send(
                    f"Added {len(playlist_songs)} songs from {playlist_info.get("title")} to the queue")
                return
            case "spotify_song":
                song_info = await self.searcher.search_spotify_song(link)
                link_is_decoded = False
            case "spotify_playlist":
                album_info, playlist_songs = await self.searcher.search_spotify_playlist(link)
                for i, song in enumerate(playlist_songs):
                    not_last_song = (i != len(playlist_songs) - 1)
                    await self.add_to_queue(song, interaction, voice_client, True, not_last_song, False)
                await interaction.followup.send(f"Added {len(playlist_songs)} songs from a Spotify playlist to the queue")
                return
            case "spotify_album":
                album_info, playlist_songs = await self.searcher.search_spotify_album(link)
                for i, song in enumerate(playlist_songs):
                    not_last_song = (i != len(playlist_songs) - 1)
                    await self.add_to_queue(song, interaction, voice_client, True, not_last_song, False)
                await interaction.followup.send(embed=added_album_to_queue_embed(album_info))
                return
            case "apple_song":
                song_info = await self.searcher.search_apple_song(link)
                link_is_decoded = False
            case _:
                await interaction.followup.send("Invalid link type.")
                return

        if song_info is None:
            await interaction.followup.send("Could not find a valid song within this link.")
            return

        await interaction.followup.send(embed=added_to_queue_embed(song_info))
        await self.add_to_queue(song_info, interaction, voice_client, False, False, link_is_decoded)

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
            await interaction.response.send_message("The bot is not in a call.", ephemeral=True)
            return
        voice_client.stop()
        self.queue.clear()
        await interaction.response.send_message("Song has stopped and queue has been cleared.", ephemeral=True)

    @app_commands.command(name="leave", description="Leave the call.")
    async def disconnect(self, interaction: discord.Interaction):
        voice_client = await(check_if_in_server(interaction))
        if voice_client is None:
            return
        await voice_client.disconnect()
        await interaction.response.send_message("Left the call.", ephemeral=True)

    @app_commands.command(name="queue", description="See what's currently in the queue")
    async def see_current_queue(self, interaction: discord.Interaction):
        await self.announcement_channel.send(embed=see_queue_embed(self.queue))

    async def add_to_queue(self, song_info, interaction, voice_client, part_of_playlist, last_song, is_decoded_link):

        song = {
            **song_info,
            "user_id": interaction.user.id,
            "playlistSong": part_of_playlist,
            "decodedLink": is_decoded_link
        }

        # If YouTube didn't get the artist name, just use the name of the uploader channel instead.
        if 'artist' not in song:
            song['artist'] = song_info['channel']

        self.queue.append(song)

        if not last_song:
            if not voice_client.is_playing() and not voice_client.is_paused():
                await self.next_song(interaction)

    async def next_song(self, interaction: discord.Interaction):

        voice_client = interaction.guild.voice_client
        voice_channel = interaction.user.voice.channel

        if not voice_client:
            return

        if len(self.queue) == 0:
            if self.announcement_channel:
                await self.announcement_channel.send("All songs have now been played. Leaving call.", delete_after=10)
            await voice_channel.edit(status="")
            await voice_client.disconnect()
            return

        song = self.queue.pop(0)

        # If the song is from a playlist or a non-Youtube link, it doesn't have the correct URL attached to it, so we need to convert it
        # before playback. This needs to be done here rather than on queue addition because otherwise the YouTube servers
        # could be called multiple times at once, which might result in an IP timeout.
        if not song['decodedLink']:
            audio_url = await self.searcher.search_youtube_video(song["url"])
            song["url"] = audio_url.get("url")

        ffmpeg_options = {
            'before_options': "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            'options': '-vn'
        }

        # The top source is if I have the FFMPEG exe stored in Windows,
        # and the other is if it's installed globally in my Raspberry Pi.
        if platform.system() == "Windows":
            source = await discord.FFmpegOpusAudio.from_probe(song['url'], **ffmpeg_options)
        else:
            source = await discord.FFmpegOpusAudio.from_probe(song['url'], **ffmpeg_options, executable="ffmpeg")

        # After the song finishes, loop through this method again to get to the next song.
        def after_song(error):
            if error:
                print(f"Error while playing:{error}")
            asyncio.run_coroutine_threadsafe(self.next_song(interaction), self.bot.loop)

        voice_client.play(source, after=after_song)
        await voice_channel.edit(status=f"Playing: {song.get('title')}")

        if self.announcement_channel:
            embed = now_playing_embed(song)
            buttons = MusicControlButtons(self, interaction.guild)
            await self.announcement_channel.send(embed=embed, view=buttons)

class MusicControlButtons(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__()
        self.cog = cog
        self.guild = guild

    @discord.ui.button(label="Play/Pause", style=discord.ButtonStyle.green, emoji="⏯️")
    async def play_pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = self.guild.voice_client
        if voice_client is None:
            await interaction.response.send_message("The bot is not in a call.", ephemeral=True)
            return
        if voice_client.is_paused():
            await self.cog.resume.callback(self.cog, interaction)
        else:
            await self.cog.pause.callback(self.cog, interaction)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.blurple, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.skip.callback(self.cog, interaction)

    @discord.ui.button(label="See Queue", style=discord.ButtonStyle.gray, emoji="📃")
    async def see_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.see_current_queue.callback(self.cog, interaction)

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))