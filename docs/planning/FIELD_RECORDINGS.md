# BITOS Field Recordings — Feature Specification

## Last updated: 2026-03-16

---

## 1. Vision

Field Recordings turns BITOS from a conversational device into an **intelligent audio capture tool**. The user presses a button, records audio in the wild — observations, interviews, ideas, environmental sounds — and the system handles everything else: storage, transcription, summarization, tagging, and cross-device browsing.

This is NOT a voice memo app. A voice memo app records and stores. BITOS Field Recordings records, *understands*, and *connects* the audio to the user's existing knowledge graph (chat history, tasks, captures).

### What makes this better than Voice Memos

| Voice Memos | BITOS Field Recordings |
|---|---|
| Records audio | Records audio + auto-transcribes |
| Manual organization | AI-tagged by topic, mood, people, location |
| Isolated files | Connected to chat context + task graph |
| Search by date only | Full-text search across all transcriptions |
| No summarization | Auto-generated summary + key points + action items |
| Phone-only playback | Device browse + companion app + export |
| No intelligence | "What did I record about fermentation last week?" |

---

## 2. Competitive Landscape Research

### Hardware Devices

**Plaud Note Pro** — The gold standard for AI voice recorders (2025-2026). Credit-card thin, 4 MEMS mics, vibration conduction sensor for phone calls, 64GB onboard, 50h battery. Key UX insight: **physical highlight button** lets users mark moments during recording that get emphasized in AI summaries. BITOS can steal this pattern — double-press during recording = timestamp bookmark.

**Zoom H1n / H6** — Professional field recorders. Excellent preamps, XY stereo mics, WAV/MP3, SD card storage. No intelligence layer. The lesson: audio quality matters for field recording. BITOS has a WM8960 codec — decent but not audiophile. Acceptable for voice/ambient, not music production.

**Sony ICD series** — Reliable dictaphones. Good battery, simple UI. No AI. The anti-pattern: overcomplicated menus with tiny buttons.

### Software

**Otter.ai** — Best live transcription with real-time multi-speaker notes. 300 free min/month. Strength: words appear as people speak. Weakness: cloud-only, no offline transcription.

**Notta / Notta Memo** — 58-language support, 98.8% claimed accuracy, hardware device (Memo) with AI extraction of decisions/action items/next steps in 10 seconds post-recording. Key insight: **post-recording summary in <10s** sets user expectations.

**Mem.ai** — Treats voice as a knowledge input, not just a file. Parses utterances into structured data ("block 2hrs Tuesday for budget review" becomes a scheduled task). Key insight: **voice as structured data input**, not just audio storage.

**Apple Voice Memos + Journal** — Dead simple. Record, done. Journal adds prompts and photos. The lesson: **zero-friction capture** is non-negotiable. One action to start recording, one to stop.

**Notion AI Meeting Notes** — Summarization + action item extraction from meeting transcripts. The lesson: **action items should be first-class output**, not buried in a transcript.

### UX Patterns from the Best

1. **One-tap capture** (Apple Voice Memos, Plaud) — recording must start instantly
2. **Live transcription display** (Otter) — shows words appearing in real-time
3. **Post-recording intelligence** (Notta, Plaud) — summary within seconds of stopping
4. **Highlight/bookmark during recording** (Plaud) — mark important moments
5. **Searchable knowledge base** (Mem.ai) — recordings become queryable knowledge
6. **Speaker labels** (Otter, AssemblyAI) — "Speaker A said..." for interviews
7. **Offline-first** (all hardware recorders) — never lose a recording due to connectivity

---

## 3. Architecture

### 3.1 System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    BITOS DEVICE (Pi Zero 2W)                 │
│                                                              │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │ WM8960   │───>│ Recording    │───>│ Local Storage     │  │
│  │ Mic      │    │ Engine       │    │ /home/pi/bitos/   │  │
│  │          │    │ (arecord)    │    │ recordings/       │  │
│  └──────────┘    └──────────────┘    └─────────┬─────────┘  │
│                                                │             │
│                                    ┌───────────┴──────────┐  │
│                                    │ Sync Queue (SQLite)  │  │
│                                    │ status: pending/     │  │
│                                    │ synced/transcribed/  │  │
│                                    │ processed            │  │
│                                    └───────────┬──────────┘  │
│                                                │             │
└────────────────────────────────────────────────┼─────────────┘
                                                 │ WiFi available
                                                 ▼
┌──────────────────────────────────────────────────────────────┐
│                    BITOS SERVER (localhost:8000)              │
│                                                              │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │ Upload       │  │ Transcription │  │ AI Processing    │  │
│  │ Endpoint     │──│ Worker        │──│ Worker           │  │
│  │ POST /record │  │ (Deepgram/    │  │ (Haiku summary,  │  │
│  │              │  │  Whisper API) │  │  tags, actions)  │  │
│  └──────────────┘  └───────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ recordings table (SQLite)                                ││
│  │ id, filename, duration_s, size_bytes, recorded_at,       ││
│  │ transcription, summary, tags, action_items,              ││
│  │ speakers, bookmarks, location, mood, status,             ││
│  │ sync_status, cloud_url                                   ││
│  └──────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ Cloud Sync Worker                                        ││
│  │ Backblaze B2 (S3-compatible) — audio files               ││
│  │ Delta sync: upload new, skip unchanged                   ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    COMPANION APP (iOS)                        │
│  Recordings list, playback, transcript edit, search, export  │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Audio Storage Architecture

**On-device storage:**
- Path: `/home/pi/bitos/recordings/`
- Format: WAV 16kHz mono S16_LE (matches existing `WM8960Pipeline` output)
- Naming: `rec_{unix_timestamp}_{short_uuid}.wav`
- Size budget: 1 min WAV at 16kHz/16bit/mono = ~1.9 MB
- Compressed (Opus): 1 min = ~100-150 KB
- SD card typical: 32GB → ~16,000 minutes WAV or ~200,000 minutes Opus
- Rotation policy: keep all locally until SD card reaches 80% capacity, then prompt user via notification; never auto-delete

**Compression pipeline:**
1. Record as WAV (reliable, no CPU overhead during capture)
2. Post-recording: convert to Opus via `opusenc` for cloud sync and long-term storage
3. Keep WAV for 7 days (faster local playback), then keep only Opus
4. Opus is well-supported, open-source, and ~10x smaller than WAV at voice-quality bitrates

**Cloud sync (Backblaze B2):**
- S3-compatible API, cheapest tier: $0.006/GB/month storage + $0.01/GB egress
- 10,000 minutes of Opus recordings = ~1.5 GB = ~$0.01/month storage
- Sync worker runs when WiFi detected, uploads Opus files in chronological order
- Metadata (transcription, summary, tags) synced as JSON sidecar files
- Sync status tracked per recording: `local_only` → `uploading` → `synced`
- Conflict resolution: device is source of truth (recordings originate here)

### 3.3 Transcription Pipeline

**Primary: Cloud STT (when online)**

Recommended: **Deepgram Nova-2**
- Cost: ~$0.0043/min ($0.26/hour) — cheapest quality option
- Speed: transcribes 1 hour in ~20 seconds
- Quality: 95%+ accuracy on clean speech
- Speaker diarization: built-in, no extra cost on most plans
- Why not Whisper API: Deepgram is 3x faster and cheaper. Whisper API ($0.006/min) is fine as fallback.
- Why not AssemblyAI: slightly more accurate (96-98%) but more expensive ($0.37/hour) and charges extra for diarization. Worth it for interview-heavy users as a premium option.

**Fallback: Local STT (offline)**

whisper.cpp with `tiny.en` model:
- Performance on Pi Zero 2W: ~3-5x realtime (a 60s recording takes 12-20s to transcribe)
- RAM: ~100MB
- Accuracy: lower than cloud (especially for accented speech, noisy environments)
- Role: provide *something* when offline, re-transcribe via cloud when connectivity returns
- UI label: "DRAFT TRANSCRIPT" with indicator that cloud re-transcription is pending

**Processing queue:**
```
Recording saved
    │
    ├── WiFi available? ──YES──> Deepgram API (fast, accurate)
    │                               │
    │                               ▼
    │                          Transcription stored
    │
    └── WiFi unavailable? ──> whisper.cpp local (slow, draft)
                                │
                                ▼
                           Draft transcript stored
                           Queued for cloud re-transcription
```

**Speaker diarization:**
- Enabled by default via Deepgram `diarize=true` parameter
- Stores speaker labels: `[Speaker 1]`, `[Speaker 2]`, etc.
- User can rename speakers in companion app ("Speaker 1" → "Dr. Martinez")
- Local whisper.cpp: no diarization (single-speaker draft only)

### 3.4 AI Processing Pipeline

After transcription is complete, a Haiku worker processes the transcript:

```python
RECORDING_ANALYSIS_PROMPT = """Analyze this audio recording transcription.

Transcription:
{transcription}

Recording metadata:
- Duration: {duration}s
- Time: {recorded_at}
- Location: {location_hint}
- Bookmarks at: {bookmark_timestamps}

Return JSON:
{
  "summary": "2-3 sentence summary of the recording",
  "key_points": ["point 1", "point 2", ...],
  "action_items": [
    {"text": "Follow up with...", "priority": "high/medium/low"}
  ],
  "tags": ["topic1", "topic2"],  // max 5
  "category": "interview|observation|idea|note|environmental|meeting",
  "mood": "neutral|excited|reflective|urgent|casual",
  "people_mentioned": ["name1", "name2"],
  "related_topics": ["topics that might connect to user's other recordings/chats"]
}"""
```

**Connection to chat context:**
- When user asks "what did I record about X?", the `/chat` endpoint searches `recordings` table via FTS5
- Recordings surface as context in the Global Workspace (Phase 8) alongside chat history
- Action items from recordings can be pushed to Tasks (Vikunja) with user confirmation

### 3.5 Distinguishing Field Recordings from Chat

This is a critical UX decision. Three-tier approach:

**Tier 1: Explicit mode (MVP)**
- User navigates to RECORDINGS in sidebar → enters recording mode
- Everything captured here is a field recording, period
- No ambiguity, no AI classification needed

**Tier 2: Duration heuristic (v1.5)**
- Voice input in CHAT screen: >45 seconds of continuous audio = prompt user
- "This seems like a long recording. Save as field recording?" (YES / NO, keep as chat)
- Configurable threshold in Settings

**Tier 3: Perception classifier (v2)**
- Extend the existing `perception.py` classifier with a new intent: `field_recording`
- Signals: user says "note to self", "recording", "observation", "field note"
- Signals: audio contains multiple speakers (interview pattern)
- Signals: environmental audio dominates (low speech-to-noise ratio)
- Add to `CLASSIFIER_PROMPT`:
  ```
  - "field_recording" = user is dictating a note/observation, recording an interview,
    or capturing environmental audio — NOT having a conversation with the assistant
  ```

**Recommended for MVP: Tier 1 only.** Explicit mode is predictable. Users know what they're getting. Add intelligence later.

---

## 4. Database Schema

```sql
-- New table in device/storage/repository.py
CREATE TABLE IF NOT EXISTS recordings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,              -- rec_1710590400_abc123.wav
    opus_filename TEXT,                  -- rec_1710590400_abc123.opus (after compression)
    duration_s REAL NOT NULL DEFAULT 0,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sample_rate INTEGER DEFAULT 16000,
    recorded_at TEXT NOT NULL,           -- ISO 8601
    -- Bookmarks (JSON array of seconds)
    bookmarks TEXT DEFAULT '[]',
    -- Processing status
    status TEXT DEFAULT 'recorded',      -- recorded → transcribing → transcribed → processing → complete → error
    -- Transcription
    transcription TEXT,
    transcription_source TEXT,           -- deepgram | whisper_api | whisper_local
    transcription_draft INTEGER DEFAULT 0,  -- 1 if local whisper, pending cloud re-transcription
    speakers TEXT,                       -- JSON: [{"id": 1, "label": "Speaker 1", "name": null}]
    -- AI analysis
    summary TEXT,
    key_points TEXT,                     -- JSON array
    action_items TEXT,                   -- JSON array of {text, priority}
    tags TEXT,                           -- JSON array
    category TEXT,                       -- interview|observation|idea|note|environmental|meeting
    mood TEXT,
    people_mentioned TEXT,              -- JSON array
    -- Sync
    sync_status TEXT DEFAULT 'local_only',  -- local_only → uploading → synced
    cloud_url TEXT,
    -- Metadata
    location TEXT,                       -- coarse location hint if available
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- FTS5 for full-text search across transcriptions and summaries
CREATE VIRTUAL TABLE IF NOT EXISTS recordings_fts USING fts5(
    transcription, summary, key_points, tags,
    content='recordings', content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS recordings_ai AFTER INSERT ON recordings BEGIN
    INSERT INTO recordings_fts(rowid, transcription, summary, key_points, tags)
    VALUES (new.id, new.transcription, new.summary, new.key_points, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS recordings_au AFTER UPDATE ON recordings BEGIN
    INSERT INTO recordings_fts(recordings_fts, rowid, transcription, summary, key_points, tags)
    VALUES ('delete', old.id, old.transcription, old.summary, old.key_points, old.tags);
    INSERT INTO recordings_fts(rowid, transcription, summary, key_points, tags)
    VALUES (new.id, new.transcription, new.summary, new.key_points, new.tags);
END;
```

---

## 5. Server API

### New endpoints

```
POST /recordings/upload
  - Multipart: audio file + metadata JSON
  - Queues transcription + AI processing
  - Returns: {id, status: "queued"}

GET /recordings
  - Query params: limit, offset, tag, category, search, date_from, date_to
  - Returns: [{id, filename, duration_s, recorded_at, summary, tags, category, status, sync_status}]

GET /recordings/{id}
  - Full recording detail: transcript, summary, key_points, action_items, speakers, etc.

GET /recordings/{id}/audio
  - Streams the audio file (WAV or Opus)

PUT /recordings/{id}
  - Update metadata: speaker names, manual tags, corrected transcript

DELETE /recordings/{id}
  - Soft delete (mark deleted, cleanup worker removes files later)

GET /recordings/search?q=fermentation
  - FTS5 search across transcriptions and summaries

POST /recordings/{id}/reprocess
  - Re-run transcription and/or AI analysis (e.g., after transcript correction)

GET /recordings/stats
  - Total count, total duration, storage used, recordings this week, top tags
```

### Background workers

```python
# In server/workers/transcription_worker.py
# Polls for recordings with status='recorded', processes sequentially

async def transcription_loop():
    while True:
        pending = db.get_recordings(status='recorded', limit=5)
        for rec in pending:
            db.update_recording(rec.id, status='transcribing')
            transcript = await transcribe(rec.filename)  # Deepgram or fallback
            db.update_recording(rec.id,
                transcription=transcript.text,
                speakers=transcript.speakers,
                transcription_source=transcript.source,
                status='transcribed')
        await asyncio.sleep(5)


# In server/workers/analysis_worker.py
# Processes transcribed recordings through Haiku

async def analysis_loop():
    while True:
        pending = db.get_recordings(status='transcribed', limit=3)
        for rec in pending:
            db.update_recording(rec.id, status='processing')
            analysis = await analyze_recording(rec)  # Haiku call
            db.update_recording(rec.id,
                summary=analysis.summary,
                key_points=json.dumps(analysis.key_points),
                action_items=json.dumps(analysis.action_items),
                tags=json.dumps(analysis.tags),
                category=analysis.category,
                mood=analysis.mood,
                people_mentioned=json.dumps(analysis.people_mentioned),
                status='complete')
        await asyncio.sleep(10)
```

---

## 6. Device UI

### 6.1 Sidebar Integration

Add `RECORD` to the sidebar items list between `FILES` and `SETTINGS`:

```python
# device/ui/components/sidebar.py
ITEMS = ["HOME", "CHAT", "TASKS", "ACTIVITY", "COMMS", "FILES", "RECORD", "SETTINGS", "FOCUS"]
```

This gives us 9 items. At 20px per item = 180px, fits within the 208px available panel height.

### 6.2 Recording Preview Panel (submenu)

When RECORD is selected in sidebar, the right panel shows:

```
┌──────────────────────────────────────┐
│  RECORD                              │
├──────────────────────────────────────┤
│                                      │
│  > NEW RECORDING                     │
│    Start field recording             │
│                                      │
│    BROWSE                            │
│    View past recordings              │
│                                      │
│    SEARCH                            │
│    Search transcriptions             │
│                                      │
│    BACK                              │
│    Return to sidebar                 │
│                                      │
└──────────────────────────────────────┘
```

### 6.3 Active Recording Screen

Full-screen takeover (like chat voice input). Single button controls everything.

```
┌────────────────────────────────────────┐
│ ● REC                    02:34    57%  │  ← status bar: red dot, elapsed time, battery
├────────────────────────────────────────┤
│                                        │
│                                        │
│            ████████████                │  ← audio level meter (horizontal bar)
│            ████████                    │
│            ████████████████            │
│                                        │
│                                        │
│           RECORDING...                 │  ← state label
│                                        │
│         ★ 1 bookmark                   │  ← bookmark count (if any)
│                                        │
│                                        │
├────────────────────────────────────────┤
│  tap=bookmark  double=pause  hold=stop │  ← hint bar
└────────────────────────────────────────┘
```

**Button mapping during recording:**
| Gesture | Action |
|---|---|
| SHORT_PRESS (tap) | Add timestamp bookmark |
| DOUBLE_PRESS | Pause / Resume recording |
| LONG_PRESS (hold) | Stop recording + save |
| TRIPLE_PRESS | Cancel recording (with confirmation) |

**Audio level visualization:**
- Real-time RMS level from the recording buffer
- Horizontal bar graph, 5 updates/sec
- Shows the user the mic is actually capturing audio

### 6.4 Post-Recording Screen

Immediately after stopping:

```
┌────────────────────────────────────────┐
│ SAVED                         02:34    │
├────────────────────────────────────────┤
│                                        │
│  ✓ Recording saved                     │
│    rec_20260316_143022.wav             │
│    2 min 34 sec · 4.8 MB              │
│                                        │
│  ⟳ Transcribing...                     │  ← or "✓ Transcribed" when done
│                                        │
│  ⟳ Analyzing...                        │  ← or "✓ Summary ready" when done
│                                        │
│  ★ 3 bookmarks saved                  │
│                                        │
├────────────────────────────────────────┤
│  tap=done  double=view  hold=discard   │
└────────────────────────────────────────┘
```

### 6.5 Recordings Browser

Scrollable list, same pattern as `CapturesPanel` and `FilesBrowserPanel`:

```
┌────────────────────────────────────────┐
│ RECORDINGS (47)                   ▼    │
├────────────────────────────────────────┤
│ > TODAY 14:30 · 2m34s                  │  ← selected/focused row
│   Bird sounds at Botanic Garden        │  ← AI summary snippet
│                                        │
│   TODAY 09:15 · 8m12s                  │
│   Interview with Dr. Martinez          │
│                                        │
│   MAR 15 18:40 · 0m45s                │
│   Idea: fermentation sensor array      │
│                                        │
│   MAR 15 11:20 · 12m08s               │
│   Meeting notes — hardware review      │
│                                        │
│   MAR 14 16:55 · 1m22s                │
│   Observation: soil moisture levels    │
│                                        │
├────────────────────────────────────────┤
│  tap=next  dbl=open  triple=prev       │
└────────────────────────────────────────┘
```

### 6.6 Recording Detail View

When a recording is opened:

```
┌────────────────────────────────────────┐
│ REC · MAR 16 14:30                     │
├────────────────────────────────────────┤
│                                        │
│  ▶ 00:00 / 02:34     ████░░░░░░       │  ← playback bar
│                                        │
│  SUMMARY                               │
│  Recorded bird calls at the            │
│  Botanic Garden greenhouse.            │
│  Identified possible Tui and           │
│  Bellbird calls near the native        │
│  section.                              │
│                                        │
│  TAGS: nature, birds, botanic          │
│                                        │
│  ★ Bookmarks: 0:45, 1:12, 2:01       │
│                                        │
├────────────────────────────────────────┤
│  tap=play/pause  dbl=transcript        │
│  triple=prev-bkmk  hold=back          │
└────────────────────────────────────────┘
```

**Playback button mapping:**
| Gesture | Action |
|---|---|
| SHORT_PRESS | Play / Pause toggle |
| DOUBLE_PRESS | Show full transcript (scroll view) |
| TRIPLE_PRESS | Jump to previous bookmark |
| LONG_PRESS | Back to recordings list |

---

## 7. Companion App Integration

### 7.1 Recordings Tab

New tab in the companion app (alongside Status, Chat Relay, Settings):

```
┌─────────────────────────────────┐
│  Recordings              🔍 ⚙️  │
├─────────────────────────────────┤
│  Filter: All ▼   Sort: Recent  │
│                                 │
│  ┌─────────────────────────────┐│
│  │ 🔴 Bird sounds at Botanic  ││
│  │    Garden                    ││
│  │    Today 2:34pm · 2m34s     ││
│  │    nature · birds · botanic ││
│  │    ☁️ Synced                 ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ 🎙 Interview: Dr. Martinez ││
│  │    Today 9:15am · 8m12s     ││
│  │    interview · research     ││
│  │    ⟳ Syncing...              ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ 💡 Idea: fermentation       ││
│  │    sensor array              ││
│  │    Mar 15 6:40pm · 0m45s    ││
│  │    idea · hardware           ││
│  │    ☁️ Synced                 ││
│  └─────────────────────────────┘│
│                                 │
├─────────────────────────────────┤
│  🏠  💬  🎙  ⚙️                │
│  Home Chat Record Settings      │
└─────────────────────────────────┘
```

### 7.2 Recording Detail (Companion)

```
┌─────────────────────────────────┐
│  ← Back       Bird sounds...    │
├─────────────────────────────────┤
│                                 │
│  ▶  ━━━━━━━━━●━━━━━━  2:34     │  ← waveform playback bar
│     0:45      1:12    2:01      │  ← bookmark indicators on waveform
│                                 │
│  ┌─ SUMMARY ───────────────────┐│
│  │ Recorded bird calls at the  ││
│  │ Botanic Garden greenhouse.  ││
│  │ Identified possible Tui and ││
│  │ Bellbird calls near native  ││
│  │ section.                    ││
│  └─────────────────────────────┘│
│                                 │
│  ┌─ KEY POINTS ────────────────┐│
│  │ • Tui-like call at 0:45     ││
│  │ • Bellbird pattern at 1:12  ││
│  │ • Unknown call at 2:01      ││
│  └─────────────────────────────┘│
│                                 │
│  ┌─ ACTION ITEMS ──────────────┐│
│  │ □ Research NZ bird call     ││
│  │   identification apps       ││
│  │ □ Return with better mic    ││
│  └─────────────────────────────┘│
│                                 │
│  ┌─ TRANSCRIPT ────────────────┐│
│  │ [0:00] Okay, I'm at the    ││
│  │ Botanic Garden, standing    ││
│  │ near the native bush        ││
│  │ section. I can hear what    ││
│  │ sounds like a Tui...        ││
│  │                    [expand] ││
│  └─────────────────────────────┘│
│                                 │
│  Tags: nature · birds · botanic │
│  Category: observation          │
│                                 │
│  [Edit Transcript] [Export] [⋯] │
│                                 │
└─────────────────────────────────┘
```

### 7.3 Companion Features

- **Search:** Full-text search across all transcriptions and summaries
- **Filters:** By date range, tag, category, duration, sync status
- **Playback:** Streaming from device (if on same network) or cloud (if synced)
- **Waveform:** Visual audio waveform with bookmark markers, tap to seek
- **Edit transcript:** Tap any word to correct transcription errors
- **Rename speakers:** Tap "Speaker 1" → type "Dr. Martinez"
- **Export:** Share audio file, transcript text, or combined report (Markdown/PDF)
- **Sync indicators:** Per-recording status (local only / syncing / synced / error)
- **Batch operations:** Multi-select for bulk tag, bulk export, bulk delete
- **Action items → Tasks:** One-tap to send action items to Vikunja/Things

---

## 8. Real-World Workflow Support

### Journalism: Interview + Quotes

1. User starts recording, speaks: "Interview with Dr. Martinez about coral restoration"
2. Bookmarks key moments with taps during the interview
3. After recording, AI generates:
   - Summary of the interview
   - Speaker-labeled transcript (Interviewer / Dr. Martinez)
   - Key quotes extracted (near bookmark timestamps)
   - Action items: "Follow up on grant proposal deadline"
4. User can search later: "what did Martinez say about funding?"

### Nature Observation

1. User records ambient nature sounds + spoken observations
2. AI separates speech from environmental audio in transcript
3. Tags: location, time of day, weather conditions (from live context)
4. Future: environmental audio classification (bird species, etc.) — v3 feature

### Idea Capture / Thought Journaling

1. Quick record: "Idea — what if we used capacitive soil sensors instead of resistive ones"
2. AI extracts: category=idea, tags=[hardware, sensors, soil], action_items=["research capacitive soil sensors"]
3. Connected to existing chat history about the hardware project

### Meeting Notes

1. Record a meeting (multiple speakers via diarization)
2. AI generates: summary, decisions made, action items with owners
3. Action items optionally pushed to task manager

---

## 9. Cost Analysis

### Per-recording costs (1 min average)

| Component | Cost |
|---|---|
| Deepgram transcription | $0.0043 |
| Haiku analysis (~500 tokens) | ~$0.0004 |
| B2 storage (Opus, ~150KB) | $0.000001/month |
| B2 egress (playback, ~150KB) | $0.0000015 |
| **Total per minute** | **~$0.005** |

### Monthly estimates

| Usage | Recordings/month | Minutes | Monthly cost |
|---|---|---|---|
| Light (2/day) | 60 | ~120 min | ~$0.60 |
| Medium (5/day) | 150 | ~300 min | ~$1.50 |
| Heavy (10/day) | 300 | ~600 min | ~$3.00 |

Very affordable. The transcription cost dominates; storage and AI analysis are negligible.

---

## 10. Phased Rollout

### Phase A — MVP (1-2 weeks) — "Record and Transcribe"

**Goal:** Basic field recording with transcription. Usable, not smart.

- [ ] `recordings` table + FTS5 in SQLite
- [ ] Recording engine: extend `WM8960Pipeline` for long-form recording to file
- [ ] RECORD sidebar item + recording preview panel (NEW RECORDING / BROWSE / BACK)
- [ ] Active recording screen with timer + level meter
- [ ] Button mapping: tap=bookmark, double=pause, hold=stop
- [ ] `POST /recordings/upload` endpoint
- [ ] Transcription worker (Deepgram primary, Whisper API fallback)
- [ ] Recordings browser panel (list with date, duration)
- [ ] Recording detail view (playback + raw transcript)
- [ ] Basic device-side playback via `aplay`

**Delivers:** A field recorder that saves + transcribes. No AI analysis yet. No cloud sync. No companion. Already more useful than a basic voice memo app because of full-text searchable transcripts.

### Phase B — Intelligence (1-2 weeks) — "Record, Understand, Connect"

**Goal:** AI-powered analysis makes recordings truly useful.

- [ ] Haiku analysis worker (summary, key points, action items, tags, category, mood)
- [ ] Summary + tags displayed in recordings browser
- [ ] Recording detail view shows summary, key points, action items
- [ ] FTS5 search endpoint (`GET /recordings/search`)
- [ ] Chat integration: "what did I record about X?" searches recordings table
- [ ] Post-recording screen shows processing progress
- [ ] Speaker diarization (Deepgram `diarize=true`)
- [ ] Bookmark timestamps included in AI analysis context
- [ ] Duration heuristic in chat: prompt to save as recording if >45s

### Phase C — Sync + Companion (2-3 weeks) — "Access Anywhere"

**Goal:** Recordings available on phone. Cloud backup.

- [ ] Opus compression worker (post-recording)
- [ ] Backblaze B2 sync worker (upload Opus + metadata JSON)
- [ ] `GET /recordings/{id}/audio` streaming endpoint
- [ ] Companion app: Recordings tab (list, search, filter)
- [ ] Companion: playback with waveform visualization
- [ ] Companion: edit transcript, rename speakers
- [ ] Companion: export (audio, text, combined)
- [ ] Sync status indicators on device + companion
- [ ] WAV cleanup worker (keep WAV 7 days, then Opus only)

### Phase D — Advanced (ongoing) — "Recording Intelligence"

**Goal:** Recordings become a knowledge layer.

- [ ] Local whisper.cpp fallback for offline transcription
- [ ] Perception classifier: auto-detect field recording intent in chat
- [ ] Action items → Vikunja/Things task creation
- [ ] Recording-aware Global Workspace signals (Phase 8 integration)
- [ ] Smart connections: "this recording mentions topics from your Tuesday chat"
- [ ] Recording templates: "Interview", "Observation", "Idea" with pre-set tags
- [ ] Environmental audio classification (bird species, music BPM, etc.)
- [ ] Batch re-processing (re-transcribe old recordings with improved models)
- [ ] Recording sharing via signed B2 URLs

---

## 11. Key Implementation Files

### New files to create

```
device/screens/panels/recording_active.py   — full-screen recording UI
device/screens/panels/recording_browser.py  — scrollable recordings list
device/screens/panels/recording_detail.py   — playback + summary + transcript
device/audio/field_recorder.py              — long-form recording engine (extends recorder.py)
device/ui/panels/record_preview.py          — sidebar preview panel for RECORD

server/workers/transcription_worker.py      — background Deepgram/Whisper processing
server/workers/analysis_worker.py           — background Haiku analysis
server/workers/sync_worker.py               — B2 cloud sync
server/routes/recordings.py                 — FastAPI recording endpoints
```

### Existing files to modify

```
device/ui/components/sidebar.py             — add "RECORD" to ITEMS list
device/ui/panel_registry.py                 — register record preview panel
device/storage/repository.py                — add recordings table + FTS5
device/main.py                              — wire recording screens to nav
server/main.py                              — mount recording routes + start workers
server/perception.py                        — add field_recording intent (Phase D)
```

---

## 12. Open Questions

1. **Max recording duration?** — SD card can handle hours, but transcription cost scales linearly. Suggest 30-minute soft cap with "extend" option.

2. **Audio quality settings?** — Default 16kHz mono is fine for voice. Should we offer 48kHz stereo for environmental/music recordings? Higher quality = more storage + slower transcription.

3. **Recording while locked?** — Should there be a quick-record gesture from the lock screen? (e.g., triple-press from lock = start recording). Would reduce friction significantly.

4. **Privacy indicators** — When recording in public, should the device show a visible indicator (RGB LED red) that recording is active? Important for social/legal context.

5. **Integration with ai-agent-env?** — The existing consciousness/memory system could benefit from field recordings as input. How tightly should this integrate? Suggest: loosely coupled via FTS5 search for now, deeper integration when Global Workspace ships.

---

## Sources

- [Plaud Note Pro Review (TechCrunch)](https://techcrunch.com/2025/12/29/plaud-note-pro-is-an-excellent-ai-powered-recorder-that-i-carry-everywhere/)
- [Plaud.ai](https://www.plaud.ai/)
- [Best Voice-to-Notes Apps 2026](https://voicetonotes.ai/blog/best-voice-to-notes-app/)
- [Best Speech-to-Text APIs 2026 (Deepgram)](https://deepgram.com/learn/best-speech-to-text-apis-2026)
- [AssemblyAI vs Deepgram vs Whisper 2026](https://www.index.dev/skill-vs-skill/ai-whisper-vs-assemblyai-vs-deepgram)
- [Top Speaker Diarization Libraries (AssemblyAI)](https://www.assemblyai.com/blog/top-speaker-diarization-libraries-and-apis)
- [whisper.cpp Performance on Raspberry Pi (ACM)](https://dl.acm.org/doi/10.1145/3769102.3774244)
- [whisper.cpp Benchmark Results](https://github.com/ggml-org/whisper.cpp/issues/89)
- [Mem.ai AI Note-Taking Guide](https://get.mem.ai/blog/best-ai-note-taking-apps-2025)
- [Offline-First Mobile Architecture (Medium)](https://medium.com/@mkaomwakuni/designing-a-robust-offline-first-mobile-architecture-with-background-sync-a19f7a66b5c3)
- [Best Android Voice Recording Apps 2026](https://zackproser.com/blog/best-android-voice-recording-apps-2026)
- [Notta Memo Hardware](https://www.notta.ai/en/hardware/memo)
