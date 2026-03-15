#!/bin/bash
# Set WM8960 mixer for BITOS
amixer -c 0 sset 'Headphone Playback Volume' 109,109
amixer -c 0 sset 'Speaker Playback Volume' 109,109
amixer -c 0 sset 'Playback Volume' 255,255
amixer -c 0 sset 'Capture Volume' 39,39
amixer -c 0 sset 'Capture Switch' on,on
amixer -c 0 sset 'Left Boost Mixer LINPUT1 Switch' on
amixer -c 0 sset 'Right Boost Mixer RINPUT1 Switch' on
amixer -c 0 sset 'Left Input Mixer Boost Switch' on
amixer -c 0 sset 'Right Input Mixer Boost Switch' on
amixer -c 0 sset 'Left Output Mixer PCM Playback Switch' on
amixer -c 0 sset 'Right Output Mixer PCM Playback Switch' on
amixer -c 0 sset 'Speaker DC Volume' 4
amixer -c 0 sset 'Speaker AC Volume' 4
echo "Audio levels set ✓"
