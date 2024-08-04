import json

from typing import Union

import discord
from discord.ext import commands

from utils import Log, LogLevel
from .bot import BaseBot, PrettyType
from db import Database

class AppModule(Log):
    def __init__(self, app, required_settings=[]):
        super(AppModule, self).__init__()
        self.app : App          = app
        self.name               = self.__class__.__name__    
        self.required_settings  = required_settings

        self.app._check_required_settings()

    def send_pretty(self, entry: Union[discord.TextChannel, discord.VoiceChannel, discord.Message, discord.Interaction, commands.Context], type: PrettyType, **kwargs):
        cor = BaseBot.send_pretty(entry, type, **kwargs)
        self.bot.run_async(cor)
    
    def send(self, ctx: commands.Context, message: str, **kwargs):
        cor = BaseBot.send(ctx, message, **kwargs)
        self.bot.run_async(cor)

    def edit(self, msg: discord.Message, message: str, **kwargs):
        cor = BaseBot.edit(msg, message, **kwargs)
        self.bot.run_async(cor)
    
    @property
    def bot(self) -> BaseBot:
        return self.app.bot

    @property
    def db(self) -> Database:
        return self.app.db

    @property
    def settings(self) -> dict:
        return self.app.settings
    
class App(Log):
    def __init__(self):
        try:
            with open("settings.json", 'r') as file:
                self.settings = json.load(file)

            self.required_settings = [                    
                "db_ip",
                "db_port",
                "db_user",
                "db_pass",
                "db_db",
                    
                "token"
            ]

            self._check_required_settings()

        except FileNotFoundError:
            self.log("Can't find settings.json", LogLevel.FATAL)
            exit(1)
        except RuntimeError as e:
            self.log(str(e), LogLevel.FATAL)
            exit(1)

        self.db = Database(self.settings["db_ip"],
                           self.settings["db_port"], 
                           self.settings["db_user"], 
                           self.settings["db_pass"], 
                           self.settings["db_db"])

        self.bot    : BaseBot   = BaseBot('**', self.settings)
        self.bot.add_listener(self.on_ready)
        self.modules = {}

    def _check_settings_exist(self, p):
        if not (p in self.settings):
            raise RuntimeError(f"Missing setting {p} in settings.json")

    def _check_required_settings(self):
        for setting in self.required_settings:
            self._check_settings_exist(setting)
            
    def addModule(self, c):
        try:
            inst = c(self)
            self.log(f"Adding module {inst.name} to app")
            self.modules[inst.name] = inst
        except RuntimeError as e:
            self.log(str(e), LogLevel.FATAL)
            exit(1)

    async def on_ready(self):
        for name, inst in self.modules.items():
            if isinstance(inst, commands.Cog):
                self.log(f"Adding Cog {name} to bot")
                await self.bot.add_cog(inst)

        synced = await self.bot.tree.sync()
        self.log(f"Synced {len(synced)} global commands")
        
    def run(self):
        self.bot.run(self.settings["token"])