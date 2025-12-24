from .agegate import AgeGate

async def setup(bot):
    await bot.add_cog(AgeGate(bot))