import discord
from discord import app_commands
from discord.ext import commands
from db.database import create_user, get_balance, update_balance, get_leaderboard, delete_user, set_balance
from typing import Optional
from decimal import Decimal, InvalidOperation
import logging
import aiohttp
from io import BytesIO

ADMIN_USER_ID = 791177475190161419
PLAYERLIST_CATEGORY_ID = 1224364527911571509
PLAYERLIST_USER_ID = 1290059415185129575
PLAYERLIST_IMAGE_URL = "http://files.raw-tea.xyz/files/Screenshot_2024-12-19-10-34-04-782_com.discord.png"

logger = logging.getLogger('discord')

class Commands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_member = None
        logger.info("Commands cog initialized")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore messages from bots
        if message.author.bot:
            return

        try:
            # Debug log for message received
            logger.info(f"Message received in channel {message.channel.id}: {message.content}")

            # Check if message is in the specified category
            if not hasattr(message.channel, 'category_id') or message.channel.category_id != PLAYERLIST_CATEGORY_ID:
                logger.debug(f"Message not in target category. Channel category ID: {getattr(message.channel, 'category_id', None)}")
                return

            # Check if message is exactly "playerlist" or "Playerlist"
            if message.content.lower() != "playerlist":
                logger.debug(f"Message content not matching: {message.content}")
                return

            logger.info("Valid playerlist command received, processing...")

            # Get the user whose avatar we'll use
            user = await self.bot.fetch_user(PLAYERLIST_USER_ID)
            if not user:
                logger.error(f"Could not fetch user {PLAYERLIST_USER_ID}")
                return

            # Download the image
            async with aiohttp.ClientSession() as session:
                logger.info(f"Downloading image from {PLAYERLIST_IMAGE_URL}")
                async with session.get(PLAYERLIST_IMAGE_URL) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download image: {response.status}")
                        return
                    image_data = await response.read()
                    logger.info("Image downloaded successfully")

            # Create webhook
            logger.info("Creating webhook...")
            webhook = await message.channel.create_webhook(name=user.name)
            logger.info(f"Webhook created with name: {webhook.name}")

            try:
                # Send message with webhook using BytesIO for the image
                image_file = discord.File(BytesIO(image_data), filename="playerlist.png")
                logger.info("Sending webhook message with image...")
                await webhook.send(
                    username=user.name,
                    avatar_url=user.avatar.url if user.avatar else None,
                    file=image_file
                )
                logger.info("Webhook message sent successfully")
            finally:
                # Always clean up the webhook
                try:
                    await webhook.delete()
                    logger.info("Webhook cleaned up successfully")
                except Exception as e:
                    logger.error(f"Error cleaning up webhook: {str(e)}")

        except aiohttp.ClientError as e:
            logger.error(f"Error downloading image: {str(e)}")
        except discord.Forbidden as e:
            logger.error(f"Permission error: {str(e)}")
        except discord.HTTPException as e:
            logger.error(f"Discord HTTP error: {str(e)}")
        except Exception as e:
            logger.error(f"Error in playerlist webhook: {str(e)}", exc_info=True)

    @app_commands.command(name="help", description="Shows all available commands")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎲 Blackjack Bot Commands",
            description="Here are all the available commands:",
            color=discord.Color.blue()
        )

        commands_info = [
            ("challenge", "Challenge a user to Blackjack with a wager"),
            ("new", "Create a new account with $100 starting balance"),
            ("bal", "Check your current balance"),
            ("dep", "Deposit money to another user"),
            ("lb", "Show top 5 richest users"),
            ("help", "Shows this help message")
        ]

        for name, desc in commands_info:
            embed.add_field(
                name=f"/{name}",
                value=desc,
                inline=False
            )

        if interaction.user.id == ADMIN_USER_ID:
            admin_commands = [
                ("da", "[Admin] Delete a user's account"),
                ("give", "[Admin] Give money to a user")
            ]
            embed.add_field(
                name="\nAdmin Commands",
                value="\n".join([f"/{cmd} - {desc}" for cmd, desc in admin_commands]),
                inline=False
            )

        await interaction.response.send_message(embed=embed)

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

    @app_commands.command(name="da", description="[Admin] Delete a user's account")
    @app_commands.describe(user="User whose account to delete")
    async def delete_account(self, interaction: discord.Interaction, user: discord.User):
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return

        success = await delete_user(user.id)
        if success:
            await interaction.response.send_message(f"Successfully deleted {user.name}'s account.")
        else:
            await interaction.response.send_message(f"Failed to delete account: User {user.name} doesn't have an account.")

    @app_commands.command(name="give", description="[Admin] Give money to a user")
    @app_commands.describe(user="User to give money to", amount="Amount to give")
    async def give_money(self, interaction: discord.Interaction, user: discord.User, amount: float):
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("Amount must be positive!", ephemeral=True)
            return

        current_balance = await get_balance(user.id)
        if current_balance is None:
            await interaction.response.send_message(f"Failed: User {user.name} doesn't have an account.", ephemeral=True)
            return

        try:
            # Convert float to Decimal before addition
            new_balance = current_balance + Decimal(str(amount))
            success = await set_balance(user.id, new_balance)

            if success:
                await interaction.response.send_message(
                    f"Successfully given ${amount:.2f} to {user.name}.\nTheir new balance is ${new_balance:.2f}"
                )
            else:
                await interaction.response.send_message(f"Failed to update {user.name}'s balance.", ephemeral=True)
        except (InvalidOperation, ValueError) as e:
            await interaction.response.send_message(f"Error processing amount: Invalid number format", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Commands(bot))