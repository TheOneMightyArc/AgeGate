from .agegate import AgeGat

async def setup(bot):
    await bot.add_cog(AgeGate(bot))