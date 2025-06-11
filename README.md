# SafeNet-MobilePASS Discord Bot

This project is a Python-based Discord bot that automates the retrieval of SafeNet MobilePASS passcodes and delivers them securely to authorized users via Discord. It uses GUI automation to interact with the SafeNet MobilePASS application and listens for passcode requests through Discord messages.

## Features

- **Automated Passcode Retrieval:** Uses `pywinauto` to control the SafeNet MobilePASS desktop app and copy passcodes.
- **Discord Integration:** Listens for `!getpasscode:token_name` commands in Discord channels and responds with the requested passcode.
- **User Authorization:** Only users listed in `credentials.json` can request passcodes.
- **Logging:** Errors and important events are logged to daily log files.
- **Configurable:** All sensitive data and settings are stored in `credentials.json`.

## Requirements

- Python 3.7+
- SafeNet MobilePASS installed on Windows
- Discord account and bot token
- The following Python packages:
  - `psutil`
  - `pyperclip`
  - `requests`
  - `pywinauto`
  - `websocket-client`

Install dependencies with:

```sh
pip install psutil pyperclip requests pywinauto websocket-client
```

## Setup

1. **Clone the repository:**

   ```sh
   git clone <repo-url>
   cd SafeNet-MobilePASS
   ```

2. **Configure credentials:**

   - Copy `credentials.example.json` to `credentials.json` (if provided) or create your own.
   - Fill in your Discord bot token, channel IDs, SafeNet token names, PIN, and authorized users.

   Example `credentials.json`:

   ```json
   {
     "token": "YOUR_DISCORD_BOT_TOKEN",
     "DISCORD_Gateway_URL": "wss://gateway.discord.gg/?v=9&encoding=json",
     "req_channel_id": "YOUR_REQUEST_CHANNEL_ID",
     "val_channel_id": "YOUR_VALIDATION_CHANNEL_ID",
     "token_name2": "YourTokenName",
     "token_PIN": "123456",
     "authorized_users": {
       "DiscordUsername1": "Real Name 1",
       "DiscordUsername2": "Real Name 2"
     }
   }
   ```

3. **Run the bot:**
   ```sh
   python main.py
   ```

## Usage

- In your Discord server, send a message in the configured channel:
  ```
  !getpasscode:YourTokenName
  ```
- If you are authorized, the bot will reply with the current passcode for the specified token.

## Security

- Only users listed in `authorized_users` can request passcodes.
- Passcodes are sent only in the specified Discord channel.
- All sensitive information is kept in `credentials.json` (do not commit this file to version control).

## Logging

- Logs are stored in the `logs/` directory with daily log files named `Error_Logs_YYYY-MM-DD.log`.

## Troubleshooting

- Ensure SafeNet MobilePASS is installed at the default path or update `SAFENET_PATH` in `main.py`.
- The bot must run on a Windows machine with GUI access.
- If you encounter issues with GUI automation, try running the script as administrator.

## Disclaimer

This project is for internal use only. Handle credentials and passcodes securely. Use at your own risk.

---

**Author:**  
AKRIMA HUZAIFA AKHTAR
