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
            "remote_components": ["ejs:github"],
        }

        self.ytdl_playlist_options = {
            **self.ytdl_options,
            "extract_flat": True,
        }

    # This makes an async loop to run the YouTube searcher in a new thread.
    async def search_youtube_video(self, link, ytdl_options=None):
        ytdl_options = ytdl_options or self.ytdl_options

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.extract(link, ytdl_options))

    async def search_youtube_playlist(self, link):
        # Need to use 'extract_flat' here because otherwise, depending on the size of the playlist,
        # it might take too long to get data for every song.

        playlist_links = await self.search_youtube_video(link, self.ytdl_playlist_options)
        return playlist_links

    # This actually looks through YouTube for the video/playlist.
    def extract(self, query, ytdl_options):
        with yt_dlp.YoutubeDL(ytdl_options) as ytdl:
            result = ytdl.extract_info(query, download=False)
        return result

    async def search_spotify_video(self, link):

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

        ytdl_spotify_options = {
            **self.ytdl_options,
            "default_search": "ytsearch"
        }

        results = await self.search_youtube_video(song_name, ytdl_spotify_options)
        videos = results.get("entries", [])

        song = videos[0]
        return song

    async def search_spotify_playlist(self, link):
        # # Capture anything after track, and before the next symbol, which should be the end of the ID.
        if re.search('spotify.link', link):
            web_response = requests.head(link, allow_redirects=True, timeout=5)
            link = web_response.url

        playlist_id_search = re.search(r'/playlist/([a-zA-Z0-9]+)', link)
        album_id_search = re.search(r'/album/([a-zA-Z0-9]+)', link)
        if playlist_id_search:
            playlist_id = playlist_id_search.group(1)
            playlist_songs = self.sp.playlist_items(playlist_id)
        elif album_id_search:
            album_id = album_id_search.group(1)
            playlist_songs = self.sp.album_tracks(album_id)
        else:
            print("Could not find a valid Spotify playlist ID in this link.")
            return None

        spotify_playlist_songs = []

        ytdl_spotify_playlist_options = {
            **self.ytdl_playlist_options,
            "default_search": "ytsearch"
        }

        for song in playlist_songs["items"]:
            song_artist_names = f"{song["name"]} - {song["artists"][0]['name']}"

            results = await self.search_youtube_video(song_artist_names, ytdl_spotify_playlist_options)
            videos = results.get("entries", [])
            spotify_playlist_songs.append(videos[0])

        return spotify_playlist_songs