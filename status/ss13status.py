#Standard Imports
import asyncio
import ipaddress
import struct
import select
import socket
import urllib.parse

#Discord Imports
import discord

#Redbot Imports
from redbot.core import commands, checks, Config, utils

__version__ = "0.1.0"
__author__ = "Crossedfall"

BaseCog = getattr(commands, "Cog", object)

class SS13Status(BaseCog):

    def __init__(self, bot):
        global serv

        self.bot = bot
        self.config = Config.get_conf(self, 3257193194, force_registration=True)

        default_guild = {
            "server": "127.0.0.1",
            "game_port": 7777,
            "offline_message": "Currently offline",
            "server_url": "byond://127.0.0.1:7777", 
            "new_round_channel": None,
            "admin_notice_channel": None,
            "comms_key": "default_pwd",
        }

        self.config.register_guild(**default_guild)
        serv = bot.loop.create_task(self.server())
    
    def __unload(self):
        serv.cancel()
        print("No longer listening")

    @commands.guild_only()
    @commands.group()
    async def setstatus(self, ctx):
        """
        Configuration group for the SS13 status command
        """
        pass
    
    @setstatus.command(aliases=['host'])
    @checks.is_owner()
    async def server(self, ctx, host: str):
        """
        Sets the server IP used for status checks
        """
        try:
            ipaddress.ip_address(host)
            await self.config.guild(ctx.guild).server.set(host)
            await ctx.send(f"Server set to `{host}")
        except(ValueError):
            await ctx.send(f"`{host}` is not a valid IP address!")
    
    @setstatus.command()
    @checks.is_owner()
    async def port(self, ctx, port: int):
        """
        Sets the port used for the status checks
        """
        try:
            if 1024 <= port <= 65535:
                await self.config.guild(ctx.guild).game_port.set(port)
                await ctx.send(f"Database port set to: {port}")
            else:
                await ctx.send(f"{port} is not a valid port!")
        except (ValueError, KeyError, AttributeError):
            await ctx.send("There was a problem setting your port. Please check to ensure you're attempting to use a port from 1024 to 65535")

    @setstatus.command()
    @checks.is_owner()
    async def offline(self, ctx, msg: str):
        """
        Set a custom message for whenever the server is offline.
        """ 
        try:
            await self.config.guild(ctx.guild).offline_message.set(msg)
            await ctx.send(f"Offline message set to: `{msg}`")
        except (ValueError, KeyError, AttributeError):
            await ctx.send("There was a problem setting your custom offline message. Please check your entry and try again.")
    
    @setstatus.command()
    @checks.is_owner()
    async def byondurl(self, ctx, url: str):
        """
        Set the byond URL for your server (For embeds)
        """
        try:
            await self.config.guild(ctx.guild).server_url.set(url)
            await ctx.send(f"Server url set to: `{url}`")

        except (ValueError, KeyError, AttributeError):
            await ctx.send("There was a problem setting your server URL. Please check your entry and try again.")
    
    @setstatus.command()
    @checks.is_owner()
    async def newroundnotificationchannel(self, ctx, text_channel: discord.TextChannel):
        """
        Set the text channel to display new round notifications
        """
        try: 
            await self.config.guild(ctx.guild).new_round_channel.set(text_channel.id)
            await ctx.send(f"New round notifications will be sent to: <#{text_channel.id}>")

        except(ValueError, KeyError, AttributeError):
            await ctx.send("There was a problem setting the notification channel. Please check your entry and try again.")

    @setstatus.command()
    @checks.is_owner()
    async def adminchannel(self, ctx, text_channel: discord.TextChannel):
        """
        Set the text channel to display admin notifications
        """
        try:
            await self.config.guild(ctx.guild).admin_notice_channel.set(text_channel.id)
            await ctx.send(f"Admin notifiations will be sent to: <#{text_channel.id}>")

        except(ValueError, KeyError, AttributeError):
            await ctx.send("There was a problem setting the notification channel. Please check your entry and try again.")

    @setstatus.command()
    @checks.is_owner()
    async def commskey(self, ctx, key: str):
        """
        Set the communications key for the server
        """
        try:
            await self.config.guild(ctx.guild).comms_key.set(key)
            await ctx.send("Comms key set. You may wish to edit or otherwise remove the key from this channel.")
        
        except(ValueError, KeyError, AttributeError):
            await ctx.send("There was a problem setting your communications key. Please check your entry and try again.")

    @setstatus.command()
    @checks.admin_or_permissions(administrator=True)
    async def current(self, ctx):
        """
        Lists the current settings
        """
        settings = await self.config.guild(ctx.guild).all()
        embed=discord.Embed(title="__Current Settings:__")
        
        for k, v in settings.items():
            if k is 'comms_key':
                embed.add_field(name=f"{k}:", value="`redacted`", inline=False)
            elif k is 'new_round_channel' or k is 'admin_notice_channel':
                embed.add_field(name=f"{k}:", value=f"<#{v}>", inline=False)
            else:
                embed.add_field(name=f"{k}:", value=v, inline=False)
        
        await ctx.send(embed=embed)

    @commands.guild_only()
    @commands.command()
    async def status(self, ctx):
        """
        Gets the current server status and round details
        """
        server = await self.config.guild(ctx.guild).server()
        port = await self.config.guild(ctx.guild).game_port()        
        msg = await self.config.guild(ctx.guild).offline_message()
        server_url = await self.config.guild(ctx.guild).server_url()

        data = await self.query_server(server, port)

        if not data:
            embed=discord.Embed(title="__Server Status:__", description=f"{msg}", color=0xff0000)
            await ctx.send(embed=embed)

        else:
            duration = int(*data['round_duration'])
            hours = int(round(duration/3600))
            minutes = int(round(duration/60))

            #Might make the embed configurable at a later date

            embed=discord.Embed(color=0x26eaea)
            embed.add_field(name="Version", value=str(*data['version']), inline=True)
            embed.add_field(name="Map", value=str(*data['map_name']), inline=True)
            embed.add_field(name="Mode", value=str(*data['mode']), inline=True)
            embed.add_field(name="Players", value=str(*data['players']), inline=True)
            embed.add_field(name="Admins", value=str(*data['admins']), inline=True)
            embed.add_field(name="Round Duration", value=f"{hours:02d}:{minutes:02d}", inline=True)
            embed.add_field(name="Server Link:", value=f"{server_url}", inline=False)

            await ctx.send(embed=embed)
        

    async def query_server(self, game_server:str, game_port:int ) -> dict:
        """
        Querries the server for information
        """
        querystr = "?status" #Might expand on this later to allow extra queries so I'm making this a seperate string for now
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        try:
            query = b"\x00\x83" + struct.pack('>H', len(querystr) + 6) + b"\x00\x00\x00\x00\x00" + querystr.encode() + b"\x00" #Creates a packet for byond according to TG's standard
            conn.settimeout(20) #Byond is slow, timeout set relatively high to account for any latency
            conn.connect((game_server, game_port)) 

            conn.sendall(query)

            data = conn.recv(4096)
            print(data)

            parsed_data = urllib.parse.parse_qs(data[5:-1].decode())

            return parsed_data
            """
            +----------------+--------+
            | Reported Items | Return |
            +----------------+--------+
            | Version        | str    |
            | mode           | str    |
            | respawn        | int    |
            | enter          | int    |
            | vote           | int    |
            | ai             | int    |
            | host           | str    |
            | active_players | int    |
            | players        | int    |
            | revision       | str    |
            | revision_date  | date   |
            | admins         | int    |
            | gamestate      | int    |
            | map_name       | str    |
            | security_level | str    |
            | round_duration | int    |
            | shuttle_mode   | str    |
            | shuttle_timer  | str    |
            +----------------+--------+
            """
        except ConnectionRefusedError:
            return None

        finally:
            conn.close()

    async def handle_data(self, reader, writer):
        data = await reader.read(10000)
        msg = data.decode()
        msg = msg.split(" ")[1]
        addr = writer.get_extra_info('peername')

        print(f"Received {msg!r} from {addr!r}")
        
        parsed_data = urllib.parse.parse_qs(msg[2:len(msg)])

        print(parsed_data)

        if 'serverStart' in parsed_data:
            await self.bot.get_channel(447654424521998337).send("New round starting!")
        elif ('admin' in parsed_data['announce_channel']):
            await self.bot.get_channel(447654424521998337).send(f"New ticket: {str(*parsed_data['announce'])}")
        else:
            pass

        writer.close()


    async def server(self):
        await asyncio.sleep(10)

        server = await asyncio.start_server(self.handle_data, '127.0.0.1', 8080)
        addr = server.sockets[0].getsockname()

        print(f'Listening on {addr}')

        async with server:
            await server.serve_forever()