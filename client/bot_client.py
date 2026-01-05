"""
X Monetization Bot - Desktop Client
This runs on the user's PC and connects to the web dashboard
"""

import os
import sys
import time
import requests
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
import socketio

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    import win32gui
    import win32con
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    HAS_WIN32 = True
else:
    HAS_WIN32 = False

class BotClient:
    def __init__(self, server_url, username, password):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.config = None
        self.driver = None
        self.running = False
        self.sio = socketio.Client()

        # Setup socket events
        self.setup_socket_events()

    def setup_socket_events(self):
        @self.sio.on('connect')
        def on_connect():
            self.log("✅ Connected to server")

        @self.sio.on('disconnect')
        def on_disconnect():
            self.log("❌ Disconnected from server")

        @self.sio.on('bot_command')
        def on_command(data):
            cmd = data.get('command')
            if cmd == 'stop':
                self.log("🛑 Stop command received")
                self.stop()
            elif cmd == 'update_config':
                self.log("🔄 Config update received")
                self.load_config()

    def log(self, message):
        """Print locally and send to server"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {message}")

        # Send to server
        if self.sio.connected:
            try:
                self.sio.emit('client_log', {'message': message, 'username': self.username})
            except:
                pass

    def login(self):
        """Login to server and get token"""
        self.log("🔐 Logging in to server...")

        try:
            response = requests.post(
                f"{self.server_url}/api/client/login",
                json={'username': self.username, 'password': self.password},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                self.log("✅ Login successful!")
                return True
            else:
                self.log(f"❌ Login failed: {response.json().get('message', 'Unknown error')}")
                return False
        except Exception as e:
            self.log(f"❌ Connection error: {e}")
            return False

    def load_config(self):
        """Load configuration from server"""
        try:
            response = requests.get(
                f"{self.server_url}/api/client/config",
                headers={'Authorization': f'Bearer {self.token}'},
                timeout=10
            )

            if response.status_code == 200:
                self.config = response.json()
                self.log("✅ Configuration loaded")
                return True
            else:
                self.log("❌ Failed to load config")
                return False
        except Exception as e:
            self.log(f"❌ Error loading config: {e}")
            return False

    def connect_socket(self):
        """Connect to server via WebSocket"""
        try:
            self.sio.connect(
                self.server_url,
                auth={'token': self.token, 'username': self.username}
            )
            return True
        except Exception as e:
            self.log(f"❌ Socket connection failed: {e}")
            return False

    def setup_driver(self):
        """Setup Chrome browser"""
        self.log("🚀 Starting Chrome browser...")

        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--start-maximized')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Navigate to Twitter
        self.driver.get("https://twitter.com/home")

        # Bring to foreground on Windows
        if HAS_WIN32:
            time.sleep(1)
            windows = []

            def find_chrome(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if 'Twitter' in title or 'X' in title or 'Chrome' in title:
                        windows.append(hwnd)

            win32gui.EnumWindows(find_chrome, windows)
            if windows:
                for hwnd in windows:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    break

        self.log("✅ Browser ready")

    def wait_for_login(self):
        """Wait for user to login to Twitter"""
        self.log("⏳ Waiting for you to login to Twitter...")
        self.log("📱 Please login in the Chrome window that just opened")

        max_wait = 300  # 5 minutes
        start_time = time.time()

        while time.time() - start_time < max_wait:
            if self.check_login_status():
                return True
            time.sleep(5)

        self.log("❌ Login timeout - please try again")
        return False

    def check_login_status(self):
        """Check if user is logged into Twitter"""
        try:
            current_url = self.driver.current_url

            # Check URL
            if '/home' in current_url:
                # Verify by looking for compose button
                try:
                    self.driver.find_element(By.CSS_SELECTOR, '[data-testid="SideNav_NewTweet_Button"]')
                    self.log("✅ Login detected!")
                    return True
                except:
                    pass

            return False
        except:
            return False

    def run(self):
        """Main bot loop"""
        self.log("🤖 Starting X Monetization Bot Client")
        self.log(f"🌐 Server: {self.server_url}")

        # Login to server
        if not self.login():
            return

        # Load config
        if not self.load_config():
            return

        # Connect WebSocket
        if not self.connect_socket():
            self.log("⚠️ WebSocket connection failed, continuing without live updates")

        # Setup browser
        self.setup_driver()

        # Wait for Twitter login
        if not self.wait_for_login():
            self.cleanup()
            return

        self.log("✅ Login successful! Starting bot...")
        self.running = True

        # Send ready status to server
        try:
            requests.post(
                f"{self.server_url}/api/client/status",
                headers={'Authorization': f'Bearer {self.token}'},
                json={'status': 'running', 'username': self.username}
            )
        except:
            pass

        # Main bot loop
        while self.running:
            try:
                self.process_lists()
            except Exception as e:
                self.log(f"❌ Error: {e}")
                time.sleep(30)

        self.cleanup()

    def process_lists(self):
        """Process Twitter lists"""
        x_lists = self.config.get('x_lists', [])
        targets = self.config.get('targets', {})

        rest_duration = targets.get('rest_duration_seconds', 3)
        target_replies = targets.get('replies_per_day', 1000)

        self.log(f"🎯 TARGET: {target_replies} replies today")

        for i, list_url in enumerate(x_lists, 1):
            list_name = f"List {i}"
            self.log(f"📋 Loading: {list_name}")

            try:
                self.driver.get(list_url)
                time.sleep(5)

                # Process tweets from this list
                # (Add your tweet processing logic here)

                self.log(f"✅ Processed {list_name}")
            except Exception as e:
                self.log(f"❌ Error loading {list_name}: {e}")

            time.sleep(rest_duration)

    def stop(self):
        """Stop the bot"""
        self.running = False
        self.log("🛑 Stopping bot...")

    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

        if self.sio.connected:
            try:
                self.sio.disconnect()
            except:
                pass

        self.log("👋 Bot stopped")


if __name__ == "__main__":
    print("=" * 50)
    print("  X Monetization Bot - Desktop Client")
    print("=" * 50)
    print()

    # Get credentials
    server_url = input("Server URL (e.g., https://your-app.onrender.com): ").strip()
    username = input("Username: ").strip()
    password = input("Password: ").strip()

    print()
    print("Starting bot client...")
    print()

    # Create and run client
    client = BotClient(server_url, username, password)

    try:
        client.run()
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
        client.stop()
        client.cleanup()
