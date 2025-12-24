import discord
from discord import app_commands, TextStyle
from redbot.core import commands
import logging

log = logging.getLogger("red.agegate_slash")


class MinAgeModal(discord.ui.Modal):
    """Modal for setting minimum account age in seconds."""

    def __init__(self, agegate_cog, guild: discord.Guild):
        super().__init__(title="Set Minimum Account Age")
        self.agegate_cog = agegate_cog
        self.guild = guild

        self.days = discord.ui.TextInput(
            label="Days",
            placeholder="e.g., 7",
            default="7",
            min_length=1,
            max_length=3,
        )
        self.hours = discord.ui.TextInput(
            label="Hours (0-23)",
            placeholder="e.g., 0",
            default="0",
            min_length=1,
            max_length=2,
            required=False,
        )
        self.add_item(self.days)
        self.add_item(self.hours)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            days = int(self.days.value)
            hours = int(self.hours.value) if self.hours.value else 0

            if days < 0 or hours < 0 or hours > 23:
                await interaction.response.send_message(
                    "❌ Days must be ≥ 0 and hours must be 0-23.",
                    ephemeral=True,
                )
                return

            total_seconds = (days * 86400) + (hours * 3600)
            await self.agegate_cog.config.guild(self.guild).min_age_seconds.set(
                total_seconds
            )

            readable = self.agegate_cog._seconds_to_readable(total_seconds)
            await interaction.response.send_message(
                f"✅ Minimum account age set to **{readable}**",
                ephemeral=True,
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter valid numbers.", ephemeral=True
            )


class BanReasonModal(discord.ui.Modal):
    """Modal