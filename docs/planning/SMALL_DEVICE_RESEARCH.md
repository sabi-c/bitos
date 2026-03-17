# Small AI Companion Device Research

**Date:** 2026-03-16
**Goal:** Find the best small, watch-like device to serve as a wearable interface for a personal AI agent backend (ferrofluid blob avatar, voice interaction, WebSocket connection to Mac mini server).

---

## Requirements

- Small form factor (watch-face or pendant size)
- Display capable of rendering a 128x128+ animated blob
- WiFi and/or BLE for backend connectivity
- ESP32-S3 preferred (familiar toolchain, existing firmware patterns)
- Microphone + speaker for voice interaction
- Battery powered, ideally 4+ hours
- Under $80 ideally, under $40 even better
- Open-source friendly (Arduino/ESP-IDF/MicroPython)

---

## Category 1: ESP32 Round AMOLED Displays (Watch Form Factor)

### Waveshare ESP32-S3 Touch AMOLED 1.43" Round
- **Display:** 1.43" round AMOLED, 466x466, capacitive touch, 16.7M colors
- **Processor:** ESP32-S3R8 dual-core LX7 @ 240MHz
- **Memory:** 8MB PSRAM, 16MB Flash
- **Connectivity:** WiFi 2.4GHz, Bluetooth 5 LE
- **Sensors:** QMI8658 6-axis IMU, RTC chip
- **Extras:** TF card slot, lithium battery header, USB-C
- **Price:** ~$22-30 (board only), ~$35 with CNC metal watch case
- **URL:** https://www.waveshare.com/esp32-s3-touch-amoled-1.43.htm
- **Backend connection:** WiFi WebSocket directly to server, or BLE to phone relay
- **Notes:** Gorgeous round AMOLED. Perfect for blob avatar. No mic/speaker onboard -- would need external I2S mic + amp module. Battery header present but battery not included.

### Waveshare ESP32-S3 Touch AMOLED 2.06" Watch
- **Display:** 2.06" AMOLED, 410x502, capacitive touch
- **Processor:** ESP32-S3R8 dual-core LX7 @ 240MHz
- **Memory:** 8MB PSRAM, 32MB Flash
- **Connectivity:** WiFi 2.4GHz, Bluetooth 5 LE
- **Sensors:** 6-axis IMU, RTC, audio codec chip
- **Extras:** Dual digital microphone array, audio codec, watch strap mounts
- **Price:** ~$30-39
- **URL:** https://www.waveshare.com/esp32-s3-touch-amoled-2.06.htm
- **Backend connection:** WiFi WebSocket direct
- **Notes:** This is the standout. Has onboard dual mics AND audio codec -- ready for voice interaction out of the box. Rectangular watch form factor. Supports offline voice recognition via Xiaozhi framework. The 2.06" screen is large enough for a beautiful blob + status text.

### Waveshare ESP32-S3 Touch AMOLED 1.75" Round
- **Display:** 1.75" round AMOLED, 466x466, capacitive touch
- **Processor:** ESP32-S3R8 dual-core LX7 @ 240MHz
- **Memory:** 8MB PSRAM, 16MB Flash
- **Connectivity:** WiFi 2.4GHz, Bluetooth 5 LE
- **Extras:** Dual microphone array
- **Price:** ~$25-35
- **URL:** https://www.waveshare.com/esp32-s3-touch-amoled-1.75.htm
- **Notes:** Round + mics. Great middle ground between 1.43" and 2.06".

### Waveshare ESP32-S3 Touch LCD 1.28" Round
- **Display:** 1.28" round IPS LCD, 240x240, capacitive touch
- **Processor:** ESP32-S3 dual-core LX7 @ 240MHz
- **Memory:** 2MB PSRAM, 16MB Flash
- **Connectivity:** WiFi 2.4GHz, Bluetooth 5 LE
- **Sensors:** 6-axis IMU
- **Extras:** Battery charging circuit, USB-C
- **Price:** ~$12-18 (board), ~$20 with metal watch case
- **URL:** https://www.waveshare.com/esp32-s3-touch-lcd-1.28.htm
- **Backend connection:** WiFi WebSocket
- **Notes:** Cheapest option. LCD not AMOLED so less vibrant, but 240x240 is perfect for the 128x128 blob with room to spare. Only 2MB PSRAM though. No mic/speaker.

---

## Category 2: LilyGo Smartwatch Dev Kits

### LilyGo T-Watch S3
- **Display:** 1.54" IPS LCD, 240x240, capacitive touch
- **Processor:** ESP32-S3 @ 240MHz
- **Memory:** 8MB PSRAM, 16MB Flash
- **Connectivity:** WiFi, BLE, LoRa (SX1262)
- **Sensors:** BMA423 accelerometer, RTC
- **Extras:** Built-in battery, watch case, PDM microphone, speaker (MAX98357A)
- **Price:** ~$55
- **URL:** https://lilygo.cc/products/t-watch-s3
- **Backend connection:** WiFi WebSocket (LoRa for offline/mesh scenarios)
- **Notes:** Complete watch package with case, battery, mic, AND speaker. Ready to wear. LoRa is bonus for range. The 1.54" LCD is adequate. This is the most "ready to go" option.

### LilyGo T-Watch S3 Plus
- **Display:** 1.54" IPS LCD, 240x240, capacitive touch
- **Processor:** ESP32-S3 @ 240MHz
- **Memory:** 8MB PSRAM, 16MB Flash
- **Connectivity:** WiFi, BLE, LoRa
- **Extras:** GPS (MIA-M10Q), 940mAh battery, mic, speaker
- **Price:** ~$59
- **URL:** https://lilygo.cc/products/t-watch-s3-plus
- **Notes:** Same as T-Watch S3 but adds GPS and bigger battery. GPS not needed for AI companion use case but bigger battery is nice.

### LilyGo T-Watch Ultra
- **Display:** 2.06" AMOLED, 410x502, capacitive touch
- **Processor:** ESP32-S3 @ 240MHz
- **Memory:** 16MB Flash, 8MB PSRAM
- **Connectivity:** WiFi, BLE 5.0, LoRa, GNSS, NFC (ST25R3916)
- **Sensors:** BHI260AP AI motion sensor, haptic motor (DRV2605)
- **Extras:** MAX98357A speaker, mic, 1100mAh battery, MicroSD
- **Price:** ~$78
- **URL:** https://lilygo.cc/products/t-watch-ultra
- **Notes:** The premium option. AMOLED, haptic feedback, NFC, big battery, all sensors. Overkill for a blob companion but the AMOLED + haptics would make it feel premium. Most expensive ESP32 watch option.

---

## Category 3: Compact Dev Boards (Not Watch Form Factor)

### M5StickC Plus2
- **Display:** 1.14" TFT, 135x240
- **Processor:** ESP32-PICO-V3-02
- **Memory:** 8MB Flash, 2MB PSRAM
- **Connectivity:** WiFi, Bluetooth
- **Extras:** IMU, RTC, IR, mic, buzzer, 200mAh battery, Grove port
- **Price:** ~$20
- **URL:** https://shop.m5stack.com/products/m5stickc-plus2-esp32-mini-iot-development-kit
- **Notes:** Tiny stick form factor (48x25x13mm). Has mic but tiny screen. Could work as a pendant/clip-on. Very cheap. The 135x240 is rectangular and narrow -- blob would need to be small.

### Seeed Studio XIAO ESP32S3 + Round Display
- **Display:** 1.28" round IPS LCD, 240x240, capacitive touch (expansion board)
- **Processor:** ESP32-S3 @ 240MHz
- **Memory:** 8MB PSRAM, 8MB Flash
- **Connectivity:** WiFi, BLE 5.0
- **Extras:** RTC, TF card, battery charging circuit
- **Price:** ~$7 (XIAO board) + ~$18 (round display) = ~$25 total
- **URL:** https://www.seeedstudio.com/XIAO-ESP32S3-p-5627.html + https://www.seeedstudio.com/1-28-Round-Touch-Display-for-Seeed-Studio-XIAO-ESP32.html
- **Notes:** Modular approach. The XIAO Sense variant adds camera + mic for $14. Round display is 39mm disc -- very wearable. Would need custom 3D-printed case. No speaker.

---

## Category 4: Open-Source AI Wearable Projects

### Omi (formerly "Friend")
- **Form factor:** Coin-sized pendant/clip
- **Hardware:** BLE 5.2, MEMS microphone, 150mAh battery (10-14hr)
- **Display:** None
- **Price:** Dev kit ~$89, pre-built ~$89
- **Open source:** Yes -- https://github.com/BasedHardware/omi
- **Backend connection:** BLE to phone app, phone relays to cloud
- **Notes:** No display -- audio-only capture device. Great reference for the audio pipeline but not suitable for blob avatar display. Could be complementary (wear Omi for always-on listening, separate watch for blob display).

### ADeus
- **Form factor:** Wearable recorder
- **Hardware:** ESP32-based, microphone
- **Display:** None
- **Price:** DIY
- **Open source:** Yes -- https://github.com/adamcohenhillel/ADeus
- **Notes:** Self-hosted AI wearable. Captures audio, stores on your own server. Good architectural reference but no display.

### Xiaozhi ESP32
- **Form factor:** Various (supports 70+ board configs)
- **Hardware:** ESP32-S3/C3/P4 based
- **Open source:** Yes -- https://github.com/78/xiaozhi-esp32
- **Notes:** Open-source voice assistant framework for ESP32. Supports wake-word detection, streaming ASR/TTS, LLM integration via MCP. This firmware could be adapted for any of the Waveshare/LilyGo boards above. Very relevant as a starting point for the voice pipeline.

---

## Category 5: Tiny Android Phones

### Unihertz Jelly Star
- **Display:** 3.0" LCD, 480x854
- **Processor:** MediaTek Helio G99 octa-core @ 2.2GHz
- **Memory:** 8GB RAM, 256GB storage
- **Connectivity:** 4G LTE, WiFi, BLE 5.3, NFC, GPS
- **Battery:** 2000mAh
- **Price:** ~$170-220
- **URL:** https://www.unihertz.com/products/jelly-star
- **Notes:** Full Android 13 phone. Could run a custom Flutter/Kotlin app with the blob rendered natively. Way more powerful than any ESP32. But: expensive, bulky compared to a watch board, and overkill. The 3" screen is gorgeous though. Could be used as a prototype/demo device before building custom hardware. Supports custom launchers and can be locked to a single app.

---

## Category 6: Open-Source Smartwatch OS Projects

### Watchy (SQFMI)
- **Display:** 1.54" E-Paper (200x200)
- **Processor:** ESP32-S3
- **Connectivity:** WiFi, BLE
- **Price:** ~$50
- **URL:** https://watchy.sqfmi.com/
- **Notes:** E-paper means no animation -- completely unsuitable for blob avatar. Cool project but wrong display tech.

### PineTime
- **Display:** 1.3" IPS LCD, 240x240, capacitive touch
- **Processor:** nRF52832 (ARM Cortex-M4, NOT ESP32)
- **Price:** ~$27
- **Notes:** Runs InfiniTime or Wasp-os. Different MCU ecosystem (nRF52, not ESP32). Less relevant but shows what's possible with open firmware on a $27 watch.

---

## Top 5 Recommendations (Ranked)

### 1. Waveshare ESP32-S3 Touch AMOLED 2.06" Watch -- BEST OVERALL
**Price: ~$30-39 | Score: 9.5/10**

The clear winner. It has everything needed in one board:
- Stunning 2.06" AMOLED for the blob avatar (410x502 is way beyond the 128x128 minimum)
- Dual onboard microphones for voice capture
- Audio codec chip for speaker output
- ESP32-S3 with 8MB PSRAM (plenty for WiFi + animation)
- Watch strap mounting points -- actually wearable
- Supports the Xiaozhi voice assistant framework out of the box
- $30 is absurdly cheap for what you get

**Gap:** Needs external battery (has header) and a small speaker/amp module if the codec doesn't include one. Needs a case/strap.

### 2. LilyGo T-Watch S3 -- MOST COMPLETE OUT-OF-BOX
**Price: ~$55 | Score: 8.5/10**

The most "put it on and go" option:
- Complete watch with case, strap, battery, mic, speaker
- 1.54" IPS LCD (240x240) is adequate for blob
- LoRa is a bonus (mesh networking potential)
- Well-documented, active community
- Arduino + ESP-IDF + MicroPython support

**Gap:** LCD not AMOLED (less vibrant blacks for the ferrofluid look). 1.54" is smaller than ideal.

### 3. Waveshare ESP32-S3 Touch AMOLED 1.43" Round -- BEST LOOKING
**Price: ~$22-30 (board) / ~$35 (with watch case) | Score: 8/10**

The best display for the blob:
- Round AMOLED at 466x466 -- the ferrofluid blob would look incredible on this
- Round form factor matches a watch face perfectly
- CNC metal case option makes it look premium
- Cheapest AMOLED option

**Gap:** No microphone or speaker onboard. Would need to add I2S MEMS mic (~$3) and MAX98357A amp + speaker (~$5), which means custom wiring and a bigger case.

### 4. Seeed XIAO ESP32S3 Sense + Round Display -- BEST MODULAR/DIY
**Price: ~$32-40 total | Score: 7.5/10**

Most flexible for custom builds:
- Tiny 21x17.5mm main board + 39mm round display disc
- XIAO Sense variant includes camera + digital mic
- 1.28" round LCD (240x240) with touch
- Deep sleep as low as 14uA
- Perfect for designing a custom 3D-printed pendant or watch case

**Gap:** No speaker. Needs custom enclosure. Two-board assembly. Only 1.28" display.

### 5. LilyGo T-Watch Ultra -- PREMIUM OPTION
**Price: ~$78 | Score: 7/10**

For when you want everything:
- 2.06" AMOLED (same panel as Waveshare #1)
- Haptic feedback motor (DRV2605) -- blob could "pulse" physically
- NFC for tap interactions
- 1100mAh battery (best battery life)
- LoRa + GNSS
- Complete watch package

**Gap:** Expensive for a dev device. Many features (GNSS, NFC, LoRa) add cost without adding value for the AI companion use case.

---

## Honorable Mentions

| Device | Price | Why It's Interesting | Why It Didn't Rank |
|--------|-------|---------------------|--------------------|
| M5StickC Plus2 | $20 | Cheapest, has mic, tiny | Screen too small (1.14") |
| Unihertz Jelly Star | $170 | Full Android, 3" screen | Expensive, not ESP32, bulky |
| Waveshare 1.28" LCD Round | $12-18 | Dirt cheap | No AMOLED, no mic, low PSRAM |
| Omi Dev Kit | $89 | Open-source AI wearable | No display at all |

---

## Software Stack Recommendations

For whichever device is chosen:

1. **Firmware base:** Xiaozhi ESP32 framework (https://github.com/78/xiaozhi-esp32) -- provides wake-word, streaming ASR, TTS, MCP tool integration
2. **Display rendering:** LVGL (built-in support on all Waveshare/LilyGo boards) for UI, custom canvas widget for blob animation
3. **Backend protocol:** WebSocket over WiFi to the existing ai-agent-env server (`/ws/voice` for audio, `/ws/blob` for animation events)
4. **Animation:** Port the ferrofluid blob engine from Python to C (metaball field at 128x128, render to LVGL canvas). The ESP32-S3 at 240MHz with PSRAM can handle this.
5. **Audio pipeline:** I2S mic capture -> WiFi stream to server -> server processes with Whisper -> response -> TTS audio stream back -> I2S DAC output

---

## Next Steps

1. Order the **Waveshare ESP32-S3 AMOLED 2.06" Watch** (~$30) as primary dev board
2. Order the **Waveshare 1.43" Round AMOLED** (~$25) as a comparison for the round form factor
3. Flash Xiaozhi ESP32 firmware to validate voice pipeline
4. Port blob renderer to C/LVGL as a proof of concept
5. Design WebSocket integration with existing `/ws/voice` and `/ws/blob` endpoints
