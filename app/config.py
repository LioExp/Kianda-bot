import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kiandabot.db")
GREEN_API_INSTANCE_ID = os.getenv("GREEN_API_INSTANCE_ID", "")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
GREEN_API_URL = os.getenv("GREEN_API_URL", "https://api.green-api.com")

COMMISSION_GROUP_RATE = 0.05
COMMISSION_PLATFORM_RATE = 0.05