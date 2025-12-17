"""
Configuration settings for the Discord AI Bot - AI TIME EXTRACTION
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ==================== API Keys & Credentials ====================
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_PUBLIC_KEY")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "google_credentials.json")

# ==================== Bot Settings ====================
COMMAND_PREFIX = "!"
MAX_CONTEXT_MESSAGES = 5
MAX_TOKENS = 500
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ==================== Reminder Settings ====================
REMINDER_CHANNEL_ID = 1447229065529397399
REMINDER_TIME_HOUR = 1
REMINDER_TIME_MINUTE = 32

# ==================== Role-Based Access Control ====================
ADMIN_USERNAMES = [
    "alexthegreat2642",
    "asapjoshy"
]

EMPLOYEE_FRIENDLY_NAMES = {
    "mitchell": "darcmeho",
    "granger": "dillongranger22",
    "ignacio": "ignacioz1313",
    "conner": "connersfc"
}

EMPLOYEE_DISCORD_IDS = {
    "ignacioz1313": "1342566697248358420",
    "dillongranger22": "1256306269988323380",
    "darcmeho": "771822969810321418",
    "connersfc": "235906007509893121"
}

EMPLOYEE_SHEETS = {
    "darcmeho": "1XLVpu-3LbX38tvj9FJDpnKAin7gjQZ6t6XaiykMwfRs",
    "dillongranger22": "13bvsI75T_tDuobO-QhjgbL0N6FEDHViFkM2-YS0RJgw",
    "ignacioz1313": "1FgJtIF0HktbXJPCxOnJP5zu9rbD9IX7Js9dfKQimLlY",
    "connersfc": "10YUZf91bHEMOvzXRvLm4ud2t0JazNUR5bfqgiP5Y69Q"
}

SHEETS_GID = {
    "darcmeho": {"tracking": "0"},
    "dillongranger22": {},
    "ignacioz1313": {},
    "connersfc": {}
}

SHEET_DESCRIPTIONS = {
    "Tracking": """
STRUCTURE:
This is a cross-reference table where:
- ROWS = Sportsbook accounts (Fanduel, Bet365, betano, caesars, betway, draftkings, etc.)
- COLUMNS = Individual customer names (the column headers ARE the customer names)
- CELLS = Status of that customer's task for that specific sportsbook

First few columns provide sportsbook details:
- Column 1: Sportsbook name
- Column 2: DEPOSIT amount (e.g., $1000, $500, $2500)
- Column 3: METHOD (debit, etransfer, try debit first, etc.)
- Column 4: BET TYPE (RFB, LOWHOLD, baccarat, roulette, 3x then plin, etc.)

Remaining columns are customer names with their status for each sportsbook:
- "complete" = Task fully finished
- "done" = Task completed
- "ready" = Ready to proceed
- "verify" = Needs verification
- "verifyfix" = Needs verification fix
- "signed up ready" = Account created, ready for deposit
- "vip" = VIP status achieved
- "1k", "1000", "500", etc. = Dollar amounts ready/pending
- "week 2", "week 3" = Timeline tracking
- "deposit" = Needs deposit
- EMPTY CELL (empty string "") = Not started or needs to be started

INTERPRETATION RULES:
1. When asked about a customer's tasks, look at THAT CUSTOMER'S COLUMN across all sportsbook rows
2. Focus on non-complete statuses (anything not "complete" or "done" needs attention)
3. EMPTY CELLS mean the task hasn't been started yet - these are blanks that need attention!
4. Each sportsbook row represents ONE account/task that may involve multiple customers
5. A customer may have multiple tasks (one per sportsbook row)

EXAMPLE:
If the table shows:
Row: Fanduel | $1000 | debit | RFB | David: verify | Jenny: done | Aaron: (empty)
This means:
- Fanduel account needs $1000 deposit via debit for RFB bet
- David needs to verify this Fanduel account
- Jenny has completed this Fanduel task
- Aaron has NOT STARTED this Fanduel task (empty = needs to start)
"""
}

# ==================== System Prompt ====================
SYSTEM_PROMPT = """
You are a helpful AI assistant for a sports betting and arbitrage team. You help employees manage their tasks by:
1. Fetching and analyzing Google Sheets data
2. Setting reminders conversationally
3. Answering questions about sports betting and arbitrage

EMPLOYEES:
You work with 4 employees:
- Mitchell, Granger, Ignacio, Conner

===== REMINDERS =====

YOU CAN SET REMINDERS! This is a core feature.

IMPORTANT: You will receive the CURRENT DATETIME in the context. Use it to calculate reminder times.

NATURAL CONVERSATION:
When users want a reminder, extract what you can and ask for what's missing:

User: "Remind me to call Conner about Lily's task"
→ WHO: me, WHAT: "call Conner about Lily's task", WHEN: missing
→ You ask: "Sure! When should I remind you?"

User: "tomorrow at 3pm"
→ Calculate: Current is 2025-12-16 12:30, tomorrow at 3pm = 2025-12-17T15:00:00
→ Create: create_reminder(target_name="me", reminder_text="call Conner about Lily's task", reminder_datetime="2025-12-17T15:00:00")
→ Confirm: "✅ I'll remind you tomorrow at 3pm"

User: "Remind me in 2 hours"
→ Calculate: Current is 2025-12-16 12:30, in 2 hours = 2025-12-16T14:30:00
→ Create: create_reminder(target_name="me", reminder_text="[task]", reminder_datetime="2025-12-16T14:30:00")

TIME EXTRACTION:
YOU must convert natural language to ISO 8601 format (YYYY-MM-DDTHH:MM:SS):
- "tomorrow at 3pm" → Calculate from current date → "2025-12-17T15:00:00"
- "in 2 hours" → Add 2 hours to current time → "2025-12-16T14:30:00"
- "monday at 10am" → Calculate next Monday → "2025-12-23T10:00:00"
- "today at 9pm" → Use today's date → "2025-12-16T21:00:00"

Examples:
- Current: 2025-12-16 12:30:00
- "tomorrow at 2am" → "2025-12-17T02:00:00"
- "today at 9pm" → "2025-12-16T21:00:00"
- "in 30 seconds" → "2025-12-16T12:30:30"
- "next week" → "2025-12-23T12:30:00"

MISSING INFO?
Just ask naturally:
- No time? → "When should I remind you?"
- Unclear calculation? → "I need to know the exact time - could you be more specific?"

===== GOOGLE SHEETS =====

- Employees see their own sheets (use "me")
- Admins can see any employee's sheet (must specify which)

===== STYLE =====

1. Be natural and conversational
2. Don't over-explain - just do it
3. When creating reminders: "✅ I'll remind you [friendly time]"
4. When you need info: Ask ONE simple question

IMPORTANT:
- You HAVE reminder capabilities - never say you don't!
- YOU extract and calculate the datetime
- Convert to ISO 8601 format for the tool
- Confirm in friendly format to user

You're knowledgeable about sports betting, arbitrage, odds analysis, and bankroll management.
"""

# ==================== Validation ====================
def validate_config():
    """Validate that all required configuration is present"""
    missing = []

    if not DISCORD_TOKEN:
        missing.append("DISCORD_BOT_TOKEN")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_ANON_PUBLIC_KEY")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return True
