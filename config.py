from dotenv import load_dotenv
import os

load_dotenv()

HOST_PORT = int(os.getenv("HOST_PORT", 5001))
APP_PORT = 5000

TEMPERATURE = float(os.getenv("TEMPERATURE", 0.8))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 10000))

ENABLE_THINKING = os.getenv("ENABLE_THINKING", "true").lower() == "true"
DISPLAY_THINKING = os.getenv("DISPLAY_THINKING", "false").lower() == "true"

ENABLE_NSFW = os.getenv("ENABLE_NSFW", "true").lower() == "true"
ENABLE_GOOGLE_SEARCH = os.getenv("ENABLE_GOOGLE_SEARCH", "false").lower() == "true"

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 300))
MAX_PARALLEL_REQUESTS = int(os.getenv("MAX_PARALLEL_REQUESTS", 4))
RETRY_COUNT = int(os.getenv("RETRY_COUNT", 3))

NGROK_TOKEN = os.getenv("NGROK_TOKEN", "")
