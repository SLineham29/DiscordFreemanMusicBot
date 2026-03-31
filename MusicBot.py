import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("BOT_TOKEN")

class MusicBot(commands.Bot):
    def __init__(self):
        # This is basically the bots permissions, it can send messages and join voice channels.
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.load_extension("MusicControlsCog")
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")

bot = MusicBot()
bot.run(token)
