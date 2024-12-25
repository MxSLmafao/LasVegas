import os
import discord
from discord import app_commands
from discord.ext import commands
from db.database import init_db
import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

class BlackjackBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guild_messages = True  # Enable guild messages intent
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        try:
            print('Initializing database...')
            await init_db()
            print('Loading extensions...')
            await self.load_extension('cogs.commands')
            await self.load_extension('cogs.game_manager')
            await self.load_extension('cogs.roulette_manager')  # Add this line
            print('Syncing command tree...')
            await self.tree.sync()
            print('Setup completed successfully!')
        except Exception as e:
            print(f'Error during setup: {str(e)}')
            raise

    async def on_ready(self):
        print('Bot is starting...')
        print(f'Logged in as {self.user.name} (ID: {self.user.id})')
        print('------')
        await self.change_presence(activity=discord.Game(name="Blackjack & Roulette"))

async def main():
    try:
        print('Starting bot...')
        bot = BlackjackBot()
        print('Bot instance created')
        async with bot:
            print('Connecting to Discord...')
            await bot.start(os.environ['DISCORD_TOKEN'])
    except Exception as e:
        print(f'Fatal error: {str(e)}')
        raise

if __name__ == '__main__':
    asyncio.run(main())