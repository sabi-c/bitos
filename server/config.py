"""BITOS Server Config: environment-backed settings."""
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "claude-sonnet-4-6")
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8000"))
UI_SETTINGS_FILE = os.environ.get("UI_SETTINGS_FILE", "server/data/ui_settings.json")
