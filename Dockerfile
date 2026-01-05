FROM python:3.11-slim

# Note: Chrome/Selenium not needed on server - bot runs on user's PC via desktop client
# Install only basic dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Run the application
CMD gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app
