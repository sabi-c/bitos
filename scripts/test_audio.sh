#!/bin/bash
set -e

echo "Recording 3 seconds..."
arecord -D hw:0,0 -f S16_LE -r 48000 -c 2 -d 3 /tmp/test_rec.wav

echo "Playback..."
aplay -D hw:0,0 /tmp/test_rec.wav

echo "Audio test PASS ✓"
