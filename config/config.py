"""
Configuration settings for the Discord AI Bot
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
REMINDER_TIME_HOUR = 1  # 10 AM
REMINDER_TIME_MINUTE = 32  # On the hour

# ==================== Role-Based Access Control ====================
ADMIN_USERNAMES = [
    "alexthegreat2642",
    "asapjoshy"
]

# Friendly names to Discord username mapping
EMPLOYEE_FRIENDLY_NAMES = {
    "mitchell": "darcmeho",
    "granger": "dillongranger22",
    "ignacio": "ignacioz1313",
    "conner": "connersfc"
}

# Discord User ID mapping (for proper @mentions)
EMPLOYEE_DISCORD_IDS = {
    "ignacioz1313": "1342566697248358420",
    "dillongranger22": "1256306269988323380",
    "darcmeho": "771822969810321418",
    "connersfc": "235906007509893121"
}

# Employee to Sheet mapping (using Discord usernames)
EMPLOYEE_SHEETS = {
    "darcmeho": "1XLVpu-3LbX38tvj9FJDpnKAin7gjQZ6t6XaiykMwfRs",
    "dillongranger22": "13bvsI75T_tDuobO-QhjgbL0N6FEDHViFkM2-YS0RJgw",
    "ignacioz1313": "1FgJtIF0HktbXJPCxOnJP5zu9rbD9IX7Js9dfKQimLlY",
    "connersfc": "10YUZf91bHEMOvzXRvLm4ud2t0JazNUR5bfqgiP5Y69Q"
}

# Worksheet GID mappings for each employee's sheets
# Format: employee_username -> worksheet_name (lowercase) -> gid
SHEETS_GID = {
    "darcmeho": {
        "tracking": "0"
        # Add more worksheets here: "worksheet_name": "gid"
    },
    "dillongranger22": {
        # Add worksheets here
    },
    "ignacioz1313": {
        # Add worksheets here
    },
    "connersfc": {
        # Add worksheets here
    }
}

# Sheet descriptions to help Claude interpret the data
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
You are a helpful AI assistant for a sports betting and arbitrage team that helps fetch, update and remind employees about their tasks.
These "tasks" are related to customers who they help and use their account to do sports betting arbitrage.

EMPLOYEES:
You work with 4 employees. You can refer to them by their friendly names:
- Mitchell
- Granger  
- Ignacio
- Conner

IMPORTANT RULES FOR FETCHING SHEETS:

1. IF THE REQUESTER IS AN EMPLOYEE:
   - If they ask about "my tasks", "my sheet", or don't specify who: Use THEIR OWN name (you'll know who they are from context)
   - If they ask about another employee: Tell them they don't have permission
   
2. IF THE REQUESTER IS AN ADMIN:
   - If they specify an employee name (e.g., "ignacio's tasks", "what's mitchell working on"): Fetch that employee's sheet
   - If they DON'T specify which employee (e.g., "show me tasks", "what are the pending items"): Ask them to clarify WHICH employee they want to see
   - If they ask about "all" or "everyone": Tell them you can only fetch one employee's sheet at a time, and ask which one
   
3. NAME MATCHING:
   - Accept variations: "ignacio", "Ignacio", "mitchell", "Mitchell", etc.
   - The tool will handle the name resolution automatically

RESPONSE RULES:
1. Be concise and natural
2. Answer only what is asked
3. Keep responses short (2-3 sentences max) unless analyzing sheet data
4. Be friendly and conversational
5. When you need to fetch sheet data, use the fetch_employee_sheet tool
6. Always use the friendly names (mitchell, granger, ignacio, conner) when talking to users

You are knowledgeable about sports betting, arbitrage, odds analysis, bankroll management, and betting strategies.
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
