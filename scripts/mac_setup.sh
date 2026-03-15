#!/bin/bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS MAC MINI SETUP"
echo "  Sets up the backend brain for your device"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── STEP 1: Prerequisites check ──
echo "[1/8] Checking prerequisites..."

command -v brew >/dev/null 2>&1 || {
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
}

command -v python3 >/dev/null 2>&1 || brew install python3
command -v node >/dev/null 2>&1 || brew install node
command -v docker >/dev/null 2>&1 || {
    echo "Docker not found. Install Docker Desktop from:"
    echo "  https://www.docker.com/products/docker-desktop/"
    echo "Then re-run this script."
    exit 1
}

echo "  ✓ Prerequisites OK"

# ── STEP 2: Python environment ──
echo "[2/8] Setting up Python environment..."
cd "$(dirname "$0")/.."
REPO_DIR="$(pwd)"

python3 -m venv .venv-mac
source .venv-mac/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -r requirements-server.txt -q
echo "  ✓ Python environment ready"

# ── STEP 3: Environment config ──
echo "[3/8] Configuring environment..."
if [ ! -f ".env" ]; then
    cp .env.template .env
    echo ""
    echo "  ⚠ Created .env from template."
    echo "  Add your Anthropic API key:"
    echo "  nano .env"
    echo "  → Set ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
    read -p "  Press ENTER after adding your API key..."
fi

# Verify API key is set
if grep -q "ANTHROPIC_API_KEY=sk-ant-" .env 2>/dev/null; then
    echo "  ✓ API key configured"
else
    echo "  ✗ ANTHROPIC_API_KEY not set in .env"
    echo "  Edit .env and add: ANTHROPIC_API_KEY=sk-ant-..."
    exit 1
fi

# ── STEP 4: Vikunja (task management) ──
echo "[4/8] Setting up Vikunja (task management)..."
VIKUNJA_DIR="$HOME/.bitos/vikunja"
mkdir -p "$VIKUNJA_DIR"

if ! docker ps 2>/dev/null | grep -q vikunja; then
    cat > "$VIKUNJA_DIR/docker-compose.yml" << 'YAML'
version: '3'
services:
  vikunja:
    image: vikunja/vikunja
    environment:
      VIKUNJA_SERVICE_JWTSECRET: "bitos-vikunja-secret-change-me"
      VIKUNJA_SERVICE_FRONTENDURL: "http://localhost:3456"
    ports:
      - "3456:3456"
    volumes:
      - vikunja_data:/app/vikunja/files
    restart: unless-stopped
volumes:
  vikunja_data:
YAML
    docker compose -f "$VIKUNJA_DIR/docker-compose.yml" up -d
    echo "  ✓ Vikunja starting at http://localhost:3456"
    echo "  → Visit http://localhost:3456 to create your account"
    echo "  → Then: Settings → API Tokens → create token"
    echo "  → Add to .env: VIKUNJA_API_TOKEN=your-token"
else
    echo "  ✓ Vikunja already running"
fi

# ── STEP 5: BlueBubbles check ──
echo "[5/8] Checking BlueBubbles (iMessage)..."
if curl -sf "http://localhost:1234/api/v1/ping?password=test" >/dev/null 2>&1; then
    echo "  ✓ BlueBubbles running at localhost:1234"
else
    echo "  ⚠ BlueBubbles not detected."
    echo "  Download and install from:"
    echo "  https://bluebubbles.app/"
    echo ""
    echo "  After installing:"
    echo "  1. Grant Full Disk Access + Accessibility permissions"
    echo "  2. Set a password in BlueBubbles settings"
    echo "  3. Add to .env: BLUEBUBBLES_BASE_URL=http://localhost:1234"
    echo "  4. Add to .env: BLUEBUBBLES_PASSWORD=your-password"
    echo "  5. Add to .env: IMSG_ENABLED=true"
    echo ""
    echo "  (Continuing setup — iMessage will work once configured)"
fi

# ── STEP 6: Tailscale check ──
echo "[6/8] Checking Tailscale..."
if command -v tailscale >/dev/null 2>&1; then
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
    if [ -n "$TAILSCALE_IP" ]; then
        echo "  ✓ Tailscale running: $TAILSCALE_IP"
        sed -i '' "s|SERVER_URL=.*|SERVER_URL=http://$TAILSCALE_IP:8000|g" .env 2>/dev/null || true
        echo "  ✓ Updated SERVER_URL to http://$TAILSCALE_IP:8000"
    else
        echo "  ⚠ Tailscale installed but not connected"
        echo "  Run: tailscale up"
    fi
else
    echo "  ⚠ Tailscale not installed."
    echo "  Install from: https://tailscale.com/download"
    echo "  (Recommended: Pi needs to reach this Mac)"
fi

# ── STEP 7: BITOS server as launchd service ──
echo "[7/8] Installing BITOS server as Mac service..."
PLIST="$HOME/Library/LaunchAgents/com.bitos.server.plist"
VENV_PYTHON="$REPO_DIR/.venv-mac/bin/python"
LOG_DIR="$HOME/.bitos/logs"
mkdir -p "$LOG_DIR"

cat > "$PLIST" << PLIST_XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.bitos.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_PYTHON</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>server.main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$REPO_DIR/server</string>
    </dict>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/bitos-server.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/bitos-server-error.log</string>
</dict>
</plist>
PLIST_XML

while IFS='=' read -r key value; do
    [[ "$key" =~ ^#.*$ ]] && continue
    [[ -z "$key" ]] && continue
    /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:$key string $value" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:$key $value" "$PLIST" 2>/dev/null || true
done < .env

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
sleep 2

if curl -sf "http://localhost:8000/health" >/dev/null 2>&1; then
    echo "  ✓ BITOS server running at http://localhost:8000"
else
    echo "  ✗ Server failed to start"
    echo "  Check logs: tail $LOG_DIR/bitos-server-error.log"
    exit 1
fi

# ── STEP 8: Smoke test ──
echo "[8/8] Running smoke test..."
python scripts/smoke_test.py || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS MAC MINI READY"
echo ""
echo "  Server:    http://localhost:8000"
echo "  Vikunja:   http://localhost:3456"
echo ""
echo "  Next steps:"
echo "  1. Visit http://localhost:3456"
echo "     → Create account + get API token"
echo "     → Add VIKUNJA_API_TOKEN to .env"
echo ""
echo "  2. Install BlueBubbles (iMessage)"
echo "     → https://bluebubbles.app/"
echo "     → Add credentials to .env"
echo ""
echo "  3. Enable Gmail"
echo "     → Set GMAIL_ENABLED=true in .env"
echo ""
echo "  4. After .env changes:"
echo "     make mac-restart"
echo ""
echo "  Pi device connects via SERVER_URL in its secrets."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
