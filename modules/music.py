import asyncio 
import yt_dlp as youtube_dl
from googleapiclient.discovery import build as yt_build

from typing import Union
from functools import wraps

import discord
from discord.ext import commands

from app import App, AppModule, PrettyType, BaseBot
from utils import Log, LogLevel, BotInternalException, split_array
from .priv_system import PrivSystem, PrivSystemLevels

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'force-ipv4': True,
    'cachedir': False,
    'add_header': [
        'Accept-Encoding: gzip, deflate',
        'Sec-Fetch-Mode: cors',
    ],
    'geo_bypass': True,
    'geo_bypass_country': 'KZ'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer, Log):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')
        
        self.log(f"YTDLSource: {self.title} created")
        
    def __del__(self):
        self.log(f"YTDLSource: {self.title} deleted")
        
    @classmethod
    def from_url(cls, url, *, stream=False):
        ytdl.cache.remove()
        data = ytdl.extract_info(url, download=not stream)

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Song(Log):
    def __init__(self, url):
        self._stream : YTDLSource = None
        self._url = url
        self.log(f"Song: {self.url} created")

    def __del__(self):
        self.log(f"Song: {self.url} deleted")
        self.stream.cleanup()

    def load(self):
        self._stream = YTDLSource.from_url(self._url, stream=True)

    @property
    def is_ended(self):
        if self._stream:
            original : discord.FFmpegPCMAudio = self._stream.original
            if original._stdout:
                return self._stream.read() == b''
        
        return True

    @property
    def stream(self):
        if self.is_ended:
            self.load()

        return self._stream
    
    @property
    def title(self):
        return self.stream.title
    
    @property
    def url(self):
        if self._url.startswith("https://www.youtube.com/watch?v="):
            return self._url
        else:
            return f"https://www.youtube.com/watch?v={self._url}"
        
class MusicPlayer(Log):
    def __init__(self, module : AppModule, guild : discord.Guild, text : discord.TextChannel):
        self.module = module
        self.text = text
        self.guild = guild
        self._current : Song = None
        self.queue = []
        self.loop = False
    
    def add_song(self, song):
        if len(self.queue) > 0 or self.current:
            self.module.send_pretty(self.text, PrettyType.SUCCESS, title = "Added to queue", fields = {
                "Title": song.title,
                "URL": song.url,
                "Position": len(self.queue)
            })
        self.queue.append(song)

    def del_song(self, index):
        if index < len(self.queue):
            self.module.send_pretty(self.text, PrettyType.SUCCESS, title = "Deleted from queue", fields = {
                "Title": self.queue[index].title,
                "URL": self.queue[index].url
            })
            self.queue.pop(index)
        else:
            self.module.send_pretty(self.text, PrettyType.ERROR, title = "Index out of range")

    def _after(self, e):
        self.play_next()

    def _play(self, song : Song):
        self.guild.voice_client.play(song.stream, after=self._after)

    def _stop(self):
        self.guild.voice_client.stop()

    def _pause(self):
        self.guild.voice_client.pause()
        
    def _resume(self):
        self.guild.voice_client.resume()

    @property
    def is_playing(self):
        return self.guild.voice_client.is_playing()
    
    @property
    def is_paused(self):
        return self.guild.voice_client.is_paused()
    
    @property
    def current(self) -> Song:
        if self._current and not self._current.is_ended:
            return self._current
        
        if self.loop:
            return self._current
        
        if len(self.queue) <= 0:
            return None
        
        self._current = self.queue.pop(0)
        self.module.send_pretty(self.text, PrettyType.SUCCESS, title = "Playing", fields = {
            "Title": self._current.title,
            "URL": self._current.url
        })

        return self._current

    def play_next(self):
        if self.current:
            self._play(self.current)
        else:
            self._stop()
            self.module.send_pretty(self.text, PrettyType.INFO, title = "Queue is empty")

    def skip(self):
        if not len(self.queue) and not self.is_playing:
            self.module.send_pretty(self.text, PrettyType.WARNING, title = "Nothing to skip")
        else:
            self._stop()

    def stop(self):
        if self.is_playing:
            self._stop()
            self.module.send_pretty(self.text, PrettyType.SUCCESS, title = "Stopped")
        else:
            self.module.send_pretty(self.text, PrettyType.WARNING, title = "Nothing to stop")
        
        self._current = None
        self.clear()
        
    def pause(self):
        if self.is_playing and not self.is_paused:
            self._pause()
            self.module.send_pretty(self.text, PrettyType.SUCCESS, title = "Paused")
        else:
            self.module.send_pretty(self.text, PrettyType.WARNING, title = "Nothing to pause")

    def resume(self):
        if not self.is_playing and self.is_paused:
            self._resume()
            self.module.send_pretty(self.text, PrettyType.SUCCESS, title = "Resumed")
        else:
            self.module.send_pretty(self.text, PrettyType.WARNING, title = "Nothing to resume")

    def clear(self):
        self.queue = []

    def print_queue(self):
        if len(self.queue) > 0:
            self.module.send_pretty(self.text, PrettyType.SUCCESS, title = "Queue", message = "\n".join([f"{i}: {song.title}" for i, song in enumerate(self.queue)]))
        else:
            self.module.send_pretty(self.text, PrettyType.WARNING, title = "Queue is empty")

class Music(commands.Cog, AppModule):
    def __init__(self, app: App):
        super(Music, self).__init__(app, [
            "google_api_key"    
        ])

        self.youtube = yt_build('youtube', 'v3', developerKey=self.settings["google_api_key"])
        self.music_players = {}

    def _find(self, query : str, max_results : int = 1):
        return self.youtube.search().list(q=query, part='id', maxResults=max_results).execute()

    async def _join(self, ctx : commands.Context, channel : discord.VoiceChannel):
        if ctx.voice_client:
            if ctx.voice_client.channel != channel:
                self.log(f"Moving to {channel.name}")
                await ctx.voice_client.move_to(channel)
            else:
                self.log(f"Already in {channel.name}")
        else:
            self.log(f"Joining {channel.name}")
            await channel.connect()

    async def _leave(self, ctx : commands.Context):
        if ctx.voice_client:
            self.send_pretty(ctx, PrettyType.SUCCESS, title = "Left", fields = {
                "Channel": ctx.voice_client.channel.mention
            })
            await ctx.voice_client.disconnect()
        else:
            self.send_pretty(ctx, PrettyType.ERROR, title = "Not connected")

    def _get_channel(self, ctx : commands.Context) -> discord.VoiceChannel:
        if ctx.author.voice:
            return ctx.author.voice.channel
        else:
            raise BotInternalException("User not in voice channel")    

    async def _get_player(self, ctx : commands.Context, join : bool = True):
        channel = self._get_channel(ctx)
                
        if not ctx.voice_client and join:
            await self._join(ctx, channel)

        if channel.guild.id in self.music_players:
            player = self.music_players[channel.guild.id]
            player.channel = ctx.channel
            return player
        else:
            player = MusicPlayer(self, ctx.guild, ctx.channel)
            self.music_players[channel.guild.id] = player
            return player

    def silent():
        def decorator(func):
            @wraps(func)
            async def wrapper(self, ctx: Union[commands.Context, discord.Interaction], *args, **kwargs):                    
                if ctx.prefix == '/':
                    await BaseBot.send_pretty(ctx, PrettyType.INFO, title = "Done")

                return await func(self, ctx, *args, **kwargs)
            return wrapper
        return decorator

    @commands.hybrid_group(name="music", fallback="join")
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def _music(self, ctx: commands.Context):
        channel = self._get_channel(ctx)
        
        await self._join(ctx, channel)
            
    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def leave(self, ctx: commands.Context):
        await self._leave(ctx)
            
    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def play(self, ctx: commands.Context, url: str):        
        player = await self._get_player(ctx)
        song = Song(url)
        player.add_song(song)
        
        if not player.is_playing:
            player.play_next()
            
    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def find(self, ctx: commands.Context, *, query: str):
        try:
            self.log(f"Finding {query}")
            result = self._find(query)
            self.log(f"Found {len(result['items'])} results")
            self.log(f"Result: {result['items'][0]}")
            url = result["items"][0]["id"]["videoId"]
        except Exception as e:
            raise BotInternalException(f"Query failed. Error: {str(e)}")
        
        player = await self._get_player(ctx)
        song = Song(url)
        player.add_song(song)
            
        if not player.is_playing:
            player.play_next()
            
    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def stop(self, ctx: commands.Context):
        player = await self._get_player(ctx, False)
        player.stop()
            
    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def next(self, ctx: commands.Context):        
        player = await self._get_player(ctx, False)
        player.skip()
            
    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def queue(self, ctx: commands.Context):        
        player = await self._get_player(ctx, False)
        player.print_queue()

    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def delete(self, ctx: commands.Context, index: int):        
        player = await self._get_player(ctx, False)
        player.del_song(index)

    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def loop(self, ctx: commands.Context):
        player = await self._get_player(ctx, False)
        
        if player.loop:
            player.loop = False
            self.send_pretty(ctx, PrettyType.SUCCESS, title = "Loop disabled")
        else:
            player.loop = True
            self.send_pretty(ctx, PrettyType.SUCCESS, title = "Loop enabled")
            
    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def pause(self, ctx: commands.Context):
        player = await self._get_player(ctx, False)
        player.pause()
        
    @_music.command()
    @PrivSystem.withPriv(PrivSystemLevels.USER)
    @silent()
    async def resume(self, ctx: commands.Context):
        player = await self._get_player(ctx, False)
        player.resume()