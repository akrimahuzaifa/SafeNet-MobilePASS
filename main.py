import json
import time
import psutil
import pyperclip
import requests
import subprocess
import threading
import websocket
from pywinauto import Application
from enum import Enum

class DiscordMsgType(Enum):
    REQUEST = 1
    VALIDATION = 2

# === Load Configs ===
with open('credentials.json') as f:
    credentials = json.load(f)

with open('authidpass.json') as f:
    auth_data = json.load(f)

DISCORD_TOKEN = credentials["token"]
DISCORD_GATEWAY = credentials["DISCORD_Gateway_URL"]
SAFENET_PATH = r"C:\Program Files (x86)\SafeNet\Authentication\MobilePASS\MobilePASS.exe"  # Adjust if needed

# === Helper: Launch SafeNet ===
def launch_safenet():
    if not any("MobilePASS" in p.name() for p in psutil.process_iter()):
        subprocess.Popen(SAFENET_PATH)
        time.sleep(5)

# === Helper: Automate SafeNet ===
def get_passcode(token_pin = credentials["token_PIN"], token_name = credentials["token_name"]):
    launch_safenet()
    app = Application(backend="uia").connect(title_re=".*MobilePASS.*")
    window = app.window(title_re=".*MobilePASS.*")
    window.set_focus()

    try:
        window.child_window(title=token_name, control_type="ListItem").click_input()
        time.sleep(1)
        pin_box = window.child_window(control_type="Edit")
        pin_box.type_keys(token_pin)
        window.child_window(title="Continue", control_type="Button").click_input()
        time.sleep(2)
        window.child_window(title="Copy Passcode", control_type="Button").click_input()
        time.sleep(0.5)
        return pyperclip.paste()
    except Exception as e:
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
def parse_and_validate(msg):
    try:
        print(f"Received message: {msg}")
        user_id, password = msg.strip().split(':')
        print(f"Parsed user_id: {user_id}, password: {password}")
        print(f"Auth data: {auth_data}")
        print(f"User ID {user_id} found in auth data") if user_id in auth_data else print(f"User ID {user_id} NOT found in auth data")
        print(f"Password match: {auth_data[user_id]['password'] == password}") if auth_data[user_id]['password'] == password else print("No password match, user ID not found")
        print(f"Password match Auth: {auth_data[user_id]['password']} == {password}")
            
        if user_id in auth_data and auth_data[user_id]['password'] == password:
            print(f"User ID and password condition is true")
            print(f"Credentials token_name: {credentials['token_name']}")
            print(f"Credentials token_pin: {credentials['token_PIN']}")
            print(f"Returning user_id: {user_id}, token_name: {credentials['token_name']}, token_pin: {credentials['token_PIN']}")
            return user_id, credentials['token_name'], credentials['token_PIN']
    except:
        return None, None, None
    return None, None, None

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
    #sent_message_one_time = False
    while True:
        response = recieve_json_response(ws)
        try:
            if 'd' in response and 'content' in response['d']:
                content = response['d']['content']
                username = response['d']['author']['username']
                request_channel_id = response['d']['channel_id']

                print(f"{username}: {content}")

                user_id, token_name, token_pin = parse_and_validate(content)
                print(f"GOT Parsed user_id: {user_id}, token_name: {token_name}, token_pin: {token_pin}")
                if token_name:
                    send_discord_message(request_channel_id, f"🔄 Getting passcode for `{user_id}`...")
                    passcode = get_passcode(token_pin, token_name)
                    send_discord_message(request_channel_id, f"🔐 Passcode for `{user_id}`: `{passcode}`")
                    
                #else:
                    #send_discord_message(request_channel_id, "❌ VALIDATION: Invalid credentials. Use format: `user_id:password`", DiscordMsgType.VALIDATION)
                    #if not sent_message_one_time:
                        #send_discord_message(request_channel_id, "❗️ Please provide credentials in the format: `user_id:password`")
                        #sent_message_one_time = True
                        #print("❗️ Please provide credentials in the format: `user_id:password`")

        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    main()
