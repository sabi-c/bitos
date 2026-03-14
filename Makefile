.PHONY: dev-server dev-device dev-preview dev-both install

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
