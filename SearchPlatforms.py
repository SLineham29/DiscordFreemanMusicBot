import yt_dlp
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import re
import requests

class SearchPlatforms:
    def __init__(self, client_id, client_secret):
        self.sp = spotipy.Spotify(client_credentials_manager=
                             SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))

        self.ytdl_options = {
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
    async def search_youtube(self, query):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.extract(query))

    # This actually looks through YouTube for the video.
    def extract(self, query):
        with yt_dlp.YoutubeDL(self.ytdl_options) as ytdl:
            result = ytdl.extract_info(query, download=False)
        return result


    async def get_spotify_song_info(self, link):

        # # Capture anything after track, and before the next symbol, which should be the end of the ID.
        if re.search('spotify.link', link):
            web_response = requests.head(link, allow_redirects=True, timeout=5)
            link = web_response.url

        id_search = re.search(r'/track/([a-zA-Z0-9]+)', link)

        if id_search:
            song_id = id_search.group(1)
        else:
            print("Could not find a valid Spotify song ID in this link.")
            return

        song = self.sp.track(song_id)
        song_name = f"{song['name']} - {song['artists'][0]['name']}"

        ytdl_search_options = {
            **self.ytdl_options,
            "default_search": "ytsearch"
        }

        results = await self.search_youtube(song_name)
        videos = results.get("entries", [])

        # if not videos:
            # await interaction.followup.send(f"Could not any videos with name: {song_name}")
            # return

        # song = videos[0]

        # await play(song, interaction, voice_client)