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
        """Convert seconds to human-readable format (e.g., '3d 5h 30m')."""
        if seconds == 0:
            return "0 seconds"
        
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0:
            parts.append(f"{secs}s")
        
        return " ".join(parts)

    async def _check_rate_limit(self, guild: discord.Guild) -> bool:
        """Check if we're exceeding ban rate limits. Returns True if within limits."""
        settings = await self.config.guild(guild).all()
        now = discord.utils.utcnow().timestamp()
        
        # Reset counter if 60 seconds have passed
        if now - settings["last_ban_timestamp"] > 60:
            await self.config.guild(guild).recent_bans_count.set(0)
            await self.config.guild(guild).last_ban_timestamp.set(now)
            return True
        
        # Check if we've exceeded the rate limit
        if settings["recent_bans_count"] >= settings["join_rate_limit"]:
            self._get_logger().warning(
                f"[AgeGate] Rate limit exceeded in {guild.name} ({guild.id}). "
                f"Skipping bans until window resets."
            )
            return False
        
        return True

    async def _increment_ban_counter(self, guild: discord.Guild):
        """Increment the ban counter for rate limiting."""
        settings = await self.config.guild(guild).all()
        new_count = settings["recent_bans_count"] + 1
        await self.config.guild(guild).recent_bans_count.set(new_count)
        await self.config.guild(guild).last_ban_timestamp.set(discord.utils.utcnow().timestamp())

    async def _notify_staff(self, guild: discord.Guild, member: discord.Member, account_age: timedelta):
        """Send staff notification about new account."""
        settings = await self.config.guild(guild).all()
        
        if not settings["staff_notification_channel_id"]:
            return False
        
        try:
            channel = guild.get_channel(settings["staff_notification_channel_id"])
            if not channel or not isinstance(channel, discord.TextChannel):
                self._get_logger().error(
                    f"[AgeGate] Invalid notification channel for {guild.name}"
                )
                return False
            
            # Check channel permissions
            if not channel.permissions_for(guild.me).send_messages:
                self._get_logger().error(
                    f"[AgeGate] No permission to send messages in {channel.mention}"
                )
                return False
            
            account_age_seconds = int(account_age.total_seconds())
            age_readable = self._seconds_to_readable(account_age_seconds)
            min_age_readable = self._seconds_to_readable(settings['min_age_seconds'])
            
            embed = discord.Embed(
                title="🚨 New Account Alert",
                description=f"A new member with a young account has joined.",
                color=discord.Color.yellow(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Account Age", value=age_readable, inline=False)
            embed.add_field(name="Minimum Required Age", value=min_age_readable, inline=False)
            embed.add_field(name="Action", value=settings["action_type"].upper(), inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await channel.send(embed=embed)
            return True
            
        except Exception as e:
            self._get_logger().exception(
                f"[AgeGate] Error notifying staff in {guild.name}: {e}"
            )
            return False

    @tasks.loop(minutes=1)
    async def delayed_punishment_task(self):
        """Check for members whose delay period has expired and apply punishment."""
        all_guilds_data = await self.config.all_guilds()
        now = discord.utils.utcnow().timestamp()

        for guild_id, data in all_guilds_data.items():
            guild = self.bot.get_guild(guild_id)
            if not guild or "delayed_members" not in data:
                continue

            delayed_members = data["delayed_members"].copy()
            members_to_punish = []

            for user_id_str, action_timestamp in delayed_members.items():
                if now >= action_timestamp:
                    members_to_punish.append(user_id_str)

            if members_to_punish:
                async with self.config.guild(guild).delayed_members() as delayed_members_config:
                    for user_id_str in members_to_punish:
                        user_id = int(user_id_str)
                        
                        try:
                            member = guild.get_member(user_id)
                            if not member:
                                # Member already left
                                self._get_logger().info(
                                    f"[AgeGate] Member {user_id} left before delayed punishment in {guild.name}"
                                )
                            else:
                                settings = await self.config.guild(guild).all()
                                reason = settings["ban_reason"]
                                
                                # Send DM before punishment
                                try:
                                    ban_duration_readable = self._seconds_to_readable(settings['temp_ban_duration_seconds'])
                                    dm_message = f"You have been automatically punished from **{guild.name}** for having a new account.\n**Reason:** {reason}"
                                    if settings["ban_type"] == "temporary":
                                        dm_message += f"\nThis ban is temporary and will last for **{ban_duration_readable}**."
                                    await member.send(dm_message)
                                except (discord.Forbidden, discord.HTTPException):
                                    pass

                                # Apply ban
                                min_age_readable = self._seconds_to_readable(settings['min_age_seconds'])
                                await guild.ban(
                                    member,
                                    reason=f"AgeGate: Account younger than {min_age_readable} (delayed action)"
                                )
                                self._get_logger().info(
                                    f"[AgeGate] Delayed punishment applied to {member.display_name} ({user_id}) in {guild.name}"
                                )

                                # Track for temporary bans
                                if settings["ban_type"] == "temporary":
                                    unban_time = discord.utils.utcnow() + timedelta(seconds=settings["temp_ban_duration_seconds"])
                                    async with self.config.guild(guild).temp_banned_users() as temp_banned_users:
                                        temp_banned_users[user_id_str] = unban_time.timestamp()

                        except discord.Forbidden:
                            self._get_logger().error(
                                f"[AgeGate] Failed to punish {user_id} in {guild.name}. Bot role too low."
                            )
                        except Exception as e:
                            self._get_logger().exception(
                                f"[AgeGate] Error punishing delayed member {user_id}: {e}"
                            )
                        finally:
                            # Remove from config regardless of success
                            if user_id_str in delayed_members_config:
                                del delayed_members_config[user_id_str]

    @delayed_punishment_task.before_loop
    async def before_delayed_punishment_task(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def unban_task(self):
        """Periodically checks if any temporary bans have expired."""
        all_guilds_data = await self.config.all_guilds()
        now = discord.utils.utcnow().timestamp()

        for guild_id, data in all_guilds_data.items():
            guild = self.bot.get_guild(guild_id)
            if not guild or "temp_banned_users" not in data:
                continue

            temp_banned = data["temp_banned_users"].copy()
            users_to_unban = []

            for user_id_str, unban_timestamp in temp_banned.items():
                if now >= unban_timestamp:
                    users_to_unban.append(user_id_str)

            if users_to_unban:
                async with self.config.guild(guild).temp_banned_users() as temp_banned_users:
                    for user_id_str in users_to_unban:
                        user_id = int(user_id_str)
                        try:
                            user = discord.Object(id=user_id)
                            await guild.unban(user, reason="AgeGate: Temporary ban expired.")
                            self._get_logger().info(
                                f"[AgeGate] Unbanned {user_id} in {guild.name} as their temp ban expired."
                            )
                        except discord.Forbidden:
                            self._get_logger().error(
                                f"[AgeGate] Failed to unban {user_id} in {guild.name}. "
                                f"Bot role may be too low or lacks ban permissions."
                            )
                        except discord.NotFound:
                            # User might have been unbanned manually already
                            self._get_logger().debug(
                                f"[AgeGate] User {user_id} not in ban list (possibly already unbanned)"
                            )
                        except Exception as e:
                            self._get_logger().exception(
                                f"[AgeGate] Unexpected error unbanning {user_id}: {e}"
                            )
                        finally:
                            # Remove from config regardless of success
                            if user_id_str in temp_banned_users:
                                del temp_banned_users[user_id_str]

    @unban_task.before_loop
    async def before_unban_task(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Monitor new member joins and apply AgeGate logic."""
        guild = member.guild
        settings = await self.config.guild(guild).all()

        if not settings["enabled"]:
            return

        now = discord.utils.utcnow()
        account_age = now - member.created_at

        if account_age < timedelta(seconds=settings["min_age_seconds"]):
            action_type = settings["action_type"].lower()

            # Handle staff notification
            if action_type == "notify":
                await self._notify_staff(guild, member, account_age)
                self._get_logger().info(
                    f"[AgeGate] Staff notified about young account {member.id} in {guild.name}"
                )
                return

            # Handle delayed punishment
            if action_type == "delay":
                delay_seconds = settings["delay_punishment_seconds"]
                punishment_time = now + timedelta(seconds=delay_seconds)
                
                async with self.config.guild(guild).delayed_members() as delayed_members:
                    delayed_members[str(member.id)] = punishment_time.timestamp()
                
                await self._notify_staff(guild, member, account_age)
                delay_readable = self._seconds_to_readable(delay_seconds)
                self._get_logger().info(
                    f"[AgeGate] Delayed punishment scheduled for {member.display_name} ({member.id}) "
                    f"in {delay_readable} in {guild.name}"
                )
                return

            # Handle immediate ban (original behavior)
            if action_type == "ban":
                # Check rate limiting
                if not await self._check_rate_limit(guild):
                    self._get_logger().warning(
                        f"[AgeGate] Skipped ban for {member.id} in {guild.name} due to rate limit"
                    )
                    return

                reason = settings["ban_reason"]

                try:
                    # Send DM notification
                    ban_duration_readable = self._seconds_to_readable(settings['temp_ban_duration_seconds'])
                    dm_message = f"You have been automatically banned from **{guild.name}**.\n**Reason:** {reason}"
                    if settings["ban_type"] == "temporary":
                        dm_message += f"\nThis ban is temporary and will last for **{ban_duration_readable}**."
                    await member.send(dm_message)
                except (discord.Forbidden, discord.HTTPException):
                    pass  # DMs closed or failed

                try:
                    min_age_readable = self._seconds_to_readable(settings['min_age_seconds'])
                    await guild.ban(
                        member,
                        reason=f"AgeGate: Account younger than {min_age_readable}. Reason: {reason}"
                    )
                    self._get_logger().info(
                        f"[AgeGate] Banned new account: {member.display_name} ({member.id}) from {guild.name}."
                    )

                    await self._increment_ban_counter(guild)

                    if settings["ban_type"] == "temporary":
                        unban_time = now + timedelta(seconds=settings["temp_ban_duration_seconds"])
                        async with self.config.guild(guild).temp_banned_users() as temp_banned_users:
                            temp_banned_users[str(member.id)] = unban_time.timestamp()

                except discord.Forbidden:
                    self._get_logger().error(
                        f"[AgeGate] Failed to ban {member.display_name} in {guild.name}. Bot role too low."
                    )
                except Exception as e:
                    self._get_logger().exception(
                        f"[AgeGate] Failed to ban {member.id}: {e}"
                    )

    @commands.group(name="agegateset")
    @commands.guild_only()
    @commands.admin_or_permissions(ban_members=True)
    async def agegate_settings(self, ctx: commands.Context):
        """Configure AgeGate settings via prefix commands."""
        pass

    @agegate_settings.command(name="toggle")
    async def toggle_agegate(self, ctx: commands.Context, on_or_off: bool = None):
        """Turn the automatic monitoring of new accounts on or off."""
        current_status = await self.config.guild(ctx.guild).enabled()
        
        if on_or_off is None:
            on_or_off = not current_status

        await self.config.guild(ctx.guild).enabled.set(on_or_off)
        await ctx.send(f"✅ AgeGate is now **{'ENABLED' if on_or_off else 'DISABLED'}**.")

    @agegate_settings.command(name="staffchannel")
    async def set_staff_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set the channel for staff notifications. Leave blank to disable notifications."""
        if channel is None:
            await self.config.guild(ctx.guild).staff_notification_channel_id.set(None)
            await ctx.send("✅ Staff notifications have been **disabled**.")
        else:
            # Verify bot has send_messages permission
            if not channel.permissions_for(ctx.guild.me).send_messages:
                return await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}")

            await self.config.guild(ctx.guild).staff_notification_channel_id.set(channel.id)
            await ctx.send(f"✅ Staff notifications will be sent to {channel.mention}")

    @agegate_settings.command(name="status", aliases=["settings"])
    async def show_settings(self, ctx: commands.Context):
        """Show the current AgeGate settings."""
        settings = await self.config.guild(ctx.guild).all()
        
        status = "✅ ENABLED" if settings['enabled'] else "❌ DISABLED"
        action_type = settings['action_type'].upper()
        ban_type = settings['ban_type'].capitalize()

        min_age_readable = self._seconds_to_readable(settings['min_age_seconds'])
        
        embed = discord.Embed(
            title="AgeGate Configuration",
            color=await ctx.embed_color(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name="Minimum Account Age", value=f"**{min_age_readable}**", inline=False)
        embed.add_field(name="Action Type", value=action_type, inline=True)
        
        if settings['action_type'] == 'delay':
            delay_readable = self._seconds_to_readable(settings['delay_punishment_seconds'])
            embed.add_field(name="Delay Duration", value=delay_readable, inline=True)
        
        if settings['action_type'] in ['ban', 'delay']:
            embed.add_field(name="Ban Type", value=ban_type, inline=True)
            if settings['ban_type'] == 'temporary':
                duration_readable = self._seconds_to_readable(settings['temp_ban_duration_seconds'])
                embed.add_field(name="Temp Ban Duration", value=duration_readable, inline=True)

        embed.add_field(name="Rate Limit", value=f"{settings['join_rate_limit']} ban(s)/min", inline=True)
        
        staff_channel = ctx.guild.get_channel(settings["staff_notification_channel_id"]) if settings["staff_notification_channel_id"] else None
        staff_info = staff_channel.mention if staff_channel else "Not configured"
        embed.add_field(name="Staff Notification Channel", value=staff_info, inline=False)
        
        embed.add_field(name="Ban Reason", value=settings['ban_reason'], inline=False)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AgeGate(bot))