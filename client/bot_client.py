"""
X Monetization Bot - Desktop Client
This runs on the user's PC and connects to the web dashboard
"""

import os
import sys
import time
import requests
import json
import random
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
import socketio
from ai_generator import AIReplyGenerator

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
        self.ai_generator = None  # Will be initialized after loading config
        self.replied_tweets = set()  # Track replied tweets in memory
        self.stats = {'replies_today': 0, 'errors': 0}

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

                # Initialize AI generator with Groq API key from server config
                # For now, using hardcoded key - you can add it to server config
                groq_api_key = "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"
                self.ai_generator = AIReplyGenerator(groq_api_key)

                self.log("✅ Configuration loaded")
                self.log("✅ AI Generator initialized (Groq API only - no templates)")
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
        self.log(f"📊 Current count: {self.stats['replies_today']}/{target_replies}")

        for i, list_url in enumerate(x_lists, 1):
            if not self.running or self.stats['replies_today'] >= target_replies:
                break

            list_name = f"List {i}"
            self.log(f"📋 Loading: {list_name}")

            try:
                self.driver.get(list_url)
                time.sleep(random.uniform(3, 5))

                # Scroll to load tweets
                for _ in range(3):
                    scroll_amount = random.randint(400, 800)
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                    time.sleep(random.uniform(0.5, 1))

                # Find tweets
                tweets = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
                self.log(f"📊 Found {len(tweets)} tweets in {list_name}")

                # Process each tweet
                for tweet_elem in tweets:
                    if not self.running or self.stats['replies_today'] >= target_replies:
                        break

                    try:
                        tweet_data = self.extract_tweet_data(tweet_elem)
                        if tweet_data and tweet_data['id'] not in self.replied_tweets:
                            if self.reply_to_tweet(tweet_data, list_name):
                                time.sleep(rest_duration)
                    except Exception as e:
                        continue

                self.log(f"✅ Processed {list_name}")
            except Exception as e:
                self.log(f"❌ Error loading {list_name}: {e}")

            time.sleep(random.uniform(2, 4))

    def extract_tweet_data(self, tweet_element):
        """Extract tweet information"""
        try:
            text_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="tweetText"]')
            tweet_text = text_elem.text

            author_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="User-Name"]')
            author = author_elem.text.split('\n')[0].replace('@', '')

            links = tweet_element.find_elements(By.TAG_NAME, 'a')
            tweet_id = None
            for link in links:
                href = link.get_attribute('href')
                if href and '/status/' in href:
                    tweet_id = href.split('/status/')[-1].split('?')[0].split('/')[0]
                    break

            if not tweet_id or not tweet_text or len(tweet_text) < 10:
                return None

            return {
                'text': tweet_text,
                'author': author,
                'id': tweet_id,
                'element': tweet_element
            }
        except:
            return None

    def reply_to_tweet(self, tweet_data, list_name):
        """Reply to a tweet using AI only"""
        try:
            # Generate AI reply (no templates)
            reply = self.ai_generator.generate_reply(tweet_data['text'], tweet_data['author'])

            if not reply:
                self.log(f"⚠️ AI failed to generate reply - skipping tweet")
                self.stats['errors'] += 1
                return False

            # Click reply button
            try:
                reply_btn = tweet_data['element'].find_element(By.CSS_SELECTOR, '[data-testid="reply"]')
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reply_btn)
                time.sleep(random.uniform(0.3, 0.7))
                reply_btn.click()
            except:
                return False

            time.sleep(random.uniform(0.5, 1))

            # Type reply
            try:
                reply_box = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
                )
                # Human-like typing
                for char in reply:
                    reply_box.send_keys(char)
                    time.sleep(random.uniform(0.02, 0.06))
            except:
                return False

            time.sleep(random.uniform(0.5, 1))

            # Send tweet
            try:
                send_btn = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="tweetButton"]')
                send_btn.click()
            except:
                return False

            # Track replied tweet
            self.replied_tweets.add(tweet_data['id'])
            self.stats['replies_today'] += 1

            self.log(f"✅ [{self.stats['replies_today']}] @{tweet_data['author']}: {reply[:60]}...")

            # Close modal
            time.sleep(random.uniform(0.5, 1))
            try:
                close_btn = self.driver.find_element(By.CSS_SELECTOR, '[aria-label="Close"]')
                close_btn.click()
                time.sleep(random.uniform(0.3, 0.5))
            except:
                pass

            return True

        except Exception as e:
            self.log(f"⚠️ Reply failed: {str(e)[:50]}")
            self.stats['errors'] += 1
            return False

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
