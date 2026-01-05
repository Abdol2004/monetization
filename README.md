# X Monetization Bot - Web Application

A web-based Twitter/X automation bot with user authentication and premium features.

## Features

- 🔐 User authentication system (login/register)
- 👑 Premium user management
- 🤖 Automated tweet replies with AI-powered rage bait generation
- 📊 Real-time statistics dashboard
- ☁️ Cloud deployment ready (Render)
- 🗄️ MongoDB database integration
- 🔄 Live activity logs with WebSocket
- 🎯 Customizable targeting and engagement settings

## Setup Instructions

### 1. MongoDB Setup

1. Create a free MongoDB Atlas account at https://www.mongodb.com/cloud/atlas
2. Create a new cluster
3. Get your connection string (it looks like: `mongodb+srv://username:password@cluster.mongodb.net/`)
4. Replace `<password>` with your actual password in the connection string

### 2. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your:
# - MongoDB URI
# - Secret key (random string)
# - Grok API key (from https://console.groq.com)

# Run the application
python app.py
```

Visit http://localhost:5000

### 3. Deploy to Render

#### Option A: Using Render Dashboard

1. Create account at https://render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app`
5. Add Environment Variables:
   - `MONGODB_URI` - Your MongoDB connection string
   - `SECRET_KEY` - Random secret string
   - `GROK_API_KEY` - Your Groq API key
6. Click "Create Web Service"

#### Option B: Using render.yaml

1. Push your code to GitHub
2. In Render dashboard, click "New +" → "Blueprint"
3. Connect your repository
4. Render will automatically detect `render.yaml`
5. Add your environment variables
6. Deploy!

### 4. Install Chrome/Chromium on Render

The bot needs Chrome for Selenium. Add this to your render.yaml build command or add a custom Dockerfile.

For Render, you may need to use a Docker container. Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app
```

## Usage

1. **Register**: Create an account at `/register`
2. **Login**: Login at `/login`
3. **Upgrade to Premium**: Click "Upgrade to Premium" (currently free for testing)
4. **Configure Bot**: Set your targets and lists in the dashboard
5. **Start Bot**: Click "START BOT"
6. **Login to X/Twitter**: A new tab will open - login to your Twitter account
7. **Bot Runs**: The bot will work in the background even if you minimize the browser
8. **Monitor**: Watch real-time logs and statistics

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb+srv://user:pass@cluster.mongodb.net/db` |
| `SECRET_KEY` | Flask secret key | Any random string |
| `GROK_API_KEY` | Groq API key for AI | `gsk_...` |
| `PORT` | Server port (auto-set by Render) | `5000` |

## How It Works

1. User registers and logs in via web interface
2. Premium users can access the bot dashboard
3. Users configure targeting settings (lists, reply targets, etc.)
4. When "START BOT" is clicked:
   - Bot opens Twitter login in new tab
   - User logs in manually
   - Bot runs in headless mode in background
   - Real-time logs stream to dashboard via WebSocket
5. Bot works even when browser is minimized
6. All data stored in MongoDB

## API Endpoints

- `POST /register` - Create new user
- `POST /login` - Login user
- `GET /dashboard` - Main dashboard (requires login + premium)
- `POST /api/bot/start` - Start bot
- `POST /api/bot/stop` - Stop bot
- `GET /api/stats` - Get current statistics
- `POST /api/config` - Save configuration

## Tech Stack

- **Backend**: Flask, Flask-SocketIO, Flask-Login
- **Database**: MongoDB (via PyMongo)
- **Automation**: Selenium WebDriver
- **AI**: Groq API (Llama 3.3 70B)
- **Frontend**: Vanilla JavaScript, Socket.io
- **Deployment**: Render (or any cloud platform)

## Security Notes

- Passwords are hashed with Werkzeug
- Sessions managed with Flask-Login
- MongoDB credentials in environment variables
- Secret key for session encryption

## Troubleshooting

**Bot won't start on Render:**
- Make sure Chrome is installed (use Dockerfile)
- Check environment variables are set
- View logs in Render dashboard

**Can't connect to MongoDB:**
- Whitelist all IPs (0.0.0.0/0) in MongoDB Atlas
- Check connection string format
- Verify username/password

**Selenium errors:**
- Ensure Chrome/Chromium is installed
- Use headless mode (already configured)
- Check Render logs for browser errors

## License

MIT License - Use at your own risk
