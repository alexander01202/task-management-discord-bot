# Discord AI Task Management Bot - Milestone 2

## 🎯 Overview
AI-powered Discord bot for managing sports betting arbitrage tasks with Google Sheets integration and role-based access control.

## ✨ Features

### Milestone 1 ✅
- ✅ Conversational AI with memory (Claude Sonnet 4)
- ✅ Persistent conversation history (Supabase)
- ✅ Context-aware responses
- ✅ Web search capabilities

### Milestone 2 ✅
- ✅ Google Sheets integration
- ✅ Role-based access control (Admin, Employee, User)
- ✅ Per-employee sheet access
- ✅ Permission-based data access

## 🏗️ Project Structure

```
discord_bot/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
│
├── config/                 # Configuration
│   ├── __init__.py
│   └── config.py          # Settings & environment variables
│
├── database/              # Database operations
│   ├── __init__.py
│   └── database.py        # Supabase interactions
│
├── services/              # External services
│   ├── __init__.py
│   ├── ai_service.py      # Claude API
│   └── google_sheets.py   # Google Sheets API
│
├── handlers/              # Discord event handlers
│   ├── __init__.py
│   ├── message_handler.py # Message processing
│   └── command_handler.py # Bot commands
│
└── utils/                 # Utilities
    ├── __init__.py
    └── permissions.py     # Role-based access control
```

## 📋 Prerequisites

- Python 3.11+
- Discord Bot Token
- Anthropic API Key
- Supabase Account
- Google Cloud Project with Sheets API enabled

## 🚀 Installation

### 1. Clone & Setup

```bash
# Navigate to project directory
cd discord_bot

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Google Sheets API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project or select existing
3. Enable **Google Sheets API**
4. Create **Service Account** credentials
5. Download JSON key file
6. Rename it to `google_credentials.json`
7. Place it in the `discord_bot/` directory
8. Share each Google Sheet with the service account email (found in JSON file)

### 3. Environment Variables

Create `.env` file in `discord_bot/` directory:

```env
# Discord
DISCORD_BOT_TOKEN=your_discord_bot_token

# Anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_PUBLIC_KEY=your_supabase_key

# Google Sheets
GOOGLE_CREDENTIALS_PATH=google_credentials.json
```

### 4. Run the Bot

```bash
python main.py
```

## 👥 Role-Based Access Control

### Roles

| Role | Can Access | Permissions |
|------|-----------|-------------|
| **Admin** | All employee sheets | Full access, can use `!sheet <username>` |
| **Employee** | Own sheet only | Can use `!mysheet` |
| **User** | No sheets | Can chat with bot |

### Admins
- alexthegreat2642
- asapjoshy

### Employees
| Username | Sheet ID |
|----------|----------|
| ignacioz1313 | 1FgJtIF0HktbXJPCxOnJP5zu9rbD9IX7Js9dfKQimLlY |
| dillongranger22 | 13bvsI75T_tDuobO-QhjgbL0N6FEDHViFkM2-YS0RJgw |
| darcmeho | 1XLVpu-3LbX38tvj9FJDpnKAin7gjQZ6t6XaiykMwfRs |
| connersfc | 10YUZf91bHEMOvzXRvLm4ud2t0JazNUR5bfqgiP5Y69Q |

## 💬 Bot Commands

### For Everyone
- `@bot <message>` - Chat with the bot
- `!help` - Show help information

### For Employees & Admins
- `!mysheet` - View your task sheet
- `!stats` - View conversation statistics
- `!clear` - Clear conversation history
- `!employees` - List accessible employees

### Admin Only
- `!sheet <username>` - View any employee's sheet

## 🔧 Configuration

Edit `config/config.py` to:
- Add/remove admins
- Add/remove employees
- Change bot settings (token limits, model, etc.)
- Modify system prompt

### Adding a New Employee

1. Edit `config/config.py`:
```python
EMPLOYEE_SHEETS = {
    "existing_user": "sheet_id",
    "new_employee": "new_sheet_id"  # Add this line
}
```

2. Share the Google Sheet with the service account email
3. Restart the bot

### Adding a New Admin

1. Edit `config/config.py`:
```python
ADMIN_USERNAMES = [
    "existing_admin",
    "new_admin"  # Add this line
]
```

2. Restart the bot

## 🗄️ Database Schema

### conversation_history table

```sql
CREATE TABLE conversation_history (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    user_message TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_user_channel ON conversation_history(user_id, channel_id);
CREATE INDEX idx_timestamp ON conversation_history(timestamp DESC);
```

## 🧪 Testing

### Test Permission System

```python
from utils import PermissionManager

# Check role
role = PermissionManager.get_user_role("ignacioz1313")
print(role)  # "employee"

# Check sheet access
can_access, sheet_id = PermissionManager.can_access_sheet(
    requester_username="ignacioz1313",
    target_username="ignacioz1313"
)
print(can_access, sheet_id)  # True, <sheet_id>
```

### Test Google Sheets

```python
from services import GoogleSheetsService

sheets = GoogleSheetsService()
data = sheets.get_sheet_data("1FgJtIF0HktbXJPCxOnJP5zu9rbD9IX7Js9dfKQimLlY")
print(data)
```

## 🔒 Security Best Practices

1. **Never commit credentials** - Use `.env` and `.gitignore`
2. **Service Account** - Use service accounts, not personal OAuth
3. **Least Privilege** - Employees can only access their own sheets
4. **Admins Only** - Cross-sheet access restricted to admins
5. **Environment Variables** - All secrets in environment variables

## 📊 Architecture

### Separation of Concerns

| Component | Responsibility |
|-----------|---------------|
| `config/` | Configuration & settings |
| `database/` | Supabase operations |
| `services/` | External API integrations |
| `handlers/` | Discord event handling |
| `utils/` | Shared utilities & permissions |
| `main.py` | Application entry point |

### Design Patterns

- **Dependency Injection** - Services passed to handlers
- **Single Responsibility** - Each class has one job
- **Strategy Pattern** - AI service abstraction
- **Repository Pattern** - Database abstraction

## 🚀 Deployment

### Heroku

1. Create `Procfile`:
```
worker: python main.py
```

2. Deploy:
```bash
heroku create your-bot-name
heroku config:set DISCORD_BOT_TOKEN="..." ANTHROPIC_API_KEY="..." ...
git push heroku main
heroku ps:scale worker=1
```

## 🐛 Troubleshooting

### Google Sheets Access Denied
- Ensure sheet is shared with service account email
- Check `google_credentials.json` is in correct location
- Verify service account has appropriate scopes

### Permission Issues
- Check username spelling in config (case-sensitive)
- Verify user role in logs
- Test with `!help` command to see your role

### Database Errors
- Verify Supabase credentials
- Check table exists
- Ensure RLS policies are enabled

## 💰 Cost Estimate

- **Discord Bot**: FREE
- **Supabase**: FREE (up to 500MB)
- **Google Sheets API**: FREE (up to 500 requests/100s)
- **Anthropic API**: $5-10/month
- **Heroku**: $7/month (Hobby dyno)

**Total: ~$12-17/month**

## 📝 License

Private/Proprietary - All rights reserved

## 🤝 Support

For issues:
1. Check logs: `python main.py` (local) or `heroku logs --tail` (production)
2. Verify configuration in `config/config.py`
3. Test permissions with `!help` command
4. Check service account has sheet access

---

**Built with ❤️ for sports betting arbitrage teams**
