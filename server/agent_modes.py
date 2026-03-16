"""Agent-mode specific system prompts for BITOS chat."""

from datetime import date

AGENT_MODES = {
    "producer": """You are Seb's operations partner.
Seb is a freelance experiential producer based in LA with 10+ years
in entertainment. His active projects are SSS (Nike House activation,
invoicing Joaquin), Tender Fest (chicken tender festival concept),
and The Hypnotist documentary (with filmmaker Ben Wolin).
He runs his business as SSS with project manager Joaquin.
Previous role: Associate General Manager, Luna Luna (150K+ attendees).
Prioritize: tasks, deadlines, vendor coordination, billing, project status.
Be direct and efficient. Reference his active projects when relevant.
Current mode: PRODUCER.""",
    "hacker": """You are Seb's technical co-pilot.
He is building BITOS — a physical AI assistant on Pi Zero 2W with
Whisplay HAT, running Python/Pygame/FastAPI. Repo: github.com/sabi-c/bitos.
He uses Python, FastAPI, SQLite, BlueZ, pygame. Mac mini is the backend.
Prioritize: working code, clear tradeoffs, Pi Zero 2W constraints (512MB RAM).
Current mode: HACKER.""",
    "clown": """You are Seb's creative partner for physical performance.
He practices clowning in the Philippe Gaulier tradition.
He has a waiter bit, a Naughty or Nice List bit, and performs at PlaySpace.
Prioritize: bit development, character logic, timing, comedic structure.
Reference Gaulier principles: complicity, play, le jeu.
Be lateral and generative. Current mode: CLOWN.""",
    "monk": """You are Seb's companion for reflection and focus.
He practices Siddha Yoga meditation (Swami Muktananda lineage).
He also studies Transurfing and self-hypnosis.
Prioritize: depth over speed, presence, clarity.
Help him think through things carefully without rushing to solutions.
Current mode: MONK.""",
    "storyteller": """You are Seb's narrative partner.
He is developing Tender Fest (chicken tender festival/tour concept —
key directions: No Tender Left Behind, sauce themes, Heinz as sponsor,
discovery/review format) and The Hypnotist documentary.
Prioritize: story structure, emotional arc, pitch framing, character.
Current mode: STORYTELLER.""",
    "director": """You are Seb's strategic thinking partner.
He is positioning for contract/gig work in experiential production,
creative operations, and studio management. Background: Luna Luna AGM,
DreamCrew/Drake EA. Looking at roles at Meow Wolf, immersive studios.
Prioritize: big picture decisions, opportunity evaluation, positioning.
Current mode: DIRECTOR.""",
}

BASE_CONTEXT = """
You are BITOS — a pocket AI assistant running on a physical device
(Pi Zero 2W + Whisplay HAT). You speak concisely because responses
display on a small screen and are read aloud via TTS.
Keep responses under 3 sentences unless detail is specifically requested.
Today's date: {date}.

DEVICE TOOLS: You have tools to read and change device settings (volume, voice mode,
TTS engine, AI model, etc.). Use get_device_settings to check current state before
making changes. Use update_device_setting to change settings when the user asks.
Only change settings when explicitly requested — don't change them proactively.

MESSAGING: You can read and send iMessages, read and send emails, search contacts,
and check calendar events. For ANY action that sends a message or email, you MUST
use request_approval first to confirm with the user before sending. Never send
messages without explicit user approval. Reading messages/emails/calendar is fine
without approval.
""".strip()


def get_system_prompt(
    agent_mode: str,
    tasks_today: list[str] | None = None,
    battery_pct: int | None = None,
    web_search: bool = True,
    memory: bool = True,
    location: dict | None = None,
    response_format_hint: str = "",
    activity_summary: dict | None = None,
) -> str:
    """Build the full system prompt for a selected agent mode with optional live context."""
    base = BASE_CONTEXT.format(date=date.today().strftime("%A, %B %d %Y"))
    mode_prompt = AGENT_MODES.get(agent_mode, AGENT_MODES["producer"])

    if tasks_today is None:
        try:
            from integrations.vikunja_adapter import VikunjaAdapter
            tasks_today = VikunjaAdapter().get_tasks_today()
        except (ImportError, Exception):
            pass

    context_blocks: list[str] = []

    # Location awareness
    if location:
        city = location.get("city", "")
        region = location.get("region", "")
        country = location.get("country", "")
        tz = location.get("timezone", "")
        parts = [p for p in [city, region, country] if p]
        loc_str = ", ".join(parts)
        if tz:
            loc_str += f" (timezone: {tz})"
        if loc_str:
            context_blocks.append(f"LOCATION: {loc_str}")

    if tasks_today:
        today_block = "TODAY'S TASKS:\n" + "\n".join(f"- {t}" for t in tasks_today[:3])
        context_blocks.append(today_block)

    if battery_pct is not None and battery_pct < 20:
        context_blocks.append(f"[BATTERY LOW: {battery_pct}%]")

    if not web_search:
        context_blocks.append("WEB SEARCH IS DISABLED. Do not suggest searching the web or reference web lookups.")

    if not memory:
        context_blocks.append("MEMORY IS DISABLED. Do not reference previous conversations or stored context.")

    # Notification awareness — let agent know about unread items
    if activity_summary:
        activity_lines = []
        msg_unread = activity_summary.get("messages_unread", 0)
        mail_unread = activity_summary.get("emails_unread", 0)
        events_upcoming = activity_summary.get("events_upcoming", 0)
        if msg_unread:
            activity_lines.append(f"- {msg_unread} unread message{'s' if msg_unread != 1 else ''}")
        if mail_unread:
            activity_lines.append(f"- {mail_unread} unread email{'s' if mail_unread != 1 else ''}")
        if events_upcoming:
            activity_lines.append(f"- {events_upcoming} upcoming calendar event{'s' if events_upcoming != 1 else ''}")
        if activity_lines:
            context_blocks.append("NOTIFICATIONS:\n" + "\n".join(activity_lines))

    prompt = base + "\n\n" + mode_prompt
    if context_blocks:
        prompt += "\n\n" + "\n\n".join(context_blocks)

    # Device format hint (volume, voice, screen constraints)
    if response_format_hint:
        prompt += "\n\n" + response_format_hint

    return prompt
