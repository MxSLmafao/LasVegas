import discord
from discord import app_commands
from discord.ext import commands
from game.roulette import RouletteGame
from db.database import get_balance, update_balance
from typing import Dict, Optional
import logging
from decimal import Decimal

logger = logging.getLogger('discord')

class RouletteManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_tables: Dict[str, RouletteGame] = {}  # table_id: game
        self.player_tables: Dict[int, str] = {}  # player_id: table_id
        logger.info("RouletteManager initialized")

    @app_commands.command(name="roulette", description="Start a new roulette table")
    async def create_table(self, interaction: discord.Interaction):
        # Check if player already in a game
        if interaction.user.id in self.player_tables:
            await interaction.response.send_message("You're already at a roulette table!")
            return

        # Check if player has an account
        balance = await get_balance(interaction.user.id)
        if balance is None:
            await interaction.response.send_message("You need an account to play! Use /new to create one.")
            return

        # Create new table
        game = RouletteGame(interaction.user.id)
        self.active_tables[game.table_id] = game
        self.player_tables[interaction.user.id] = game.table_id

        await interaction.response.send_message(
            f"Roulette table created! Table ID: {game.table_id}\n"
            f"Other players can join using `/join {game.table_id}`\n"
            f"Start the game with `/start {game.table_id}` once players have joined."
        )

    @app_commands.command(name="join", description="Join a roulette table")
    @app_commands.describe(table_id="The ID of the table to join")
    async def join_table(self, interaction: discord.Interaction, table_id: str):
        # Check if player already in a game
        if interaction.user.id in self.player_tables:
            await interaction.response.send_message("You're already at a roulette table!")
            return

        # Check if player has an account
        balance = await get_balance(interaction.user.id)
        if balance is None:
            await interaction.response.send_message("You need an account to play! Use /new to create one.")
            return

        # Check if table exists
        game = self.active_tables.get(table_id)
        if not game:
            await interaction.response.send_message("Table not found!")
            return

        # Try to join the table
        if game.add_player(interaction.user.id):
            self.player_tables[interaction.user.id] = table_id
            await interaction.response.send_message(f"You've joined the roulette table {table_id}!")
        else:
            await interaction.response.send_message("Couldn't join the table. Game might have already started.")

    @app_commands.command(name="start", description="Start the roulette game")
    @app_commands.describe(table_id="The ID of the table to start")
    async def start_game(self, interaction: discord.Interaction, table_id: str):
        # Check if table exists
        game = self.active_tables.get(table_id)
        if not game:
            await interaction.response.send_message("Table not found!")
            return

        # Try to start the game
        if game.start_game(interaction.user.id):
            await interaction.response.send_message("The roulette game has started! Check your DMs for betting instructions.")
            
            # Send DMs to all players
            for player_id in game.players:
                try:
                    user = await self.bot.fetch_user(player_id)
                    if user:
                        embed = discord.Embed(
                            title="🎲 Roulette Game",
                            description="Choose a pocket number between 1 and 36.\n"
                                      "Simply type the number in this DM.",
                            color=discord.Color.green()
                        )
                        await user.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error sending DM to user {player_id}: {str(e)}")
        else:
            await interaction.response.send_message(
                "Couldn't start the game. Make sure:\n"
                "1. You're the table creator\n"
                "2. There are at least 2 players\n"
                "3. The game hasn't already started"
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore messages from bots or in non-DM channels
        if message.author.bot or not isinstance(message.channel, discord.DMChannel):
            return

        # Check if player is in a game
        table_id = self.player_tables.get(message.author.id)
        if not table_id:
            return

        game = self.active_tables.get(table_id)
        if not game or not game.game_started:
            return

        # Handle pocket selection
        if message.author.id not in game.player_choices:
            try:
                pocket = int(message.content)
                if game.set_player_choice(message.author.id, pocket):
                    await message.author.send(
                        f"You chose pocket {pocket} ({game.get_color(pocket)}).\n"
                        f"Now, how much would you like to bet? Type the amount (e.g., 100)."
                    )
                else:
                    await message.author.send("Please choose a number between 1 and 36.")
            except ValueError:
                await message.author.send("Please enter a valid number between 1 and 36.")
            return

        # Handle bet amount
        if message.author.id not in game.player_bets:
            try:
                bet_amount = Decimal(message.content)
                player_balance = await get_balance(message.author.id)
                
                if bet_amount <= 0:
                    await message.author.send("Bet amount must be positive!")
                    return
                
                if player_balance < bet_amount:
                    await message.author.send("Insufficient funds!")
                    return

                if game.set_player_bet(message.author.id, bet_amount):
                    await message.author.send(f"You bet ${bet_amount:.2f}. Waiting for other players...")
                    
                    # Check if all players have bet
                    if game.is_ready_to_spin():
                        await self.spin_and_resolve(game)
            except (ValueError, InvalidOperation):
                await message.author.send("Please enter a valid bet amount (e.g., 100).")

    async def spin_and_resolve(self, game: RouletteGame):
        winning_number = game.spin()
        winners = game.get_winners()

        # Update balances and send results
        for player_id in game.players:
            # Deduct initial bets
            await update_balance(player_id, -game.player_bets[player_id])
            
            # Add winnings if any
            if player_id in winners:
                await update_balance(player_id, winners[player_id])

            # Send result message
            try:
                user = await self.bot.fetch_user(player_id)
                if user:
                    embed = discord.Embed(
                        title="🎲 Roulette Results",
                        description=f"The ball landed on {winning_number} ({game.get_color(winning_number)})!",
                        color=discord.Color.gold()
                    )
                    
                    if player_id in winners:
                        embed.add_field(
                            name="Result",
                            value=f"Congratulations! You won ${winners[player_id]:.2f}!",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="Result",
                            value=f"Sorry, you lost ${game.player_bets[player_id]:.2f}.",
                            inline=False
                        )
                    
                    await user.send(embed=embed)
            except Exception as e:
                logger.error(f"Error sending result to user {player_id}: {str(e)}")

        # Clean up game state
        table_id = game.table_id
        for player_id in game.players:
            if player_id in self.player_tables:
                del self.player_tables[player_id]
        if table_id in self.active_tables:
            del self.active_tables[table_id]

async def setup(bot: commands.Bot):
    await bot.add_cog(RouletteManager(bot))
