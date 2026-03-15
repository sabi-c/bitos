#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT="/tmp/bitos_audio_smoke.wav"
rm -f "$OUT"

printf '== Audio smoke test ==\n'

python - <<'PY'
from device.audio.recorder import AudioRecorder

out = "/tmp/bitos_audio_smoke.wav"
try:
    AudioRecorder().record_to_wav(out, seconds=3.0)
    print("RECORD: PASS")
except Exception as exc:
    print(f"RECORD: FAIL ({exc})")
    raise
PY

python - <<'PY'
from device.audio.player import AudioPlayer

out = "/tmp/bitos_audio_smoke.wav"
try:
    ok = AudioPlayer().play_file(out)
    print("PLAYBACK: PASS" if ok else "PLAYBACK: FAIL")
    if not ok:
        raise SystemExit(1)
except Exception as exc:
    print(f"PLAYBACK: FAIL ({exc})")
    raise
PY
