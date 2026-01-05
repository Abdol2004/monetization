# 🚀 QUICKSTART GUIDE

## Start the App (EASIEST METHOD)

**Just double-click: `start.bat`**

That's it! The script will:
1. Install all dependencies
2. Test MongoDB connection
3. Start the server at http://localhost:5000

## Using the App

1. **Go to**: http://localhost:5000
2. **Register**: Create account with username/email/password
3. **Upgrade**: Click "Upgrade to Premium" (free for now)
4. **Configure**: Set your targets and lists
5. **Start Bot**: Click "START BOT"
6. **Login to X**: A new tab opens - login manually
7. **Monitor**: Watch live logs in dashboard

## Troubleshooting

**MongoDB connection fails?**
- Check your `.env` file has correct MONGODB_URI
- Run: `pip install --upgrade certifi pymongo`
- Your current MongoDB is already configured!

**Port 5000 in use?**
- Change PORT in `.env` to 5001 or 8000
- Restart the app

**Chrome not found?**
- Install Google Chrome from https://www.google.com/chrome/

## Deploy to Render

1. Push code to GitHub
2. Go to https://render.com
3. Create "New Web Service"
4. Connect your repo
5. Add environment variables from `.env`
6. Deploy!

## Current Status

✅ MongoDB: Connected
✅ Flask: Ready
✅ Templates: Created
✅ Bot: Ready
✅ SSL: Fixed for Python 3.13

**Everything is ready to go!**
