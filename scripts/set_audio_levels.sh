#!/bin/bash
set -euo pipefail

amixer -c 0 sset 'Headphone Playback Volume' 109,109 || true
amixer -c 0 sset 'Speaker Playback Volume' 109,109 || true
amixer -c 0 sset 'Playback Volume' 255,255 || true
amixer -c 0 sset 'Capture Volume' 39,39 || true
amixer -c 0 sset 'Capture Switch' on,on || true
amixer -c 0 sset 'Left Boost Mixer LINPUT1 Switch' on || true
amixer -c 0 sset 'Right Boost Mixer RINPUT1 Switch' on || true
amixer -c 0 sset 'Left Input Mixer Boost Switch' on || true
amixer -c 0 sset 'Right Input Mixer Boost Switch' on || true
amixer -c 0 sset 'Speaker' 90% || true
amixer -c 0 sset 'Headphone' 90% || true
amixer -c 0 sset 'Capture' 80% || true
