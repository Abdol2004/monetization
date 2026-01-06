from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import threading
import time
import random
import json
import requests
import re
import sys

# Fix Windows console encoding for emojis (for local development)
if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*")

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# MongoDB setup with SSL fix for Python 3.13
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')

try:
    import certifi
    import ssl

    # Create custom SSL context
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
        tls=True,
        tlsAllowInvalidCertificates=True,
        tlsCAFile=certifi.where()
    )

    # Test connection
    client.admin.command('ping')
    print("✅ MongoDB connected successfully!")

except Exception as e:
    print(f"⚠️ MongoDB connection failed: {e}")
    print("⚠️ Falling back to local mode - you won't be able to register/login")
    # Create a mock client that won't crash the app
    client = None

db = client['x_monetization'] if client is not None else None

# Collections
users_collection = db['users'] if client is not None else None
engagements_collection = db['engagements'] if client is not None else None
configs_collection = db['configs'] if client is not None else None

# Bot instances per user
active_bots = {}

# ============= MongoDB Connection Helper =============
def get_mongodb_connection():
    """Get or reconnect to MongoDB if connection is lost"""
    global client, db, users_collection, engagements_collection, configs_collection

    try:
        # Check if connection exists and is alive
        if client is not None:
            client.admin.command('ping')
            return True
    except:
        pass

    # Reconnect
    try:
        import certifi
        import ssl

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            tls=True,
            tlsAllowInvalidCertificates=True,
            tlsCAFile=certifi.where()
        )

        # Test connection
        client.admin.command('ping')

        # Update global references
        db = client['x_monetization']
        users_collection = db['users']
        engagements_collection = db['engagements']
        configs_collection = db['configs']

        print("✅ MongoDB reconnected successfully!")
        return True

    except Exception as e:
        print(f"⚠️ MongoDB reconnection failed: {e}")
        return False

# ============= User Model =============
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.email = user_data['email']
        self.is_premium = user_data.get('is_premium', False)
        self.created_at = user_data.get('created_at', datetime.utcnow())

@login_manager.user_loader
def load_user(user_id):
    if users_collection is None:
        return None
    try:
        from bson.objectid import ObjectId
        user_data = users_collection.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except Exception as e:
        print(f"Error loading user: {e}")
    return None

# ============= Configuration Manager =============
class ConfigManager:
    GROK_API_KEY = os.environ.get('GROK_API_KEY', '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')
    GROK_API_URL = "https://api.groq.com/openai/v1/chat/completions"

    @staticmethod
    def load(user_id):
        get_mongodb_connection()  # Ensure connection
        if configs_collection is not None:
            config = configs_collection.find_one({'user_id': user_id})
            if config:
                return config
        return {
            "user_id": user_id,
            "x_lists": [
                "https://x.com/i/lists/1995877357249270077",
                "https://x.com/i/lists/1904483699346784446",
                "https://x.com/i/lists/1911725019513684062"
            ],
            "targets": {
                "replies_per_day": 1000,
                "rest_duration_seconds": 3,
                "replies_per_session": 400,
                "engagement_threshold": 400
            },
            "engagement_style": "controversial",
            "mode": "viral_hunting"
        }

    @staticmethod
    def save(user_id, config_data):
        get_mongodb_connection()  # Ensure connection
        if configs_collection is not None:
            config_data['user_id'] = user_id
            configs_collection.update_one(
                {'user_id': user_id},
                {'$set': config_data},
                upsert=True
            )

# ============= MongoDB Database Manager =============
class MongoDBManager:
    def __init__(self, user_id):
        self.user_id = user_id

    def add_engagement(self, tweet_id, url, author, content, reply, list_source):
        get_mongodb_connection()  # Ensure connection
        if engagements_collection is None:
            return False

        date_only = datetime.utcnow().strftime('%Y-%m-%d')
        try:
            engagements_collection.insert_one({
                'user_id': self.user_id,
                'tweet_id': tweet_id,
                'tweet_url': url,
                'author': author,
                'tweet_content': content,
                'reply_content': reply,
                'list_source': list_source,
                'date_only': date_only,
                'timestamp': datetime.utcnow()
            })
            return True
        except Exception as e:
            print(f"DB Error: {e}")
            return False

    def already_replied_to_tweet(self, tweet_id):
        get_mongodb_connection()  # Ensure connection
        if engagements_collection is None:
            return False
        return engagements_collection.find_one({
            'user_id': self.user_id,
            'tweet_id': tweet_id
        }) is not None

    def get_today_count(self):
        get_mongodb_connection()  # Ensure connection
        if engagements_collection is None:
            return 0
        date_only = datetime.utcnow().strftime('%Y-%m-%d')
        return engagements_collection.count_documents({
            'user_id': self.user_id,
            'date_only': date_only
        })

    def get_stats(self):
        get_mongodb_connection()  # Ensure connection
        if engagements_collection is None:
            return {'today_replies': 0, 'unique_authors': 0, 'total_all_time': 0}

        date_only = datetime.utcnow().strftime('%Y-%m-%d')

        today_replies = engagements_collection.count_documents({
            'user_id': self.user_id,
            'date_only': date_only
        })

        unique_authors = len(engagements_collection.distinct('author', {
            'user_id': self.user_id,
            'date_only': date_only
        }))

        total_all_time = engagements_collection.count_documents({
            'user_id': self.user_id
        })

        return {
            'today_replies': today_replies,
            'unique_authors': unique_authors,
            'total_all_time': total_all_time
        }

# ============= Bot Classes (NOT USED ON SERVER - Bot runs on client PC) =============
# These classes are kept for reference but not imported/used on server
# The desktop client (client/bot_client.py) handles all bot logic

# ============= Rage Bait Reply Generator =============
class RageBaitGenerator:
    def __init__(self):
        self.api_key = ConfigManager.GROK_API_KEY
        self.api_url = ConfigManager.GROK_API_URL

        self.rage_templates = [
            "This is exactly why {context} is failing. Everyone sees it but you.",
            "Respectfully, you're missing {context} completely here.",
            "This take aged like milk. {context} proves otherwise.",
            "Tell me you don't understand {context} without telling me.",
            "Everyone's hyping this but ignoring {context}.",
            "Unpopular opinion: {context} makes this irrelevant.",
            "This would work if {context} wasn't literally proven wrong.",
            "Nah. {context} contradicts this entirely.",
            "The {context} issue alone destroys this argument.",
            "Am I the only one seeing {context} as the obvious problem?",
            "This is why {context} keeps winning. Y'all miss the point.",
            "Cool story until you factor in {context}.",
            "Everyone celebrating while {context} exists is wild.",
            "This ignores {context} and it shows.",
            "Hard disagree. {context} is what actually matters.",
            "Y'all forgot {context} and it's embarrassing.",
            "The {context} in the room nobody wants to address.",
            "This take falls apart when you consider {context}.",
            "Imagine thinking this works with {context} right there.",
            "But what about {context} though? Exactly.",
            "{context} has entered the chat and it's over.",
            "This aged poorly. {context} was always the issue.",
            "Everyone ignoring {context} and wondering why it failed.",
            "The fact that nobody mentions {context} says everything.",
            "This sounds smart until you realize {context}.",
            "Wrong. {context} is the actual answer.",
            "{context} watching this take: 💀",
            "POV: you've never heard of {context}",
            "My brother in Christ, {context} exists.",
            "This giving 'I forgot {context}' energy.",
            "The {context} disrespect is insane.",
            "{context} literally disproves this.",
            "Show me the data on {context}. I'll wait.",
            "This works until {context} enters the equation.",
            "Y'all really out here ignoring {context}.",
            "The {context} problem makes this irrelevant.",
            "Everyone's wrong about this. {context} is clear.",
            "This is cap. {context} proves it.",
            "Controversial but {context} says otherwise.",
            "Not sorry but {context} kills this argument.",
            "The {context} factor alone is a dealbreaker.",
            "This aged like fine milk. {context} >>",
            "Genuinely asking: what about {context}?",
            "How do you explain {context} with this logic?",
            "But doesn't {context} contradict this?",
            "Real question: where does {context} fit?",
            "Help me understand {context} in this scenario.",
            "Curious how {context} doesn't break this.",
            "What's your take on {context} here?",
            "So we're just ignoring {context} now?",
            "Bold claim considering {context} exists.",
        ]

        self.context_fillers = [
            "the implementation", "scalability", "real-world data", "basic economics",
            "market reality", "historical precedent", "the obvious solution", "proven strategies",
            "actual results", "the fundamentals", "expert consensus", "the track record",
            "opportunity cost", "the incentive structure", "game theory", "network effects",
            "distribution", "execution risk", "technical debt", "user experience",
            "the core problem", "regulatory reality", "competitive dynamics", "unit economics",
            "customer acquisition", "the GTM strategy", "product-market fit", "sustainable growth",
            "liquidity", "tokenomics", "smart contract risk", "on-chain data",
            "the protocol design", "decentralization", "consensus mechanisms", "gas optimization"
        ]

    def detect_language(self, text):
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        return 'chinese' if len(chinese_chars) > 3 else 'english'

    def generate_reply(self, tweet_text, author):
        language = self.detect_language(tweet_text)

        if language != 'english':
            return self.generate_with_ai(tweet_text, author, language)

        if random.random() < 0.5:
            template = random.choice(self.rage_templates)
            context = random.choice(self.context_fillers)
            reply = template.format(context=context)
            return reply[:280]
        else:
            return self.generate_with_ai(tweet_text, author, language)

    def generate_with_ai(self, tweet_text, author, language='english'):
        try:
            if language == 'chinese':
                system_prompt = "你是社交媒体专家。用中文回复，要有争议性但礼貌。让人想互动。40字内，不用话题标签。"
            else:
                system_prompt = "You're a viral engagement expert. Reply with controlled controversy and criticism that sparks heated discussion. Be provocative but not offensive. Challenge the main point boldly. Make people want to argue back. Under 40 words. NO hashtags."

            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Tweet: {tweet_text}\n\nGenerate a critical, controversial reply:"}
                    ],
                    "temperature": 0.95,
                    "max_tokens": 100
                },
                timeout=15
            )

            if response.status_code == 200:
                reply = response.json()['choices'][0]['message']['content'].strip()
                reply = ' '.join([w for w in reply.split() if not w.startswith('#')])
                reply = reply.strip('"\'')
                return reply[:280]
            else:
                template = random.choice(self.rage_templates)
                context = random.choice(self.context_fillers)
                return template.format(context=context)[:280]

        except Exception as e:
            print(f"AI Error: {str(e)}")
            template = random.choice(self.rage_templates)
            context = random.choice(self.context_fillers)
            return template.format(context=context)[:280]

# ============= Human Simulator =============
class HumanSimulator:
    @staticmethod
    def quick_delay(min_sec=0.5, max_sec=1.5):
        time.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    def human_type(element, text):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.02, 0.06))

    @staticmethod
    def quick_scroll(driver):
        scroll_amount = random.randint(400, 800)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.5, 1))

# ============= X List Bot =============
class XListBot:
    def __init__(self, user_id, callback=None):
        self.user_id = user_id
        self.driver = None
        self.wait = None
        self.db = MongoDBManager(user_id)
        self.ai = RageBaitGenerator()
        self.running = False
        self.callback = callback
        self.stats = {"replies_today": 0, "errors": 0, "current_session": 0}
        self.replied_ids = set()
        self.login_complete = False

    def log(self, message):
        if self.callback:
            self.callback(message)
        print(message)

    def setup_driver(self):
        self.log("🚀 Starting Chrome browser...")

        options = Options()
        # IMPORTANT: NO headless mode - user needs to see and interact
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Keep browser window visible and in foreground
        options.add_argument('--start-maximized')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')

        # Don't open about:blank
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        self.driver = webdriver.Chrome(options=options)

        # Immediately navigate to Twitter before doing anything else
        self.log("🌐 Navigating to Twitter...")
        self.driver.get("https://twitter.com/home")

        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 10)

        # Windows-specific: Force window to foreground AFTER page loads
        if HAS_WIN32:
            try:
                time.sleep(1)
                # Find Chrome window and bring to front
                def find_chrome_window(hwnd, windows):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if 'Twitter' in title or 'X' in title or 'Chrome' in title:
                            windows.append(hwnd)

                windows = []
                win32gui.EnumWindows(find_chrome_window, windows)
                if windows:
                    for hwnd in windows:
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        self.log("✓ Browser window is now in focus!")
                        break
            except Exception as e:
                self.log(f"⚠️ Could not bring window to front: {e}")

        self.log("✓ Chrome opened - You should see Twitter now!")

    def get_login_url(self):
        """Return the Twitter login URL for user to login in new tab"""
        self.driver.get("https://twitter.com/login")
        time.sleep(2)
        return self.driver.current_url

    def check_login_status(self):
        """Check if user has completed login"""
        try:
            current_url = self.driver.current_url.lower()

            # If on login page, definitely not logged in
            if 'login' in current_url or 'i/flow/login' in current_url:
                return False

            # Check for various Twitter logged-in pages
            if any(x in current_url for x in ['home', 'notifications', 'explore', 'messages', 'lists', 'bookmarks', 'communities', 'premium', 'twitter.com/home', 'x.com/home']):
                self.login_complete = True
                self.log("✓ Login detected via URL")
                return True

            # Also check if we can find elements that only appear when logged in
            try:
                # Try to find the tweet compose button
                self.driver.find_element(By.CSS_SELECTOR, '[data-testid="SideNav_NewTweet_Button"]')
                self.login_complete = True
                self.log("✓ Login detected via compose button")
                return True
            except:
                pass

            # Try to find the profile menu
            try:
                self.driver.find_element(By.CSS_SELECTOR, '[data-testid="AppTabBar_Profile_Link"]')
                self.login_complete = True
                self.log("✓ Login detected via profile link")
                return True
            except:
                pass

        except Exception as e:
            self.log(f"⚠️ Error checking login: {e}")
            pass

        return False

    def wait_for_login(self):
        """Wait for user to complete login"""
        self.log("🔐 Checking login status...")

        # Give page more time to fully load
        time.sleep(5)

        # Check current URL
        try:
            current_url = self.driver.current_url
            self.log(f"📍 Current URL: {current_url}")
        except:
            pass

        # First check if already logged in
        if self.check_login_status():
            self.log("✅ Already logged in! Starting bot...")
            return True

        self.log("🔐 Please login to Twitter in the browser window...")

        # Wait for login
        timeout = 120  # 2 minutes timeout
        start_time = time.time()

        while not self.login_complete and self.running:
            if self.check_login_status():
                self.log("✅ Login successful! Starting bot...")
                HumanSimulator.quick_delay(2, 3)
                return True

            # Check timeout
            if time.time() - start_time > timeout:
                self.log("❌ Login timeout - please try again")
                return False

            time.sleep(2)

        return self.login_complete

    def extract_tweet_data(self, tweet_element):
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

    def reply_to_tweet(self, tweet_info, list_name):
        try:
            if self.db.already_replied_to_tweet(tweet_info['id']):
                return False

            if tweet_info['id'] in self.replied_ids:
                return False

            reply = self.ai.generate_reply(tweet_info['text'], tweet_info['author'])

            if not reply:
                self.stats['errors'] += 1
                return False

            try:
                reply_btn = tweet_info['element'].find_element(By.CSS_SELECTOR, '[data-testid="reply"]')
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reply_btn)
                HumanSimulator.quick_delay(0.3, 0.7)
                reply_btn.click()
            except:
                return False

            HumanSimulator.quick_delay(0.5, 1)

            try:
                reply_box = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
                )
                HumanSimulator.human_type(reply_box, reply)
            except:
                return False

            HumanSimulator.quick_delay(0.5, 1)

            try:
                send_btn = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="tweetButton"]')
                send_btn.click()
            except:
                return False

            tweet_url = f"https://twitter.com/{tweet_info['author']}/status/{tweet_info['id']}"
            if not self.db.add_engagement(
                tweet_info['id'],
                tweet_url,
                tweet_info['author'],
                tweet_info['text'][:200],
                reply,
                list_name
            ):
                self.log(f"⚠️ Skipped duplicate: {tweet_info['id']}")
                return False

            self.replied_ids.add(tweet_info['id'])
            self.stats['replies_today'] += 1
            self.stats['current_session'] += 1

            self.log(f"✅ [{self.stats['replies_today']}/1000] @{tweet_info['author']}: {reply[:60]}...")

            HumanSimulator.quick_delay(0.5, 1)

            try:
                close_btn = self.driver.find_element(By.CSS_SELECTOR, '[aria-label="Close"]')
                close_btn.click()
                HumanSimulator.quick_delay(0.3, 0.5)
            except:
                pass

            return True

        except Exception as e:
            self.log(f"⚠️ Reply failed: {str(e)[:50]}")
            self.stats['errors'] += 1

            try:
                self.driver.find_element(By.CSS_SELECTOR, '[aria-label="Close"]').click()
            except:
                pass

            return False

    def process_list(self, list_url, list_name, rest_duration, target_replies):
        try:
            self.log(f"📋 Loading: {list_name}")
            self.driver.get(list_url)
            HumanSimulator.quick_delay(2, 3)

            for _ in range(3):
                HumanSimulator.quick_scroll(self.driver)

            tweets = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            self.log(f"📊 Found {len(tweets)} tweets in {list_name}")

            replied_count = 0

            for tweet in tweets:
                if not self.running or self.stats['replies_today'] >= target_replies:
                    break

                tweet_info = self.extract_tweet_data(tweet)
                if not tweet_info:
                    continue

                if self.reply_to_tweet(tweet_info, list_name):
                    replied_count += 1
                    time.sleep(rest_duration)

                if self.stats['current_session'] % 50 == 0 and self.stats['current_session'] > 0:
                    self.log(f"⏸️ Quick 30s break at {self.stats['current_session']} replies...")
                    time.sleep(30)

            self.log(f"✓ Processed {list_name}: {replied_count} replies")

        except Exception as e:
            self.log(f"❌ Error in list {list_name}: {str(e)[:50]}")

    def run(self, config):
        self.running = True

        # Setup driver - this already navigates to Twitter home
        self.setup_driver()

        # Wait a bit for page to load
        time.sleep(3)

        # Check if already logged in, if not redirect to login
        if not self.check_login_status():
            self.log("🔐 Not logged in, redirecting to login page...")
            self.driver.get("https://twitter.com/login")
        else:
            self.log("✅ Already logged in to Twitter!")

        # Wait for user to complete login (if needed)
        if not self.wait_for_login():
            self.log("❌ Login failed or cancelled")
            self.stop()
            return

        x_lists = config.get('x_lists', [])
        target_replies = config['targets']['replies_per_day']
        rest_duration = config['targets']['rest_duration_seconds']

        self.stats['replies_today'] = self.db.get_today_count()

        self.log(f"🎯 TARGET: {target_replies} replies today")
        self.log(f"📊 Already done today: {self.stats['replies_today']}")
        self.log(f"⏱️ Rest duration: {rest_duration}s between replies")
        self.log(f"📋 Working with {len(x_lists)} lists")

        try:
            cycle_count = 0

            while self.running and self.stats['replies_today'] < target_replies:
                cycle_count += 1
                self.log(f"\n🔄 CYCLE {cycle_count} - Progress: {self.stats['replies_today']}/{target_replies}")

                for idx, list_url in enumerate(x_lists, 1):
                    if not self.running or self.stats['replies_today'] >= target_replies:
                        break

                    list_name = f"List {idx}"
                    self.process_list(list_url, list_name, rest_duration, target_replies)

                    if self.stats['replies_today'] < target_replies:
                        HumanSimulator.quick_delay(3, 5)

                if self.stats['replies_today'] < target_replies and self.running:
                    self.log(f"⏸️ 60s break before next cycle...")
                    time.sleep(60)

        except Exception as e:
            self.log(f"❌ Critical error: {str(e)}")
        finally:
            stats = self.db.get_stats()
            self.log(f"\n🏁 SESSION COMPLETE!")
            self.log(f"📊 Today: {stats['today_replies']}/{target_replies} replies")
            self.log(f"👥 Engaged with {stats['unique_authors']} unique authors")
            self.log(f"💯 All-time total: {stats['total_all_time']} replies")

            if stats['today_replies'] >= target_replies:
                self.log(f"🎉 TARGET REACHED! {target_replies} replies completed!")

    def stop(self):
        self.log("🛑 Stopping bot...")
        self.running = False
        if self.driver:
            try:
                self.driver.quit()
                self.log("✅ Browser closed")
            except Exception as e:
                self.log(f"⚠️ Error closing browser: {e}")
                pass
        self.log("✅ Bot stopped successfully")

# ============= Flask Routes =============
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Ensure MongoDB connection
        if not get_mongodb_connection():
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if users_collection.find_one({'$or': [{'username': username}, {'email': email}]}):
            return jsonify({'success': False, 'message': 'Username or email already exists'}), 400

        hashed_password = generate_password_hash(password)
        user_data = {
            'username': username,
            'email': email,
            'password': hashed_password,
            'is_premium': False,
            'created_at': datetime.utcnow()
        }

        result = users_collection.insert_one(user_data)
        return jsonify({'success': True, 'message': 'Registration successful'})

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Ensure MongoDB connection
        if not get_mongodb_connection():
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        user_data = users_collection.find_one({'username': username})

        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            return jsonify({'success': True, 'redirect': url_for('dashboard')})

        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_premium:
        return render_template('upgrade.html')

    config = ConfigManager.load(current_user.id)
    db_manager = MongoDBManager(current_user.id)
    stats = db_manager.get_stats()

    return render_template('dashboard.html',
                         username=current_user.username,
                         config=config,
                         stats=stats)

@app.route('/upgrade-premium', methods=['POST'])
@login_required
def upgrade_premium():
    # Ensure MongoDB connection
    if not get_mongodb_connection():
        return jsonify({'success': False, 'message': 'Database connection error'}), 500

    from bson.objectid import ObjectId
    users_collection.update_one(
        {'_id': ObjectId(current_user.id)},
        {'$set': {'is_premium': True}}
    )
    return jsonify({'success': True, 'message': 'Upgraded to premium'})

@app.route('/api/config', methods=['GET', 'POST'])
@login_required
def api_config():
    if not current_user.is_premium:
        return jsonify({'success': False, 'message': 'Premium required'}), 403

    if request.method == 'POST':
        config_data = request.get_json()
        ConfigManager.save(current_user.id, config_data)
        return jsonify({'success': True})

    config = ConfigManager.load(current_user.id)
    return jsonify(config)

@app.route('/api/stats')
@login_required
def api_stats():
    if not current_user.is_premium:
        return jsonify({'success': False, 'message': 'Premium required'}), 403

    db_manager = MongoDBManager(current_user.id)
    stats = db_manager.get_stats()
    return jsonify(stats)

@app.route('/api/bot/start', methods=['POST'])
@login_required
def start_bot():
    if not current_user.is_premium:
        return jsonify({'success': False, 'message': 'Premium required'}), 403

    # Bot now runs on client PC via desktop client
    return jsonify({
        'success': False,
        'message': 'Please download and run the desktop client to start the bot on your PC'
    })

@app.route('/api/bot/stop', methods=['POST'])
@login_required
def stop_bot():
    # Bot now runs on client PC via desktop client
    return jsonify({
        'success': False,
        'message': 'Bot runs on your PC. Close the desktop client to stop it.'
    })

# ============= Desktop Client API Endpoints =============
@app.route('/api/client/login', methods=['POST'])
def client_login():
    """Login endpoint for desktop client"""
    if not get_mongodb_connection():
        return jsonify({'success': False, 'message': 'Database connection error'}), 500

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user_data = users_collection.find_one({'username': username})

    if user_data and check_password_hash(user_data['password'], password):
        # Check if premium
        if not user_data.get('is_premium', False):
            return jsonify({'success': False, 'message': 'Premium subscription required'}), 403

        # Generate a simple token (user_id)
        token = str(user_data['_id'])
        return jsonify({
            'success': True,
            'token': token,
            'username': username
        })

    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/client/config', methods=['GET'])
def client_config():
    """Get configuration for desktop client"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not token:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    # Verify token and load config
    try:
        config = ConfigManager.load(token)
        return jsonify(config)
    except Exception as e:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

@app.route('/api/client/status', methods=['POST'])
def client_status():
    """Receive status updates from desktop client"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not token:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json()
    status = data.get('status')
    username = data.get('username')

    # Emit status to web dashboard
    socketio.emit('client_status', {
        'username': username,
        'status': status,
        'timestamp': datetime.utcnow().isoformat()
    }, room=token)

    return jsonify({'success': True})

@app.route('/api/client/log', methods=['POST'])
def client_log():
    """Receive logs from desktop client"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not token:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json()
    message = data.get('message')

    # Emit log to web dashboard
    socketio.emit('bot_log', {'message': message}, room=token)

    return jsonify({'success': True})

@socketio.on('connect')
def handle_connect(auth=None):
    try:
        if current_user.is_authenticated:
            print(f'Client connected: {current_user.username}')
    except:
        pass

@socketio.on('disconnect')
def handle_disconnect():
    try:
        if current_user.is_authenticated:
            print(f'Client disconnected: {current_user.username}')
    except:
        pass

@socketio.on('client_log')
def handle_client_log(data):
    """Handle logs from desktop client"""
    try:
        message = data.get('message')
        username = data.get('username')

        # Find user and emit to their room
        if get_mongodb_connection():
            user_data = users_collection.find_one({'username': username})
            if user_data:
                user_id = str(user_data['_id'])
                socketio.emit('bot_log', {'message': message}, room=user_id)
    except Exception as e:
        print(f"Error handling client log: {e}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
