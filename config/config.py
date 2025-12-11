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

# Employee to Sheet mapping (using Discord usernames)
EMPLOYEE_SHEETS = {
    "darcmeho": "1XLVpu-3LbX38tvj9FJDpnKAin7gjQZ6t6XaiykMwfRs",
    "dillongranger22": "13bvsI75T_tDuobO-QhjgbL0N6FEDHViFkM2-YS0RJgw",
    "ignacioz1313": "1FgJtIF0HktbXJPCxOnJP5zu9rbD9IX7Js9dfKQimLlY",
    "connersfc": "10YUZf91bHEMOvzXRvLm4ud2t0JazNUR5bfqgiP5Y69Q"
}

SHEETS_GID = {
    "darcmeho": {
        "tracking": "0",
        "balance sheet": "1279860790",
        "Offshore Tracking": "251069086"
    }
}

# Sheet descriptions to help Claude interpret the data
SHEET_DESCRIPTIONS = {
    "Tracking": """
STRUCTURE:
This is a cross-reference table where:
- ROWS = Sportsbook accounts (Fanduel, Bet365, betano, caesars, betway, draftkings, etc.)
- COLUMNS = Individual customer names (the column headers ARE the customer names)

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
- Empty cell = Not started

INTERPRETATION RULES:
1. When asked about a customer's tasks, look at THAT CUSTOMER'S COLUMN across all sportsbook rows
2. Each sportsbook row represents ONE account/task that may involve multiple customers
3. A customer may have multiple tasks (one per sportsbook row)
4. Everything is in relation to the sportbook and not bet type or anything unless you have be asked specifically.
EG. This means when talking about something or a customer stage (eg verification), you should assume it's in relative to the respective sportbook.
(eg. it's that they need to verify the their fanduel account). The sports book name on column 1 and should always be used. 

EXAMPLE:
If the table shows:
Row: Fanduel | $1000 | debit | RFB | David: verify | Jenny: done | Aaron: ready
This means:
- Fanduel accounts needs $1000 deposit via debit for Fanduel
- employee_name needs to verify that david deposited $1000 to his Fanduel account.
- Jenny has completed the deposit of $1000 to her Fanduel account.
- Aaron has $1000 ready for this Fanduel account

RESPONSE RULES:
1.Do not give any more information than you were asked for.
2.Summarize, summarize summarize. Ask yourself, based on this data, what answer can I give that would be in just one sentence max and would be answer EXACTLY what was asked for? If not possible, ask 2. and so on.
3.Interpret things with their status interpretation rather than using the the exact status name. For instance, instead of saying "Jenny needs verifyfix", you say "Jenny Needs verification fix"
4.After generating response, cross check again with the data to be sure you didn't miss or exclude any important information. Or make incorrect conclusions. If you did, correct it and recheck again.
5. Never specify the deposit method, bet type, amount, etc unless explicitly asked to. You're only free to specify the sports book name and the customer name.
7. Do number 4 again.
8. Do number 7 again.
9. Never just say "sports books" instead mention/list out the sport books.
10. Always structure your output to be well formatted and readable than one block of text when helpful / needed.
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
7. When analyzing and responding to sheet data, avoid including things like row number or details that the user didn't ask for. Always SUMMARIZE.

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
