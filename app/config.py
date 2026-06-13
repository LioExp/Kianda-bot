import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kiandabot.db")

GREEN_API_INSTANCE_ID = os.getenv("GREEN_API_INSTANCE_ID", "")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN", "")
GREEN_API_URL = os.getenv("GREEN_API_URL", "https://api.greenapi.com")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

ADMIN_PHONE = "244924641157"
DASHBOARD_KEY = os.getenv("DASHBOARD_KEY", "kianda2026")

COMMISSION_GROUP_RATE = 0.05
COMMISSION_PLATFORM_RATE = 0.05
COMMISSION_VENDOR_RATE = 1 - COMMISSION_GROUP_RATE - COMMISSION_PLATFORM_RATE

FREE_TRIAL_DAYS = 30

DEFAULT_POST_HOURS = [7, 11, 17, 20]
