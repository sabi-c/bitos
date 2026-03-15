#!/bin/bash

echo "=== Voice Loop Test ==="
echo "Recording 3s..."
arecord -D hw:0,0 -f S16_LE -r 48000 -c 2 -d 3 /tmp/test_rec.wav
if [ ! -s /tmp/test_rec.wav ]; then
    echo "FAIL: no audio recorded"
    exit 1
fi
echo "OK: recorded $(wc -c < /tmp/test_rec.wav) bytes"
echo "Playing back..."
aplay -D hw:0,0 -f S16_LE -r 48000 -c 2 /tmp/test_rec.wav
echo "PASS: voice loop complete"
