import discord
from datetime import timedelta, datetime
from redbot.core import commands, Config
from discord.ext import tasks
import logging
from typing import Optional

# Setup logging
log = logging.getLogger("red.agegate")


class MinAgeModal(discord.ui.Modal):
    """Modal for setting minimum account age in seconds."""
    
    def __init__(self, cog, guild: discord.Guild, callback=None):
        super().__init__(title="Set Minimum Account Age")
        self.cog = cog
        self.guild = guild
        self.callback = callback
        
        self.days = discord.ui.TextInput(
            label="Days",
            placeholder="e.g., 7",
            default="7",
            min_length=1,
            max_length=3
        )
        self.hours = discord.ui.TextInput(
            label="Hours (0-23)",
            placeholder="e.g., 0",
            default="0",
            min_length=1,
            max_length=2,
            required=False
        )
        self.add_item(self.days)
        self.add_item(self.hours)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            days = int(self.days.value)
            hours = int(self.hours.value) if self.hours.value else 0
            
            if days < 0 or hours < 0 or hours > 23:
                await interaction.response.send_message(
                    "❌ Days must be ≥ 0 and hours must be 0-23",
                    ephemeral=True
                )
                return
            
            total_seconds = (days * 86400) + (hours * 3600)
            await self.cog.config.guild(self.guild).min_age_seconds.set(total_seconds)
            
            readable = self.cog._seconds_to_readable(total_seconds)
            await interaction.response.send_message(
                f"✅ Minimum account age set to **{readable}**",
                ephemeral=True
            )
            
            if self.callback:
                await self.callback(interaction)
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter valid numbers",
                ephemeral=True
            )


class BanReasonModal(discord.ui.Modal):
    """Modal for setting ban reason."""
    
    def __init__(self, cog, guild: discord.Guild, callback=None):
        super().__init__(title="Set Ban Reason")
        self.cog = cog
        self.guild = guild
        self.callback = callback
        
        self.reason = discord.ui.TextInput(
            label="Ban Reason",
            placeholder="Enter the reason for banning new accounts...",
            default="Your account is too new. Please wait until your account is older to join.",
            min_length=1,
            max_length=512,
            style=discord.TextInputStyle.paragraph
        )
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.config.guild(self.guild).ban_reason.set(self.reason.value)
        await interaction.response.send_message(
            f"✅ Ban reason set to: `{self.reason.value}`",
            ephemeral=True
        )
        
        if self.callback:
            await self.callback(interaction)


class ActionTypeModal(discord.ui.Modal):
    """Modal for setting action type."""
    
    def __init__(self, cog, guild: discord.Guild, callback=None):
        super().__init__(title="Set Action Type")
        self.cog = cog
        self.guild = guild
        self.callback = callback
        
        self.action = discord.ui.TextInput(
            label="Action Type (ban/delay/notify)",
            placeholder="Enter: ban, delay, or notify",
            default="ban",
            min_length=3,
            max_length=6
        )
        self.add_item(self.action)
    
    async def on_submit(self, interaction: discord.Interaction):
        action = self.action.value.lower()
        
        if action not in ["ban", "delay", "notify"]:
            await interaction.response.send_message(
                "❌ Invalid action type. Please choose: `ban`, `delay`, or `notify`",
                ephemeral=True
            )
            return
        
        await self.cog.config.guild(self.guild).action_type.set(action)
        action_descriptions = {
            "ban": "Immediately ban new accounts",
            "delay": "Wait before banning (set delay duration next)",
            "notify": "Only notify staff (no ban action)"
        }
        await interaction.response.send_message(
            f"✅ Action type set to **{action}**: {action_descriptions[action]}",
            ephemeral=True
        )
        
        if self.callback:
            await self.callback(interaction)


class BanTypeModal(discord.ui.Modal):
    """Modal for setting ban type."""
    
    def __init__(self, cog, guild: discord.Guild, callback=None):
        super().__init__(title="Set Ban Type")
        self.cog = cog
        self.guild = guild
        self.callback = callback
        
        self.ban_type = discord.ui.TextInput(
            label="Ban Type (permanent/temporary)",
            placeholder="Enter: permanent or temporary",
            default="permanent",
            min_length=9,
            max_length=9
        )
        self.add_item(self.ban_type)
    
    async def on_submit(self, interaction: discord.Interaction):
        ban_type = self.ban_type.value.lower()
        
        if ban_type not in ["permanent", "temporary"]:
            await interaction.response.send_message(
                "❌ Invalid type. Please choose: `permanent` or `temporary`",
                ephemeral=True
            )
            return
        
        await self.cog.config.guild(self.guild).ban_type.set(ban_type)
        await interaction.response.send_message(
            f"✅ Ban type set to **{ban_type}**",
            ephemeral=True
        )
        
        if self.callback:
            await self.callback(interaction)


class DelayDurationModal(discord.ui.Modal):
    """Modal for setting delay punishment duration in seconds."""
    
    def __init__(self, cog, guild: discord.Guild, callback=None):
        super().__init__(title="Set Delay Duration")
        self.cog = cog
        self.guild = guild
        self.callback = callback
        
        self.hours = discord.ui.TextInput(
            label="Hours",
            placeholder="e.g., 24",
            default="24",
            min_length=1,
            max_length=4
        )
        self.minutes = discord.ui.TextInput(
            label="Minutes (0-59)",
            placeholder="e.g., 0",
            default="0",
            min_length=1,
            max_length=2,
            required=False
        )
        self.add_item(self.hours)
        self.add_item(self.minutes)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            hours = int(self.hours.value)
            minutes = int(self.minutes.value) if self.minutes.value else 0
            
            if hours <= 0 or minutes < 0 or minutes > 59:
                await interaction.response.send_message(
                    "❌ Hours must be > 0 and minutes must be 0-59",
                    ephemeral=True
                )
                return
            
            total_seconds = (hours * 3600) + (minutes * 60)
            await self.cog.config.guild(self.guild).delay_punishment_seconds.set(total_seconds)
            
            readable = self.cog._seconds_to_readable(total_seconds)
            await interaction.response.send_message(
                f"✅ Delay duration set to **{readable}**",
                ephemeral=True
            )
            
            if self.callback:
                await self.callback(interaction)
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter valid numbers",
                ephemeral=True
            )


class TempBanDurationModal(discord.ui.Modal):
    """Modal for setting temporary ban duration in seconds."""
    
    def __init__(self, cog, guild: discord.Guild, callback=None):
        super().__init__(title="Set Temp Ban Duration")
        self.cog = cog
        self.guild = guild
        self.callback = callback
        
        self.days = discord.ui.TextInput(
            label="Days",
            placeholder="e.g., 7",
            default="7",
            min_length=1,
            max_length=3
        )
        self.hours = discord.ui.TextInput(
            label="Hours (0-23)",
            placeholder="e.g., 0",
            default="0",
            min_length=1,
            max_length=2,
            required=False
        )
        self.add_item(self.days)
        self.add_item(self.hours)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            days = int(self.days.value)
            hours = int(self.hours.value) if self.hours.value else 0
            
            if days <= 0 or hours < 0 or hours > 23:
                await interaction.response.send_message(
                    "❌ Days must be > 0 and hours must be 0-23",
                    ephemeral=True
                )
                return
            
            total_seconds = (days * 86400) + (hours * 3600)
            await self.cog.config.guild(self.guild).temp_ban_duration_seconds.set(total_seconds)
            
            readable = self.cog._seconds_to_readable(total_seconds)
            await interaction.response.send_message(
                f"✅ Temporary ban duration set to **{readable}**",
                ephemeral=True
            )
            
            if self.callback:
                await self.callback(interaction)
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter valid numbers",
                ephemeral=True
            )


class RateLimitModal(discord.ui.Modal):
    """Modal for setting rate limit."""
    
    def __init__(self, cog, guild: discord.Guild, callback=None):
        super().__init__(title="Set Rate Limit")
        self.cog = cog
        self.guild = guild
        self.callback = callback
        
        self.bans_per_minute = discord.ui.TextInput(
            label="Bans Per Minute",
            placeholder="e.g., 5",
            default="5",
            min_length=1,
            max_length=2
        )
        self.add_item(self.bans_per_minute)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            rate = int(self.bans_per_minute.value)
            
            if rate <= 0:
                await interaction.response.send_message(
                    "❌ Rate limit must be > 0",
                    ephemeral=True
                )
                return
            
            await self.cog.config.guild(self.guild).join_rate_limit.set(rate)
            await interaction.response.send_message(
                f"✅ Rate limit set to **{rate}** ban(s) per minute",
                ephemeral=True
            )
            
            if self.callback:
                await self.callback(interaction)
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number",
                ephemeral=True
            )


class AgeGate(commands.Cog):
    """
    Automatically monitors and punishes new accounts based on their creation date.
    Supports: immediate ban, delayed punishment, or staff notification only.
    All configuration via interactive modals.
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

    @agegate_settings.command(name="configure")
    async def configure_agegate(self, ctx: commands.Context):
        """Guide through all configuration options via interactive modals."""
        step = 0
        
        async def next_step(interaction: discord.Interaction):
            nonlocal step
            step += 1
            await show_modal()
        
        async def show_modal():
            modals = [
                MinAgeModal(self, ctx.guild, next_step),
                BanReasonModal(self, ctx.guild, next_step),
                ActionTypeModal(self, ctx.guild, next_step),
                BanTypeModal(self, ctx.guild, next_step),
                TempBanDurationModal(self, ctx.guild, next_step),
                DelayDurationModal(self, ctx.guild, next_step),
                RateLimitModal(self, ctx.guild, next_step),
            ]
            
            if step < len(modals):
                modal = modals[step]
                # For the first modal, use the context interaction
                if step == 0:
                    await ctx.interaction.response.send_modal(modal)
                else:
                    # For subsequent modals, we need to rely on the callback
                    pass
            else:
                # All modals completed
                settings = await self.config.guild(ctx.guild).all()
                status = "✅ ENABLED" if settings['enabled'] else "❌ DISABLED"
                
                embed = discord.Embed(
                    title="✅ AgeGate Configuration Complete",
                    description="All settings have been configured successfully!",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                min_age_readable = self._seconds_to_readable(settings['min_age_seconds'])
                embed.add_field(name="Minimum Account Age", value=f"**{min_age_readable}**", inline=False)
                embed.add_field(name="Action Type", value=settings['action_type'].upper(), inline=True)
                embed.add_field(name="Ban Type", value=settings['ban_type'].capitalize(), inline=True)
                
                if settings['action_type'] == 'delay':
                    delay_readable = self._seconds_to_readable(settings['delay_punishment_seconds'])
                    embed.add_field(name="Delay Duration", value=delay_readable, inline=True)
                
                if settings['ban_type'] == 'temporary':
                    duration_readable = self._seconds_to_readable(settings['temp_ban_duration_seconds'])
                    embed.add_field(name="Temp Ban Duration", value=duration_readable, inline=True)
                
                embed.add_field(name="Rate Limit", value=f"{settings['join_rate_limit']} ban(s)/min", inline=True)
                embed.add_field(name="Ban Reason", value=settings['ban_reason'], inline=False)
                
                if ctx.interaction.response.is_done():
                    await ctx.interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await ctx.interaction.response.send_message(embed=embed, ephemeral=True)
        
        await show_modal()

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