.PHONY: dev-server dev-device dev-preview dev-both run-dev run-server run-both verify-hw run-pi run-pi-server install ssh ssh-pi start stop restart status logs logs-device logs-server check-install db-web vnc push deploy ship setup-offline-ai

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

check-install:
	@echo "Checking install.sh references..."
	@grep -n "bitos\.service\b" scripts/install.sh && \
	  echo "WARNING: old service name found" || \
	  echo "OK: no old bitos.service references"
	@grep -n "bitos-server\|bitos-device" \
	  scripts/install.sh | head -5
	@echo "Service setup looks correct"

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
