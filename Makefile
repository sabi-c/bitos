.PHONY: dev-server dev-device dev-preview dev-both install ssh-pi logs db-web vnc push deploy ship

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
	ssh pi@bitos "journalctl -u bitos -f --output=cat"

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
	ssh pi@bitos "sudo systemctl restart bitos"

ship: push deploy logs

shutdown-pi:
	ssh pi@bitos "sudo systemctl stop bitos"

reboot-pi:
	ssh pi@bitos "sudo reboot"
