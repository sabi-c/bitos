"""BITOS Server Config: environment-backed settings."""
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "claude-sonnet-4-6")
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8000"))
UI_SETTINGS_FILE = os.environ.get("UI_SETTINGS_FILE", "server/data/ui_settings.json")

# LLM bridge/provider selection
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
SYSTEM_PROMPT = os.environ.get(
    "BITOS_SYSTEM_PROMPT",
    "You are BITOS, a helpful pocket AI companion. Keep responses concise — you're rendering on a tiny 240×280 pixel screen. Be direct and useful.",
)

# OpenAI-compatible providers
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

OPENCLAW_API_KEY = os.environ.get("OPENCLAW_API_KEY", "")
OPENCLAW_BASE_URL = os.environ.get("OPENCLAW_BASE_URL", "https://api.openclaw.example/v1")
OPENCLAW_MODEL = os.environ.get("OPENCLAW_MODEL", "openclaw-default")

NANOCLAW_API_KEY = os.environ.get("NANOCLAW_API_KEY", "")
NANOCLAW_BASE_URL = os.environ.get("NANOCLAW_BASE_URL", "https://api.nanoclaw.example/v1")
NANOCLAW_MODEL = os.environ.get("NANOCLAW_MODEL", "nanoclaw-default")

# Spotify integration
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8000/callback/spotify")
