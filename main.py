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
from datetime import datetime, timedelta
from pywinauto import Application
from enum import Enum

class DiscordMsgType(Enum):
    REQUEST = 1
    VALIDATION = 2

# === Load Configs FCHOWD ===
with open('credentials.json') as f:
    credentials = json.load(f)

auth_data = credentials["authorized_users"]

DISCORD_TOKEN = credentials["token"]
DISCORD_GATEWAY = credentials["DISCORD_Gateway_URL"]
SAFENET_PATH = r"C:\Program Files (x86)\SafeNet\Authentication\MobilePASS\MobilePASS.exe"  # Adjust if needed

# --- Path Configuration ---
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

# --- Log Directory and File Setup ---
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"Error_Logs_{datetime.now().strftime('%Y-%m-%d')}.log"

# --- Logging Setup ---
def write_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{log_entry}\n")
    print(log_entry)

# === Helper: Launch SafeNet ===
def launch_safenet():
    if not any("MobilePASS" in p.name() for p in psutil.process_iter()):
        subprocess.Popen(SAFENET_PATH)
        time.sleep(5)

# === Helper: Automate SafeNet ===
def get_passcode(token_name, token_pin=credentials["token_PIN"]):
    launch_safenet()
    app = Application(backend="uia").connect(title="MobilePASS")
    window = app.window(title_re=".*MobilePASS.*")
    window.set_focus()

    try:
        # Check if "Copy Passcode" button is present (passcode window still open)
        if window.child_window(title="Copy Passcode", control_type="Button").exists(timeout=2):
            # Optionally, click it to copy the passcode again
            window.child_window(title="Copy Passcode", control_type="Button").click_input()
            time.sleep(0.5)
            return pyperclip.paste()
        # Otherwise, proceed with normal flow
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

# === Discord Utilities ===
def send_discord_message(channel_id, message, DiscordMsgType=DiscordMsgType.REQUEST):
    headers = {
        "authorization": DISCORD_TOKEN,
        "content-type": "application/json"
    }
    payload = {
        "content": message
    }
    
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    if DiscordMsgType == DiscordMsgType.VALIDATION:
        url = f"https://discord.com/api/v9/channels/{credentials['val_channel_id']}/messages"
    requests.post(url, headers=headers, json=payload)

# === WebSocket Helpers ===
def send_json_request(ws, request):
    ws.send(json.dumps(request))

def recieve_json_response(ws):
    return json.loads(ws.recv())

def heartbeat(interval, ws):
    while True:
        time.sleep(interval)
        heartbeat_json = {"op": 1, "d": None}
        send_json_request(ws, heartbeat_json)

# === Auth Logic ===
def parse_and_validate(username, msg):
    try:
        #print(f"checking conditions for received message: {msg}")
        print(f"Message start with !getpasscode: {msg.strip().startswith("!getpasscode")}")
        print(f"Message contains Token name {credentials['token_name2']}: {credentials['token_name2'] in msg}")

        if msg.strip().startswith("!getpasscode") and (credentials['token_name2'] in msg):
            #print(f"Received message: {msg}")
            #print("Ignoring !getpasscode command")
            prefix, token_name = msg.strip().split(':')

            # Validate allowed users and token name    
            if username in auth_data and token_name == credentials['token_name2']:
                #print(f"User ID and token name condition is true")
                print(f"Credentials token_name: {token_name}")
                print(f"Credentials token_pin: {credentials['token_PIN']}")
                
                return token_name, credentials['token_PIN']
        else:
            print("Ignoring message, does not start with !getpasscode or does not contain valid token names")
            #send_discord_message(credentials['req_channel_id'], "❌ VALIDATION: Ignoring message, does not start with !getpasscode or does not contain valid token names. Use format: `!getpasscode:token_name`", DiscordMsgType.VALIDATION)
            return None, None
    except:
        return None, None
    return None, None

# === Main Bot Logic ===
def main():
    ws = websocket.WebSocket()
    ws.connect(DISCORD_GATEWAY)
    event = recieve_json_response(ws)

    heartbeat_interval = event['d']['heartbeat_interval'] / 1000
    threading.Thread(target=heartbeat, args=(heartbeat_interval, ws), daemon=True).start()

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
    send_json_request(ws, payload)
    print("Connected to Discord WebSocket")
    time.sleep(1)  # Allow some time for the connection to establish
    while True:
        response = recieve_json_response(ws)
        try:
            if 'd' in response and 'content' in response['d']:
                content = response['d']['content']
                username = response['d']['author']['username']
                request_channel_id = response['d']['channel_id']

                print(f"{username}: {content}")

                if "!getpasscode" not in content:
                    print(f"Ignoring message from {username} as it does not contain !getpasscode")
                    continue
                token_name, token_pin = parse_and_validate(username, content)
                print(f"GOT Parsed=> token_name: {token_name}, token_pin: {token_pin}")
                if token_name and token_pin:
                    send_discord_message(request_channel_id, f"🔄 Getting passcode for `{token_name}, request by {username}`...")
                    passcode = get_passcode(token_name, token_pin)
                    send_discord_message(request_channel_id, f"🔐 Passcode for `{token_name}`: `{passcode}`")
                    
                #else:
                    #send_discord_message(request_channel_id, "❌ VALIDATION: Invalid credentials. Use format: `!getpasscode:token_name`", DiscordMsgType.VALIDATION)

        except Exception as e:
            if 'NoneType' not in str(e):
                write_log(f"Error: {str(e)}")
            #print("Error:", e)

if __name__ == "__main__":
    main()
