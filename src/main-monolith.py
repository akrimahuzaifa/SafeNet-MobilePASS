import discord
from discord.ext import commands
import logging
import json
import os
import asyncio
import time
import psutil
import pyperclip
import subprocess
import ctypes
from datetime import datetime
from pathlib import Path
from enum import Enum
from pywinauto import Application

# === Config ===
with open('credentials.json') as f:
    credentials = json.load(f)

DISCORD_TOKEN = credentials["appToken"]
SAFENET_PATH = r"C:\\Program Files (x86)\\SafeNet\\Authentication\\MobilePASS\\MobilePASS.exe"
auth_data = credentials["authorized_users"]

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"Error_Logs_{datetime.now().strftime('%Y-%m-%d')}.log"

class DiscordMsgType(Enum):
    REQUEST = 1
    VALIDATION = 2

def write_log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full = f"[{timestamp}] {msg}"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(full + "\n")
    print(full)

def is_desktop_active():
    return ctypes.windll.user32.GetForegroundWindow() != 0

def launch_safenet():
    if not any("MobilePASS" in p.name() for p in psutil.process_iter()):
        subprocess.Popen(SAFENET_PATH)
        time.sleep(5)

async def get_passcode(token_name, token_pin=credentials["token_PIN"]):
    if not is_desktop_active():
        return "❌ Cannot retrieve passcode: No active desktop. Ensure screen is unlocked and session active."
    try:
        launch_safenet()
        app = Application(backend="uia").connect(title="MobilePASS")
        window = app.window(title_re=".*MobilePASS.*")
        window.set_focus()

        if window.child_window(title="Copy Passcode", control_type="Button").exists(timeout=2):
            window.child_window(title="Copy Passcode", control_type="Button").click_input()
            time.sleep(0.5)
            return pyperclip.paste()

        if window.child_window(title=token_name, control_type="ListItem").exists(timeout=2):
            window.child_window(title=token_name, control_type="ListItem").click_input()
            time.sleep(1)
            window.child_window(control_type="Edit").type_keys(token_pin)
            window.child_window(title="Continue", control_type="Button").click_input()
            time.sleep(2)
            window.child_window(title="Copy Passcode", control_type="Button").click_input()
            time.sleep(0.5)
            return pyperclip.paste()

        return "❗️Failed to retrieve passcode: SafeNet UI elements not found."
    except Exception as e:
        write_log(f"⚠️ get_passcode failed: {e}")
        return f"❌ Failed to retrieve passcode: {e}"

def parse_and_validate(username, msg):
    try:
        #print(f"parse_and_validate called with username: '{username}', msg: '{msg}'")
        if msg.strip().startswith("!getpasscode") and credentials["token_name"] in msg:
            _, token_name = msg.strip().split(' ')
            #print(f"cmd: {_}")
            #print(f"Parsed token_name: =='{token_name}'== from message.")

            # Disabled user authentication: allow any user to request passcode
            # if username in auth_data and token_name == credentials["token_name"]:
            #     return token_name, credentials["token_PIN"]
            if token_name.strip() == credentials["token_name"]:
                return token_name.strip(), credentials["token_PIN"]
    except:
        pass
    return None, None

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    write_log(f'✅ Logged in as {bot.user.name}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

@bot.command()
async def getpasscode(ctx, *, arg=None):
    username = ctx.author.name
    msg = ctx.message.content
    token_name, token_pin = parse_and_validate(username, msg)

    # Only allow command in a specific channel
    allowed_channel_id = credentials.get("req_channel_id")
    expected_token_name = credentials["token_name"]

    # Only process if the command is for this bot's token
    if not (token_name and token_name == expected_token_name):
        # Ignore commands not meant for this bot
        return

    # Now, only check for channel restriction
    if str(ctx.channel.id) != str(allowed_channel_id):
        await ctx.channel.send("❌ This command can only be used in the Dedicated and authorized channel.")
        print("Blocked command from unauthorized channel.")
        return

    await ctx.reply(f"🔄 Getting passcode for `{token_name}`...\nPlease Wait {ctx.author.mention}!")
    passcode = await get_passcode(token_name, token_pin)
    await ctx.reply(f"🔐 Passcode for `{token_name}`: `{passcode}`")

if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN, log_handler=logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w'), log_level=logging.DEBUG)
    except KeyboardInterrupt:
        write_log("🛑 Bot stopped manually.")
    except Exception as e:
        write_log(f"💥 Fatal error: {e}")
