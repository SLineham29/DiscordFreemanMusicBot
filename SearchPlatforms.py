import random
import yt_dlp
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import re
import requests
from yt_dlp.utils import DownloadError, ExtractorError
from ytmusicapi import YTMusic
from urllib.parse import unquote, parse_qs, urlparse

# This actually looks through YouTube for the video/playlist.
def extract(query, ytdl_options):
    try:
        with yt_dlp.YoutubeDL(ytdl_options) as ytdl:
            result = ytdl.extract_info(query, download=False)
        return result
    except DownloadError as e:
        print(f"Error while downloading {query}: {e}")
        return str(e)
    except ExtractorError as e:
        print(f"Error while extracting {query}: {e}")
        return str(e)
    except Exception as e:
        print(f"Error: {e}")
        return str(e)

def search_itunes_for_info(song_id):
    # Instead of paying £80 a year for Apple developer access, they keep this simple lookup page free to use to
    # quickly get song and playlist information from a given ID.
    itunes_search_link = f"https://itunes.apple.com/lookup?id={song_id}&country=gb"
    json_results = requests.get(itunes_search_link)

    if json_results.status_code == 200:
        parsed_results = json_results.json()
        if parsed_results["resultCount"] != 0:
            return parsed_results["results"][0]
        else:
            print("iTunes could not find a valid song from the given ID")
            return None
    else:
        print(f"Invalid response from iTunes API: Status {json_results.status_code}")
        return None

def get_spotify_playlist_and_randomise(sp, items_so_far, id):
    playlist_items = []
    playlist_items.extend(items_so_far)

    results = sp.playlist_items(id, offset=100, limit=100)
    playlist_items.extend(results["items"])

    while results['next']:
        results = sp.next(results)
        playlist_items.extend(results["items"])
    random.shuffle(playlist_items)
    random_songs = random.sample(playlist_items, 50)
    return random_songs

def normalise_song_title(title):
    title = title.lower()
    title = re.sub(r'[\-\(\)\[\]/]', ' ', title)
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title

class SearchPlatforms:
    def __init__(self, client_id, client_secret):

        auth_manager = SpotifyOAuth(client_id=client_id,
                                    client_secret=client_secret,
                                    redirect_uri="https://127.0.0.1:8080/callback",
                                    scope="playlist-read-private playlist-read-collaborative",
                                    open_browser=False)
        self.sp = spotipy.Spotify(auth_manager=auth_manager)

        self.yt_music = YTMusic()

        self.ytdl_options = {
            "format": "251/bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio",
            "noplaylist": True,
            "quiet": True,
            "source_address": "0.0.0.0",
            "socket_timeout": 10,
            "retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": True,
            "extract_flat": False,
            "remote_components": ["ejs:github"],
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            }
        }

        # Need to use 'extract_flat' here because otherwise, depending on the size of the playlist,
        # it might take too long to get data for every song.
        self.ytdl_playlist_options = {
            **self.ytdl_options,
            "extract_flat": True,
            "noplaylist": False,
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
        playlist_info = await self.search_youtube_video(link, self.ytdl_playlist_options)
        playlist_details = {
            "title": playlist_info["title"],
            "author": playlist_info["uploader"],
            "thumbnail": playlist_info["thumbnails"][-1]["url"],
            "track_count": playlist_info["playlist_count"]
        }
        playlist_songs = playlist_info.get("entries", [])
        for song in playlist_songs:
            song["thumbnail"] = song["thumbnails"][-1]["url"]
        return playlist_details, playlist_songs

    async def search_youtube_music_song(self, song_query=None, song_link=None):
        song = None

        if song_link:
            song_id = parse_qs(urlparse(song_link).query)['v'][0]
            song_info = self.yt_music.get_song(song_id)
            song = {
                "url": 'https://music.youtube.com/watch?v=' + song_info['videoDetails']['videoId'],
                "title": song_info['videoDetails']['title'],
                "duration": int(song_info['videoDetails']['lengthSeconds']),
                "thumbnail": song_info['videoDetails']['thumbnail']['thumbnails'][-1]['url'],
                "artist": song_info['videoDetails']['author']
            }
        elif song_query:
            results = self.yt_music.search(song_query, filter='songs', limit=1)
            if not results:
                song_query += " (Audio)"
                yt_song = await self.search_youtube_with_query(song_query)
                if yt_song is None:
                    return None
                song = {
                    "url": yt_song['original_url'],
                    "title": yt_song['fulltitle'],
                    "duration": yt_song['duration'],
                    "thumbnail": yt_song['thumbnails'][-1]['url'],
                    "artist": yt_song['artists'][0]
                }
                return song
            song_info = results[0]
            song = {
                "url": 'https://music.youtube.com/watch?v=' + song_info['videoId'],
                "title": song_info['title'],
                "duration": song_info['duration_seconds'],
                "thumbnail": song_info['thumbnails'][-1]['url'],
                "artist": song_info['artists'][0]['name']
            }
        return song

    async def search_youtube_music_album(self, album_query=None, album_link=None):
        album_songs = []
        album_song_info = None

        if album_link:
            album_id = parse_qs(urlparse(album_link).query)['list'][0]
            browse_id = self.yt_music.get_album_browse_id(album_id)
            album_song_info = self.yt_music.get_album(browse_id)
        elif album_query:
            yt_album = self.yt_music.search(album_query, filter='albums', limit=1)
            album_song_info = self.yt_music.get_album(yt_album[0]['browseId'])

        album_details = {
            "title": album_song_info['title'],
            "artist": album_song_info['artists'][0]['name'],
            "thumbnail": album_song_info['thumbnails'][-1]['url'],
            "track_count": album_song_info['trackCount'],
        }
        for song in album_song_info['tracks']:
            if song.get('videoType') != 'MUSIC_VIDEO_TYPE_ATV':
                print(song['title'] + " is a music video, fixing...")
                search_query = f"{song['title']} - {album_details['artist']}"
                song_search = self.yt_music.search(search_query, filter='songs', limit=1)
                if song_search:
                    song['videoId'] = song_search[0]['videoId']

            song_info = {
                "url": 'https://music.youtube.com/watch?v=' + song['videoId'],
                "title": song['title'],
                "duration": song['duration_seconds'],
                "thumbnail": album_details['thumbnail'],
                "artist": song['artists'][0]['name'],
            }
            album_songs.append(song_info)
        return album_details, album_songs

    async def search_youtube_music_playlist(self, playlist_query=None, playlist_link=None):
        playlist_songs = []
        playlist_song_info = None

        if playlist_link:
            playlist_id = parse_qs(urlparse(playlist_link).query)['list'][0]
            playlist_song_info = self.yt_music.get_playlist(playlist_id)
        elif playlist_query:
            yt_playlist = self.yt_music.search(playlist_query, filter='playlists', limit=1)
            playlist_song_info = self.yt_music.get_playlist(yt_playlist[0]['browseId'])

        playlist_details = {
            "title": playlist_song_info["title"],
            "author": playlist_song_info['author']['name'],
            "thumbnail": playlist_song_info['thumbnails'][-1]['url'],
            "track_count": playlist_song_info['trackCount'],
        }
        for song in playlist_song_info['tracks']:
            song_info = {
                "url": 'https://music.youtube.com/watch?v=' + song['videoId'],
                "title": song['title'],
                "duration": song['duration_seconds'],
                "thumbnail": song['thumbnails'][-1]['url'],
                "artist": song['artists'][0]['name'],
            }
            playlist_songs.append(song_info)
        return playlist_details, playlist_songs

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
        spotify_song = self.sp.track(song_id)
        return await self.spotify_isrc_or_name_query(spotify_song)

    # Due to Spotify's API changes, you can now only play playlists that the API user account is either the owner of or has collaborated to.
    async def search_spotify_playlist(self, link):
        playlist_songs = []

        # # Capture anything after track, and before the next symbol, which should be the end of the ID.
        if re.search('spotify.link', link):
            web_response = requests.head(link, allow_redirects=True, timeout=5)
            link = web_response.url

        playlist_id_search = re.search(r'/playlist/([a-zA-Z0-9]+)', link)
        if not playlist_id_search:
            print("Could not find a valid Spotify playlist ID in this link.")
            return None

        playlist_id = playlist_id_search.group(1)
        playlist_info = self.sp.playlist(playlist_id)
        if not playlist_info['items']:
            return None

        playlist_details = {
            "title": playlist_info['name'],
            "author": playlist_info['owner']['display_name'],
            "thumbnail": playlist_info['images'][0]['url'],
            "track_count": playlist_info['items']['total']
        }

        if playlist_info['items']['total'] > 100:
            playlist_song_info = get_spotify_playlist_and_randomise(self.sp, playlist_info['items']['items'], playlist_id)
            playlist_details['track_count'] = f"50 chosen / {playlist_info['items']['total']}"
        else:
            playlist_song_info = playlist_info['items']['items']
        for song in playlist_song_info:
            song_details = await self.spotify_isrc_or_name_query(song['item'])
            playlist_songs.append(song_details)
        return playlist_details, playlist_songs

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
        album_query = f"{album_info['name']} - {album_info['artists'][0]['name']} ({album_info['release_date'][:4]})"

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

        return await self.search_youtube_music_album(album_query=album_query)

    async def spotify_isrc_or_name_query(self, spotify_song):
        isrc = spotify_song.get("external_ids", {}).get("isrc")
        if isrc:
            yt_song = await self.search_youtube_music_song(song_query=isrc)
            if yt_song is None:
                print(f"Song does not exist, retrying with {spotify_song['name']}")
                yt_song = await self.search_youtube_music_song(song_query=spotify_song['name'])
            sp_song_normalised = normalise_song_title(spotify_song['name'])
            yt_song_normalised = normalise_song_title(yt_song['title'])
            if sp_song_normalised in yt_song_normalised or yt_song_normalised in sp_song_normalised:
                return yt_song
            else:
                print(f"{yt_song['title']} isn't the same as {spotify_song['name']}, retrying using a query search.")
        song_name = f"{spotify_song['name']} - {spotify_song['artists'][0]['name']}"
        yt_song = await self.search_youtube_music_song(song_query=song_name)
        return yt_song

    async def search_apple_song(self, link):
        id_search = re.search(r'i=([a-zA-Z0-9]+)', link)

        if not id_search:
            print("Could not find a valid iTunes ID in this link.")

        song_id = id_search.group(1)

        song_info = search_itunes_for_info(song_id)

        song_name = f"{song_info['trackName']} - {song_info['artistName']}"

        song = await self.search_youtube_music_song(song_query=song_name)
        return song

    async def search_apple_album(self, link):
        id_search = re.search(r'/album/.*/(\d+)', link)

        if not id_search:
            print("Could not find a valid iTunes ID in this link.")

        song_id = id_search.group(1)

        itunes_info = search_itunes_for_info(song_id)

        album_query = f"{itunes_info['collectionName']} - {itunes_info['artistName']} ({itunes_info['releaseDate'][:4]})"

        return await self.search_youtube_music_album(album_query=album_query)

    def search_audio_page(self, link):
        # Cleaning up the URL to get the filename.
        clean_url = link.split('?')[0]
        parsed_title = clean_url.split('/')[-1]
        cleaned_title = unquote(parsed_title)

        song = {
            "url": link,
            "title": cleaned_title,
            "artist": "(Local / Hosted File)",
            "duration": 0
        }
        return song