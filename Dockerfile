# Gunakan image Playwright resmi yang sudah memiliki Chromium & dependensinya
FROM mcr.microsoft.com/playwright/python:v1.41.2-jammy

# Set working directory
WORKDIR /app

# Copy requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy sisa file proyek
COPY . .

# Jalankan Bot Telegram
CMD ["python", "telegram_bot.py"]
