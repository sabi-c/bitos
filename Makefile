.PHONY: dev-server dev-device dev-preview dev-both run-dev run-server run-both verify-hw run-pi run-pi-server install ssh ssh-pi start stop restart status logs logs-device logs-server db-web vnc push deploy ship setup-offline-ai flash mac-setup mac-start mac-stop mac-restart mac-logs mac-logs-error mac-status mac-uninstall setup help push-secrets mac-update pi-update update-all

install:
	pip install -r requirements.txt

dev-server:
	cd server && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-device:
	cd device && python main.py

dev-preview:
	python web_preview/server.py

dev-both:
	@echo "Starting server and device..."
	@make dev-server &
	@sleep 2
	@make dev-device

# Remote access shortcuts
ssh-pi:
	ssh pi@bitos

logs:
	ssh pi@bitos "journalctl -u bitos-server -u bitos-device -f --no-pager -n 50"

start:
	ssh pi@bitos "sudo systemctl start bitos-server bitos-device"

stop:
	ssh pi@bitos "sudo systemctl stop bitos-device bitos-server"

restart:
	ssh pi@bitos "sudo systemctl restart bitos-server && sleep 3 && sudo systemctl restart bitos-device"

status:
	ssh pi@bitos "systemctl status bitos-server bitos-device --no-pager"

logs-device:
	ssh pi@bitos "journalctl -u bitos-device -f --no-pager"

logs-server:
	ssh pi@bitos "journalctl -u bitos-server -f --no-pager"

db-web:
	ssh pi@bitos "sqlite_web ~/bitos/server/bitos.db \
	    --port 8080 --host 0.0.0.0 &"

vnc:
	@echo "Connect VNC client to bitos:5900"
	ssh pi@bitos "x11vnc -display :0 -forever -rfbport 5900 &"

push:
	rsync -av --exclude __pycache__ --exclude .git \
	    device/ pi@bitos:~/bitos/device/
	rsync -av --exclude __pycache__ --exclude .git \
	    server/ pi@bitos:~/bitos/server/

deploy: push
	ssh pi@bitos "sudo systemctl restart bitos-server && sleep 3 && sudo systemctl restart bitos-device"

ship: push deploy logs


run-dev:
	BITOS_DISPLAY=pygame \
	BITOS_AUDIO=mock \
	BITOS_BUTTON=keyboard \
	BITOS_WIFI=mock \
	BITOS_BLUETOOTH=mock \
	bash -lc "if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi; python device/main.py"

run-server:
	bash -lc "if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi; PYTHONPATH=server uvicorn server.main:app --reload --port 8000"

run-both:
	make -j2 run-server run-dev


verify-hw:
	python scripts/verify_hardware.py

smoke-test:
	@ssh pi@bitos 'cd ~/bitos && bash scripts/smoke_test.sh'

run-pi:
	BITOS_DISPLAY=st7789 \
	BITOS_AUDIO=hw:0 \
	BITOS_BUTTON=gpio \
	bash -lc "source .venv/bin/activate && source /etc/bitos/secrets && python device/main.py"

run-pi-server:
	bash -lc "source .venv/bin/activate && source /etc/bitos/secrets && uvicorn server.main:app --host 0.0.0.0 --port 8000"


setup-offline-ai:
	ssh pi@bitos "bash ~/bitos/scripts/setup/06_offline_ai.sh"
ssh: ssh-pi

flash:
	@bash scripts/flash_sd.sh


# Mac mini management
mac-setup:
	@bash scripts/mac_setup.sh

mac-start:
	@launchctl load \
	  ~/Library/LaunchAgents/com.bitos.server.plist
	@echo "BITOS server starting..."

mac-stop:
	@launchctl unload \
	  ~/Library/LaunchAgents/com.bitos.server.plist
	@echo "BITOS server stopped"

mac-restart:
	@launchctl unload \
	  ~/Library/LaunchAgents/com.bitos.server.plist \
	  2>/dev/null || true
	@sleep 1
	@launchctl load \
	  ~/Library/LaunchAgents/com.bitos.server.plist
	@echo "BITOS server restarted"

mac-logs:
	@tail -f ~/.bitos/logs/bitos-server.log

mac-logs-error:
	@tail -f ~/.bitos/logs/bitos-server-error.log

mac-status:
	@echo "=== BITOS Server ===" && \
	 curl -sf http://localhost:8000/health | python3 -m json.tool \
	 || echo "OFFLINE" && \
	 echo "" && \
	 echo "=== Vikunja ===" && \
	 curl -sf http://localhost:3456/api/v1/info \
	 | python3 -m json.tool 2>/dev/null || echo "OFFLINE"

mac-uninstall:
	@launchctl unload \
	  ~/Library/LaunchAgents/com.bitos.server.plist \
	  2>/dev/null || true
	@rm -f ~/Library/LaunchAgents/com.bitos.server.plist
	@docker compose -f ~/.bitos/vikunja/docker-compose.yml \
	  down 2>/dev/null || true
	@echo "BITOS Mac services removed"


setup:
	@bash scripts/setup_everything.sh

# Alias for quick reference
help:
	@echo "BITOS — Quick Commands"
	@echo "────────────────────────────────────"
	@echo "FIRST TIME:"
	@echo "  make setup          full setup (Mac + SD card)"
	@echo "  make flash          SD card only"
	@echo "  make push-secrets   connect Pi to this Mac"
	@echo ""
	@echo "DAILY:"
	@echo "  make mac-status     check everything running"
	@echo "  make mac-update     update Mac server code"
	@echo "  make pi-update      update Pi code"
	@echo "  make logs           live Mac server logs"
	@echo "  make logs-device    live Pi device logs (SSH)"
	@echo ""
	@echo "IF BROKEN:"
	@echo "  make mac-restart    restart Mac server"
	@echo "  make ssh            SSH into Pi"
	@echo "  make verify-hw      Pi hardware check"
	@echo "────────────────────────────────────"

push-secrets:
	@SERVER_URL=$$(grep '^SERVER_URL=' .env 2>/dev/null | cut -d= -f2-); \
	if [ -z "$$SERVER_URL" ]; then \
	  echo "SERVER_URL missing in .env"; exit 1; \
	fi; \
	ssh pi@bitos "sudo mkdir -p /etc/bitos && sudo sh -c 'grep -v ^SERVER_URL= /etc/bitos/secrets 2>/dev/null; echo SERVER_URL=$$SERVER_URL' > /tmp/bitos_secrets && sudo mv /tmp/bitos_secrets /etc/bitos/secrets"
	@echo "Pi secrets updated with SERVER_URL"

mac-update:
	@git pull --rebase
	@make mac-restart
	@echo "Mac updated ✓"

pi-update:
	@ssh pi@bitos "bash ~/bitos/scripts/ota_update.sh"
	@echo "Pi updated ✓"

update-all:
	@make mac-update
	@make pi-update
	@echo "Both updated ✓"
