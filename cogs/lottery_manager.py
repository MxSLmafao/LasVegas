import discord
from discord import app_commands
from discord.ext import commands, tasks
from db.database import (
    get_balance, update_balance, create_lottery, 
    add_lottery_entry, get_active_lottery,
    get_lottery_entries, set_lottery_winner
)
from typing import Optional, Dict
import logging
from datetime import datetime, timedelta
import random
from decimal import Decimal

logger = logging.getLogger('discord')

ADMIN_USER_ID = 791177475190161419  # Same as in commands.py
ENTRY_FEE = Decimal('2.0')

class LotteryManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_lottery: Optional[dict] = None
        self._check_lottery_loop = tasks.loop(minutes=1)(self.check_lottery)
        self._check_lottery_loop.start()
        logger.info("LotteryManager initialized")

    def cog_unload(self):
        self._check_lottery_loop.cancel()

    @app_commands.command(name="lotto", description="[Admin] Start a new lottery with custom prize")
    @app_commands.describe(prize="Prize amount for the lottery winner")
    async def start_lottery(self, interaction: discord.Interaction, prize: float):
        # Check if user is admin
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message(
                "You don't have permission to use this command!", 
                ephemeral=True
            )
            return

        # Validate prize amount
        if prize <= 0:
            await interaction.response.send_message(
                "Prize amount must be positive!", 
                ephemeral=True
            )
            return

        try:
            # Check if there's already an active lottery
            active_lottery = await get_active_lottery()
            if active_lottery:
                time_left = active_lottery['end_time'] - datetime.now()
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)

                await interaction.response.send_message(
                    f"There's already an active lottery!\n"
                    f"Time remaining: {hours}h {minutes}m\n"
                    f"Current prize: ${active_lottery['prize_amount']:.2f}",
                    ephemeral=True
                )
                return

            # Create new lottery
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=6)
            lottery_id = await create_lottery(start_time, end_time, Decimal(str(prize)))

            # Create embed with lottery information
            embed = discord.Embed(
                title="🎰 New Lottery Started!",
                description=(
                    "A new lottery round has begun!\n"
                    f"Entry fee: ${ENTRY_FEE:.2f}\n"
                    f"Prize pool: ${prize:.2f} 🏆"
                ),
                color=discord.Color.gold()
            )

            embed.add_field(
                name="How to Join",
                value="Click the button below to enter!",
                inline=False
            )

            embed.add_field(
                name="End Time",
                value=f"<t:{int(end_time.timestamp())}:R>",
                inline=False
            )

            # Create join button
            join_button = discord.ui.Button(
                label="Join Lottery", 
                style=discord.ButtonStyle.primary, 
                custom_id=f"lottery_join_{lottery_id}"
            )

            view = discord.ui.View()
            view.add_item(join_button)

            await interaction.response.send_message(embed=embed, view=view)
            self.active_lottery = {
                'lottery_id': lottery_id,
                'start_time': start_time,
                'end_time': end_time,
                'prize_amount': Decimal(str(prize)),
                'total_pot': Decimal('0')
            }
            logger.info(f"New lottery {lottery_id} started by admin {interaction.user.id} with prize ${prize:.2f}")

        except Exception as e:
            logger.error(f"Error starting lottery: {str(e)}")
            await interaction.response.send_message(
                "An error occurred while starting the lottery. Please try again.",
                ephemeral=True
            )

    @app_commands.command(name="lottoend", description="[Admin] End the current lottery early")
    async def end_lottery(self, interaction: discord.Interaction):
        # Check if user is admin
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message(
                "You don't have permission to use this command!", 
                ephemeral=True
            )
            return

        try:
            # Check if there's an active lottery
            active_lottery = await get_active_lottery()
            if not active_lottery:
                await interaction.response.send_message(
                    "There is no active lottery to end!",
                    ephemeral=True
                )
                return

            # Get all entries
            entries = await get_lottery_entries(active_lottery['lottery_id'])

            if entries:
                # Select winner and distribute prize
                winner_id = random.choice(entries)
                await set_lottery_winner(active_lottery['lottery_id'], winner_id)

                # Give prize to winner
                winner_prize = active_lottery['prize_amount']
                await update_balance(winner_id, float(winner_prize))

                try:
                    winner = await self.bot.fetch_user(winner_id)
                    embed = discord.Embed(
                        title="🎰 Lottery Ended Early!",
                        description=(
                            "The lottery has been ended early by an administrator!\n\n"
                            f"🏆 Winner: {winner.mention}\n"
                            f"💰 Prize: ${winner_prize:.2f}\n\n"
                            "Congratulations! 🎉"
                        ),
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed)
                except Exception as e:
                    logger.error(f"Error announcing lottery winner: {str(e)}")
                    await interaction.response.send_message(
                        "An error occurred while announcing the winner.",
                        ephemeral=True
                    )
            else:
                # No entries case
                await set_lottery_winner(active_lottery['lottery_id'], None)
                embed = discord.Embed(
                    title="🎰 Lottery Ended Early!",
                    description=(
                        "The lottery has been ended early by an administrator!\n\n"
                        "❌ No entries were made in this lottery.\n"
                        "No prize will be distributed."
                    ),
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error ending lottery: {str(e)}")
            await interaction.response.send_message(
                "An error occurred while ending the lottery. Please try again.",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or not isinstance(interaction.data.get('custom_id', ''), str):
            return

        custom_id = interaction.data['custom_id']
        if not custom_id.startswith('lottery_join_'):
            return

        try:
            lottery_id = int(custom_id.split('_')[2])
            await self.handle_lottery_join(interaction, lottery_id)
        except ValueError:
            logger.error(f"Invalid lottery ID in custom_id: {custom_id}")

    async def handle_lottery_join(self, interaction: discord.Interaction, lottery_id: int):
        """Handle a user attempting to join a lottery"""
        try:
            # Check if user has an account
            balance = await get_balance(interaction.user.id)
            if balance is None:
                await interaction.response.send_message(
                    "You need an account to join the lottery!\nUse /new to create one.",
                    ephemeral=True
                )
                return

            # Check if user has enough balance
            if balance < ENTRY_FEE:
                await interaction.response.send_message(
                    f"You need ${ENTRY_FEE:.2f} to join the lottery!\n"
                    f"Your current balance: ${balance:.2f}",
                    ephemeral=True
                )
                return

            # Try to add entry
            if await add_lottery_entry(lottery_id, interaction.user.id):
                # Deduct entry fee
                if await update_balance(interaction.user.id, float(-ENTRY_FEE)):
                    await interaction.response.send_message(
                        "You've successfully entered the lottery! Good luck! 🍀",
                        ephemeral=True
                    )

                    # Update the embed with total entries
                    if isinstance(interaction.message, discord.Message):
                        active_lottery = await get_active_lottery()
                        if active_lottery:
                            entries = await get_lottery_entries(active_lottery['lottery_id'])
                            embed = interaction.message.embeds[0]

                            # Update or add fields
                            embed.clear_fields()
                            embed.add_field(
                                name="Prize Pool",
                                value=f"${active_lottery['prize_amount']:.2f} 🏆",
                                inline=True
                            )
                            embed.add_field(
                                name="Entry Fee",
                                value=f"${ENTRY_FEE:.2f} 💰",
                                inline=True
                            )
                            embed.add_field(
                                name="Total Entries",
                                value=f"{len(entries)} tickets sold 🎫",
                                inline=True
                            )
                            embed.add_field(
                                name="Entry Pot",
                                value=f"${active_lottery['total_pot']:.2f} 💵",
                                inline=True
                            )
                            embed.add_field(
                                name="End Time",
                                value=f"<t:{int(active_lottery['end_time'].timestamp())}:R>",
                                inline=True
                            )

                            await interaction.message.edit(embed=embed)
                else:
                    logger.error(f"Failed to update balance for user {interaction.user.id}")
                    await interaction.response.send_message(
                        "An error occurred while processing your entry. Please try again.",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "You've already joined this lottery or the lottery has ended!",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in lottery join: {str(e)}")
            await interaction.response.send_message(
                "An error occurred while joining the lottery. Please try again later.",
                ephemeral=True
            )

    async def check_lottery(self):
        """Check and process expired lotteries"""
        try:
            active_lottery = await get_active_lottery()
            if not active_lottery or datetime.now() < active_lottery['end_time']:
                return

            # Get all entries
            entries = await get_lottery_entries(active_lottery['lottery_id'])

            if entries:
                # Select winner
                winner_id = random.choice(entries)
                await set_lottery_winner(active_lottery['lottery_id'], winner_id)

                # Give prize to winner
                winner_prize = active_lottery['prize_amount']
                await update_balance(winner_id, float(winner_prize))

                # Announce winner
                try:
                    winner = await self.bot.fetch_user(winner_id)
                    for guild in self.bot.guilds:
                        for channel in guild.text_channels:
                            try:
                                embed = discord.Embed(
                                    title="🎰 Lottery Results!",
                                    description=(
                                        f"The lottery has ended!\n\n"
                                        f"🏆 Winner: {winner.mention}\n"
                                        f"💰 Prize: ${winner_prize:.2f}\n\n"
                                        "Congratulations! 🎉"
                                    ),
                                    color=discord.Color.green()
                                )
                                await channel.send(embed=embed)
                                break  # Send to first available channel only
                            except discord.Forbidden:
                                continue
                except Exception as e:
                    logger.error(f"Error announcing lottery winner: {str(e)}")
            else:
                # No entries case
                await set_lottery_winner(active_lottery['lottery_id'], None)
                logger.warning(f"Lottery {active_lottery['lottery_id']} ended with no entries")

        except Exception as e:
            logger.error(f"Error in lottery check loop: {str(e)}")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._check_lottery_loop.is_running():
            self._check_lottery_loop.start()

async def setup(bot: commands.Bot):
    await bot.add_cog(LotteryManager(bot))