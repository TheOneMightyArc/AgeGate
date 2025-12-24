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
    """Modal for setting ban reason."""

    def __init__(self, agegate_cog, guild: discord.Guild):
        super().__init__(title="Set Ban Reason")
        self.agegate_cog = agegate_cog
        self.guild = guild

        self.reason = discord.ui.TextInput(
            label="Ban Reason",
            placeholder="Enter the reason for banning new accounts...",
            default="Your account is too new. Please wait until your account is older to join.",
            min_length=1,
            max_length=512,
            style=TextStyle.long,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await self.agegate_cog.config.guild(self.guild).ban_reason.set(self.reason.value)
        await interaction.response.send_message(
            "✅ Ban reason saved.",
            ephemeral=True,
        )


class ActionTypeModal(discord.ui.Modal):
    """Modal for setting action type."""

    def __init__(self, agegate_cog, guild: discord.Guild):
        super().__init__(title="Set Action Type")
        self.agegate_cog = agegate_cog
        self.guild = guild

        self.action = discord.ui.TextInput(
            label="Action Type (ban/delay/notify)",
            placeholder="ban / delay / notify",
            default="ban",
            min_length=3,
            max_length=6,
        )
        self.add_item(self.action)

    async def on_submit(self, interaction: discord.Interaction):
        action = self.action.value.lower()
        if action not in ["ban", "delay", "notify"]:
            await interaction.response.send_message(
                "❌ Invalid action type. Use `ban`, `delay`, or `notify`.",
                ephemeral=True,
            )
            return

        await self.agegate_cog.config.guild(self.guild).action_type.set(action)
        await interaction.response.send_message(
            f"✅ Action type set to **{action}**.",
            ephemeral=True,
        )


class BanTypeModal(discord.ui.Modal):
    """Modal for setting ban type."""

    def __init__(self, agegate_cog, guild: discord.Guild):
        super().__init__(title="Set Ban Type")
        self.agegate_cog = agegate_cog
        self.guild = guild

        self.ban_type = discord.ui.TextInput(
            label="Ban Type (permanent/temporary)",
            placeholder="permanent / temporary",
            default="permanent",
            min_length=7,
            max_length=9,
        )
        self.add_item(self.ban_type)

    async def on_submit(self, interaction: discord.Interaction):
        ban_type = self.ban_type.value.lower()
        if ban_type not in ["permanent", "temporary"]:
            await interaction.response.send_message(
                "❌ Invalid ban type. Use `permanent` or `temporary`.",
                ephemeral=True,
            )
            return

        await self.agegate_cog.config.guild(self.guild).ban_type.set(ban_type)
        await interaction.response.send_message(
            f"✅ Ban type set to **{ban_type}**.",
            ephemeral=True,
        )


class TempBanDurationModal(discord.ui.Modal):
    """Modal for setting temporary ban duration."""

    def __init__(self, agegate_cog, guild: discord.Guild):
        super().__init__(title="Set Temp Ban Duration")
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

            if days <= 0 or hours < 0 or hours > 23:
                await interaction.response.send_message(
                    "❌ Days must be > 0 and hours must be 0-23.",
                    ephemeral=True,
                )
                return

            total_seconds = (days * 86400) + (hours * 3600)
            await self.agegate_cog.config.guild(self.guild).temp_ban_duration_seconds.set(
                total_seconds
            )

            readable = self.agegate_cog._seconds_to_readable(total_seconds)
            await interaction.response.send_message(
                f"✅ Temporary ban duration set to **{readable}**",
                ephemeral=True,
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter valid numbers.", ephemeral=True
            )


class DelayDurationModal(discord.ui.Modal):
    """Modal for setting delay punishment duration."""

    def __init__(self, agegate_cog, guild: discord.Guild):
        super().__init__(title="Set Delay Duration")
        self.agegate_cog = agegate_cog
        self.guild = guild

        self.hours = discord.ui.TextInput(
            label="Hours",
            placeholder="e.g., 24",
            default="24",
            min_length=1,
            max_length=4,
        )
        self.minutes = discord.ui.TextInput(
            label="Minutes (0-59)",
            placeholder="e.g., 0",
            default="0",
            min_length=1,
            max_length=2,
            required=False,
        )
        self.add_item(self.hours)
        self.add_item(self.minutes)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            hours = int(self.hours.value)
            minutes = int(self.minutes.value) if self.minutes.value else 0

            if hours <= 0 or minutes < 0 or minutes > 59:
                await interaction.response.send_message(
                    "❌ Hours must be > 0 and minutes must be 0-59.",
                    ephemeral=True,
                )
                return

            total_seconds = (hours * 3600) + (minutes * 60)
            await self.agegate_cog.config.guild(self.guild).delay_punishment_seconds.set(
                total_seconds
            )

            readable = self.agegate_cog._seconds_to_readable(total_seconds)
            await interaction.response.send_message(
                f"✅ Delay duration set to **{readable}**",
                ephemeral=True,
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter valid numbers.", ephemeral=True
            )


class RateLimitModal(discord.ui.Modal):
    """Modal for setting rate limit."""

    def __init__(self, agegate_cog, guild: discord.Guild):
        super().__init__(title="Set Rate Limit")
        self.agegate_cog = agegate_cog
        self.guild = guild

        self.bans_per_minute = discord.ui.TextInput(
            label="Bans Per Minute",
            placeholder="e.g., 5",
            default="5",
            min_length=1,
            max_length=2,
        )
        self.add_item(self.bans_per_minute)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rate = int(self.bans_per_minute.value)

            if rate <= 0:
                await interaction.response.send_message(
                    "❌ Rate limit must be > 0",
                    ephemeral=True,
                )
                return

            await self.agegate_cog.config.guild(self.guild).join_rate_limit.set(rate)
            await interaction.response.send_message(
                f"✅ Rate limit set to **{rate}** ban(s) per minute",
                ephemeral=True,
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number", ephemeral=True
            )


class AgeGateSlashWizard(commands.Cog):
    """Slash command wizard for AgeGate configuration (owner only)."""

    def __init__(self, bot):
        self.bot = bot
        # Get reference to AgeGate cog for config access
        self.agegate_cog = None

    async def cog_load(self):
        """Called when cog is loaded. Get reference to AgeGate cog."""
        self.agegate_cog = self.bot.get_cog("AgeGate")
        if not self.agegate_cog:
            logging.warning(
                "[AgeGate Slash] AgeGate cog not found. Make sure agegate.py is loaded first."
            )

    @app_commands.command(
        name="agegate_configure",
        description="Interactive AgeGate configuration wizard (bot owner only)",
    )
    @app_commands.checks.is_owner()
    async def agegate_configure(self, interaction: discord.Interaction):
        """Start the AgeGate configuration modal wizard."""
        if not self.agegate_cog:
            await interaction.response.send_message(
                "❌ AgeGate cog is not loaded. Please load agegate.py first.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a guild.",
                ephemeral=True,
            )
            return

        # Start with first modal
        modal = MinAgeModal(self.agegate_cog, guild)
        await interaction.response.send_modal(modal)


async def setup(bot):
    await bot.add_cog(AgeGateSlashWizard(bot))