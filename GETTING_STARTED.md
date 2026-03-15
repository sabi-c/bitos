# Getting Started

## Mac Mini Setup (backend brain)

The Mac mini runs the AI server, task management,
and bridges to iMessage, Gmail, and calendar.

### One-command setup
```bash
git clone git@github.com:sabi-c/bitos.git
cd bitos
make setup
```

This installs:
- BITOS FastAPI server (auto-starts on login)
- Vikunja task manager (Docker, port 3456)
- Checks for BlueBubbles + Tailscale
- Prepares Pi SD cloud-init files in the same session
- Runs smoke test to confirm everything works

### After setup
Then run `make push-secrets` to point your Pi to this Mac mini.

- `make mac-status` check everything is running
- `make mac-logs` watch server logs
- `make mac-restart` apply `.env` changes

### Connecting the Pi
The Pi needs to know your Mac mini's address.
On Pi: `sudo nano /etc/bitos/secrets`
Set: `SERVER_URL=http://<tailscale-ip>:8000`

With Tailscale: `mac_setup.sh` sets this automatically.
