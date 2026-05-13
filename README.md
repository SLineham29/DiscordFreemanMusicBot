# DiscordFreemanMusicBot
This is my implementation of a Discord bot designed to play music and videos in a voice channel when given a valid YouTube / Spotify / Apple Music link.

## Project Setup
1. Ensure [Python](https://www.python.org/) and [FFMPeg](https://ffmpeg.org/) are installed on the device you'll be hosting the bot on.
2. Create a Python venv within this cloned project and activate it.
3. Download the project requirements by running the following command within the venv:
```
pip install -r requirements.txt
```

## Bot Setup
1. Create a new application within the [Discord Developer Portal](https://discord.com/developers/applications).
2. Within the new application's page, go to the "**Bot**" tab under overview on the left-hand side.
3. Scroll down and enable "**Message Content Intent**".
4. Scroll back up to "**Token**", click 'Reset Token', then copy the new token that is given to you.
5. Within this project's root directory, create a file called `.env` and add the following line into it, replacing 'PlaceTokenHere' with the token you've just copied:
```
BOT_TOKEN=PlaceTokenHere
```
6. Run the bot by using the following command:
```
python MusicBot.py
```

> [!WARNING]
> In order for the bot to parse Spotify links, you will need to provide your own Spotify developer client ID and secret, which now requires a Spotify Premium account and [can be obtained here](https://developer.spotify.com/).\
> You will need to add the following 2 lines to your `.env` file, replacing the placeholder values with your own ID and secret.
> ```
> SPOTIPY_CLIENT_ID=IdGoesHere
> SPOTIPY_CLIENT_SECRET=SecretGoesHere
> ```
