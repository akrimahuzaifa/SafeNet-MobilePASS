import sys
import json
import time
import psutil
import pyperclip
import requests
import subprocess
import threading
import websocket
from pathlib import Path
from datetime import datetime
from pywinauto import Application
from enum import Enum

class DiscordMsgType(Enum):
    REQUEST = 1
    VALIDATION = 2

# === Load Configs ===
with open('credentials.json') as f:
    credentials = json.load(f)

auth_data = credentials["authorized_users"]

DISCORD_TOKEN = credentials["token"]
DISCORD_GATEWAY = credentials["DISCORD_Gateway_URL"]
SAFENET_PATH = r"C:\Program Files (x86)\SafeNet\Authentication\MobilePASS\MobilePASS.exe"

# --- Path Configuration ---
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"Error_Logs_{datetime.now().strftime('%Y-%m-%d')}.log"

def write_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{log_entry}\n")
    print(log_entry)

def launch_safenet():
    if not any("MobilePASS" in p.name() for p in psutil.process_iter()):
        subprocess.Popen(SAFENET_PATH)
        time.sleep(5)

def get_passcode(token_name, token_pin=credentials["token_PIN"]):
    launch_safenet()
    try:
        app = Application(backend="uia").connect(title="MobilePASS", timeout=10)
        window = app.window(title_re=".*MobilePASS.*")
        window.set_focus()

        if window.child_window(title="Copy Passcode", control_type="Button").exists(timeout=2):
            window.child_window(title="Copy Passcode", control_type="Button").click_input()
            time.sleep(0.5)
            return pyperclip.paste()

        if window.child_window(title=token_name, control_type="ListItem").exists(timeout=2):
            window.child_window(title=token_name, control_type="ListItem").click_input()
            time.sleep(1)
            pin_box = window.child_window(control_type="Edit")
            pin_box.type_keys(token_pin)
            window.child_window(title="Continue", control_type="Button").click_input()
            time.sleep(2)
            window.child_window(title="Copy Passcode", control_type="Button").click_input()
            time.sleep(0.5)
            return pyperclip.paste()
        return "❗️Failed to retrieve passcode: Neither token list nor passcode window found."
    except Exception as e:
        write_log(f"⚠️ Failed to retrieve passcode: {str(e)}")
        return f"❌ Failed to retrieve passcode: {e}"

def send_discord_message(channel_id, message, DiscordMsgType=DiscordMsgType.REQUEST):
    headers = {
        "authorization": DISCORD_TOKEN,
        "content-type": "application/json"
    }
    payload = {"content": message}

    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    if DiscordMsgType == DiscordMsgType.VALIDATION:
        url = f"https://discord.com/api/v9/channels/{credentials['val_channel_id']}/messages"
    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        write_log(f"❌ Failed to send Discord message: {e}")

def heartbeat(interval, ws):
    while True:
        try:
            time.sleep(interval)
            heartbeat_json = {"op": 1, "d": None}
            ws.send(json.dumps(heartbeat_json))
        except Exception as e:
            write_log(f"💓 Heartbeat failed: {e}")
            break

def parse_and_validate(username, msg):
    try:
        if msg.strip().startswith("!getpasscode") and (credentials['token_name'] in msg):
            prefix, token_name = msg.strip().split(':')
            if username in auth_data and token_name == credentials['token_name']:
                return token_name, credentials['token_PIN']
    except:
        pass
    return None, None

def watchdog():
    while True:
        time.sleep(300)
        print("🔍 Watchdog check - verifying app status... \n✅ Watchdog check - app is running")
        #write_log("✅ Watchdog check - app is running")

def main():
    ws = websocket.WebSocket()
    try:
        ws.connect(DISCORD_GATEWAY)
        ws.settimeout(30)
        event = json.loads(ws.recv())
        heartbeat_interval = event['d']['heartbeat_interval'] / 1000
        threading.Thread(target=heartbeat, args=(heartbeat_interval, ws), daemon=True).start()
        threading.Thread(target=watchdog, daemon=True).start()

        payload = {
            "op": 2,
            "d": {
                "token": DISCORD_TOKEN,
                "properties": {
                    "$os": "windows",
                    "$browser": "chrome",
                    "$device": "pc"
                }
            }
        }
        ws.send(json.dumps(payload))
        write_log("✅ Connected to Discord WebSocket")

        while True:
            try:
                response_raw = ws.recv()
                response = json.loads(response_raw)

                d = response.get('d')
                if d and 'content' in d:
                    content = d['content']
                    username = d['author']['username']
                    msg_channel_id = d['channel_id']

                    if "!getpasscode" not in content or msg_channel_id != credentials['req_channel_id']:
                        continue

                    token_name, token_pin = parse_and_validate(username, content)
                    if token_name and token_pin:
                        print(f"{username}: {content}")
                        send_discord_message(msg_channel_id, f"🔄 Getting passcode for `{token_name}`, requested by {username}...")
                        passcode = get_passcode(token_name, token_pin)
                        send_discord_message(msg_channel_id, f"🔐 Passcode for `{token_name}`: `{passcode}`")
                        print(f"🔐 Passcode for `{token_name}`: `{passcode}`")
            except websocket.WebSocketTimeoutException:
                #write_log("⏳ WebSocket timeout, continuing...")
                continue
            except websocket.WebSocketConnectionClosedException:
                write_log("❌ WebSocket connection closed. Exiting main() to trigger restart...")
                raise
            except Exception as e:
                write_log(f"🚨 Unexpected error: {e}")
                time.sleep(5)
                continue
    except Exception as e:
        write_log(f"💥 Unhandled error during WebSocket setup: {e}")

if __name__ == "__main__":
    while True:
        try:
            write_log("🔁 Starting main()")
            main()
        except Exception as e:
            write_log(f"💥 Uncaught error in main(): {e}")
        time.sleep(5)
        write_log("🔁 Restarting main() after failure")
