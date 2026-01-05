# X Monetization Bot - Desktop Client

This is the desktop client that runs on the user's PC. The bot opens Chrome on their computer and connects to the web dashboard.

## How It Works

1. **Web Dashboard** (Hosted on Render):
   - Users register/login
   - Configure bot settings
   - View logs and stats in real-time

2. **Desktop Client** (Runs on user's PC):
   - Downloads and runs this client
   - Opens Chrome on their computer
   - Connects to web dashboard
   - Sends logs back to dashboard

## Installation

### Option 1: Python Script (For Users)

1. Install Python 3.8+ from [python.org](https://python.org)
2. Download this folder
3. Open command prompt in this folder
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Run the client:
   ```
   python bot_client.py
   ```
6. Enter your server URL, username, and password

### Option 2: Standalone EXE (Coming Soon)

We'll create a standalone .exe file so users don't need Python installed.

## Requirements

- Windows 10/11 (Linux/Mac support coming)
- Google Chrome installed
- Internet connection
- Premium account on the web dashboard

## Usage

1. Go to the web dashboard and register
2. Upgrade to premium
3. Configure your bot settings (Twitter lists, targets)
4. Download and run this desktop client
5. Login with your credentials
6. Chrome will open - login to Twitter/X manually
7. Bot starts working automatically
8. View live logs on the web dashboard

## Features

- ✅ Runs on user's PC (not the server)
- ✅ Opens visible Chrome window
- ✅ Real-time logs sent to dashboard
- ✅ Remote configuration from dashboard
- ✅ Stop/start from dashboard
- ✅ Multiple users can run simultaneously
- ✅ Each user has their own bot instance

## Troubleshooting

**"Chrome not found" error:**
- Install Google Chrome from https://www.google.com/chrome/

**"Connection error":**
- Check your internet connection
- Make sure the server URL is correct
- Check if the web dashboard is online

**"Login failed":**
- Verify your username and password
- Make sure you're a premium user

**Bot not starting:**
- Make sure you logged into Twitter in the Chrome window
- Check the dashboard for error logs
