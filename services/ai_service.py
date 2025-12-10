"""
AI Service using Anthropic Claude API with Google Sheets Tool
"""
from typing import List, Dict, Any
from anthropic import Anthropic
from config.config import (
    ANTHROPIC_API_KEY, 
    CLAUDE_MODEL, 
    MAX_TOKENS, 
    SYSTEM_PROMPT,
    MAX_CONTEXT_MESSAGES
)


class AIService:
    """Handles all AI/Claude API operations with tool calling"""
    
    def __init__(self, sheets_service):
        """
        Initialize Anthropic client
        
        Args:
            sheets_service: Google Sheets service instance for tool execution
        """
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.sheets_service = sheets_service
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any], username: str) -> str:
        """
        Execute a tool call
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            username: Username of the requester (for permission checking)
            
        Returns:
            Tool execution result as string
        """
        if tool_name == "fetch_employee_sheet":
            employee_name = tool_input.get("employee_name")
            worksheet_name = tool_input.get("worksheet_name")

            if not employee_name:
                return "Error: employee_name is required"

            # Handle special "me" keyword - employee asking for their own sheet
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
                    # Try to provide helpful error message
                    available_names = PermissionManager.get_all_employee_names()
                    return f"I don't recognize '{employee_name}'. Available employees: {', '.join(available_names)}"

            # Fetch sheet data with permission checking
            result = self.sheets_service.get_employee_sheet(employee_username, username, worksheet_name)

            if result is None:
                return f"Could not fetch sheet for {employee_name}. Either the user doesn't exist or you don't have permission."

            # Check if we got a list of worksheets (no worksheet_name specified)
            if "worksheets" in result:
                worksheets = result["worksheets"]
                if len(worksheets) == 1:
                    # Only one worksheet, fetch it automatically
                    print(f"   📋 Only one worksheet found: {worksheets[0]}, fetching automatically")
                    result = self.sheets_service.get_employee_sheet(employee_username, username, worksheets[0])
                    if result and "data" in result:
                        data = result["data"]
                        if not data:
                            return f"{employee_name}'s sheet (worksheet: {worksheets[0]}) is currently empty."
                        formatted = self.sheets_service.format_sheet_data(data, limit=50)
                        return f"Sheet data for {employee_name} (worksheet: {worksheets[0]}):\n\n{formatted}"
                else:
                    # Multiple worksheets, ask user to specify
                    worksheet_list = "\n".join([f"  • {ws}" for ws in worksheets])
                    return f"{employee_name}'s spreadsheet has {len(worksheets)} worksheets:\n{worksheet_list}\n\nPlease specify which worksheet you'd like to see."

            # We got data from a specific worksheet
            if "data" in result:
                data = result["data"]
                ws_name = result.get("worksheet_name", "unknown")

                if not data:
                    return f"{employee_name}'s sheet (worksheet: {ws_name}) is currently empty."

                # Format data for Claude to analyze
                formatted = self.sheets_service.format_sheet_data(data, limit=50)
                return f"Sheet data for {employee_name} (worksheet: {ws_name}):\n\n{formatted}"

            return f"Unexpected result format when fetching {employee_name}'s sheet."

        return f"Unknown tool: {tool_name}"

    def generate_response(
        self,
        current_message: str,
        conversation_history: List[Dict] = None,
        username: str = None,
        enable_web_search: bool = True
    ) -> str:
        """
        Generate AI response using Claude with tool calling

        Args:
            current_message: Current user message
            conversation_history: List of past conversations
            username: Username of requester (for permission checking)
            enable_web_search: Whether to enable web search tool

        Returns:
            AI generated response
        """
        print(f"\n🤖 Calling AI model ({CLAUDE_MODEL})...")

        # Build context messages from history
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

        # Add requester context to help Claude understand who's asking
        from utils.permissions import PermissionManager
        role = PermissionManager.get_user_role(username)
        friendly_name = PermissionManager.get_employee_friendly_name(username)

        requester_context = f"[REQUESTER INFO: Username={username}, Role={role}"
        if friendly_name:
            requester_context += f", FriendlyName={friendly_name}"
        requester_context += "]"

        # Add current message with requester context
        full_message = f"{requester_context}\n\n{current_message}"
        context_messages.append({
            "role": "user",
            "content": full_message
        })

        print(f"   💬 Current message: \"{current_message[:50]}{'...' if len(current_message) > 50 else ''}\"")
        print(f"   👤 Requester: {username} ({role})")
        if friendly_name:
            print(f"   📛 Friendly name: {friendly_name}")
        print(f"   📊 Total context messages: {len(context_messages)}")

        # Define tools available to Claude
        tools = []

        # Google Sheets tool
        tools.append({
            "name": "fetch_employee_sheet",
            "description": "Fetch task data from an employee's Google Sheet. First call without worksheet_name to get list of available worksheets. Then call again with specific worksheet_name. Use their friendly name (mitchell, granger, ignacio, conner) or if the requester is an employee asking about their own tasks, use 'me'.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "employee_name": {
                        "type": "string",
                        "description": "Employee friendly name (mitchell/granger/ignacio/conner) or special keyword 'me' to fetch requester's own sheet"
                    },
                    "worksheet_name": {
                        "type": "string",
                        "description": "Optional: Specific worksheet/tab name to fetch data from. If not provided, returns list of available worksheets."
                    }
                },
                "required": ["employee_name"]
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
            max_iterations = 5  # Prevent infinite loops
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                print(f"   🔄 Iteration {iteration}...")
                
                # Call Anthropic API
                response = self.client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    messages=context_messages,
                    tools=tools
                )
                
                # Check if Claude wants to use a tool
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
                    print(f"   💭 Response preview: \"{ai_response[:80]}{'...' if len(ai_response) > 80 else ''}\"")
                    
                    return ai_response
                
                # Claude wants to use tools - execute them
                print(f"   🔧 Claude is using {len(tool_use_blocks)} tool(s)...")
                
                # Add assistant's message (with tool use) to context
                context_messages.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                # Execute each tool and add results
                tool_results = []
                for tool_use in tool_use_blocks:
                    tool_name = tool_use.name
                    tool_input = tool_use.input
                    tool_use_id = tool_use.id
                    
                    print(f"      🛠️  Executing tool: {tool_name}")
                    print(f"         Input: {tool_input}")
                    
                    # Execute the tool
                    result = self._execute_tool(tool_name, tool_input, username)
                    
                    print(f"         Result preview: {result[:100]}...")
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result
                    })
                
                # Add tool results to context
                context_messages.append({
                    "role": "user",
                    "content": tool_results
                })
                
                # Continue loop to let Claude process the tool results
            
            # If we hit max iterations, return what we have
            return "I tried to process your request but ran into complexity limits. Please try rephrasing your question."
            
        except Exception as e:
            print(f"   ❌ Error calling Anthropic API: {e}")
            import traceback
            traceback.print_exc()
            return "Sorry, I encountered an error processing your request. Please try again."