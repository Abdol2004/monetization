"""
Fix SSL certificate issues for Python 3.13 and MongoDB Atlas
Run this if you're still having SSL connection issues
"""
import ssl
import certifi

# Install certifi certificates
print("Installing SSL certificates...")
print(f"Using certifi bundle: {certifi.where()}")

# Test SSL context
try:
    context = ssl.create_default_context(cafile=certifi.where())
    print("✅ SSL context created successfully")
except Exception as e:
    print(f"❌ SSL context creation failed: {e}")

print("\nIf MongoDB connection still fails, try:")
print("1. pip install --upgrade certifi")
print("2. pip install --upgrade pymongo")
print("3. Restart your terminal/IDE")
