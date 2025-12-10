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
