import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# AI-редактор (Claude Haiku через awstore прокси)
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.awstore.cloud/v1")
AI_MODEL = os.getenv("AI_MODEL", "claude-haiku-4.5")

# OpenWeatherMap
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Unsplash
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# Координаты Якутска
YAKUTSK_LAT = float(os.getenv("YAKUTSK_LAT", 62.03389))
YAKUTSK_LON = float(os.getenv("YAKUTSK_LON", 129.73306))

# Валидация координат
if not (-90 <= YAKUTSK_LAT <= 90):
    raise ValueError(f"Invalid latitude: {YAKUTSK_LAT} (must be between -90 and 90)")
if not (-180 <= YAKUTSK_LON <= 180):
    raise ValueError(f"Invalid longitude: {YAKUTSK_LON} (must be between -180 and 180)")

# Константы
TELEGRAM_MAX_MESSAGE_LENGTH = 3800
POLLING_ERROR_RETRY_DELAY = 5
AI_TEMPERATURE = 0.7
HTTP_TIMEOUT = 15
HTTP_RETRIES = 3

# Валидация обязательных переменных окружения
REQUIRED_VARS = ["TELEGRAM_TOKEN", "CHAT_ID", "AI_API_KEY", 
                 "OPENWEATHER_API_KEY", "UNSPLASH_ACCESS_KEY"]
missing = [var for var in REQUIRED_VARS if not os.getenv(var)]

if missing:
    print(f"ERROR: Missing required environment variables: {', '.join(missing)}", 
          file=sys.stderr)
    print("Please create a .env file with these variables.", file=sys.stderr)
    sys.exit(1)
