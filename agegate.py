import discord
from datetime import timedelta, datetime
from redbot.core import commands, Config
from discord.ext import tasks

class AgeGate(commands.Cog):
    """
    Automatically bans new accounts based on their creation date.
    Can be configured for permanent or temporary bans.
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
            "min_age_days": 7, # Reverted to days
            "ban_reason": "Your account is too new. Please wait until your account is older to join.",
            "ban_type": "permanent", # "permanent" or "temporary"
            "temp_ban_duration_days": 7, # Duration for temporary bans
            "temp_banned_users": {} # { "user_id": unban_timestamp }
        }
        self.config.register_guild(**default_guild)
        self.unban_task.start()

    def cog_unload(self):
        self.unban_task.cancel()

    @tasks.loop(minutes=30)
    async def unban_task(self):
        """Periodically checks if any temporary bans have expired."""
        all_guilds_data = await self.config.all_guilds()
        now = discord.utils.utcnow().timestamp()

        for guild_id, data in all_guilds_data.items():
            guild = self.bot.get_guild(guild_id)
            if not guild or "temp_banned_users" not in data:
                continue

            # Create a copy to modify while iterating
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
                            await guild.unban(user, reason="Temporary ban expired.")
                            print(f"[AgeGate] Unbanned {user_id} in {guild.name} as their temp ban expired.")
                        except discord.Forbidden:
                            print(f"[AgeGate] Failed to unban {user_id} in {guild.name}. My role may be too low or I lack ban permissions.")
                        except discord.NotFound:
                            # User might have been unbanned manually already
                            pass 
                        except Exception as e:
                            print(f"[AgeGate] An unexpected error occurred while trying to unban {user_id}: {e}")
                        
                        # Remove from config regardless of success to prevent retrying a failed unban
                        if user_id_str in temp_banned_users:
                            del temp_banned_users[user_id_str]

    @unban_task.before_loop
    async def before_unban_task(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        settings = await self.config.guild(guild).all()

        if not settings["enabled"]:
            return

        now = discord.utils.utcnow()
        account_age = now - member.created_at
        
        if account_age < timedelta(days=settings["min_age_days"]):
            reason = settings["ban_reason"]
            
            try:
                dm_message = f"You have been automatically banned from **{guild.name}**.\n**Reason:** {reason}"
                if settings["ban_type"] == "temporary":
                    dm_message += f"\nThis ban is temporary and will last for **{settings['temp_ban_duration_days']}** day(s)."
                await member.send(dm_message)
            except (discord.Forbidden, discord.HTTPException):
                pass # Ignore if DMs are closed or fail

            try:
                await guild.ban(member, reason=f"AgeGate: Account younger than {settings['min_age_days']} days. Reason: {reason}")
                print(f"[AgeGate] Banned new account: {member.display_name} ({member.id}) from {guild.name}.")

                if settings["ban_type"] == "temporary":
                    unban_time = now + timedelta(days=settings["temp_ban_duration_days"])
                    async with self.config.guild(guild).temp_banned_users() as temp_banned_users:
                        temp_banned_users[str(member.id)] = unban_time.timestamp()

            except discord.Forbidden:
                print(f"[AgeGate] Failed to ban {member.display_name} in {guild.name}. My role may be too low.")
            except Exception as e:
                print(f"[AgeGate] Failed to ban {member.id}: {e}")

    @commands.group(name="agegateset")
    @commands.guild_only()
    @commands.admin_or_permissions(ban_members=True)
    async def agegate_settings(self, ctx: commands.Context):
        """Configure AgeGate settings."""
        pass

    @agegate_settings.command(name="toggle")
    async def toggle_agegate(self, ctx: commands.Context, on_or_off: bool = None):
        """Turn the automatic banning of new accounts on or off."""
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
        await ctx.send(f"✅ Accounts newer than **{days}** days will now be automatically banned.")

    @agegate_settings.command(name="reason")
    async def set_reason(self, ctx: commands.Context, *, reason: str):
        """Set the custom reason for banning new accounts."""
        if len(reason) > 512:
            return await ctx.send("The reason must be 512 characters or fewer.")
        await self.config.guild(ctx.guild).ban_reason.set(reason)
        await ctx.send(f"✅ The ban reason has been set to: `{reason}`")

    @agegate_settings.command(name="bantype")
    async def set_ban_type(self, ctx: commands.Context, ban_type: str):
        """Set the ban type to 'permanent' or 'temporary'."""
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

    @agegate_settings.command(name="status", aliases=["settings"])
    async def show_settings(self, ctx: commands.Context):
        """Show the current AgeGate settings."""
        settings = await self.config.guild(ctx.guild).all()
        status = "✅ ENABLED" if settings['enabled'] else "❌ DISABLED"
        ban_type = settings['ban_type'].capitalize()
        
        embed = discord.Embed(title="AgeGate Status", color=await ctx.embed_color())
        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name="Minimum Account Age", value=f"**{settings['min_age_days']}** days", inline=False)
        embed.add_field(name="Ban Type", value=ban_type, inline=True)
        if settings['ban_type'] == "temporary":
            embed.add_field(name="Temp Ban Duration", value=f"{settings['temp_ban_duration_days']} day(s)", inline=True)
        embed.add_field(name="Ban Reason", value=settings['ban_reason'], inline=False)
        await ctx.send(embed=embed)