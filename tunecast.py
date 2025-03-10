import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from collections import deque
import re

# Configuration for youtube_dl to only download audio and to be quiet in console output
ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

# IMPORTANT: Remove privileged intents that aren't enabled in the Discord Developer Portal
intents = discord.Intents.default()
intents.message_content = True # Changed to False as this is a privileged intent

# FFmpeg options for processing audio
ffmpeg_options = {
    'executable': 'C:\\ffmpeg\\bin\\ffmpeg.exe',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Class to handle creating an audio source from a YouTube URL
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')
        self.requester = None

    @classmethod
    async def create_source(cls, search, *, loop=None, requester=None):
        loop = loop or asyncio.get_event_loop()
        
        # Determine if search is a URL or search term
        if not re.match(r'https?://', search):
            search = f"ytsearch:{search}"
            
        # Extract the data in a separate thread to not block the event loop
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
        
        if 'entries' in data:
            # Take first item from a playlist
            data = data['entries'][0]
            
        source = cls(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), data=data)
        source.requester = requester
        return source

# Music player class to handle queue and playback
class MusicPlayer:
    def __init__(self, ctx):
        self.bot = ctx.bot
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.cog = ctx.cog
        
        self.queue = deque()
        self.next = asyncio.Event()
        self.current = None
        self.volume = 0.5
        self.now_playing = None
        
        ctx.bot.loop.create_task(self.player_loop())
        
    async def player_loop(self):
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            self.next.clear()
            
            if not self.queue:
                # Wait for songs to be added to the queue
                await asyncio.sleep(1)
                continue
                
            # Get the next song from the queue
            source = self.queue.popleft()
            self.current = source
            
            self.guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            await self.channel.send(f"🎵 Now playing: **{source.title}**")
            
            # Wait for the song to finish
            await self.next.wait()
            self.current = None

# Create the bot with a command prefix - CHANGED TO > HERE
bot = commands.Bot(command_prefix='>', intents=intents)

# Store music players for different guilds
players = {}

# Get or create a music player for a guild
def get_player(ctx):
    if ctx.guild.id not in players:
        players[ctx.guild.id] = MusicPlayer(ctx)
    return players[ctx.guild.id]

# Events
@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=">help for commands"))

# Command for the bot to join the voice channel
@bot.command(name='join', help='Joins the voice channel you are in.')
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(f"Joined {channel.name}")
    else:
        await ctx.send("You are not connected to a voice channel.")

# Command to disconnect the bot from the voice channel
@bot.command(name='leave', help='Leaves the voice channel and clears the queue.')
async def leave(ctx):
    if ctx.voice_client:
        if ctx.guild.id in players:
            del players[ctx.guild.id]
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel and cleared the queue.")
    else:
        await ctx.send("I'm not connected to any voice channel.")

# Command to play a song from a YouTube URL or search term
@bot.command(name='play', help='Plays a song from YouTube URL or search term.')
async def play(ctx, *, query: str):
    if ctx.author.voice is None:
        return await ctx.send("You need to be in a voice channel to play music.")
    
    if ctx.voice_client is None:
        await ctx.author.voice.channel.connect()
    
    async with ctx.typing():
        try:
            player = get_player(ctx)
            source = await YTDLSource.create_source(query, loop=bot.loop, requester=ctx.author)
            
            player.queue.append(source)
            
            await ctx.send(f"Added **{source.title}** to the queue.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

# Command to show the current queue
@bot.command(name='queue', help='Shows the current song queue.')
async def queue(ctx):
    player = get_player(ctx)
    
    if not player.queue and not player.current:
        return await ctx.send("The queue is empty.")
    
    queue_list = "**Current Queue:**\n"
    
    if player.current:
        queue_list += f"Currently Playing: {player.current.title}\n\n"
    
    if player.queue:
        for i, song in enumerate(player.queue, 1):
            queue_list += f"{i}. {song.title}\n"
    
    await ctx.send(queue_list)

# Command to skip the current song
@bot.command(name='skip', help='Skips the current song.')
async def skip(ctx):
    if ctx.voice_client is None:
        return await ctx.send("I'm not playing any music.")
    
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the current song.")
    else:
        await ctx.send("There is no song playing to skip.")

# Command to pause the current song
@bot.command(name='pause', help='Pauses the current song.')
async def pause(ctx):
    if ctx.voice_client is None:
        return await ctx.send("I'm not playing any music.")
    
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the music.")
    else:
        await ctx.send("The music is already paused.")

# Command to resume the current song
@bot.command(name='resume', help='Resumes the current song.')
async def resume(ctx):
    if ctx.voice_client is None:
        return await ctx.send("I'm not connected to a voice channel.")
    
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the music.")
    else:
        await ctx.send("The music is not paused.")

# Command to stop playing and clear the queue
@bot.command(name='stop', help='Stops playing and clears the queue.')
async def stop(ctx):
    if ctx.voice_client is None:
        return await ctx.send("I'm not playing any music.")
    
    if ctx.guild.id in players:
        del players[ctx.guild.id]
    
    ctx.voice_client.stop()
    await ctx.send("Stopped playing and cleared the queue.")

# Command to change the volume
@bot.command(name='volume', help='Changes the player volume (0-100).')
async def volume(ctx, volume: int):
    if ctx.voice_client is None:
        return await ctx.send("I'm not connected to a voice channel.")
    
    if 0 > volume > 100:
        return await ctx.send("Volume must be between 0 and 100.")
    
    ctx.voice_client.source.volume = volume / 100
    await ctx.send(f"Changed volume to {volume}%")

# Command to show help for the bot
@bot.command(name='helpmusic', help='Shows all available commands for the music bot.')
async def helpmusic(ctx):
    commands_list = """
    **TuneCast Bot Commands:**
    >join - Join your voice channel
    >play <song> - Play a song by URL or search term
    >queue - Show the current queue
    >skip - Skip the current song
    >pause - Pause the current song
    >resume - Resume the paused song
    >stop - Stop playing and clear the queue
    >leave - Leave the voice channel
    >volume <0-100> - Change the player volume
    """
    await ctx.send(commands_list)

# Replace with your actual Discord bot token
bot.run('TOKEN')
