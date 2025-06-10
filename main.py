import requests
import websocket
import json
import threading
import time


# Read credentials from credentials.json
with open('credentials.json', 'r') as cred_file:
    credentials = json.load(cred_file)
#print("Credentials loaded successfully:", credentials)

# Function to retrieve messages from a specific channel
def retrieve_messages(channelid):
    headers = {
    'authorization': credentials["token"],
    'content-type': 'application/json'
    }
    r = requests.get(f'https://discord.com/api/v9/channels/{channelid}/messages', headers=headers)
    jsonn = json.loads(r.text)
    for value in jsonn:
        #print(value,'\n')
        print(f'{value['timestamp']} {value['author']['username']}: {value['content']}','\n')

#retrieve_messages('1381826673959239821') #working

def send_json_request(ws, request):
    ws.send(json.dumps(request))

def recieve_json_response(ws):
    response = ws.recv()
    if response:
        return json.loads(response)
    
def heartbeat(interval, ws):
    print( 'Heartbeat begin' )
    while True:
        time.sleep(interval)
        heartbeatJSON = {
            "op": 1,
            "d": "null"
        }
        send_json_request(ws, heartbeatJSON)
        print("Heartbeat sent")

ws = websocket.WebSocket()
ws.connect(credentials["DISCORD_Gateway_URL"])
event = recieve_json_response(ws)

heartbeat_interval = event['d']['heartbeat_interval'] / 1000
threading.Thread(target=heartbeat, args=(heartbeat_interval, ws), daemon=True).start()

token = credentials["token"]
payload = {
    "op": 2,
    "d": {
        "token": token,
        "properties": {
            "$os": "windows",
            "$browser": "chrome",
            "$device": "pc"
        }
    }
}
send_json_request(ws, payload)
while True:
    response = recieve_json_response(ws)
    try:
        print(f"{response['d']['author']['username']}: {response['d']['content']}")
        op_code = response('op')
        if op_code == 11:
            print("Received a heartbeat ACK")

    except:
        #print("Received a non-message event or an error in the response.")
        pass