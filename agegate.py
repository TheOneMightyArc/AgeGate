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
            "min_age_days": 7,
            "ban_reason": "Your account is too new. Please wait until your account is older to join.",
            "action_type": "ban",  # "ban", "notify", or "delay"
            "ban_type": "permanent",  # "permanent" or "temporary"
            "temp_ban_duration_days": 7,
            "delay_punishment_hours": 24,  # Hours to wait before taking action
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
            
            age_days = account_age.days
            age_hours = account_age.seconds // 3600
            
            embed = discord.Embed(
                title="🚨 New Account Alert",
                description=f"A new member with a young account has joined.",
                color=discord.Color.yellow(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Account Age", value=f"{age_days}d {age_hours}h", inline=False)
            embed.add_field(name="Minimum Required Age", value=f"{settings['min_age_days']} days", inline=False)
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
                                    dm_message = f"You have been automatically punished from **{guild.name}** for having a new account.\n**Reason:** {reason}"
                                    if settings["ban_type"] == "temporary":
                                        dm_message += f"\nThis ban is temporary and will last for **{settings['temp_ban_duration_days']}** day(s)."
                                    await member.send(dm_message)
                                except (discord.Forbidden, discord.HTTPException):
                                    pass

                                # Apply ban
                                await guild.ban(
                                    member,
                                    reason=f"AgeGate: Account younger than {settings['min_age_days']} days (delayed action)"
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

        if account_age < timedelta(days=settings["min_age_days"]):
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
                
                await self._notify_staff(guild, member, account_age_seconds)
                self._get_logger().info(
                    f"[AgeGate] Delayed punishment scheduled for {member.display_name} ({member.id}) "
                    f"in {delay_hours} hours in {guild.name}"
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
                    dm_message = f"You have been automatically banned from **{guild.name}**.\n**Reason:** {reason}"
                    if settings["ban_type"] == "temporary":
                        dm_message += f"\nThis ban is temporary and will last for **{settings['temp_ban_duration_days']}** day(s)."
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
        """Configure AgeGate settings."""
        pass

    @agegate_settings.command(name="toggle")
    async def toggle_agegate(self, ctx: commands.Context, on_or_off: bool = None):
        """Turn the automatic monitoring of new accounts on or off."""
        current_status = await self.config.guild(ctx.guild).enabled()
        
        if on_or_off is None:
            on_or_off = not current_status

        await self.config.guild(ctx.guild).enabled.set(on_or_off)
        await ctx.send(f"✅ AgeGate is now **{'ENABLED' if on_or_off else 'DISABLED'}**.")

    @agegate_settings.command(name="days")
    async def set_days(self, ctx: commands.Context, days: int):
        """Set the minimum account age in days."""
        if days < 0:
            return await ctx.send("The number of days must be 0 or greater.")

        await self.config.guild(ctx.guild).min_age_days.set(days)
        await ctx.send(f"✅ Accounts newer than **{days}** days will be monitored by AgeGate.")

    @agegate_settings.command(name="reason")
    async def set_reason(self, ctx: commands.Context, *, reason: str):
        """Set the custom reason for handling new accounts."""
        if len(reason) > 512:
            return await ctx.send("The reason must be 512 characters or fewer.")

        await self.config.guild(ctx.guild).ban_reason.set(reason)
        await ctx.send(f"✅ The ban reason has been set to: `{reason}`")

    @agegate_settings.command(name="action")
    async def set_action_type(self, ctx: commands.Context, action: str):
        """Set the action type: 'ban' (immediate), 'delay' (wait x hours), or 'notify' (staff alert only)."""
        action = action.lower()
        
        if action not in ["ban", "delay", "notify"]:
            return await ctx.send(
                "Invalid action type. Please choose: `ban` (immediate), `delay` (wait x hours), or `notify` (staff alert only)."
            )

        await self.config.guild(ctx.guild).action_type.set(action)
        action_descriptions = {
            "ban": "Immediately ban new accounts",
            "delay": "Wait before banning (use `/agegateset delayhours` to set duration)",
            "notify": "Only notify staff (no ban action)"
        }
        await ctx.send(f"✅ Action type set to **{action}**: {action_descriptions[action]}")

    @agegate_settings.command(name="delayhours")
    async def set_delay_hours(self, ctx: commands.Context, hours: int):
        """Set the delay in hours before applying punishment (only used with 'delay' action type)."""
        if hours <= 0:
            return await ctx.send("The delay must be greater than 0 hours.")

        await self.config.guild(ctx.guild).delay_punishment_hours.set(hours)
        await ctx.send(f"✅ Punishment will be delayed by **{hours}** hour(s) for new accounts.")

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

    @agegate_settings.command(name="bantype")
    async def set_ban_type(self, ctx: commands.Context, ban_type: str):
        """Set the ban type to 'permanent' or 'temporary' (only used with 'ban' action type)."""
        ban_type = ban_type.lower()
        
        if ban_type not in ["permanent", "temporary"]:
            return await ctx.send("Invalid type. Please choose either `permanent` or `temporary`.")

        await self.config.guild(ctx.guild).ban_type.set(ban_type)
        await ctx.send(f"✅ Ban type has been set to **{ban_type}**.")

    @agegate_settings.command(name="duration")
    async def set_duration(self, ctx: commands.Context, days: int):
        """Set the duration in days for temporary bans."""
        if days <= 0:
            return await ctx.send("The duration for temporary bans must be greater than 0.")

        await self.config.guild(ctx.guild).temp_ban_duration_days.set(days)
        await ctx.send(f"✅ Temporary bans will now last for **{days}** day(s).")

    @agegate_settings.command(name="ratelimit")
    async def set_rate_limit(self, ctx: commands.Context, bans_per_minute: int):
        """Set the maximum number of bans per minute to prevent join floods."""
        if bans_per_minute <= 0:
            return await ctx.send("Rate limit must be greater than 0.")

        await self.config.guild(ctx.guild).join_rate_limit.set(bans_per_minute)
        await ctx.send(f"✅ Rate limit set to **{bans_per_minute}** ban(s) per minute.")

    @agegate_settings.command(name="status", aliases=["settings"])
    async def show_settings(self, ctx: commands.Context):
        """Show the current AgeGate settings."""
        settings = await self.config.guild(ctx.guild).all()
        
        status = "✅ ENABLED" if settings['enabled'] else "❌ DISABLED"
        action_type = settings['action_type'].upper()
        ban_type = settings['ban_type'].capitalize()

        embed = discord.Embed(
            title="AgeGate Configuration",
            color=await ctx.embed_color(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name="Minimum Account Age", value=f"**{settings['min_age_days']}** days", inline=False)
        embed.add_field(name="Action Type", value=action_type, inline=True)
        
        if settings['action_type'] == 'delay':
            embed.add_field(name="Delay Duration", value=f"{settings['delay_punishment_hours']} hour(s)", inline=True)
        
        if settings['action_type'] in ['ban', 'delay']:
            embed.add_field(name="Ban Type", value=ban_type, inline=True)
            if settings['ban_type'] == 'temporary':
                embed.add_field(name="Temp Ban Duration", value=f"{settings['temp_ban_duration_days']} day(s)", inline=True)

        embed.add_field(name="Rate Limit", value=f"{settings['join_rate_limit']} ban(s)/min", inline=True)
        
        staff_channel = ctx.guild.get_channel(settings["staff_notification_channel_id"]) if settings["staff_notification_channel_id"] else None
        staff_info = staff_channel.mention if staff_channel else "Not configured"
        embed.add_field(name="Staff Notification Channel", value=staff_info, inline=False)
        
        embed.add_field(name="Ban Reason", value=settings['ban_reason'], inline=False)
        
        await ctx.send(embed=embed)