"""
AI Service - NATURAL REMINDER HANDLING
"""
from typing import List, Dict, Any
from anthropic import Anthropic
from datetime import datetime
from config.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    MAX_TOKENS,
    SYSTEM_PROMPT,
    MAX_CONTEXT_MESSAGES
)
from services.reminder_service import ReminderService
from utils.time_parser import TimeParser


class AIService:
    """Handles all AI/Claude API operations with natural tool calling"""

    def __init__(self, sheets_service, reminder_service: ReminderService = None):
        """Initialize Anthropic client"""
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.sheets_service = sheets_service
        self.reminder_service = reminder_service or ReminderService()
        self.time_parser = TimeParser()

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any], username: str, user_id: str, channel_id: str, guild_id: str = None) -> str:
        """Execute a tool call"""

        if tool_name == "fetch_employee_sheet":
            employee_name = tool_input.get("employee_name")
            worksheet_name = tool_input.get("worksheet_name")

            if not employee_name:
                return "Error: employee_name is required"

            # Handle "me" keyword
            if employee_name.lower() == "me":
                from utils.permissions import PermissionManager
                if PermissionManager.is_employee(username):
                    employee_username = username
                else:
                    return "You are not an employee, so you don't have a personal sheet."
            else:
                # Resolve friendly name to Discord username
                from utils.permissions import PermissionManager
                employee_username = PermissionManager.resolve_employee_name(employee_name)

                if not employee_username:
                    available_names = PermissionManager.get_all_employee_names()
                    return f"I don't recognize '{employee_name}'. Available employees: {', '.join(available_names)}"

            # Fetch sheet data
            query = worksheet_name if worksheet_name else None
            result = self.sheets_service.get_employee_sheet(employee_username, username, query)

            if result is None:
                return f"Could not fetch sheet for {employee_name}. Either the user doesn't exist or you don't have permission."

            # Handle list of worksheets
            if "worksheets" in result:
                worksheets = result["worksheets"]
                best_guess = result.get("best_guess")
                confidence = result.get("confidence", 0)

                if best_guess and confidence > 0.4:
                    worksheet_list = "\n".join([f"  • {ws}" for ws in worksheets])
                    return f"{employee_name}'s spreadsheet has {len(worksheets)} worksheets:\n{worksheet_list}\n\nI think you might be looking for '{best_guess}' ({confidence:.0%} confidence). Which worksheet would you like to see?"
                else:
                    worksheet_list = "\n".join([f"  • {ws}" for ws in worksheets])
                    return f"{employee_name}'s spreadsheet has {len(worksheets)} worksheets:\n{worksheet_list}\n\nWhich worksheet would you like to see?"

            # Handle specific worksheet data
            if "data" in result:
                data = result["data"]
                ws_name = result.get("worksheet_name", "unknown")
                confidence = result.get("confidence")

                if not data:
                    return f"{employee_name}'s sheet (worksheet: {ws_name}) is currently empty."

                from config.config import SHEET_DESCRIPTIONS
                sheet_description = SHEET_DESCRIPTIONS.get(ws_name, "")

                formatted = self.sheets_service.format_sheet_data(data, limit=50)
                response = f"Sheet data for {employee_name} (worksheet: {ws_name}"
                if confidence:
                    response += f", {confidence:.0%} confidence match"
                response += "):\n\n"
                if sheet_description:
                    response += f"SHEET GUIDE:\n{sheet_description}\n\nDATA:\n"
                response += formatted
                return response

            return f"Unexpected result format when fetching {employee_name}'s sheet."

        elif tool_name == "create_reminder":
            # Extract parameters
            target_name = tool_input.get("target_name", "").strip()
            reminder_text = tool_input.get("reminder_text", "").strip()
            time_expression = tool_input.get("time_expression", "").strip()

            if not reminder_text:
                return "Error: reminder_text is required"

            if not time_expression:
                return "Error: time_expression is required"

            # Parse the time expression (flexible!)
            reminder_time = self.time_parser.parse(time_expression)

            if not reminder_time:
                # Time parser couldn't figure it out
                return f"I couldn't understand the time '{time_expression}'. Could you clarify? For example: 'tomorrow', 'in 2 hours', 'Monday at 3pm', or 'next week'."

            # Determine target username
            from utils.permissions import PermissionManager

            if not target_name or target_name.lower() in ["me", "myself"]:
                # Reminder for the requester
                target_username = username
                target_user_id = user_id
            else:
                # Reminder for someone else
                target_username = PermissionManager.resolve_employee_name(target_name)

                if not target_username:
                    available_names = PermissionManager.get_all_employee_names()
                    return f"I don't recognize '{target_name}'. Available employees: {', '.join(available_names)}"

                from config.config import EMPLOYEE_DISCORD_IDS
                target_user_id = EMPLOYEE_DISCORD_IDS.get(target_username)

            # Check if reminder is in the past
            if reminder_time <= datetime.now():
                return f"That time is in the past. When should I actually remind you?"

            # Create the reminder
            try:
                reminder = self.reminder_service.create_reminder(
                    creator_user_id=user_id,
                    creator_username=username,
                    target_username=target_username,
                    reminder_text=reminder_text,
                    reminder_time=reminder_time,
                    channel_id=channel_id,
                    guild_id=guild_id,
                    target_user_id=target_user_id
                )

                formatted_time = self.time_parser.format_datetime(reminder_time)

                if target_username == username:
                    return f"✅ I'll remind you {formatted_time}"
                else:
                    friendly_name = PermissionManager.get_employee_friendly_name(target_username)
                    display_name = friendly_name.title() if friendly_name else target_username
                    return f"✅ I'll remind {display_name} {formatted_time}"

            except Exception as e:
                return f"Error creating reminder: {str(e)}"

        elif tool_name == "list_reminders":
            try:
                reminders = self.reminder_service.get_user_reminders(username, include_past=False)

                if not reminders:
                    return "You don't have any pending reminders."

                result = f"You have {len(reminders)} pending reminder(s):\n\n"

                for i, reminder in enumerate(reminders, 1):
                    reminder_time = datetime.fromisoformat(reminder['reminder_time'])
                    formatted_time = self.time_parser.format_datetime(reminder_time)

                    target = reminder['target_username']
                    text = reminder['reminder_text']
                    reminder_id = reminder['id']

                    if target == username:
                        result += f"{i}. (ID #{reminder_id}) [{formatted_time}] {text}\n"
                    else:
                        from utils.permissions import PermissionManager
                        friendly_name = PermissionManager.get_employee_friendly_name(target)
                        display_name = friendly_name.title() if friendly_name else target
                        result += f"{i}. (ID #{reminder_id}) [{formatted_time}] Remind {display_name}: {text}\n"

                return result

            except Exception as e:
                return f"Error fetching reminders: {str(e)}"

        elif tool_name == "cancel_reminder":
            reminder_id = tool_input.get("reminder_id")

            if not reminder_id:
                return "Error: reminder_id is required"

            try:
                success = self.reminder_service.cancel_reminder(reminder_id, username)

                if success:
                    return f"✅ Reminder cancelled"
                else:
                    return f"Could not cancel reminder #{reminder_id}. Either it doesn't exist or you don't have permission."

            except Exception as e:
                return f"Error cancelling reminder: {str(e)}"

        return f"Unknown tool: {tool_name}"

    def generate_response(
        self,
        current_message: str,
        conversation_history: List[Dict] = None,
        username: str = None,
        user_id: str = None,
        channel_id: str = None,
        guild_id: str = None,
        enable_web_search: bool = True
    ) -> str:
        """Generate AI response using Claude with tool calling"""

        print(f"\n🤖 Calling AI model ({CLAUDE_MODEL})...")

        # Build context messages
        context_messages = []

        if conversation_history:
            history_to_use = conversation_history[-MAX_CONTEXT_MESSAGES:]
            print(f"   📚 Building context from {len(history_to_use)} past conversations")

            for entry in history_to_use:
                context_messages.append({
                    "role": "user",
                    "content": entry["user_message"]
                })
                context_messages.append({
                    "role": "assistant",
                    "content": entry["bot_response"]
                })

        # Add requester context
        from utils.permissions import PermissionManager
        role = PermissionManager.get_user_role(username)
        friendly_name = PermissionManager.get_employee_friendly_name(username)

        requester_context = f"[REQUESTER INFO: Username={username}, Role={role}"
        if friendly_name:
            requester_context += f", FriendlyName={friendly_name}"
        requester_context += "]"

        full_message = f"{requester_context}\n\n{current_message}"
        context_messages.append({
            "role": "user",
            "content": full_message
        })

        print(f"   💬 Current message: \"{current_message[:50]}{'...' if len(current_message) > 50 else ''}\"")
        print(f"   👤 Requester: {username} ({role})")

        # Define tools
        tools = []

        # Google Sheets tool
        tools.append({
            "name": "fetch_employee_sheet",
            "description": "Fetch task data from an employee's Google Sheet. Use 'me' for the requester's own sheet, or use employee friendly names (mitchell/granger/ignacio/conner).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "employee_name": {
                        "type": "string",
                        "description": "Employee friendly name or 'me' for requester's own sheet"
                    },
                    "worksheet_name": {
                        "type": "string",
                        "description": "Optional: Specific worksheet name. If not provided, returns list of available worksheets."
                    }
                },
                "required": ["employee_name"]
            }
        })

        # Reminder tool - SIMPLIFIED!
        tools.append({
            "name": "create_reminder",
            "description": "Create a reminder. Accept ANY natural time expression - don't constrain the user. If unclear, ask them to clarify.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "target_name": {
                        "type": "string",
                        "description": "Who to remind: 'me' (default) or employee friendly name (mitchell/granger/ignacio/conner)"
                    },
                    "reminder_text": {
                        "type": "string",
                        "description": "What to remind about - be specific and clear"
                    },
                    "time_expression": {
                        "type": "string",
                        "description": "FLEXIBLE time expression from user's message. Examples: 'tomorrow', 'in 2 hours', 'Monday at 3pm', 'next week', '3pm', 'tomorrow morning'. Accept ANY natural expression."
                    }
                },
                "required": ["reminder_text", "time_expression"]
            }
        })

        tools.append({
            "name": "list_reminders",
            "description": "List all pending reminders for the requester",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        })

        tools.append({
            "name": "cancel_reminder",
            "description": "Cancel a reminder by its ID",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reminder_id": {
                        "type": "integer",
                        "description": "The ID of the reminder to cancel"
                    }
                },
                "required": ["reminder_id"]
            }
        })

        # Web search tool
        if enable_web_search:
            tools.append({
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5
            })

        try:
            max_iterations = 5
            iteration = 0

            while iteration < max_iterations:
                iteration += 1
                print(f"   🔄 Iteration {iteration}...")

                response = self.client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    messages=context_messages,
                    tools=tools
                )

                tool_use_blocks = [block for block in response.content if hasattr(block, 'type') and block.type == "tool_use"]

                if not tool_use_blocks:
                    # No tool use, extract final response
                    ai_response = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            ai_response += block.text

                    if not ai_response:
                        ai_response = "I'm not sure how to respond to that."

                    print(f"   ✅ AI response received ({len(ai_response)} chars)")
                    return ai_response

                # Execute tools
                print(f"   🔧 Claude is using {len(tool_use_blocks)} tool(s)...")

                context_messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                tool_results = []
                for tool_use in tool_use_blocks:
                    tool_name = tool_use.name
                    tool_input = tool_use.input
                    tool_use_id = tool_use.id

                    print(f"      🛠️  Executing tool: {tool_name}")
                    print(f"         Input: {tool_input}")

                    result = self._execute_tool(
                        tool_name,
                        tool_input,
                        username,
                        user_id,
                        channel_id,
                        guild_id
                    )

                    print(f"         Result preview: {result[:100]}...")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result
                    })

                context_messages.append({
                    "role": "user",
                    "content": tool_results
                })

            return "I tried to process your request but ran into complexity limits. Please try rephrasing your question."

        except Exception as e:
            print(f"   ❌ Error calling Anthropic API: {e}")
            import traceback
            traceback.print_exc()
            return "Sorry, I encountered an error processing your request. Please try again."
