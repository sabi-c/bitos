#!/bin/bash
set -e

echo "=== BITOS VOICE LOOP TEST ==="
echo ""

echo "Step 1: Testing server health..."
curl -sf http://localhost:8000/health && echo "✓ Server healthy" || { echo "✗ Server down"; exit 1; }

echo ""
echo "Step 2: Testing audio record (3 seconds)..."
arecord -D hw:0,0 -f S16_LE -r 48000 -c 2 -d 3 /tmp/voice_test.wav && echo "✓ Recorded" || { echo "✗ Record failed"; exit 1; }

echo ""
echo "Step 3: Testing audio playback..."
aplay -D hw:0,0 /tmp/voice_test.wav && echo "✓ Playback worked" || { echo "✗ Playback failed"; exit 1; }

echo ""
echo "Step 4: Testing Claude API..."
python3 -c "
import anthropic, os
key = None
with open('/etc/bitos/secrets') as f:
    for line in f:
        if line.startswith('ANTHROPIC_API_KEY='):
            key = line.split('=',1)[1].strip()
if not key or 'sk-ant' not in key:
    print('✗ No real API key found')
    exit(1)
client = anthropic.Anthropic(api_key=key)
r = client.messages.create(model='claude-haiku-4-5-20251001', max_tokens=50, messages=[{'role':'user','content':'say ok'}])
print('✓ Claude API working:', r.content[0].text[:30])
" || { echo "✗ Claude API failed"; exit 1; }

echo ""
echo "=== VOICE LOOP READY ==="
