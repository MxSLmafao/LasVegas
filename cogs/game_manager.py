import discord
from discord import app_commands
from discord.ext import commands
from game.blackjack import BlackjackGame
from db.database import get_balance, update_balance
from typing import Dict, Optional

class GameManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pending_challenges: Dict[int, tuple] = {}  # challenger_id: (challenged_id, wager)
        self.active_games: Dict[int, BlackjackGame] = {}  # player_id: game

    @app_commands.command(name="challenge", description="Challenge a user to Blackjack")
    @app_commands.describe(user="User to challenge", wager="Amount to wager")
    async def challenge(self, interaction: discord.Interaction, user: discord.User, wager: float):
        if wager <= 0:
            await interaction.response.send_message("Wager must be positive!")
            return

        challenger_balance = await get_balance(interaction.user.id)
        challenged_balance = await get_balance(user.id)

        if not challenger_balance or not challenged_balance:
            await interaction.response.send_message("Both players must have accounts!")
            return

        if challenger_balance < wager or challenged_balance < wager:
            await interaction.response.send_message("Insufficient funds!")
            return

        self.pending_challenges[interaction.user.id] = (user.id, wager)

        accept_button = discord.ui.Button(label="Accept", style=discord.ButtonStyle.green, custom_id="accept")
        deny_button = discord.ui.Button(label="Deny", style=discord.ButtonStyle.red, custom_id="deny")
        withdraw_button = discord.ui.Button(label="Withdraw", style=discord.ButtonStyle.gray, custom_id="withdraw")

        view = discord.ui.View()
        view.add_item(accept_button)
        view.add_item(deny_button)
        view.add_item(withdraw_button)

        embed = discord.Embed(
            title="Blackjack Challenge!",
            description=f"{interaction.user.mention} challenges {user.mention} for ${wager:.2f}!",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.message or not interaction.data:
            return

        custom_id = interaction.data.get("custom_id")
        if not custom_id in ["accept", "deny", "withdraw", "hit", "call"]:
            return

        if custom_id in ["accept", "deny", "withdraw"]:
            await self.handle_challenge_response(interaction, custom_id)
        else:
            await self.handle_game_action(interaction, custom_id)

    async def handle_challenge_response(self, interaction: discord.Interaction, action: str):
        for challenger_id, (challenged_id, wager) in self.pending_challenges.items():
            if action == "accept" and interaction.user.id == challenged_id:
                game = BlackjackGame(challenger_id, challenged_id, wager)
                self.active_games[challenger_id] = game
                self.active_games[challenged_id] = game
                game.deal_initial_cards()
                
                await self.send_game_state(game)
                del self.pending_challenges[challenger_id]
                await interaction.message.delete()
                
            elif action == "deny" and interaction.user.id == challenged_id:
                del self.pending_challenges[challenger_id]
                await interaction.message.edit(content="Challenge denied!", view=None)
                
            elif action == "withdraw" and interaction.user.id == challenger_id:
                del self.pending_challenges[challenger_id]
                await interaction.message.edit(content="Challenge withdrawn!", view=None)

    async def handle_game_action(self, interaction: discord.Interaction, action: str):
        game = self.active_games.get(interaction.user.id)
        if not game or game.current_turn != interaction.user.id:
            return

        if action == "hit":
            card = game.hit(interaction.user.id)
            await self.send_game_state(game)
            
            if game.is_bust(interaction.user.id):
                await self.end_game(game)
                
        elif action == "call":
            if game.current_turn == game.player1_id:
                game.current_turn = game.player2_id
                await self.send_game_state(game)
            else:
                await self.end_game(game)

    async def send_game_state(self, game: BlackjackGame):
        for player_id in [game.player1_id, game.player2_id]:
            user = await self.bot.fetch_user(player_id)
            if user:
                embed = discord.Embed(
                    title="Blackjack Game",
                    description=f"Wager: ${game.wager:.2f}",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="Your Hand",
                    value=f"{game.get_hand_display(player_id)} (Score: {game.get_score(player_id)})",
                    inline=False
                )

                view = discord.ui.View()
                if game.current_turn == player_id and not game.game_ended:
                    hit_button = discord.ui.Button(label="Hit", style=discord.ButtonStyle.primary, custom_id="hit")
                    call_button = discord.ui.Button(label="Call", style=discord.ButtonStyle.secondary, custom_id="call")
                    view.add_item(hit_button)
                    view.add_item(call_button)

                await user.send(embed=embed, view=view)

    async def end_game(self, game: BlackjackGame):
        winner_id = game.determine_winner()
        
        if winner_id == 0:  # Draw
            await update_balance(game.player1_id, 0)
            await update_balance(game.player2_id, 0)
            result_message = "It's a draw!"
        else:
            winner = await self.bot.fetch_user(winner_id)
            loser_id = game.player2_id if winner_id == game.player1_id else game.player1_id
            
            await update_balance(winner_id, game.wager)
            await update_balance(loser_id, -game.wager)
            result_message = f"{winner.name} wins ${game.wager:.2f}!"

        game.game_ended = True
        
        for player_id in [game.player1_id, game.player2_id]:
            user = await self.bot.fetch_user(player_id)
            if user:
                embed = discord.Embed(
                    title="Game Over",
                    description=result_message,
                    color=discord.Color.gold()
                )
                await user.send(embed=embed)

        del self.active_games[game.player1_id]
        del self.active_games[game.player2_id]

async def setup(bot: commands.Bot):
    await bot.add_cog(GameManager(bot))
