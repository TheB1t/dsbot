import json
import random

import functools

from typing import Union
from functools import wraps

import discord
from discord.ext import commands, tasks

from utils import Log, LogLevel, Cache, BotInternalException, get_file_extension

from enum import Enum, auto

class PrettyType(Enum):
    SUCCESS     = auto()
    ERROR       = auto()
    WARNING     = auto()
    INFO        = auto()

class BaseBot(commands.Bot, Log):
    def __init__(self, command_prefix: str, settings):
        intents                         = discord.Intents.default()
        intents.guild_messages          = True
        intents.dm_messages             = True
        intents.members                 = True
        intents.message_content         = True
        
        super().__init__(command_prefix, intents=intents)

        self.__cache                    = Cache()
        self.__cache.load()
                
    def getMessageString(self, ctx: commands.Context):
        message = ctx.message
        _server = message.guild.name if message.guild else 'DM'
        _ch = 'DM' if _server == 'DM' else message.channel
        _msg = message.content if message.content else 'empty'
        _att = [f"{a.filename} # {a.size}" for a in message.attachments]
        return f"[{_server}][{_ch}] <{message.author}> -> {_msg} ({_att})"

    def log_function_call(log_message):
        """Decorator to log function calls with a custom message."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                print(f"{log_message}: Calling {func.__name__} with arguments {args} and keyword arguments {kwargs}")
                result = func(*args, **kwargs)
                print(f"{log_message}: {func.__name__} returned {result}")
                return result
            return wrapper
        return decorator

    def run_async(self, func):
        return self.loop.create_task(func)

    @staticmethod
    async def send_pretty(entry: Union[discord.TextChannel, discord.VoiceChannel, discord.Interaction, commands.Context], type: PrettyType, title: str = None, message: str = None, fields: dict = None, view: discord.ui.View = None, delete_after=None, ephemeral=True):       
        color = discord.Color.light_gray()
        
        if type == PrettyType.SUCCESS:
            color = discord.Color.green()
        elif type == PrettyType.ERROR:
            color = discord.Color.red()
        elif type == PrettyType.WARNING:
            color = discord.Color.orange()
        elif type == PrettyType.INFO:
            color = discord.Color.blue()
        
        embed = discord.Embed(title=title, description=message, color=color, timestamp=discord.utils.utcnow())
        
        embed.set_footer(text=type.name)   

        if fields:
            for key, value in fields.items():
                embed.add_field(name=key, value=value)
            
        try:
            if isinstance(entry, discord.Interaction):
                view = view if view else discord.interactions.MISSING
                return await entry.response.send_message(embed=embed, view=view, ephemeral=ephemeral)
            elif isinstance(entry, discord.TextChannel) or isinstance(entry, discord.VoiceChannel):
                return await entry.send(embed=embed, view=view, delete_after=delete_after)
            elif isinstance(entry, commands.Context):
                if (entry.prefix == '/'):
                    return await entry.send(embed=embed, view=view, ephemeral=ephemeral)
                
                return await entry.send(embed=embed, view=view, delete_after=delete_after)
        
        except Exception as e:
            raise BotInternalException(str(e))
    
    @staticmethod
    async def send(entry: Union[discord.TextChannel, commands.Context], message: str, delete_after=None, ephemeral=True):
        try:
            if isinstance(entry, discord.TextChannel) or isinstance(entry, discord.VoiceChannel):
                return await entry.send(message, delete_after=delete_after)
            elif isinstance(entry, commands.Context):
                if (entry.prefix == '/'):
                    return await entry.send(message, ephemeral=ephemeral)
                
                return await entry.send(message, delete_after=delete_after)

        except Exception as e:
            raise BotInternalException(str(e))

    @staticmethod
    async def edit(msg: discord.Message, message: str, delete_after=None):
        try:
            await msg.edit(content=message)
            
            if delete_after and not msg.flags.ephemeral:
                await msg.delete(delay=delete_after)
        except Exception as e:
            raise BotInternalException(str(e))

    # [BOT] Events
    async def on_ready(self):
        self.log(f"[AUTH] ({self.user.id}) <{self.user.name}> logged in")

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound) or isinstance(error, commands.MissingRequiredArgument):
            await BaseBot.send_pretty(ctx, PrettyType.ERROR, "Error", str(error))
            return
        
        if isinstance(error, commands.HybridCommandError):
            error = error.original

        if isinstance(error, commands.CommandInvokeError) or isinstance(error, discord.app_commands.errors.CommandInvokeError):
            error = error.original

            if isinstance(error, BotInternalException):
                self.log(str(error), LogLevel.WARN)
                await BaseBot.send_pretty(ctx, PrettyType.ERROR, "Error", str(error))
                return
            
        raise error

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        ctx = await self.get_context(message)
        if not len(message.content):
            return
        
        if ctx.prefix != self.command_prefix:
            return
        
        _msg = self.getMessageString(ctx)
        self.log(_msg)
        await self.process_commands(message)