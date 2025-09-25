import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
# please enable the intents manually here as well as in the discord developer portal
intent = discord.Intents.default()
intent.message_content = True
intent.members = True

bot = commands.Bot(command_prefix='!', intents=intent)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user.name}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    # if 'hello' in message.content.lower():
    #     await message.channel.send(f'Hello, {message.author.mention}!')
    
    # Add a space after the colon if missing, but only for !getpasscode command
    print(f"Received message: {message.content}")

    # Preprocess: Add a space after colon for !getpasscode
    if message.content.startswith('!getpasscode:') and not message.content.startswith('!getpasscode: '):
        parts = message.content.split(':', 1)
        if len(parts) == 2:
            # Create a copy of the message with the fixed content
            fixed_content = f"{parts[0]}: {parts[1]}"
            # Create a context with the fixed content
            ctx = await bot.get_context(message)
            # Manually invoke the command with the fixed argument
            await bot.invoke(await bot.get_command('getpasscode').callback(ctx, arg=parts[1].strip()))
            return
    
    #Important to add this line to allow commands to be processed
    print(f"Processed message content: {message}")
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    await member.send(f'Welcome to the server, {member.name}!')
    channel = discord.utils.get(member.guild.text_channels, name='general')
    if channel:
        await channel.send(f'Welcome to the server, {member.mention}!')

@bot.command()
async def test(ctx):
    await ctx.send(f"Test command received, {ctx.author.mention}!")

@bot.command()
async def dm(ctx, *, msg):
    await ctx.author.send(f'Replying in DM to you msg: {msg}')

@bot.command()
async def reply(ctx):
    await ctx.reply(f'{ctx.author.mention}\nThis is reply to your message: {ctx.message.content}')

@bot.command()
async def getpasscode(ctx, *, arg=None):
    print(f"getpasscode command invoked with arg: {ctx}")
    await ctx.send(f'{ctx.author.mention}\nThis is passcode reply to your message: {arg}')

bot.run(token, log_handler=handler, log_level=logging.DEBUG)