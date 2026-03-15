#!/bin/bash
# Set WM8960 mixer levels for BITOS — uses cset (raw ALSA controls)
set -e
CARD="-c 0"

echo "Setting WM8960 audio levels..."
amixer $CARD cset name='Headphone Playback Volume' 109,109 || true
amixer $CARD cset name='Speaker Playback Volume' 109,109 || true
amixer $CARD cset name='Playback Volume' 255,255 || true
amixer $CARD cset name='Capture Volume' 39,39 || true
amixer $CARD cset name='Capture Switch' on,on || true
amixer $CARD cset name='Left Boost Mixer LINPUT1 Switch' on || true
amixer $CARD cset name='Right Boost Mixer RINPUT1 Switch' on || true
amixer $CARD cset name='Left Input Mixer Boost Switch' on || true
amixer $CARD cset name='Right Input Mixer Boost Switch' on || true
amixer $CARD cset name='Left Output Mixer PCM Playback Switch' on || true
amixer $CARD cset name='Right Output Mixer PCM Playback Switch' on || true
amixer $CARD cset name='Speaker DC Volume' 4 || true
amixer $CARD cset name='Speaker AC Volume' 4 || true
echo "Audio levels set ✓"
