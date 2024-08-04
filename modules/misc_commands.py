import asyncio 

import discord
from discord.ext import commands

from app import App, AppModule
from utils import LogLevel, BotInternalException, split_array
from .priv_system import PrivSystem, PrivSystemLevels

class MiscCommands(commands.Cog, AppModule):
    def __init__(self, app: App):
        super(MiscCommands, self).__init__(app)

    async def remove_list(self, ctx, messages):
        channel = ctx.message.channel

        if isinstance(channel, discord.DMChannel):
            for msg in messages:
                await msg.delete()
                await asyncio.sleep(1)
        else:
            await channel.delete_messages(messages)

    @commands.hybrid_group(name="cleanmsg", fallback="onlybot")
    @PrivSystem.withPriv(PrivSystemLevels.OWNER)
    async def clean(self, ctx: commands.Context):
        channel = ctx.message.channel
        
        messages = [message async for message in channel.history(limit=1000000)]
        messages_filtered = [message for message in messages if message.author == self.bot.user and message.id != ctx.message.id]
        message_arrays = split_array(messages_filtered, 100)

        for message_array in message_arrays:        
            await self.remove_list(ctx, message_array)
            
        self.send(channel, f"Removed {len(messages_filtered)} messages")

    @clean.command(name="all")
    @PrivSystem.withPriv(PrivSystemLevels.OWNER)
    async def cleanAll(self, ctx: commands.Context):
        channel = ctx.message.channel
        
        messages = [message async for message in channel.history(limit=1000000)]
        messages_filtered = [message for message in messages if message.id != ctx.message.id]
        message_arrays = split_array(messages_filtered, 100)
        
        for message_array in message_arrays:
            await self.remove_list(ctx, message_array)
            
        self.send(channel, f"Removed {len(messages)} messages")
        
    @commands.hybrid_command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    async def sync(self, ctx: commands.Context):
        num = await self.bot.tree.sync()
        self.send(ctx, f"Synced {len(num)} commands")