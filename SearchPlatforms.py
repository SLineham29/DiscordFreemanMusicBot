import yt_dlp
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import re
import requests
from ytmusicapi import YTMusic

# This actually looks through YouTube for the video/playlist.
def extract(query, ytdl_options):
    with yt_dlp.YoutubeDL(ytdl_options) as ytdl:
        result = ytdl.extract_info(query, download=False)
    return result

class SearchPlatforms:
    def __init__(self, client_id, client_secret):
        self.sp = spotipy.Spotify(client_credentials_manager=
                             SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))

        self.yt_music = YTMusic()

        self.ytdl_options = {
            "format": "251/bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio",
            "noplaylist": True,
            "quiet": True,
            "source_address": "0.0.0.0",
            "socket_timeout": 10,
            "retries": 3,
            "skip_unavailable_fragments": True,
            "extract_flat": False,
            "remote_components": ["ejs:github"],
        }

        # Need to use 'extract_flat' here because otherwise, depending on the size of the playlist,
        # it might take too long to get data for every song.
        self.ytdl_playlist_options = {
            **self.ytdl_options,
            "extract_flat": True,
        }

        self.ytdl_yt_search_options = {
            **self.ytdl_options,
            "default_search": "ytsearch"
        }

    # This makes an async loop to run the YouTube searcher in a new thread.
    async def search_youtube_video(self, link, ytdl_options=None):
        ytdl_options = ytdl_options or self.ytdl_options
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: extract(link, ytdl_options))

    async def search_youtube_with_query(self, query):
        results = await self.search_youtube_video(query, self.ytdl_yt_search_options)
        entries = results.get("entries", [])
        if not entries:
            return None
        return entries[0]

    async def search_youtube_playlist(self, link):
        playlist_links = await self.search_youtube_video(link, self.ytdl_playlist_options)
        return playlist_links

    async def search_youtube_music(self, song_name, search_filter):
        results = self.yt_music.search(song_name, filter=search_filter, limit=1)

        if not results:
            song = self.search_youtube_with_query(song_name)
            return song

        song_info = results[0]
        song = {
            **song_info,
            "url": 'https://youtube.com/watch?v=' + song_info['videoId'],
            "duration": song_info['duration_seconds'],
            "thumbnail": song_info['thumbnails'][-1]['url'],
            "artist": song_info['artists'][0]['name'],
        }

        return song

    async def search_spotify_song(self, link):

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

        song = await self.search_youtube_music(song_name, 'songs')
        return song

    async def search_spotify_playlist(self, link):
        spotify_playlist_songs = []

        # # Capture anything after track, and before the next symbol, which should be the end of the ID.
        if re.search('spotify.link', link):
            web_response = requests.head(link, allow_redirects=True, timeout=5)
            link = web_response.url

        playlist_id_search = re.search(r'/playlist/([a-zA-Z0-9]+)', link)
        if not playlist_id_search:
            print("Could not find a valid Spotify playlist ID in this link.")
            return None

        playlist_id = playlist_id_search.group(1)
        playlist_songs = self.sp.playlist_items(playlist_id)

        ytdl_spotify_playlist_options = {
            **self.ytdl_yt_search_options,
            "playlist_items": "1"
        }

        for song in playlist_songs["items"]:
            song_artist_names = f"{song["name"]} - {song["artists"][0]['name']} (Audio)"
            results = await self.search_youtube_video(song_artist_names, ytdl_spotify_playlist_options)
            videos = list(results.get("entries", []))
            spotify_playlist_songs.append(videos[0])
        return spotify_playlist_songs

    async def search_spotify_album(self, link):
        album_songs = []

        if re.search('spotify.link', link):
            web_response = requests.head(link, allow_redirects=True, timeout=5)
            link = web_response.url

        album_id_search = re.search(r'/album/([a-zA-Z0-9]+)', link)
        if not album_id_search:
            print("Could not find a valid Spotify album ID in this link.")
            return None

        album_id = album_id_search.group(1)
        album_info = self.sp.album(album_id)
        album_query = f"{album_info['name']} - {album_info['artists'][0]['name']}"

        yt_album = self.yt_music.search(album_query, filter='albums', limit=1)
        if not yt_album:
            ytdl_spotify_playlist_options = {
                **self.ytdl_yt_search_options,
                "playlist_items": "1"
            }

            playlist_songs = self.sp.album_tracks(album_id)

            for song in playlist_songs["items"]:
                song_artist_names = f"{song["name"]} - {song["artists"][0]['name']} (Audio)"
                results = await self.search_youtube_video(song_artist_names, ytdl_spotify_playlist_options)
                videos = list(results.get("entries", []))
                album_songs.append(videos[0])
            return album_songs

        album_song_info = self.yt_music.get_album(yt_album[0]['browseId'])
        album_details = {
            "title": album_song_info["title"],
            "artist": album_song_info['artists'][0]['name'],
            "thumbnail": album_song_info['thumbnails'][-1]['url'],
            "track_count": album_song_info['trackCount'],
        }
        for song in album_song_info['tracks']:
            song_info = {
                "url": 'https://youtube.com/watch?v=' + song['videoId'],
                "title": song['title'],
                "duration": song['duration_seconds'],
                "thumbnail": album_details['thumbnail'],
                "artist": song['artists'][0]['name'],
            }
            album_songs.append(song_info)
        return album_details, album_songs

    async def search_apple_song(self, link):
        id_search = re.search(r'i=([a-zA-Z0-9]+)', link)

        if not id_search:
            print("Could not find a valid iTunes ID in this link.")

        song_id = id_search.group(1)

        # Instead of paying £80 a year for Apple developer access, they keep this simple lookup page free to use to
        # quickly get song and playlist information from a given ID.
        itunes_search_link = f"https://itunes.apple.com/lookup?id={song_id}"
        json_results = requests.get(itunes_search_link)

        if json_results.status_code == 200:
            parsed_results = json_results.json()
            if parsed_results["resultCount"] != 0:
                song_info = parsed_results["results"][0]
            else:
                print("iTunes could not find a valid song from the given ID")
                return None
        else:
            print("Invalid response from iTunes API.")
            return None

        song_name = f"{song_info['trackName']} - {song_info['artistName']}"

        song = await self.search_youtube_music(song_name, 'songs')
        return song