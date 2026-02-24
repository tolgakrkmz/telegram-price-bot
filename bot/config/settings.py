import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPER_API_KEY = os.getenv("SUPER_API_KEY")
SUPER_API_BASE = os.getenv("SUPER_API_BASE")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set")
if not SUPER_API_KEY:
    raise RuntimeError("SUPER_API_KEY is not set")
if not SUPER_API_BASE:
    raise RuntimeError("SUPER_API_BASE is not set")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
