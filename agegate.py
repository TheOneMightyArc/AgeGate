import discord
from datetime import timedelta, datetime
from redbot.core import commands, Config
from discord.ext import tasks
import logging
from typing import Optional

# Setup logging
log = logging.getLogger("red.agegate")


class AgeGate(commands.Cog):
    """
    Automatically monitors and punishes new accounts based on their creation date.
    Supports: immediate ban, delayed punishment, or staff notification only.
    Configuration via prefix commands or slash wizard.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=199819922001,
            force_registration=True
        )

        default_guild = {
            "enabled": False,
            "min_age_seconds": 604800,  # 7 days in seconds
            "ban_reason": "Your account is too new. Please wait until your account is older to join.",
            "action_type": "ban",  # "ban", "notify", or "delay"
            "ban_type": "permanent",  # "permanent" or "temporary"
            "temp_ban_duration_seconds": 604800,  # 7 days in seconds
            "delay_punishment_seconds": 86400,  # 24 hours in seconds
            "staff_notification_channel_id": None,  # Channel ID for staff alerts
            "temp_banned_users": {},  # { "user_id": unban_timestamp }
            "delayed_members": {},  # { "user_id": action_timestamp }
            "join_rate_limit": 5,  # Max bans per minute
            "last_ban_timestamp": 0,
            "recent_bans_count": 0,
        }

        self.config.register_guild(**default_guild)
        self.unban_task.start()
        self.delayed_punishment_task.start()

    def cog_unload(self):
        self.unban_task.cancel()
        self.delayed_punishment_task.cancel()

    def _get_logger(self):
        """Get configured logger for this cog."""
        return log

    def _seconds_to_readable(self, seconds: int) -> str:
        """Convert seconds to human-readable format (e.g., '3d 5h 30m')."