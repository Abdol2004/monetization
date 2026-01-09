"""
AI Reply Generator - Groq API Only (No Templates)
"""

import requests
import re

class AIReplyGenerator:
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    def detect_language(self, text):
        """Detect if text is Chinese or English"""
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        return 'chinese' if len(chinese_chars) > 3 else 'english'

    def generate_reply(self, tweet_text, author):
        """Generate AI reply using Groq API only"""
        language = self.detect_language(tweet_text)
        return self.generate_with_ai(tweet_text, author, language)

    def generate_with_ai(self, tweet_text, author, language='english'):
        """Call Groq API to generate controversial reply"""
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
                # Remove hashtags
                reply = ' '.join([w for w in reply.split() if not w.startswith('#')])
                # Remove quotes
                reply = reply.strip('"\'')
                return reply[:280]
            else:
                # If API fails, return None instead of template fallback
                print(f"❌ Groq API Error: Status {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ AI Error: {str(e)}")
            # Return None instead of template fallback
            return None
