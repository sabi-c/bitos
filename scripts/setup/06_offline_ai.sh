#!/bin/bash
set -euo pipefail
# Optional: run this to enable offline TTS + STT
# Takes ~10 min and ~500MB of disk space

MODELS_DIR="$HOME/bitos/models"
mkdir -p "$MODELS_DIR/tts" "$MODELS_DIR/stt"

echo "[1/3] Installing Piper TTS..."
pip install piper-tts --break-system-packages -q

echo "[2/3] Downloading Piper voice model (63MB)..."
python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='rhasspy/piper-voices',
    filename='en/en_US/lessac/medium/en_US-lessac-medium.onnx',
    local_dir='$MODELS_DIR/tts'
)
hf_hub_download(
    repo_id='rhasspy/piper-voices',
    filename='en/en_US/lessac/medium/en_US-lessac-medium.onnx.json',
    local_dir='$MODELS_DIR/tts'
)
" 2>/dev/null || \
wget -q -P "$MODELS_DIR/tts" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

echo "[3/3] Building whisper.cpp for local STT..."
cd /tmp
git clone --depth=1 https://github.com/ggerganov/whisper.cpp
cd whisper.cpp && make -j4
bash models/download-ggml-model.sh tiny.en
cp main "$MODELS_DIR/stt/whisper-cpp"
cp models/ggml-tiny.en.bin "$MODELS_DIR/stt/"

echo "Offline AI ready."
echo "Set BITOS_WAKE_WORD=on to enable wake word (pip install openwakeword)"
