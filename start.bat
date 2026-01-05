@echo off
cls
echo ========================================
echo   X Monetization Bot - Starting Server
echo ========================================
echo.
echo [1/3] Installing/Upgrading dependencies...
pip install --upgrade certifi pymongo dnspython python-dotenv -q
pip install -r requirements.txt -q
echo.
echo [2/3] Testing MongoDB connection...
python -c "from pymongo import MongoClient; import certifi; import os; from dotenv import load_dotenv; load_dotenv(); uri = os.getenv('MONGODB_URI'); client = MongoClient(uri, tls=True, tlsAllowInvalidCertificates=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000); client.admin.command('ping'); print('MongoDB connected successfully!')"
if errorlevel 1 (
    echo WARNING: MongoDB connection failed - check your .env file
    echo.
)
echo.
echo [3/3] Starting Flask server...
echo ========================================
echo.
echo   APP RUNNING AT: http://localhost:5000
echo.
echo   Press Ctrl+C to stop the server
echo ========================================
echo.
python app.py
pause
