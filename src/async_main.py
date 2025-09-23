import asyncio
import json
import time
import psutil
import pyperclip
import requests
import subprocess
import websockets
import ctypes
from datetime import datetime
from pathlib import Path
from enum import Enum
from pywinauto import Application
from websockets.exceptions import ConnectionClosed, WebSocketException

# === Config ===
with open('credentials.json') as f:
    credentials = json.load(f)

DISCORD_TOKEN = credentials["token"]
DISCORD_GATEWAY = credentials["DISCORD_Gateway_URL"]
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

def get_passcode(token_name, token_pin=credentials["token_PIN"]):
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

def send_discord_message(channel_id, message, msg_type=DiscordMsgType.REQUEST):
    headers = {"authorization": DISCORD_TOKEN, "content-type": "application/json"}
    payload = {"content": message}
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    if msg_type == DiscordMsgType.VALIDATION:
        url = f"https://discord.com/api/v9/channels/{credentials['val_channel_id']}/messages"
    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        write_log(f"Failed to send Discord message: {e}")

def parse_and_validate(username, msg):
    try:
        if msg.strip().startswith("!getpasscode") and credentials["token_name"] in msg:
            _, token_name = msg.strip().split(':')
            if username in auth_data and token_name == credentials["token_name"]:
                return token_name, credentials["token_PIN"]
    except:
        pass
    return None, None

async def heartbeat(ws, interval):
    while True:
        await asyncio.sleep(interval)
        try:
            await ws.send(json.dumps({"op": 1, "d": None}))
        except Exception as e:
            write_log(f"💓 Heartbeat failed: {e}")
            break

async def handle_messages(ws):
    while True:
        try:
            raw = await ws.recv()
            response = json.loads(raw)

            d = response.get("d")
            if d and "content" in d:
                content = d["content"]
                username = d["author"]["username"]
                channel_id = d["channel_id"]

                if "!getpasscode" not in content or channel_id != credentials["req_channel_id"]:
                    continue

                token_name, token_pin = parse_and_validate(username, content)
                if token_name:
                    print(f"{username}: {content}")
                    send_discord_message(channel_id, f"🔄 Getting passcode for `{token_name}`, requested by {username}...")
                    passcode = get_passcode(token_name, token_pin)
                    send_discord_message(channel_id, f"🔐 Passcode for `{token_name}`: `{passcode}`")

        except ConnectionClosed as e:
            write_log(f"❌ WebSocket closed: {e}. Triggering reconnect...")
            raise
        except asyncio.TimeoutError:
            #write_log("⏳ WebSocket recv timed out. Continuing...")
            continue
        except WebSocketException as e:
            write_log(f"⚠️ WebSocket error: {e}")
            raise
        except Exception as e:
            write_log(f"🚨 Unexpected error: {e}")
            await asyncio.sleep(5)

async def connect_loop():
    while True:
        try:
            async with websockets.connect(DISCORD_GATEWAY) as ws:
                hello_event = json.loads(await ws.recv())
                heartbeat_interval = hello_event["d"]["heartbeat_interval"] / 1000

                await ws.send(json.dumps({
                    "op": 2,
                    "d": {
                        "token": DISCORD_TOKEN,
                        "properties": {
                            "$os": "windows",
                            "$browser": "chrome",
                            "$device": "pc"
                        }
                    }
                }))
                write_log("✅ Connected to Discord Gateway")

                asyncio.create_task(heartbeat(ws, heartbeat_interval))
                await handle_messages(ws)

        except Exception as e:
            write_log(f"🔁 Reconnecting in 5 seconds due to error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(connect_loop())
    except KeyboardInterrupt:
        write_log("🛑 Bot stopped manually.")
    except Exception as e:
        write_log(f"💥 Fatal error: {e}")
