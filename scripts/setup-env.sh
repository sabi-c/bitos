#!/bin/bash
# BITOS .env setup — run on Pi via Pi Connect or SSH
# Creates .env from template with your API keys

set -e
cd "$(dirname "$0")/.."

echo "=== BITOS Environment Setup ==="
echo ""

# Start from template if no .env exists
if [ ! -f .env ]; then
    if [ -f .env.template ]; then
        cp .env.template .env
        echo "Created .env from template"
    else
        echo "ERROR: .env.template not found"
        exit 1
    fi
else
    echo "Existing .env found — will update values"
fi

echo ""
echo "-- Voice Transcription (cloud STT) --"
echo "Get a free Groq key at: https://console.groq.com"
echo "Or use your OpenAI key as fallback"
echo ""

read -p "Groq API key (gsk_...): " GROQ_KEY
read -p "OpenAI API key (sk-... or blank to skip): " OPENAI_KEY

echo ""
echo "-- Server Connection --"
read -p "Server URL [http://localhost:8000]: " SERVER_URL
SERVER_URL=${SERVER_URL:-http://localhost:8000}

read -p "Anthropic API key (sk-ant-...): " ANTHROPIC_KEY

# Function to set a key in .env (update if exists, append if not)
set_env() {
    local key="$1" val="$2"
    if [ -z "$val" ]; then return; fi
    if grep -q "^${key}=" .env 2>/dev/null; then
        # Use a temp file for portable sed
        sed "s|^${key}=.*|${key}=${val}|" .env > .env.tmp && mv .env.tmp .env
    else
        echo "${key}=${val}" >> .env
    fi
}

# Set the values
set_env "GROQ_API_KEY" "$GROQ_KEY"
set_env "OPENAI_API_KEY" "$OPENAI_KEY"
set_env "ANTHROPIC_API_KEY" "$ANTHROPIC_KEY"
set_env "SERVER_URL" "$SERVER_URL"
set_env "BITOS_SERVER_URL" "$SERVER_URL"

# Hardware defaults for Pi
set_env "BITOS_AUDIO" "hw:0"
set_env "BITOS_DISPLAY" "st7789"
set_env "BITOS_BUTTON" "gpio"
set_env "BITOS_BATTERY" "pisugar"

echo ""
echo "=== .env configured ==="
echo ""
echo "Audio:  hw:0 (WM8960 mic + speaker)"
echo "STT:    $([ -n "$GROQ_KEY" ] && echo 'Groq (primary)' || echo 'skipped') $([ -n "$OPENAI_KEY" ] && echo '+ OpenAI (fallback)' || echo '')"
echo "Server: $SERVER_URL"
echo ""
echo "Restart BITOS to apply:"
echo "  sudo systemctl restart bitos"
echo ""
