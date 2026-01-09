import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import random
import json
import sqlite3
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
import re

# ============= Configuration Manager =============
class ConfigManager:
    GROK_API_KEY = "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"
    GROK_API_URL = "https://api.groq.com/openai/v1/chat/completions"  # Using Groq (compatible with your key)
    
    @staticmethod
    def load():
        try:
            with open('x_monetization_config.json', 'r') as f:
                return json.load(f)
        except:
            return {
                "x_lists": [
                    "https://x.com/i/lists/1995877357249270077",
                    "https://x.com/i/lists/1904483699346784446",
                    "https://x.com/i/lists/1911725019513684062"
                ],
                "targets": {
                    "replies_per_day": 1000,
                    "rest_duration_seconds": 3
                },
                "engagement_style": "rage_bait"
            }
    
    @staticmethod
    def save(config_data):
        with open('x_monetization_config.json', 'w') as f:
            json.dump(config_data, f, indent=2)

# ============= Database =============
class MonetizationDB:
    def __init__(self):
        self.conn = sqlite3.connect('x_monetization.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS engagements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT,
                tweet_url TEXT,
                author TEXT,
                tweet_content TEXT,
                reply_content TEXT,
                list_source TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                date_only DATE
            )
        ''')
        self.conn.commit()
    
    def add_engagement(self, tweet_id, url, author, content, reply, list_source):
        date_only = datetime.now().strftime('%Y-%m-%d')
        try:
            self.conn.execute(
                '''INSERT INTO engagements 
                (tweet_id, tweet_url, author, tweet_content, reply_content, list_source, date_only) 
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (tweet_id, url, author, content, reply, list_source, date_only)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"DB Error: {e}")
            return False
    
    def already_replied_to_tweet(self, tweet_id):
        """Check if we've EVER replied to this tweet (not just today)"""
        cursor = self.conn.execute(
            'SELECT COUNT(*) FROM engagements WHERE tweet_id = ?',
            (tweet_id,)
        )
        return cursor.fetchone()[0] > 0
    
    def get_today_count(self):
        date_only = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.execute(
            'SELECT COUNT(*) FROM engagements WHERE date_only = ?',
            (date_only,)
        )
        return cursor.fetchone()[0]
    
    def get_stats(self):
        date_only = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.execute(
            '''SELECT 
                COUNT(*) as today_replies,
                COUNT(DISTINCT author) as unique_authors
            FROM engagements 
            WHERE date_only = ?''',
            (date_only,)
        )
        stats = cursor.fetchone()
        
        cursor_total = self.conn.execute('SELECT COUNT(*) FROM engagements')
        total = cursor_total.fetchone()[0]
        
        return {
            'today_replies': stats[0] or 0,
            'unique_authors': stats[1] or 0,
            'total_all_time': total
        }

# ============= AI Reply Generator (Groq API ONLY - No Templates) =============
class RageBaitGenerator:
    def __init__(self):
        self.api_key = ConfigManager.GROK_API_KEY
        self.api_url = ConfigManager.GROK_API_URL

    def detect_language(self, text):
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        return 'chinese' if len(chinese_chars) > 3 else 'english'

    def generate_reply(self, tweet_text, author):
        """Generate reply using Groq AI ONLY - no template fallback"""
        language = self.detect_language(tweet_text)
        return self.generate_with_ai(tweet_text, author, language)

    def generate_with_ai(self, tweet_text, author, language='english'):
        """Generate with Groq AI - returns None if API fails"""
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
                # API failed - return None (no template fallback)
                print(f"❌ Groq API Error: Status {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ AI Error: {str(e)}")
            # Return None instead of template fallback
            return None

# ============= Human Simulator =============
class HumanSimulator:
    @staticmethod
    def quick_delay(min_sec=0.5, max_sec=1.5):
        time.sleep(random.uniform(min_sec, max_sec))
    
    @staticmethod
    def human_type(element, text):
        """Fast typing"""
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
    def __init__(self, callback=None):
        self.driver = None
        self.wait = None
        self.db = MonetizationDB()
        self.ai = RageBaitGenerator()
        self.running = False
        self.callback = callback
        self.stats = {"replies_today": 0, "errors": 0, "current_session": 0}
        self.replied_ids = set()  # Track within session to avoid duplicates
        
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
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)
        self.log("✓ Browser ready")
    
    def login_x(self):
        self.driver.get("https://twitter.com/login")
        self.log("🔐 Please log in...")
        
        while True:
            try:
                if "home" in self.driver.current_url:
                    self.log("✅ Logged in!")
                    HumanSimulator.quick_delay(2, 3)
                    return True
            except:
                pass
            time.sleep(2)
    
    def extract_tweet_data(self, tweet_element):
        """Extract tweet info quickly"""
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
        """Fast reply to tweet"""
        try:
            # CRITICAL: Check database first to avoid duplicate replies
            if self.db.already_replied_to_tweet(tweet_info['id']):
                return False
            
            # Also skip if in current session cache
            if tweet_info['id'] in self.replied_ids:
                return False
            
            # Generate rage bait
            reply = self.ai.generate_reply(tweet_info['text'], tweet_info['author'])
            
            if not reply:
                self.stats['errors'] += 1
                return False
            
            # Click reply
            try:
                reply_btn = tweet_info['element'].find_element(By.CSS_SELECTOR, '[data-testid="reply"]')
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reply_btn)
                HumanSimulator.quick_delay(0.3, 0.7)
                reply_btn.click()
            except:
                return False
            
            HumanSimulator.quick_delay(0.5, 1)
            
            # Type reply fast
            try:
                reply_box = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
                )
                HumanSimulator.human_type(reply_box, reply)
            except:
                return False
            
            HumanSimulator.quick_delay(0.5, 1)
            
            # Send
            try:
                send_btn = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="tweetButton"]')
                send_btn.click()
            except:
                return False
            
            # Save to DB IMMEDIATELY to prevent duplicates
            tweet_url = f"https://twitter.com/{tweet_info['author']}/status/{tweet_info['id']}"
            if not self.db.add_engagement(
                tweet_info['id'],
                tweet_url,
                tweet_info['author'],
                tweet_info['text'][:200],
                reply,
                list_name
            ):
                # Failed to save - might be duplicate
                self.log(f"⚠️ Skipped duplicate: {tweet_info['id']}")
                return False
            
            # Mark as replied in session cache
            self.replied_ids.add(tweet_info['id'])
            
            self.stats['replies_today'] += 1
            self.stats['current_session'] += 1
            
            self.log(f"✅ [{self.stats['replies_today']}/1000] @{tweet_info['author']}: {reply[:60]}...")
            
            HumanSimulator.quick_delay(0.5, 1)
            
            # Close modal if exists
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
            
            # Try to close modal
            try:
                self.driver.find_element(By.CSS_SELECTOR, '[aria-label="Close"]').click()
            except:
                pass
            
            return False
    
    def process_list(self, list_url, list_name, rest_duration, target_replies):
        """Process all tweets from a list rapidly"""
        try:
            self.log(f"📋 Loading: {list_name}")
            self.driver.get(list_url)
            HumanSimulator.quick_delay(2, 3)
            
            # Scroll to load tweets
            for _ in range(3):
                HumanSimulator.quick_scroll(self.driver)
            
            # Get tweets
            tweets = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            self.log(f"📊 Found {len(tweets)} tweets in {list_name}")
            
            replied_count = 0
            
            for tweet in tweets:
                if not self.running or self.stats['replies_today'] >= target_replies:
                    break
                
                tweet_info = self.extract_tweet_data(tweet)
                if not tweet_info:
                    continue
                
                # Reply immediately
                if self.reply_to_tweet(tweet_info, list_name):
                    replied_count += 1
                    
                    # Quick rest between replies
                    time.sleep(rest_duration)
                
                # Every 50 replies, take a short break
                if self.stats['current_session'] % 50 == 0 and self.stats['current_session'] > 0:
                    self.log(f"⏸️ Quick 30s break at {self.stats['current_session']} replies...")
                    time.sleep(30)
            
            self.log(f"✓ Processed {list_name}: {replied_count} replies")
            
        except Exception as e:
            self.log(f"❌ Error in list {list_name}: {str(e)[:50]}")
    
    def run(self, config):
        """Main loop - cycles through lists until hitting 1k replies"""
        self.running = True
        self.setup_driver()
        
        if not self.login_x():
            self.log("❌ Login failed")
            return
        
        x_lists = config.get('x_lists', [])
        target_replies = config['targets']['replies_per_day']
        rest_duration = config['targets']['rest_duration_seconds']
        
        # Get today's count
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
                    
                    # Brief pause between lists
                    if self.stats['replies_today'] < target_replies:
                        HumanSimulator.quick_delay(3, 5)
                
                # NO LONGER CLEARING replied_ids - we want permanent tracking
                # Each tweet only gets ONE reply EVER
                
                # Brief break between cycles
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
        self.running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

# ============= Sleek GUI =============
class ModernGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("X List Rage Bot - 1K Daily Replies")
        self.root.geometry("900x750")
        self.root.configure(bg='#0f1419')
        
        self.bot = None
        self.bot_thread = None
        self.config = ConfigManager.load()
        self.db = MonetizationDB()
        
        self.create_ui()
        self.update_stats()
    
    def create_ui(self):
        main = tk.Frame(self.root, bg='#0f1419')
        main.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Header
        tk.Label(main, text="⚡ X List Rage Bot", bg='#0f1419', fg='#e7e9ea',
                font=('Segoe UI', 32, 'bold')).pack(pady=(0, 5))
        tk.Label(main, text="1000 Replies Per Day | Rage Bait Machine", bg='#0f1419', fg='#f91880',
                font=('Segoe UI', 13, 'bold')).pack(pady=(0, 20))
        
        # Stats
        self.create_stats(main)
        
        # Lists Display
        self.create_lists_section(main)
        
        # Settings
        self.create_settings(main)
        
        # Controls
        self.create_controls(main)
        
        # Log
        self.create_log(main)
    
    def create_stats(self, parent):
        stats_frame = tk.Frame(parent, bg='#16181c', highlightbackground='#2f3336', highlightthickness=1)
        stats_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(stats_frame, text="📊 Today's Progress", bg='#16181c', fg='#e7e9ea',
                font=('Segoe UI', 14, 'bold')).pack(pady=10)
        
        stats_grid = tk.Frame(stats_frame, bg='#16181c')
        stats_grid.pack(pady=(0, 15))
        
        # Today's replies
        card1 = tk.Frame(stats_grid, bg='#1c1f26', width=180, height=90)
        card1.grid(row=0, column=0, padx=15, pady=5)
        tk.Label(card1, text="🔥", font=('Segoe UI', 28), bg='#1c1f26', fg='#f91880').pack(pady=3)
        self.today_label = tk.Label(card1, text="0/1000", font=('Segoe UI', 22, 'bold'), 
                                    bg='#1c1f26', fg='#e7e9ea')
        self.today_label.pack()
        tk.Label(card1, text="Today's Replies", font=('Segoe UI', 9), 
                bg='#1c1f26', fg='#71767b').pack(pady=3)
        
        # Unique authors
        card2 = tk.Frame(stats_grid, bg='#1c1f26', width=180, height=90)
        card2.grid(row=0, column=1, padx=15, pady=5)
        tk.Label(card2, text="👥", font=('Segoe UI', 28), bg='#1c1f26', fg='#1d9bf0').pack(pady=3)
        self.authors_label = tk.Label(card2, text="0", font=('Segoe UI', 22, 'bold'), 
                                      bg='#1c1f26', fg='#e7e9ea')
        self.authors_label.pack()
        tk.Label(card2, text="Unique Authors", font=('Segoe UI', 9), 
                bg='#1c1f26', fg='#71767b').pack(pady=3)
        
        # All-time
        card3 = tk.Frame(stats_grid, bg='#1c1f26', width=180, height=90)
        card3.grid(row=0, column=2, padx=15, pady=5)
        tk.Label(card3, text="💯", font=('Segoe UI', 28), bg='#1c1f26', fg='#00ba7c').pack(pady=3)
        self.total_label = tk.Label(card3, text="0", font=('Segoe UI', 22, 'bold'), 
                                    bg='#1c1f26', fg='#e7e9ea')
        self.total_label.pack()
        tk.Label(card3, text="All-Time Total", font=('Segoe UI', 9), 
                bg='#1c1f26', fg='#71767b').pack(pady=3)
    
    def create_lists_section(self, parent):
        lists_frame = tk.Frame(parent, bg='#16181c', highlightbackground='#2f3336', highlightthickness=1)
        lists_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(lists_frame, text="📋 Active X Lists", bg='#16181c', fg='#e7e9ea',
                font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=10)
        
        x_lists = self.config.get('x_lists', [])
        
        if not x_lists:
            tk.Label(lists_frame, text="⚠️ No lists configured - using defaults", 
                    bg='#16181c', fg='#f91880', font=('Segoe UI', 9)).pack(anchor='w', padx=20, pady=5)
            # Set defaults if not present
            self.config['x_lists'] = [
                "https://x.com/i/lists/1995877357249270077",
                "https://x.com/i/lists/1904483699346784446",
                "https://x.com/i/lists/1911725019513684062"
            ]
            ConfigManager.save(self.config)
            x_lists = self.config['x_lists']
        
        for idx, list_url in enumerate(x_lists, 1):
            list_label = tk.Label(lists_frame, text=f"✓ List {idx}: {list_url}", 
                                 bg='#16181c', fg='#00ba7c', font=('Consolas', 9))
            list_label.pack(anchor='w', padx=20, pady=2)
    
    def create_settings(self, parent):
        settings_frame = tk.Frame(parent, bg='#16181c', highlightbackground='#2f3336', highlightthickness=1)
        settings_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(settings_frame, text="⚙️ Settings", bg='#16181c', fg='#e7e9ea',
                font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=10)
        
        settings_grid = tk.Frame(settings_frame, bg='#16181c')
        settings_grid.pack(padx=20, pady=(0, 15))
        
        # Ensure targets exist with defaults
        if 'targets' not in self.config:
            self.config['targets'] = {}
        
        if 'rest_duration_seconds' not in self.config['targets']:
            self.config['targets']['rest_duration_seconds'] = 3
        
        if 'replies_per_day' not in self.config['targets']:
            self.config['targets']['replies_per_day'] = 1000
        
        # Rest duration
        tk.Label(settings_grid, text="Rest Between Replies (seconds):", bg='#16181c', fg='#e7e9ea',
                font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', padx=10, pady=8)
        self.rest_duration = tk.Spinbox(settings_grid, from_=1, to=30, width=15, 
                                        bg='#1c1f26', fg='#e7e9ea', font=('Segoe UI', 10))
        self.rest_duration.delete(0, 'end')
        self.rest_duration.insert(0, self.config['targets']['rest_duration_seconds'])
        self.rest_duration.grid(row=0, column=1, padx=10, pady=8)
        
        # Target replies
        tk.Label(settings_grid, text="Target Replies Per Day:", bg='#16181c', fg='#e7e9ea',
                font=('Segoe UI', 10)).grid(row=1, column=0, sticky='w', padx=10, pady=8)
        self.target_replies = tk.Spinbox(settings_grid, from_=100, to=5000, increment=100, width=15,
                                         bg='#1c1f26', fg='#e7e9ea', font=('Segoe UI', 10))
        self.target_replies.delete(0, 'end')
        self.target_replies.insert(0, self.config['targets']['replies_per_day'])
        self.target_replies.grid(row=1, column=1, padx=10, pady=8)
        
        tk.Button(settings_frame, text="💾 Save Settings", command=self.save_config,
                 bg='#1d9bf0', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=8).pack(pady=(5, 10))
    
    def create_controls(self, parent):
        controls = tk.Frame(parent, bg='#0f1419')
        controls.pack(pady=15)
        
        self.start_btn = tk.Button(controls, text="▶️ START BOT", command=self.start_bot,
                                   bg='#00ba7c', fg='white', font=('Segoe UI', 18, 'bold'),
                                   relief='flat', cursor='hand2', padx=60, pady=18)
        self.start_btn.pack(side='left', padx=10)
        
        self.stop_btn = tk.Button(controls, text="⏹️ STOP BOT", command=self.stop_bot,
                                  bg='#f4212e', fg='white', font=('Segoe UI', 18, 'bold'),
                                  relief='flat', cursor='hand2', padx=60, pady=18, state='disabled')
        self.stop_btn.pack(side='left', padx=10)
    
    def create_log(self, parent):
        log_frame = tk.Frame(parent, bg='#16181c', highlightbackground='#2f3336', highlightthickness=1)
        log_frame.pack(fill='both', expand=True)
        
        tk.Label(log_frame, text="📋 Live Activity", bg='#16181c', fg='#e7e9ea',
                font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=15, pady=8)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD,
                                                  bg='#0f1419', fg='#e7e9ea',
                                                  font=('Consolas', 9), relief='flat')
        self.log_text.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        self.log_message("🔥 X List Rage Bot - Ready to dominate")
        self.log_message("🎯 Mission: 1000 critical replies per day")
        self.log_message("⚡ Working exclusively with your 3 X lists")
        self.log_message("🤖 100% Groq AI - NO template fallbacks")
    
    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def update_stats(self):
        stats = self.db.get_stats()
        target = self.config['targets']['replies_per_day']
        
        self.today_label.config(text=f"{stats['today_replies']}/{target}")
        self.authors_label.config(text=str(stats['unique_authors']))
        self.total_label.config(text=str(stats['total_all_time']))
        
        # Change color if target reached
        if stats['today_replies'] >= target:
            self.today_label.config(fg='#00ba7c')
        
        self.root.after(3000, self.update_stats)
    
    def save_config(self):
        self.config['targets']['rest_duration_seconds'] = int(self.rest_duration.get())
        self.config['targets']['replies_per_day'] = int(self.target_replies.get())
        ConfigManager.save(self.config)
        self.log_message("✅ Settings saved!")
        messagebox.showinfo("Success", "Configuration saved!")
    
    def start_bot(self):
        self.save_config()
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        self.bot = XListBot(callback=self.log_message)
        self.bot_thread = threading.Thread(target=self.bot.run, args=(self.config,), daemon=True)
        self.bot_thread.start()
        
        self.log_message("🚀 BOT LAUNCHED! Browser opening...")
        self.log_message("⚡ Starting rage bait campaign on your lists...")
    
    def stop_bot(self):
        if self.bot:
            self.log_message("🛑 Stopping bot...")
            self.bot.stop()
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernGUI(root)
    root.mainloop()