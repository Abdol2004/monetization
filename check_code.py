import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import random
import json
import sqlite3
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests

# ============= Configuration Manager =============
class ConfigManager:
    GROK_API_KEY = "YOUR_GROK_API_KEY_HERE"  # Add your Grok API key
    GROK_API_URL = "https://api.x.ai/v1/chat/completions"
    
    @staticmethod
    def load():
        try:
            with open('x_monetization_config.json', 'r') as f:
                return json.load(f)
        except:
            return {
                "mode": "viral_hunting",
                "engagement_style": "rage_bait",
                "target_language": "english",
                "lists": [],
                "targets": {
                    "verified_followers": 500,
                    "impressions_per_week": 5000000,
                    "weeks": 1
                },
                "follow_verified_only": True,
                "auto_unfollow_non_followers": True
            }
    
    @staticmethod
    def save(config_data):
        with open('x_monetization_config.json', 'w') as f:
            json.dump(config_data, f, indent=2)

# ============= Advanced Database =============
class MonetizationDB:
    def __init__(self):
        self.conn = sqlite3.connect('x_monetization.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS followers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                is_verified BOOLEAN,
                followed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                followed_back BOOLEAN DEFAULT 0,
                unfollowed BOOLEAN DEFAULT 0
            )
        ''')
        
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS engagements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT UNIQUE,
                tweet_url TEXT,
                author TEXT,
                author_verified BOOLEAN,
                tweet_content TEXT,
                reply_content TEXT,
                engagement_type TEXT,
                impressions INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                retweets INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                estimated_viral_score REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS user_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_name TEXT UNIQUE,
                language TEXT,
                users TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date DATE PRIMARY KEY,
                follows INTEGER DEFAULT 0,
                engagements INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                verified_gained INTEGER DEFAULT 0
            )
        ''')
        
        self.conn.commit()
    
    def add_follower(self, username, is_verified):
        try:
            self.conn.execute(
                'INSERT INTO followers (username, is_verified) VALUES (?, ?)',
                (username, is_verified)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass
    
    def mark_followed_back(self, username):
        self.conn.execute(
            'UPDATE followers SET followed_back = 1 WHERE username = ?',
            (username,)
        )
        self.conn.commit()
    
    def add_engagement(self, tweet_id, url, author, verified, content, reply, eng_type, viral_score):
        try:
            self.conn.execute(
                '''INSERT INTO engagements 
                (tweet_id, tweet_url, author, author_verified, tweet_content, reply_content, 
                engagement_type, estimated_viral_score) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (tweet_id, url, author, verified, content, reply, eng_type, viral_score)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass
    
    def update_impressions(self, tweet_id, impressions, likes=0, retweets=0, replies=0):
        self.conn.execute(
            '''UPDATE engagements 
            SET impressions = ?, likes = ?, retweets = ?, replies = ?
            WHERE tweet_id = ?''',
            (impressions, likes, retweets, replies, tweet_id)
        )
        self.conn.commit()
    
    def get_stats(self):
        cursor = self.conn.execute(
            '''SELECT 
                COUNT(*) as total_followers,
                SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) as verified_followers,
                SUM(CASE WHEN followed_back = 1 THEN 1 ELSE 0 END) as followed_back
            FROM followers WHERE unfollowed = 0'''
        )
        followers_stats = cursor.fetchone()
        
        cursor = self.conn.execute(
            '''SELECT 
                COUNT(*) as total_engagements,
                SUM(impressions) as total_impressions,
                AVG(estimated_viral_score) as avg_viral_score
            FROM engagements 
            WHERE DATE(timestamp) >= DATE('now', '-7 days')'''
        )
        engagement_stats = cursor.fetchone()
        
        return {
            'total_followers': followers_stats[0] or 0,
            'verified_followers': followers_stats[1] or 0,
            'followed_back': followers_stats[2] or 0,
            'total_engagements': engagement_stats[0] or 0,
            'total_impressions': engagement_stats[1] or 0,
            'avg_viral_score': round(engagement_stats[2] or 0, 2)
        }
    
    def save_list(self, list_name, language, users):
        try:
            self.conn.execute(
                'INSERT INTO user_lists (list_name, language, users) VALUES (?, ?, ?)',
                (list_name, language, json.dumps(users))
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_lists(self):
        cursor = self.conn.execute('SELECT list_name, language FROM user_lists')
        return cursor.fetchall()
    
    def get_list_users(self, list_name):
        cursor = self.conn.execute('SELECT users FROM user_lists WHERE list_name = ?', (list_name,))
        result = cursor.fetchone()
        return json.loads(result[0]) if result else []

# ============= Grok AI Reply Generator =============
class GrokAI:
    def __init__(self):
        self.api_key = ConfigManager.GROK_API_KEY
        
    def generate_viral_reply(self, tweet_text, author, style="rage_bait", max_words=40):
        if self.api_key == "YOUR_GROK_API_KEY_HERE":
            return self.generate_fallback(tweet_text, style)
        
        try:
            style_prompts = {
                "rage_bait": f"""You are a master at viral Twitter engagement. Reply to this tweet with controlled controversy that makes people want to respond. Be provocative but not offensive. Challenge assumptions. Make people think "wait, what?" and feel compelled to reply. Under {max_words} words. NO hashtags.""",
                "hot_take": f"""You are known for spicy hot takes. Reply with a contrarian but defensible opinion that sparks debate. Be bold and confident. Make it conversation-worthy. Under {max_words} words. NO hashtags.""",
                "playful_criticism": f"""Reply with witty, playful criticism that's entertaining but not mean. Like a friendly roast. Make people laugh while making a point. Under {max_words} words. NO hashtags.""",
                "devil_advocate": f"""Play devil's advocate. Challenge the tweet's premise with an interesting counterpoint that makes people think. Be intellectually engaging. Under {max_words} words. NO hashtags.""",
                "strategic_question": f"""Ask a thought-provoking question that challenges the tweet and sparks discussion. Make people want to answer and debate. Under {max_words} words. NO hashtags."""
            }
            
            system_prompt = style_prompts.get(style, style_prompts["rage_bait"])
            
            response = requests.post(
                ConfigManager.GROK_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-beta",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Tweet from @{author}: {tweet_text}\n\nGenerate viral engagement reply:"}
                    ],
                    "temperature": 0.95,
                    "max_tokens": max_words * 3
                },
                timeout=15
            )
            
            if response.status_code == 200:
                reply = response.json()['choices'][0]['message']['content'].strip()
                reply = ' '.join([w for w in reply.split() if not w.startswith('#')])
                return reply[:280]
            else:
                return self.generate_fallback(tweet_text, style)
                
        except Exception as e:
            print(f"Grok Error: {str(e)[:100]}")
            return self.generate_fallback(tweet_text, style)
    
    def generate_fallback(self, tweet_text, style):
        templates = {
            "rage_bait": [
                "This is exactly the type of thinking that's holding us back. {point}",
                "Unpopular opinion: This take misses the entire point about {point}",
                "Everyone's celebrating this but nobody's talking about {point}",
                "Hot take: This is actually {point} if you think about it",
                "Respectfully disagree. {point} is what actually matters",
                "Am I the only one seeing {point} as the obvious problem here?",
                "This sounds good until you realize {point}",
                "Wrong. {point} is the actual solution everyone's ignoring"
            ],
            "hot_take": [
                "Controversial: {point} and nobody wants to admit it",
                "Say what you want but {point} is just facts",
                "Everyone's afraid to say it but {point}",
                "Spicy take: {point} proves the opposite of this",
                "Bold claim: {point} matters more than anything in this tweet"
            ],
            "playful_criticism": [
                "Tell me you don't understand {point} without telling me 💀",
                "My brother in Christ, {point} exists",
                "POV: You forgot {point} was a thing 😭",
                "This would work if {point} wasn't literally right there"
            ],
            "devil_advocate": [
                "Playing devil's advocate: What if {point} though?",
                "Counterpoint: Wouldn't {point} actually solve this better?",
                "But consider: {point} completely flips this argument"
            ],
            "strategic_question": [
                "Genuine question: Have you considered {point}?",
                "But wait - how does {point} factor into this?",
                "Curious: What's your take on {point} here?"
            ]
        }
        
        points = [
            "the actual implementation", "scalability issues", "the real-world data",
            "what happened last time", "the obvious solution", "user experience",
            "the core problem", "market reality", "basic game theory"
        ]
        
        template_list = templates.get(style, templates["rage_bait"])
        template = random.choice(template_list)
        point = random.choice(points)
        
        return template.format(point=point)[:280]

# ============= Viral Score Calculator =============
class ViralScoreCalculator:
    @staticmethod
    def calculate_viral_potential(tweet_element, driver):
        score = 0
        
        try:
            metrics = tweet_element.text
            
            if any(char.isdigit() for char in metrics):
                score += 20
            
            try:
                tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="icon-verified"]')
                score += 15
            except:
                pass
            
            try:
                tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="tweetPhoto"]')
                score += 10
            except:
                pass
            
            try:
                time_element = tweet_element.find_element(By.TAG_NAME, 'time')
                time_text = time_element.text.lower()
                if 'min' in time_text or 'm' in time_text:
                    score += 25
                elif 'h' in time_text or 'hour' in time_text:
                    score += 15
                else:
                    score += 5
            except:
                score += 10
            
            tweet_text_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="tweetText"]')
            text_length = len(tweet_text_elem.text)
            if 100 <= text_length <= 200:
                score += 15
            elif text_length < 50:
                score += 10
            else:
                score += 5
            
            controversial_keywords = [
                'wrong', 'unpopular', 'controversial', 'hot take', 'disagree',
                'vs', 'better than', 'worse than', 'overrated', 'underrated'
            ]
            text_lower = tweet_text_elem.text.lower()
            for keyword in controversial_keywords:
                if keyword in text_lower:
                    score += 5
                    break
            
            viral_niches = ['ai', 'crypto', 'startup', 'tech', 'business', 'money']
            for niche in viral_niches:
                if niche in text_lower:
                    score += 5
                    break
            
        except Exception as e:
            score = 50
        
        return min(score, 100)

# ============= Human Behavior Simulator =============
class HumanSimulator:
    @staticmethod
    def random_delay(min_sec=2, max_sec=5):
        time.sleep(random.uniform(min_sec, max_sec))
    
    @staticmethod
    def human_type(element, text):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.04, 0.15))
            if random.random() < 0.08:
                time.sleep(random.uniform(0.2, 0.6))
    
    @staticmethod
    def random_scroll(driver, times=1):
        for _ in range(times):
            scroll = random.randint(400, 900)
            driver.execute_script(f"window.scrollBy(0, {scroll});")
            time.sleep(random.uniform(0.8, 2.5))

# ============= Main X Monetization Bot =============
class XMonetizationBot:
    def __init__(self, callback=None):
        self.driver = None
        self.wait = None
        self.db = MonetizationDB()
        self.ai = GrokAI()
        self.viral_calc = ViralScoreCalculator()
        self.running = False
        self.callback = callback
        self.stats = {"follows": 0, "engagements": 0, "errors": 0}
        
    def log(self, message):
        if self.callback:
            self.callback(message)
        print(message)
    
    def setup_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)
        self.log("✓ Browser initialized")
    
    def login_x(self):
        self.driver.get("https://twitter.com/login")
        self.log("🔐 Please log in to X (Twitter)...")
        self.log("⏳ Waiting for login completion...")
        
        while True:
            try:
                if "home" in self.driver.current_url:
                    self.log("✅ Login successful!")
                    HumanSimulator.random_delay(3, 5)
                    return True
            except:
                pass
            time.sleep(2)
    
    def follow_verified_user(self, username):
        try:
            self.driver.get(f"https://twitter.com/{username}")
            HumanSimulator.random_delay(2, 4)
            
            try:
                following_btn = self.driver.find_element(By.CSS_SELECTOR, '[data-testid*="unfollow"]')
                self.log(f"⏭️ Already following @{username}")
                return False
            except:
                pass
            
            follow_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid*="follow"]'))
            )
            follow_btn.click()
            
            self.db.add_follower(username, True)
            self.stats['follows'] += 1
            self.log(f"✅ Followed verified user: @{username}")
            return True
            
        except Exception as e:
            self.log(f"❌ Failed to follow @{username}: {str(e)[:50]}")
            return False
    
    def find_viral_tweets(self, search_term=None):
        try:
            if search_term:
                url = f"https://twitter.com/search?q={search_term}&src=typed_query&f=live"
            else:
                url = "https://twitter.com/home"
            
            self.driver.get(url)
            HumanSimulator.random_delay(3, 5)
            HumanSimulator.random_scroll(self.driver, 2)
            
            tweets = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            
            viral_candidates = []
            for tweet in tweets[:15]:
                viral_score = self.viral_calc.calculate_viral_potential(tweet, self.driver)
                if viral_score >= 70:
                    tweet_info = self.extract_tweet_data(tweet)
                    if tweet_info:
                        tweet_info['viral_score'] = viral_score
                        viral_candidates.append(tweet_info)
            
            viral_candidates.sort(key=lambda x: x['viral_score'], reverse=True)
            return viral_candidates[:5]
            
        except Exception as e:
            self.log(f"❌ Error finding viral tweets: {str(e)[:50]}")
            return []
    
    def extract_tweet_data(self, tweet_element):
        try:
            text_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="tweetText"]')
            tweet_text = text_elem.text
            
            author_elem = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="User-Name"]')
            author = author_elem.text.split('\n')[0].replace('@', '')
            
            is_verified = False
            try:
                tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="icon-verified"]')
                is_verified = True
            except:
                pass
            
            links = tweet_element.find_elements(By.TAG_NAME, 'a')
            tweet_id = None
            for link in links:
                href = link.get_attribute('href')
                if href and '/status/' in href:
                    tweet_id = href.split('/status/')[-1].split('?')[0]
                    break
            
            return {
                'text': tweet_text,
                'author': author,
                'id': tweet_id,
                'verified': is_verified,
                'element': tweet_element
            }
        except:
            return None
    
    def engage_with_tweet(self, tweet_info, engagement_style):
        try:
            reply = self.ai.generate_viral_reply(
                tweet_info['text'],
                tweet_info['author'],
                engagement_style
            )
            
            self.log(f"💬 Replying to @{tweet_info['author']}: {reply[:50]}...")
            
            reply_btn = tweet_info['element'].find_element(By.CSS_SELECTOR, '[data-testid="reply"]')
            reply_btn.click()
            HumanSimulator.random_delay(1, 2)
            
            reply_box = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
            )
            HumanSimulator.human_type(reply_box, reply)
            HumanSimulator.random_delay(1, 2)
            
            send_btn = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="tweetButton"]')
            send_btn.click()
            
            tweet_url = f"https://twitter.com/{tweet_info['author']}/status/{tweet_info['id']}"
            self.db.add_engagement(
                tweet_info['id'],
                tweet_url,
                tweet_info['author'],
                tweet_info['verified'],
                tweet_info['text'],
                reply,
                engagement_style,
                tweet_info.get('viral_score', 0)
            )
            
            self.stats['engagements'] += 1
            self.log(f"✅ Viral engagement sent! Score: {tweet_info.get('viral_score', 0)}/100")
            
            HumanSimulator.random_delay(3, 6)
            return True
            
        except Exception as e:
            self.log(f"❌ Engagement failed: {str(e)[:50]}")
            self.stats['errors'] += 1
            return False
    
    def run_viral_hunting_mode(self, config):
        engagement_style = config.get('engagement_style', 'rage_bait')
        target_verified = config['targets']['verified_followers']
        target_impressions = config['targets']['impressions_per_week']
        weeks = config['targets']['weeks']
        
        days = weeks * 7
        daily_engagements = (target_impressions // days) // 1000
        daily_follows = target_verified // days
        
        self.log(f"🎯 VIRAL HUNTING MODE")
        self.log(f"📊 Targets: {target_verified} verified followers, {target_impressions:,} impressions in {weeks} week(s)")
        self.log(f"📈 Daily plan: {daily_engagements} engagements, {daily_follows} follows")
        
        engagements_today = 0
        follows_today = 0
        
        while self.running and engagements_today < daily_engagements:
            self.log("🔍 Scanning for viral opportunities...")
            viral_tweets = self.find_viral_tweets()
            
            if not viral_tweets:
                self.log("⚠️ No high-viral tweets found, scrolling...")
                HumanSimulator.random_scroll(self.driver, 3)
                continue
            
            for tweet in viral_tweets:
                if not self.running:
                    break
                
                if self.engage_with_tweet(tweet, engagement_style):
                    engagements_today += 1
                    
                    if tweet['verified'] and follows_today < daily_follows:
                        if self.follow_verified_user(tweet['author']):
                            follows_today += 1
                    
                    delay = random.randint(45, 90)
                    self.log(f"⏳ Waiting {delay}s before next action...")
                    time.sleep(delay)
                    
                    if engagements_today % 15 == 0:
                        break_time = random.randint(300, 600)
                        self.log(f"☕ Taking {break_time//60}min break...")
                        time.sleep(break_time)
    
    def run_list_mode(self, config, list_name):
        users = self.db.get_list_users(list_name)
        engagement_style = config.get('engagement_style', 'rage_bait')
        
        if not users:
            self.log(f"❌ No users found in list: {list_name}")
            return
        
        self.log(f"📋 LIST MODE: {list_name}")
        self.log(f"👥 {len(users)} users in list")
        
        for username in users:
            if not self.running:
                break
            
            self.log(f"🎯 Targeting @{username}...")
            
            self.driver.get(f"https://twitter.com/{username}")
            HumanSimulator.random_delay(3, 5)
            
            tweets = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')[:3]
            
            for tweet_elem in tweets:
                tweet_info = self.extract_tweet_data(tweet_elem)
                if tweet_info:
                    viral_score = self.viral_calc.calculate_viral_potential(tweet_elem, self.driver)
                    tweet_info['viral_score'] = viral_score
                    
                    if self.engage_with_tweet(tweet_info, engagement_style):
                        delay = random.randint(40, 80)
                        time.sleep(delay)
                        break
            
            HumanSimulator.random_delay(60, 120)
    
    def run(self, config):
        self.running = True
        self.setup_driver()
        
        if not self.login_x():
            self.log("❌ Login failed")
            return
        
        mode = config.get('mode', 'viral_hunting')
        
        try:
            if mode == 'viral_hunting':
                self.run_viral_hunting_mode(config)
            elif mode == 'list_engagement':
                list_name = config.get('selected_list')
                if list_name:
                    self.run_list_mode(config, list_name)
                else:
                    self.log("❌ No list selected")
                    
        except Exception as e:
            self.log(f"❌ Critical error: {str(e)[:100]}")
        finally:
            stats = self.db.get_stats()
            self.log(f"🏁 Session complete!")
            self.log(f"📊 Stats: {stats['verified_followers']}/{config['targets']['verified_followers']} verified | {stats['total_impressions']:,} impressions")
    
    def stop(self):
        self.running = False
        if self.driver:
            self.driver.quit()

# ============= Modern GUI =============
class ModernGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("X Monetization Bot - Advanced Viral System")
        self.root.geometry("1200x800")
        self.root.configure(bg='#0f1419')
        
        self.bot = None
        self.bot_thread = None
        self.config = ConfigManager.load()
        self.db = MonetizationDB()
        
        self.setup_styles()
        self.create_ui()
        self.update_stats()
    
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        bg_dark = '#0f1419'
        bg_card = '#16181c'
        text_primary = '#e7e9ea'
        text_secondary = '#71767b'
        accent_blue = '#1d9bf0'
        
        style.configure('Dark.TFrame', background=bg_dark)
        style.configure('Card.TFrame', background=bg_card, relief='flat')
        style.configure('Dark.TLabel', background=bg_dark, foreground=text_primary, font=('Segoe UI', 10))
        style.configure('Title.TLabel', background=bg_dark, foreground=text_primary, font=('Segoe UI', 24, 'bold'))
        style.configure('Subtitle.TLabel', background=bg_dark, foreground=text_secondary, font=('Segoe UI', 10))
        style.configure('Card.TLabel', background=bg_card, foreground=text_primary, font=('Segoe UI', 10))
    
    def create_ui(self):
        main_container = ttk.Frame(self.root, style='Dark.TFrame')
        main_container.pack(fill='both', expand=True)
        
        header = ttk.Frame(main_container, style='Dark.TFrame')
        header.pack(fill='x', padx=20, pady=20)
        
        title = ttk.Label(header, text="⚡ X Monetization Bot", style='Title.TLabel')
        title.pack(side='left')
        
        subtitle = ttk.Label(header, text="Advanced Viral Engagement & Growth System", style='Subtitle.TLabel')
        subtitle.pack(side='left', padx=15)
        
        self.create_stats_dashboard(main_container)
        
        config_container = ttk.Frame(main_container, style='Dark.TFrame')
        config_container.pack(fill='both', expand=True, padx=20, pady=10)
        
        left_panel = ttk.Frame(config_container, style='Card.TFrame')
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_settings_panel(left_panel)
        
        right_panel = ttk.Frame(config_container, style='Card.TFrame')
        right_panel.pack(side='right', fill='both', expand=True, padx=(10, 0))
        self.create_lists_panel(right_panel)
        
        self.create_controls(main_container)
        self.create_log_panel(main_container)
    
    def create_stats_dashboard(self, parent):
        stats_frame = ttk.Frame(parent, style='Card.TFrame')
        stats_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        ttk.Label(stats_frame, text="📊 Live Statistics", 
                 style='Card.TLabel', font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=15, pady=10)
        
        stats_grid = ttk.Frame(stats_frame, style='Card.TFrame')
        stats_grid.pack(fill='x', padx=15, pady=(0, 15))
        
        stats_labels = [
            ("Verified Followers", "verified_label", "🎯"),
            ("Total Impressions", "impressions_label", "👁️"),
            ("Engagement Rate", "engagement_label", "💬"),
            ("Viral Score Avg", "viral_label", "⚡")
        ]
        
        for idx, (label, attr, emoji) in enumerate(stats_labels):
            card = tk.Frame(stats_grid, bg='#1c1f26', highlightbackground='#2f3336', highlightthickness=1)
            card.grid(row=0, column=idx, padx=10, pady=10, sticky='nsew')
            stats_grid.columnconfigure(idx, weight=1)
            
            emoji_label = tk.Label(card, text=emoji, font=('Segoe UI', 24), bg='#1c1f26', fg='#1d9bf0')
            emoji_label.pack(pady=(10, 5))
            
            value_label = tk.Label(card, text="0", font=('Segoe UI', 20, 'bold'), bg='#1c1f26', fg='#e7e9ea')
            value_label.pack()
            setattr(self, attr, value_label)
            
            desc_label = tk.Label(card, text=label, font=('Segoe UI', 9), bg='#1c1f26', fg='#71767b')
            desc_label.pack(pady=(0, 10))
    
    def create_settings_panel(self, parent):
        ttk.Label(parent, text="⚙️ Bot Configuration", 
                 style='Card.TLabel', font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=15)
        
        settings = ttk.Frame(parent, style='Card.TFrame')
        settings.pack(fill='both', expand=True, padx=15)
        
        tk.Label(settings, text="Bot Mode:", bg='#16181c', fg='#e7e9ea', font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', pady=10)
        self.mode_var = tk.StringVar(value=self.config.get('mode', 'viral_hunting'))
        mode_frame = tk.Frame(settings, bg='#16181c')
        mode_frame.grid(row=0, column=1, sticky='w', pady=10, padx=10)
        
        tk.Radiobutton(mode_frame, text="🔥 Viral Hunting", variable=self.mode_var, value='viral_hunting',
                      bg='#16181c', fg='#e7e9ea', selectcolor='#1c1f26', font=('Segoe UI', 9),
                      activebackground='#16181c', activeforeground='#1d9bf0').pack(side='left', padx=5)
        tk.Radiobutton(mode_frame, text="📋 List Engagement", variable=self.mode_var, value='list_engagement',
                      bg='#16181c', fg='#e7e9ea', selectcolor='#1c1f26', font=('Segoe UI', 9),
                      activebackground='#16181c', activeforeground='#1d9bf0').pack(side='left', padx=5)
        
        tk.Label(settings, text="Engagement Style:", bg='#16181c', fg='#e7e9ea', font=('Segoe UI', 10)).grid(row=1, column=0, sticky='w', pady=10)
        self.style_var = tk.StringVar(value=self.config.get('engagement_style', 'rage_bait'))
        style_menu = ttk.Combobox(settings, textvariable=self.style_var, state='readonly', width=20,
                                 values=['rage_bait', 'hot_take', 'playful_criticism', 'devil_advocate', 'strategic_question'])
        style_menu.grid(row=1, column=1, sticky='w', pady=10, padx=10)
        
        tk.Label(settings, text="🎯 Growth Targets", bg='#16181c', fg='#1d9bf0', 
                font=('Segoe UI', 11, 'bold')).grid(row=2, column=0, columnspan=2, sticky='w', pady=(20, 10))
        
        tk.Label(settings, text="Verified Followers:", bg='#16181c', fg='#e7e9ea').grid(row=3, column=0, sticky='w', pady=5)
        self.verified_target = tk.Spinbox(settings, from_=100, to=10000, width=15, bg='#1c1f26', fg='#e7e9ea',
                                         buttonbackground='#2f3336', font=('Segoe UI', 9))
        self.verified_target.delete(0, 'end')
        self.verified_target.insert(0, self.config['targets']['verified_followers'])
        self.verified_target.grid(row=3, column=1, sticky='w', pady=5, padx=10)
        
        tk.Label(settings, text="Target Impressions:", bg='#16181c', fg='#e7e9ea').grid(row=4, column=0, sticky='w', pady=5)
        self.impressions_target = tk.Spinbox(settings, from_=100000, to=100000000, increment=100000, width=15,
                                            bg='#1c1f26', fg='#e7e9ea', buttonbackground='#2f3336', font=('Segoe UI', 9))
        self.impressions_target.delete(0, 'end')
        self.impressions_target.insert(0, self.config['targets']['impressions_per_week'])
        self.impressions_target.grid(row=4, column=1, sticky='w', pady=5, padx=10)
        
        tk.Label(settings, text="Timeframe (weeks):", bg='#16181c', fg='#e7e9ea').grid(row=5, column=0, sticky='w', pady=5)
        self.weeks_target = tk.Spinbox(settings, from_=1, to=12, width=15, bg='#1c1f26', fg='#e7e9ea',
                                      buttonbackground='#2f3336', font=('Segoe UI', 9))
        self.weeks_target.delete(0, 'end')
        self.weeks_target.insert(0, self.config['targets']['weeks'])
        self.weeks_target.grid(row=5, column=1, sticky='w', pady=5, padx=10)
        
        save_btn = tk.Button(settings, text="💾 Save Configuration", command=self.save_config,
                           bg='#1d9bf0', fg='white', font=('Segoe UI', 10, 'bold'),
                           relief='flat', cursor='hand2', padx=20, pady=8)
        save_btn.grid(row=6, column=0, columnspan=2, pady=20)
    
    def create_lists_panel(self, parent):
        ttk.Label(parent, text="📋 User Lists Management", 
                 style='Card.TLabel', font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=15)
        
        create_frame = tk.Frame(parent, bg='#16181c')
        create_frame.pack(fill='x', padx=15, pady=10)
        
        tk.Label(create_frame, text="Create New List:", bg='#16181c', fg='#e7e9ea', 
                font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=5)
        
        input_frame = tk.Frame(create_frame, bg='#16181c')
        input_frame.pack(fill='x', pady=5)
        
        tk.Label(input_frame, text="Name:", bg='#16181c', fg='#e7e9ea').pack(side='left')
        self.list_name_entry = tk.Entry(input_frame, width=20, bg='#1c1f26', fg='#e7e9ea', 
                                        font=('Segoe UI', 9), relief='flat')
        self.list_name_entry.pack(side='left', padx=5)
        
        tk.Label(input_frame, text="Language:", bg='#16181c', fg='#e7e9ea').pack(side='left', padx=(10, 0))
        self.list_lang_var = tk.StringVar(value='english')
        lang_menu = ttk.Combobox(input_frame, textvariable=self.list_lang_var, state='readonly', 
                                width=10, values=['english', 'chinese'])
        lang_menu.pack(side='left', padx=5)
        
        tk.Label(create_frame, text="Usernames (comma-separated):", bg='#16181c', fg='#e7e9ea').pack(anchor='w', pady=(10, 5))
        self.list_users_text = tk.Text(create_frame, height=5, width=40, bg='#1c1f26', fg='#e7e9ea',
                                      font=('Segoe UI', 9), relief='flat', wrap='word')
        self.list_users_text.pack(fill='x')
        
        tk.Button(create_frame, text="➕ Create List", command=self.create_list,
                 bg='#00ba7c', fg='white', font=('Segoe UI', 9, 'bold'),
                 relief='flat', cursor='hand2', padx=15, pady=5).pack(pady=10)
        
        tk.Label(parent, text="Saved Lists:", bg='#16181c', fg='#e7e9ea',
                font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(20, 5))
        
        lists_scroll_frame = tk.Frame(parent, bg='#16181c')
        lists_scroll_frame.pack(fill='both', expand=True, padx=15, pady=5)
        
        self.lists_listbox = tk.Listbox(lists_scroll_frame, bg='#1c1f26', fg='#e7e9ea',
                                       font=('Segoe UI', 9), relief='flat', selectmode='single',
                                       highlightthickness=0)
        self.lists_listbox.pack(fill='both', expand=True)
        
        self.load_lists()
    
    def create_controls(self, parent):
        control_frame = tk.Frame(parent, bg='#0f1419')
        control_frame.pack(pady=20)
        
        self.start_btn = tk.Button(control_frame, text="▶️ START BOT", command=self.start_bot,
                                   bg='#00ba7c', fg='white', font=('Segoe UI', 14, 'bold'),
                                   relief='flat', cursor='hand2', padx=40, pady=15)
        self.start_btn.pack(side='left', padx=10)
        
        self.stop_btn = tk.Button(control_frame, text="⏹️ STOP BOT", command=self.stop_bot,
                                  bg='#f4212e', fg='white', font=('Segoe UI', 14, 'bold'),
                                  relief='flat', cursor='hand2', padx=40, pady=15, state='disabled')
        self.stop_btn.pack(side='left', padx=10)
    
    def create_log_panel(self, parent):
        log_frame = tk.Frame(parent, bg='#16181c', highlightbackground='#2f3336', highlightthickness=1)
        log_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        tk.Label(log_frame, text="📋 Activity Log", bg='#16181c', fg='#e7e9ea',
                font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=15, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD,
                                                  bg='#0f1419', fg='#e7e9ea',
                                                  font=('Consolas', 9), relief='flat')
        self.log_text.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        self.log_message("🚀 X Monetization Bot initialized")
        self.log_message("⚠️ Set your Grok API key in the code first (get free at x.ai)")
    
    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def update_stats(self):
        stats = self.db.get_stats()
        
        self.verified_label.config(text=f"{stats['verified_followers']}/{self.config['targets']['verified_followers']}")
        self.impressions_label.config(text=f"{stats['total_impressions']:,}")
        
        engagement_rate = (stats['total_engagements'] / max(stats['total_followers'], 1)) * 100
        self.engagement_label.config(text=f"{engagement_rate:.1f}%")
        self.viral_label.config(text=f"{stats['avg_viral_score']:.1f}/100")
        
        self.root.after(5000, self.update_stats)
    
    def save_config(self):
        self.config = {
            'mode': self.mode_var.get(),
            'engagement_style': self.style_var.get(),
            'targets': {
                'verified_followers': int(self.verified_target.get()),
                'impressions_per_week': int(self.impressions_target.get()),
                'weeks': int(self.weeks_target.get())
            },
            'follow_verified_only': True,
            'auto_unfollow_non_followers': True
        }
        ConfigManager.save(self.config)
        self.log_message("✅ Configuration saved!")
        messagebox.showinfo("Success", "Configuration saved successfully!")
    
    def create_list(self):
        list_name = self.list_name_entry.get().strip()
        language = self.list_lang_var.get()
        users_text = self.list_users_text.get("1.0", tk.END).strip()
        
        if not list_name or not users_text:
            messagebox.showerror("Error", "Please fill in all fields")
            return
        
        users = [u.strip().replace('@', '') for u in users_text.split(',')]
        
        if self.db.save_list(list_name, language, users):
            self.log_message(f"✅ Created list '{list_name}' with {len(users)} users")
            self.list_name_entry.delete(0, tk.END)
            self.list_users_text.delete("1.0", tk.END)
            self.load_lists()
            messagebox.showinfo("Success", f"List '{list_name}' created!")
        else:
            messagebox.showerror("Error", "List name already exists")
    
    def load_lists(self):
        self.lists_listbox.delete(0, tk.END)
        lists = self.db.get_lists()
        for list_name, lang in lists:
            self.lists_listbox.insert(tk.END, f"{list_name} ({lang})")
    
    def start_bot(self):
        if ConfigManager.GROK_API_KEY == "YOUR_GROK_API_KEY_HERE":
            messagebox.showwarning("API Key Required", 
                                  "Please set your Grok API key in the code!\n\nGet free access at: console.x.ai")
            return
        
        self.save_config()
        
        if self.config['mode'] == 'list_engagement':
            selection = self.lists_listbox.curselection()
            if not selection:
                messagebox.showerror("Error", "Please select a list for engagement")
                return
            list_name = self.lists_listbox.get(selection[0]).split(' (')[0]
            self.config['selected_list'] = list_name
        
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        self.bot = XMonetizationBot(callback=self.log_message)
        self.bot_thread = threading.Thread(target=self.bot.run, args=(self.config,), daemon=True)
        self.bot_thread.start()
        
        self.log_message("🚀 Bot started!")
    
    def stop_bot(self):
        if self.bot:
            self.log_message("🛑 Stopping bot...")
            self.bot.stop()
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
    
    def on_closing(self):
        if self.bot and self.bot.running:
            if messagebox.askokcancel("Quit", "Bot is running. Stop and quit?"):
                self.stop_bot()
                time.sleep(2)
                self.root.destroy()
        else:
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()