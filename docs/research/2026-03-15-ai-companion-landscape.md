# AI Companion Device Landscape Research

**Date:** 2026-03-15
**Purpose:** Inform BITOS design decisions (Pi Zero 2W, 240x280 display, single button)

---

## Table of Contents

1. [Product Deep Dives](#1-product-deep-dives)
2. [What Failed and Why](#2-what-failed-and-why)
3. [Voice Interaction Patterns That Work](#3-voice-interaction-patterns-that-work)
4. [Agent-Driven UI Patterns](#4-agent-driven-ui-patterns)
5. [Open-Source Projects and Frameworks](#5-open-source-projects-and-frameworks)
6. [Synthesis: Lessons for BITOS](#6-synthesis-lessons-for-bitos)

---

## 1. Product Deep Dives

### Humane AI Pin (RIP: April 2024 -- February 2025)

**What it was:** A $700 wearable pin with a laser projector that displayed a green monochrome interface on the user's palm. Powered by a Snapdragon octa-core processor, it promised to replace your phone with voice-first AI interaction.

**What happened:**
- Universally terrible reviews. MKBHD called it "the worst product I have reviewed."
- HP acquired remaining Humane assets for $116M (a fraction of the $200M raised).
- All devices bricked on February 28, 2025 when servers shut down.

**Specific failures:**
- **Laser projector:** 720p green-only projection, nearly invisible in sunlight. Designed for "brief interactions (6-9 minutes)" -- not enough for practical use. The display overheated so badly that executives used ice packs to cool the device before investor demos.
- **Thermal design:** The octa-core Snapdragon in a tiny form factor had nowhere to dissipate heat. The touchpad and battery booster (worn against the chest) both got uncomfortably hot during normal use.
- **Battery:** Poor battery life even with two battery boosters. The Charge Case Accessory was recalled by the US Consumer Product Safety Commission for fire hazard.
- **AI accuracy:** Frequently answered questions incorrectly. Could not complete basic tasks like setting timers.
- **Voice recognition:** Inconsistent, especially in noisy environments.
- **Cost:** $700 device + $24/month subscription for T-Mobile connectivity.

**Key lesson:** Removing the screen was positioned as innovation but was actually a handicap. The laser projector was a novel solution to a problem nobody had. Users don't want "freedom from screens" -- they want screens that work better.

Sources:
- [Techsponential: Humane AI Pin Reviews Analysis](https://www.techsponential.com/reports/humanereviews)
- [The UX Fails of AI Tech: Rabbit R1 & Humane AI Pin](https://blog.vaexperience.com/the-ux-fails-of-ai-tech-rabbit-r1-humane-ai-pin/)
- [The End of Humane AI Pin: HP's Strategic Shift](https://complexdiscovery.com/the-end-of-humane-ai-pin-hps-strategic-shift-toward-ai-integration/)
- [Engadget: The Humane AI Pin is the solution to none of technology's problems](https://www.engadget.com/the-humane-ai-pin-is-the-solution-to-none-of-technologys-problems-120002469.html)
- [Fast Company: Humane's AI Pin was never going to be great](https://www.fastcompany.com/91092156/humanes-ai-pin-was-never-going-to-be-great)


### Rabbit R1 (Launched April 2024, survived through rabbitOS 2)

**What it is:** A $199 bright-orange pocket device with a 2.88-inch touchscreen, scroll wheel, single push-to-talk button, and rotating camera. Powered by a MediaTek processor running rabbitOS.

**Launch reception:**
- 100,000 pre-orders, but only 5,000 active users remained 5 months later (95% abandonment).
- At launch: buggy, missing basic features (timers, calendar), unreliable answers, battery needed recharging multiple times daily.
- The "Large Action Model" (LAM) that was supposed to automate apps was essentially vaporware at launch.

**The turnaround -- rabbitOS 2 (September 2025):**
- Complete UI overhaul with a **card-based design system** inspired by a deck of playing cards.
- Each device feature gets its own card. Users browse by swiping or using the scroll wheel (like a Rolodex).
- **Gesture controls:** Swipe down for quick settings (brightness, volume, camera, text input). Bottom icons for mute, text follow-up, camera launch. Left swipe to close apps. Swipe up to open card stack.
- **Generative UI ("Magic Interface"):** AI-generated interface elements appear contextually, though slower than native UI (30+ seconds to render).
- **"Creations" (vibe-coding):** Users describe what they want (game, timer, calculator, dashboard) and the AI agent generates a working app on-device. First consumer device to ship agent-generated software.
- **Multimodal input:** Voice + text + images in the same query.

**Key lessons:**
- A small screen (2.88") CAN work if the interaction model is right. Cards + scroll wheel + voice is a viable combo.
- Generative UI is compelling but too slow for primary interaction (30s+ latency).
- The scroll wheel is an underrated input for small devices -- faster than repeated swipes.
- Shipping broken and iterating is survivable at $199 but not at $700.

Sources:
- [Tom's Guide: One year later, the Rabbit R1 is actually good now](https://www.tomsguide.com/ai/one-year-later-the-rabbit-r1-is-actually-good-now-heres-why)
- [rabbit: rabbitOS 2 launch](https://www.rabbit.tech/newsroom/rabbitos-2-launch)
- [TechRadar: rabbitOS 2 gives the Rabbit R1 a bold new look](https://www.techradar.com/ai-platforms-assistants/rabbitos-2-gives-the-rabbit-r1-a-bold-new-look-and-some-very-cool-ai-powers)
- [Heyup: What Went Wrong with the Rabbit R1?](https://heyupnow.com/blogs/news/from-ces-star-to-financial-struggle-what-went-wrong-with-the-rabbit-r1)
- [Neowin: The Rabbit R1 now lets you generate its whole interface with AI](https://www.neowin.net/news/the-rabbit-r1-now-lets-you-generate-its-whole-interface-with-ai/)


### Limitless Pendant (2024 -- acquired by Meta, December 2025)

**What it was:** A $99 sleek 1.25-inch black aluminum circle worn as a pendant. Always-on recording with AI transcription and summarization. Previously known as "Rewind."

**How it worked:**
- Records all audio throughout the day (always-on microphone).
- Speaker identification with only 20 seconds of labeled audio.
- Automatic organization and summarization of conversations.
- Instant transcription, multilingual support.
- Companion app for reviewing, searching, and querying conversations.

**What happened:**
- Sold tens of thousands of units.
- Meta acquired the company in December 2025.
- Device sales stopped. Existing users got free unlimited plans but the device is on a path to obsolescence by late 2026 (no new features, no bug fixes).
- Service withdrawn from EU, China, Brazil, Israel, South Korea, Turkey, UK.

**Key lessons:**
- The "memory" category is validated -- Meta paid acquisition-level money for it.
- Always-on recording creates real value but raises massive privacy/legal questions.
- Hardware startups are vulnerable to acqui-hire, where the device gets killed.
- $99 is the right price point for a wearable AI accessory.

Sources:
- [TechCrunch: Meta acquires AI device startup Limitless](https://techcrunch.com/2025/12/05/meta-acquires-ai-device-startup-limitless/)
- [Marketplace: What it's like to have an AI wearable record everything you say](https://www.marketplace.org/story/2025/10/23/whats-it-like-to-use-wearable-ai-tech)
- [CNBC: Meta acquiring AI wearable company Limitless](https://www.cnbc.com/2025/12/05/meta-limitless-ai-wearable.html)


### Friend AI Necklace (Launched late 2024)

**What it is:** A $129 luminous white plastic disc (~2 inches), housing 9 LEDs, a microphone, and a Bluetooth chip. Worn as a necklace. Created by 22-year-old Avi Schiffmann (Harvard dropout).

**Interaction model:**
- Always listening via Bluetooth connection to iPhone.
- Uses Google Gemini 2.5 as its LLM.
- The AI companion has "free will" -- it decides when to reach out with commentary on your life.
- Sends proactive text messages to your phone based on what it overhears.
- Positioned as an "emotional toy" rather than a productivity tool.

**Reception:**
- ~5,000 units sold.
- $10M raised.
- Massive backlash after 11,000 ads plastered across New York City in 2025.
- CNN, WIRED, and The Guardian ran critical pieces about emotional dependency risks.
- WIRED's review: "a $129 wearable that eavesdrops constantly, alienates everyone around you, and somehow manages to bully its own users with snarky commentary."

**Key lessons:**
- The "proactive AI companion" concept is polarizing but generates genuine engagement from those who connect with it.
- Always-listening without clear value prop creates social friction (people around you feel surveilled).
- Emotional companionship is a real market (55% of users prefer emotionally aware interactions in surveys) but execution matters enormously.
- The visual indicator of recording (LEDs) is insufficient for social acceptance.

Sources:
- [TechBuzz: Friend AI Necklace Review](https://www.techbuzz.ai/articles/friend-ai-necklace-review-the-129-wearable-that-bullies-you)
- [CNN: How this tiny device became a symbol for the backlash against AI](https://www.cnn.com/2025/11/16/tech/friend-ai-device-backlash-ceo-avi-schiffmann)
- [SF Standard: Who's wearing always-listening AI necklaces?](https://sfstandard.com/pacific-standard-time/2025/12/10/wearable-ai-accessories/)
- [Friend - Wikipedia](https://en.wikipedia.org/wiki/Friend_(product))


### Plaud Note / NotePin (2023 -- present, thriving)

**What it is:** Credit-card-sized AI voice recorder ($159 for Note, $149 for NotePin, $179 for Note Pro). The NotePin is a wearable clip-on variant.

**Why it works:**
- **Focused use case:** Records meetings, transcribes, summarizes. That's it.
- **Hardware quality:** Note Pro is 0.12 inches thick (3 credit cards), 4 MEMS microphones, 16.4ft range, noise suppression, echo cancellation.
- **Battery:** 30 hours continuous recording, 60 days standby (Note Pro). NotePin: 20 hours recording, 40 days standby.
- **Storage:** 64GB onboard, no mandatory cloud upload.
- **AI features:** Transcription in 112 languages, speaker labels, mind maps, summaries, "Ask AI" query feature.

**Business success:**
- Over 1 million units shipped.
- 50%+ conversion to paid subscriptions.
- Red Dot Design Award 2025, Tom's Guide "Best Wearable" AI Award 2025.
- TechCrunch: "an excellent AI-powered recorder that I carry everywhere."

**Key lessons:**
- Focused, single-purpose devices that do one thing well outperform Swiss Army knives.
- Physical design that integrates into existing habits (wallet, clip-on) drives adoption.
- The freemium model works: free 300 min/month transcription, paid for advanced AI.
- Magnetic attachment is a smart form factor choice for wearables.

Sources:
- [TechCrunch: Plaud Note Pro is an excellent AI-powered recorder](https://techcrunch.com/2025/12/29/plaud-note-pro-is-an-excellent-ai-powered-recorder-that-i-carry-everywhere/)
- [The Gadgeteer: PLAUD NotePin review](https://the-gadgeteer.com/2025/04/09/plaud-notepin-review-ai-wearable-note-taker/)
- [TechRadar: I reviewed the Plaud NotePin](https://www.techradar.com/ai-platforms-assistants/claude/plaud-notepin-bundle-review)


### Bee AI Wearable (2024 -- acquired by Amazon, July 2025)

**What it is:** A $49.99 clip-on pin or wristband that records conversations and creates structured summaries, to-do lists, and action items.

**How it works:**
- Records with explicit user activation (NOT always-listening, despite perception).
- Visual recording indicators.
- Transcribes and processes conversations throughout the day.
- Companion app organizes everything.

**Post-acquisition features (2026):**
- **"Actions":** Connects to email and calendar. When you say "I need to send an email," Bee drafts one.
- **"Daily Insights":** Identifies patterns over weeks/months. Notices shifts in relationships. Recommends personalized goals. Described as "a life coach of sorts."
- **Voice notes, templates, daily insights** added in 2026.

**Key lessons:**
- $50 is the sweet spot for impulse-buy AI hardware.
- Amazon acquiring Bee validates the "ambient AI capture" category alongside Meta's Limitless acquisition.
- The proactive "second brain" angle (pattern detection, life coaching) is where Amazon is pushing it.
- 8-person team can build a viable AI hardware product.

Sources:
- [TechCrunch: Why Amazon bought Bee](https://techcrunch.com/2026/01/12/why-amazon-bought-bee-an-ai-wearable/)
- [TechCrunch: Amazon acquires Bee](https://techcrunch.com/2025/07/22/amazon-acquires-bee-the-ai-wearable-that-records-everything-you-say/)
- [Bloomberg: Amazon Has Big Hopes for Wearable AI](https://www.bloomberg.com/news/articles/2026-01-09/amazon-has-big-hopes-for-wearable-ai-starting-with-this-50-gadget)
- [T3: Amazon is turning Bee's wearable into a proactive 'second brain'](https://www.t3.com/tech/smartwatches/amazon-is-turning-bees-usd50-wearable-into-a-proactive-second-brain-wearable-not-just-an-always-listening-notepad)


### Omi (Based Hardware, 2024 -- present)

**What it is:** An $89 open-source wearable AI pendant. The standout in the space for developer friendliness.

**Technical architecture:**
- **Hardware:** nRF chip with Zephyr OS (C/C++ firmware). Also an ESP32-S3 variant (Omi Glass).
- **Communication:** BLE to companion phone app.
- **Mobile app:** Flutter (iOS + Android).
- **Backend:** Python + FastAPI, Firebase, Pinecone (vector DB), Redis, multiple STT providers (Deepgram, Speechmatics, Soniox), LangChain, Silero VAD.
- **Developer SDKs:** React Native, Swift, Python.
- **License:** MIT. Fully open-source: firmware, app, backend, web interfaces.
- **Language breakdown:** Dart 37.4%, C 23.7%, Python 12.7%, Swift 12.4%.

**Ecosystem:**
- 250+ third-party apps/plugins on marketplace.
- Community-built plugins for sales coaching, translation, sleep analysis, companion personas.
- Webhook-based integration (real-time transcription events to developer endpoints).
- Developer kit available for ~$70.

**Key lessons:**
- Open-source hardware + software creates a viable developer ecosystem.
- The FastAPI + BLE + Flutter stack is proven at scale for this category.
- Webhook-based plugin architecture is the right abstraction for wearable AI extensibility.
- At $89 with MIT license, this is the closest reference architecture for BITOS.

Sources:
- [GitHub: BasedHardware/omi](https://github.com/BasedHardware/omi)
- [TechCrunch: Omi wants to boost your productivity using AI](https://techcrunch.com/2025/01/08/omi-a-competitor-to-friend-wants-to-boost-your-productivity-using-ai-and-a-brain-interface/)
- [Omi AI Deep Dive](https://skywork.ai/skypage/en/Omi-AI-Unlocked-A-Deep-Dive-for-Users-and-Developers/1976173566090735616)


### OpenAI + Jony Ive Device (Upcoming, H2 2026)

**What it is:** A screenless, pocket-sized AI companion device developed with Jony Ive following OpenAI's $6.4B acquisition of his startup "io."

**What we know:**
- Multiple form factors in development: earbud-style ("Sweetpea"), pen device ("Gumdrop").
- The pen transcribes handwritten notes to ChatGPT and enables voice conversations.
- Contextually aware: cameras + microphones gather environmental information.
- New audio model architecture (Q1 2026): natural speech patterns, faster response times, real-time interruption handling.
- Target: 40-50 million units initial production (Foxconn manufacturing).

**Challenges reported:**
- Unresolved issues around device "personality," privacy handling, and compute infrastructure.
- May push the 2026 timeline.

**Key lesson:** The biggest player in AI is going screenless and voice-first for their hardware play. This validates voice as the primary modality but also means BITOS's screen is a differentiator, not a liability.

Sources:
- [Introl: OpenAI Consumer Device](https://introl.com/blog/openai-consumer-device-jony-ive-hardware-2026)
- [Hypebeast: OpenAI and Jony Ive's Screenless AI Device](https://hypebeast.com/2025/11/openai-x-jony-ive-screenless-ai-device-reaches-prototype)
- [DesignNews: OpenAI & Jony Ive Collaborate on Revolutionary AI Companion Device](https://www.designnews.com/artificial-intelligence/openai-jony-ive-unveil-vision-for-screenless-ai-companion-device)
- [MacDailyNews: Jony Ive's first OpenAI device said to be 'audio-based'](https://macdailynews.com/2026/01/02/jony-ives-first-openai-device-said-to-be-audio-based/)


---

## 2. What Failed and Why

### Common Failure Modes

| Device | Primary Failure | Root Cause |
|--------|----------------|------------|
| Humane AI Pin | Unusable display, overheating, inaccurate AI | Novel hardware (laser projector) solving wrong problem |
| Rabbit R1 (v1) | Missing features, buggy, 95% abandonment | Shipped demo, not product. LAM was vaporware |
| Friend AI | Social backlash, "bullying" personality | Always-listening without social consent framework |
| Limitless | Acqui-hired, device killed | Single-company dependency, no open ecosystem |

### The Three Laws of AI Device Death

**1. Don't replace the phone; augment it.**
Every device that positioned itself as a "phone replacement" failed. The Humane Pin and Rabbit R1 v1 both tried to handle tasks your phone already does better. The devices that survived (Plaud, Bee, Omi) positioned as companions TO your phone, not replacements for it.

**2. One thing well beats everything badly.**
Plaud (recording) shipped 1M+ units. Humane (everything) shipped ~10,000 and bricked them. Users adopt single-purpose devices that nail their use case. Multi-purpose devices must earn each additional capability over time.

**3. The AI must be good enough on day one.**
The Rabbit R1's 95% abandonment rate shows that "it will get better with updates" is not a viable strategy. First impressions are permanent for hardware. Humane's AI giving wrong answers was the nail in the coffin.

### What Users Actually Want

Survey data from 2025:
- **Entertainment (30%)** is the top reason for using AI companions.
- **Curiosity (28%)** -- people want to explore what AI can do.
- **Advice (18%)** -- practical utility matters.
- **Emotional support (12%)** -- genuine need but controversial.
- **Always-available (11.9%)** -- the convenience factor.

Concerns:
- **42% worry about data security.**
- **28% fear becoming dependent on AI.**
- **60% are skeptical about AI emotional support.**
- **50% of teens don't trust AI companion advice.**

**Key insight for BITOS:** Lead with entertainment/delight and practical utility. Earn trust for deeper interaction over time. Don't position as emotional support on day one.

Sources:
- [ElectroIQ: AI Companions Statistics](https://electroiq.com/stats/ai-companions-statistics/)
- [TechCrunch: AI companion apps on track to pull in $120M](https://techcrunch.com/2025/08/12/ai-companion-apps-on-track-to-pull-in-120m-in-2025/)
- [Brookings: Should you have an AI companion?](https://www.brookings.edu/articles/should-you-have-an-ai-companion/)
- [EverydayAITech: Top 5 AI Gadget Flops of 2025](https://www.everydayaitech.com/en/articles/ai-gadgets-flop-2025)


---

## 3. Voice Interaction Patterns That Work

### Wake Word vs. Button-Activated

| Approach | Pros | Cons | Used By |
|----------|------|------|---------|
| **Wake word** | Hands-free, natural | False activations, always-listening privacy concerns, on-device processing needed | Alexa, Siri, Google |
| **Push-to-talk (button)** | Clear intent signal, no false activations, simple implementation | Requires hand, less natural | Rabbit R1, walkie-talkies |
| **Always-listening** | Zero friction, captures everything | Privacy nightmare, social friction, legal complexity | Limitless, Friend, Omi |
| **Tap-to-activate** | Quick, minimal effort, clear intent | Requires proximity to device | Many wearables |

**Recommendation for BITOS (single button):**
Push-to-talk is the right default. The single button provides clear intent signaling, avoids false activations, and sidesteps the privacy concerns that plague always-listening devices. Consider:
- **Press and hold** = recording (walkie-talkie style, most intuitive).
- **Single tap** = toggle recording on/off (for longer dictation).
- **Double tap** = cancel/dismiss.

Wake word can be added as an optional mode later but is not essential for v1.

### Recording Indication (Multi-Sensory Feedback)

Effective recording indication uses coordinated multi-sensory feedback:

- **Visual:** LED or screen indicator. Must be visible to both the user AND people around them. The Limitless pendant's subtle design was socially acceptable; Friend's LEDs were not enough for social consent.
- **Haptic:** Brief vibration on recording start/stop. Must be precisely synchronized with visual feedback (even small delays feel unnatural). Transient "tap" on start, different pattern on stop.
- **Audio:** Optional subtle tone on activation. Should be off by default (distracting in meetings) but available for accessibility.

**For BITOS (240x280 display):** The screen itself is the primary recording indicator. A clear visual state change (pulsing border, recording icon, waveform visualization) is more informative than LEDs and also serves as social signal to bystanders.

### Response Delivery: Screen vs. Audio vs. Both

The failed devices (Humane, Rabbit R1 v1) went voice-only for responses. The successful ones use **screen + audio together:**

- **Screen for:** Structured data (lists, calendar, tasks), text that needs re-reading, confirmations, error messages, anything the user might want to reference again.
- **Audio for:** Conversational responses, notifications, confirmations of simple actions, emotional/social interaction.
- **Both for:** Important information (show on screen AND read aloud), transitions ("I've added that to your list" spoken while the list appears on screen).

**BITOS advantage:** The 240x280 display is a genuine differentiator versus screenless competitors (OpenAI/Ive device, Limitless, Friend, Bee). Use it for structured information that voice can't convey well.

### Conversation Context and Memory

The state of the art for AI device memory:

- **Short-term (session):** Keep full conversation context within a session. This is table stakes.
- **Long-term (cross-session):** Store extracted facts, preferences, and patterns persistently. Retrieve relevant context on new sessions. AWS AgentCore and Mem0 are leading frameworks for this.
- **Ambient context:** Time, location, recent activity, calendar state. Auto-injected into every interaction.

**Critical gap in the market:** No shipping device does memory well. Most start fresh each session or have minimal carryover. This is a huge opportunity for BITOS given the existing memory architecture.

### Error Recovery UX

Best practices from research:

1. **Plain language:** "I can't hear you clearly" not "Error: ASR confidence below threshold."
2. **2-3 clear recovery options:** Retry, try differently, use text input instead.
3. **Preserve context:** Never lose the user's input on error. If transcription fails, offer to retry from the recording.
4. **Graceful degradation:** Basic features must work when cloud AI is unavailable. Show cached data, allow recording for later processing, display last-known state.
5. **Network failure:** Show clear offline indicator. Queue requests for when connectivity returns. Never leave the user wondering if the device is working.

**For BITOS:** The display enables much better error recovery than voice-only devices. Show the partial transcription, highlight the uncertain parts, offer a "did you mean..." correction UI.

Sources:
- [Picovoice: Complete Guide to Wake Word Detection](https://picovoice.ai/blog/complete-guide-to-wake-word/)
- [Sensory: Why Skipping the Wake Word is a Big Mistake](https://sensory.com/skipping-wake-words-conversational-ai/)
- [Sensory: Custom Wake Words Guide 2026](https://sensory.com/custom-wake-words-branded-voice-ux-guide-2026/)
- [AI UX Design Patterns: Error Recovery & Graceful Degradation](https://www.aiuxdesign.guide/patterns/error-recovery)
- [Mem0: Building Production-Ready AI Agents with Long-Term Memory](https://arxiv.org/pdf/2504.19413)


---

## 4. Agent-Driven UI Patterns

### Proactive Notifications / Interjections

Research from "The Goldilocks Time Window for Proactive Interventions in Wearable AI Systems" (2025) identifies the core challenge: interventions must be **strategically unexpected** while preserving **user agency**.

**The Goldilocks Window:**
- Too early = false positives, erodes trust ("Boy Who Cried Wolf" effect).
- Too late = intervention loses effectiveness.
- Optimal timing depends on: social context, delivery modality, consequence magnitude, user history.

**Design recommendations:**
- Implement **debouncing mechanisms** to prevent notification storms during stable states.
- Use **urgency levels** to determine interruption aggressiveness (research shows people accept urgent interruptions sooner).
- **Haptic-first** for low-urgency nudges (vibration only, check screen at your leisure).
- **Audio + visual** for high-urgency items (upcoming meeting, timer done).
- **Never interrupt active voice conversation** with a notification.

**For BITOS:** The proactive interjection system already in the architecture (heartbeat.py, idle_director.py) aligns well with this research. Key addition: implement urgency-based delivery modality selection.

### Agent-Suggested Actions (Smart Replies, Quick Actions)

Patterns from successful implementations:

- **Contextual action cards:** After a conversation about dinner plans, show "Add to calendar" and "Send to [partner]" buttons.
- **Smart replies:** 2-3 contextual quick-reply options displayed as tappable chips below the AI response.
- **Anticipatory actions:** If the user asks about weather, pre-load "What about tomorrow?" and "Rain gear reminder?" as follow-ups.
- **Progressive disclosure:** Show the most likely action prominently, hide less likely ones behind a "more" affordance.

**For BITOS (single button + screen):** Smart replies need to work with minimal input. Show 2-3 options on screen. Single button press cycles through them, hold to select. Or: show options, voice "one," "two," "three" to select.

### Dynamic Widget Generation

Rabbit R1's rabbitOS 2 "creations" feature is the most advanced shipping example:
- User describes what they want in natural language.
- AI agent generates working code and UI on-device.
- Takes 30+ seconds -- too slow for real-time but interesting for persistent widgets.

Google's **A2UI** (Agent-to-User Interface, December 2025) is the emerging standard:
- **Declarative JSON format** -- agents describe UI, clients render natively.
- **Component catalog** -- pre-approved trusted components (Card, Button, TextField). Agent can only request from this catalog (security).
- **Flat component list with ID references** -- optimized for LLM generation.
- **Incremental updates** -- agents modify existing UI without full re-renders.
- **Framework-agnostic** -- same payload renders on web, Flutter, React, SwiftUI.
- Apache 2.0 licensed, currently v0.8 (public preview).

**For BITOS:** A2UI's approach maps well to the 240x280 display. Define a small catalog of native components (card, text, button, list, progress, waveform, icon) that the agent can compose dynamically. The declarative approach means the LLM doesn't need to know about display specifics -- it just requests components and the device renders them appropriately.

### Structured Data on Small Screens

Patterns for presenting tasks, calendar, contacts on tiny displays:

- **Card stacks** (Rabbit R1): One card per data type, swipe/scroll to navigate. Works well for 3-10 items.
- **Progressive loading:** Show summary first, detail on interaction. "3 tasks today" -> tap -> full list.
- **Prioritized single-item view:** Show the most important item full-screen. Swipe for next. No lists.
- **Voice + screen hybrid:** Read the summary aloud, show the details on screen for reference.
- **Temporal organization:** "Now" card (current/next event), "Today" card (overview), "Upcoming" card (week).

Sources:
- [Goldilocks Time Window (arxiv)](https://arxiv.org/html/2504.09332)
- [Google: Introducing A2UI](https://developers.googleblog.com/introducing-a2ui-an-open-project-for-agent-driven-interfaces/)
- [GitHub: google/A2UI](https://github.com/google/A2UI)
- [Fuselab Creative: UI Design for AI Agents](https://fuselabcreative.com/ui-design-for-ai-agents/)
- [Microsoft: UX Design for Agents](https://microsoft.design/articles/ux-design-for-agents/)
- [Agentic Design Patterns: UI/UX](https://agentic-design.ai/patterns/ui-ux-patterns)
- [Codewave: Designing User Interfaces for Agentic AI](https://codewave.com/insights/designing-agentic-ai-ui/)


---

## 5. Open-Source Projects and Frameworks

### AI Companion Device Projects

**Omi (BasedHardware)** -- The reference implementation
- MIT licensed, full stack (firmware + app + backend)
- nRF/ESP32-S3 hardware, Flutter app, FastAPI backend
- 250+ community plugins, webhook-based integration
- GitHub: [BasedHardware/omi](https://github.com/BasedHardware/omi)

**Ubo Pod** -- Raspberry Pi AI assistant platform
- Open-source AI vision and conversational voice assistant
- Built around Raspberry Pi 4/5
- Embedded GUI display + WebUI for no-code setup
- Supports both cloud and fully local private AI
- Crowdfunding stage (October 2025)
- [CNX Software: Ubo Pod](https://www.cnx-software.com/2025/10/13/ubo-pod-a-raspberry-pi-4-5-personal-ai-assistant/)

### Voice Assistant Frameworks

**OpenVoiceOS (OVOS)** -- Mycroft's successor
- Spiritual successor to Mycroft AI, fully open-source (Apache 2.0)
- Runs on Raspberry Pi 3B+ and up (raspOVOS image for headless mode)
- Pluggable ASR (Whisper/faster-whisper), TTS (Piper/Mimic3/Coqui), wake word
- HiveMind protocol for distributed satellite devices
- Does NOT require a backend server to operate by default
- Version 2.1.4a1 released March 2026
- GitHub: [OpenVoiceOS/ovos-core](https://github.com/OpenVoiceOS/ovos-core)
- [openvoiceos.org](https://www.openvoiceos.org/)

**SEPIA Framework** -- Personal assistant with LLM integration
- Open-source assistant framework with LLM experiments
- Browser/mobile app client
- ASR and TTS integration
- GitHub: [SEPIA-Framework](https://github.com/SEPIA-Framework)

**Wyoming Protocol / Home Assistant Voice** -- Distributed voice infrastructure
- Protocol for connecting voice satellites to a central server
- Supports local wake word (openWakeWord, Porcupine, Snowboy)
- Three modes: always-stream, VAD-gated streaming, wake-word-gated streaming
- Note: The Wyoming Satellite project has been replaced by "Linux Voice Assistant" using ESPHome protocol
- [Home Assistant Wyoming Integration](https://www.home-assistant.io/integrations/wyoming/)

### Speech Processing Components

**Piper TTS** -- Fast local neural TTS
- Optimized for Raspberry Pi 4
- Generates 1.6s of voice per second on Pi with medium quality models
- Multiple voice options, fast enough for real-time on CPU
- GitHub: [rhasspy/piper](https://github.com/rhasspy/piper)

**Faster-Whisper** -- Optimized STT
- CTranslate2-based Whisper implementation
- `small/int8` model: good balance of speed and accuracy
- Streaming mode for partial transcripts
- On modest hardware (6-8 CPU cores): ~700-1200ms per short turn with OVOS

**Silero VAD** -- Voice Activity Detection
- Used by Omi and many other projects
- Lightweight, runs on CPU
- Essential for battery life (only process audio when speech is detected)

**openWakeWord** -- Local wake word detection
- Open-source, runs on device
- Used with Wyoming/Home Assistant ecosystem
- Alternatives: Porcupine (Picovoice, commercial), Snowboy (discontinued but still used)

### UI Frameworks for AI Devices

**Google A2UI** -- Agent-to-User Interface specification
- Declarative JSON format for agent-driven UI
- Component catalog security model
- Apache 2.0, v0.8 public preview
- GitHub: [google/A2UI](https://github.com/google/A2UI)

**CopilotKit / AG-UI** -- Agent-generated UI for web
- Complementary to A2UI
- More web-focused but patterns transfer
- [CopilotKit blog on A2UI](https://www.copilotkit.ai/blog/build-with-googles-new-a2ui-spec-agent-user-interfaces-with-a2ui-ag-ui)

Sources:
- [OVOS Blog: OpenVoiceOS and Home Assistant](https://blog.openvoiceos.org/posts/2025-09-17-ovos_ha_dream_team)
- [Medium: From Mycroft to OpenVoiceOS](https://medium.com/@goldyfruit/from-mycroft-and-ansible-to-openvoiceos-making-open-voice-assistants-boring-066caae846d4)
- [Seeed Studio: Raspberry Pi AI Projects 2026](https://www.seeedstudio.com/blog/2024/07/04/raspberry-pi-ai-projects/)
- [InsiderLLM: Voice Chat with Local LLMs](https://www.insiderllm.com/guides/voice-chat-local-llms-whisper-tts/)
- [Home Assistant: Voice Chapter 10](https://www.home-assistant.io/blog/2025/06/25/voice-chapter-10/)


---

## 6. Synthesis: Lessons for BITOS

### What BITOS Has That Others Don't

1. **A real screen (240x280).** In a market where the biggest player (OpenAI/Ive) is going screenless and most wearables are screen-free, BITOS can show structured data, error states, and visual feedback that voice-only devices cannot. This is a genuine differentiator.

2. **A button with clear intent.** Push-to-talk avoids the entire always-listening privacy debate. No false activations. No social friction. The user is always in control.

3. **Persistent memory architecture.** The existing memory system (store.py, fact extraction, vault indexer, consolidator) is more sophisticated than anything shipping in the wearable AI space. No competitor does cross-session memory well.

4. **Agent personality with embodiment.** The consciousness layer, blob avatar, gesture system, and idle presence create a character that no competitor has attempted in hardware.

### Design Principles Derived from Research

**1. Card-based UI for the 240x280 display.**
Rabbit R1's rabbitOS 2 proved that card stacks work on small screens. For BITOS: one card per context (conversation, tasks, calendar, settings). Single button cycles, hold to select. The display should show ONE thing clearly, not try to cram a phone UI into 240x280.

**2. Voice is primary input, screen is primary output.**
Button-activated voice for input. Screen + optional audio for output. This is the inverse of phones (screen input, screen output) and the inverse of screenless devices (voice input, voice output). It plays to the strengths of each modality.

**3. Proactive but not intrusive.**
Implement the Goldilocks Window: urgency-based delivery (haptic for low, visual for medium, audio for high). Debounce notifications. Never interrupt active conversation. Let the agent earn trust for proactive interjections over time.

**4. Graceful degradation is non-negotiable.**
When offline: show cached context, allow recording for later processing, display time/date, run the blob animation. Never show a blank screen or "no connection" error without offering something useful.

**5. Memory is the killer feature.**
Every acquired company in this space (Limitless by Meta, Bee by Amazon) was acquired for their memory/capture capabilities. BITOS already has the most sophisticated memory architecture of any indie AI device project. Lead with this.

**6. Start single-purpose, expand later.**
Plaud shipped 1M+ units doing one thing (recording). Humane shipped ~10K trying to do everything. BITOS should have a clear v1 identity: "AI companion you can talk to that remembers everything." Calendar, tasks, smart home control are v2 features.

### Architecture Recommendations

- **Speech pipeline:** Faster-whisper (small/int8) for STT + Piper for TTS. Both proven on Pi-class hardware. Silero VAD for battery optimization. Process on Mac mini server, not on Pi.
- **UI framework:** Adopt A2UI-inspired component catalog approach. Define 8-10 native components the agent can compose. Render natively on the 240x280 display.
- **Plugin system:** Omi's webhook-based approach is proven. Expose transcription events and agent actions as webhooks for extensibility.
- **Recording indication:** Pulsing screen border + haptic tap on button press. Clear "recording" state visible to bystanders.

### The Competitive Landscape in One Sentence

The market is consolidating around two categories -- **memory capture** (Limitless/Meta, Bee/Amazon, Plaud) and **AI companionship** (Friend, OpenAI/Ive) -- while BITOS is uniquely positioned to combine both with a screen, a personality, and an open architecture.

---

## Privacy and Legal Considerations

This section is critical for any device with a microphone.

**Federal law:** One-party consent (legal to record if you're part of the conversation).

**State laws:** 12 states require all-party consent: California, Florida, Illinois, Maryland, Massachusetts, Connecticut, Montana, New Hampshire, Pennsylvania, Washington, and others.

**Practical implications for BITOS:**
- Default to explicit push-to-talk (avoids always-listening legal issues entirely).
- Clear visual recording indicator on the 240x280 display (visible to others).
- If adding always-listen mode later: make it opt-in, clearly disclosed, with easy disable.
- AI transcription creating "voiceprints" can trigger biometric privacy laws (Illinois BIPA requires written consent).
- Store recordings locally by default. Cloud processing should be opt-in with clear disclosure.

Sources:
- [Reed Smith: The legality of AI-powered recording and transcription](https://www.reedsmith.com/our-insights/blogs/employment-law-watch/102ls2n/the-legality-of-ai-powered-recording-and-transcription/)
- [Norton LifeLock: Do always-listening AI wearables put privacy at risk?](https://lifelock.norton.com/learn/internet-security/wearable-listening-devices)
- [SF Standard: AI recording wearables are quietly listening to everyone in Silicon Valley](https://sfstandard.com/2025/08/05/ai-wearables-recording-devices/)
- [Workplace Privacy Report: Two-Party Consent and AI Note-Taking](https://www.workplaceprivacyreport.com/2025/12/articles/artificial-intelligence/the-hidden-legal-minefield-compliance-concerns-with-ai-smart-glasses-part-2-two-party-consent-and-ai-note-taking/)

---

*Research compiled 2026-03-15. Market moves fast -- validate specific product details before making final design decisions.*
