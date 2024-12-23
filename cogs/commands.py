import discord
from discord import app_commands
from discord.ext import commands
from db.database import create_user, get_balance, update_balance, get_leaderboard
from typing import Optional

class Commands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="new", description="Create a new account with $100 starting balance")
    async def new_account(self, interaction: discord.Interaction):
        success = await create_user(interaction.user.id, interaction.user.name)
        if success:
            await interaction.response.send_message("Account created successfully with $100!")
        else:
            await interaction.response.send_message("You already have an account!")

    @app_commands.command(name="bal", description="Check your balance")
    async def balance(self, interaction: discord.Interaction):
        balance = await get_balance(interaction.user.id)
        if balance is not None:
            await interaction.response.send_message(f"Your balance: ${balance:.2f}")
        else:
            await interaction.response.send_message("You don't have an account! Use /new to create one.")

    @app_commands.command(name="dep", description="Deposit money to another user")
    @app_commands.describe(user="User to send money to", amount="Amount to send")
    async def deposit(self, interaction: discord.Interaction, user: discord.User, amount: float):
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive!")
            return

        sender_balance = await get_balance(interaction.user.id)
        if sender_balance is None:
            await interaction.response.send_message("You don't have an account!")
            return

        if sender_balance < amount:
            await interaction.response.send_message("Insufficient funds!")
            return

        receiver_balance = await get_balance(user.id)
        if receiver_balance is None:
            await interaction.response.send_message("Recipient doesn't have an account!")
            return

        await update_balance(interaction.user.id, -amount)
        await update_balance(user.id, amount)
        await interaction.response.send_message(f"Successfully sent ${amount:.2f} to {user.name}")

    @app_commands.command(name="lb", description="Show top 5 richest users")
    async def leaderboard(self, interaction: discord.Interaction):
        leaders = await get_leaderboard()
        
        embed = discord.Embed(title="🏆 Richest Players", color=discord.Color.gold())
        for i, (username, balance) in enumerate(leaders, 1):
            embed.add_field(
                name=f"{i}. {username}",
                value=f"${balance:.2f}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Commands(bot))
