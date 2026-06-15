import datetime
import math
import discord

class QueueCreator(discord.ui.View):
    def __init__(self, given_queue: list):
        super().__init__(timeout=120)
        self.queue = given_queue
        self.max_per_page = 10
        self.max_pages = math.ceil(len(self.queue) / self.max_per_page)
        self.current_page = 0
        self.queue_runtime = 0

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    def create_queue_embed(self):
        embed = discord.Embed(
            colour=discord.Colour.blue()
        )
        match(len(self.queue)):
            case 0:
                embed.title="There is currently nothing in the queue."
                embed.colour=discord.Colour.brand_red()
                self.previous_page.disabled = True
                self.next_page.disabled = True
                return embed
            case 1:
                embed.title="Queue Length: 1 Song"
            case _:
                embed.title=f"Queue Length: {len(self.queue)} Songs"

        start_index = self.current_page * self.max_per_page
        end_index = start_index + self.max_per_page
        page_songs = self.queue[start_index:end_index]
        queue_string = ""

        self.queue_runtime = 0
        for song in self.queue:
            self.queue_runtime += song.get('duration')

        for position, song in enumerate(page_songs, start=start_index + 1):
            queue_string += f"**{position})** {song.get('title')} - Added By <@{song['user_id']}>\n"

        embed.description = queue_string
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.max_pages} | Total Runtime: {datetime.timedelta(seconds=self.queue_runtime)}")
        self.update_buttons()
        return embed

    async def check_if_in_vc(self, interaction: discord.Interaction):
        bot_vc = interaction.guild.voice_client
        user_vc = interaction.user.voice

        if not user_vc or not user_vc.channel:
            await interaction.response.send_message("Join the same voice channel as the bot to change the queue pages.", ephemeral=True)
            return False

        if user_vc.channel.id != bot_vc.channel.id:
            await interaction.response.send_message("Join the same voice channel as the bot to change the queue pages.", ephemeral=True)
            return False

        return True

    def update_buttons(self):
        self.previous_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == self.max_pages - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):

        is_valid = await self.check_if_in_vc(interaction)
        if not is_valid:
            return

        if self.current_page == 0:
            interaction.response.send_message("Already on the first page...", ephemeral=True)
            return
        self.current_page -= 1
        self.update_buttons()

        await interaction.response.edit_message(embed=self.create_queue_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.grey, emoji="➡️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_valid = await self.check_if_in_vc(interaction)
        if not is_valid:
            return

        if self.current_page == self.max_pages - 1:
            interaction.response.send_message("Already on the last page...", ephemeral=True)
            return
        self.current_page += 1
        self.update_buttons()

        await interaction.response.edit_message(embed=self.create_queue_embed(), view=self)