"""
Discord message handling with reminder context
"""
import discord
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from database import Database
from services import AIService
from utils import PermissionManager


class State(TypedDict):
    """LangGraph state schema"""
    messages: Annotated[list, add_messages]
    user_id: str
    channel_id: str
    guild_id: str  # Added for reminder context
    username: str  # For permission checking


class MessageHandler:
    """Handles Discord message processing with LangGraph"""

    def __init__(self, database: Database, ai_service: AIService):
        """
        Initialize message handler

        Args:
            database: Database instance
            ai_service: AI service instance
        """
        self.db = database
        self.ai = ai_service
        self.graph = self._create_conversation_graph()

    def _call_ai_model(self, state: State):
        """
        LangGraph node: Call AI model with conversation history

        Args:
            state: LangGraph state

        Returns:
            Updated state with AI response
        """
        # Get conversation history from database
        history = self.db.get_conversation_history(
            state["user_id"],
            state["channel_id"]
        )

        # Get current message
        current_message = state["messages"][-1].content

        # Generate AI response (with username, user_id, channel_id, guild_id for reminders)
        ai_response = self.ai.generate_response(
            current_message=current_message,
            conversation_history=history,
            username=state["username"],
            user_id=state["user_id"],
            channel_id=state["channel_id"],
            guild_id=state.get("guild_id")
        )

        # Save conversation to database
        self.db.save_conversation(
            state["user_id"],
            state["channel_id"],
            current_message,
            ai_response
        )

        # Return updated state
        return {
            "messages": [{"role": "assistant", "content": ai_response}]
        }

    def _create_conversation_graph(self):
        """
        Create LangGraph workflow for conversation management

        Returns:
            Compiled LangGraph application
        """
        print("\n🔧 Building LangGraph workflow...")

        # Initialize state graph
        workflow = StateGraph(State)

        # Add AI response node
        workflow.add_node("ai_response", self._call_ai_model)
        print("   ✅ Added AI response node")

        # Set entry point
        workflow.set_entry_point("ai_response")
        print("   ✅ Set entry point")

        # Add edge to end
        workflow.add_edge("ai_response", END)
        print("   ✅ Added end edge")

        # Compile with memory saver
        memory = MemorySaver()
        app = workflow.compile(checkpointer=memory)
        print("   ✅ Compiled with memory saver")

        return app

    async def process_message(self, message: discord.Message, content: str) -> str:
        """
        Process a Discord message and generate response

        Args:
            message: Discord message object
            content: Cleaned message content

        Returns:
            Bot response string
        """
        print("   🔄 Processing message through LangGraph...")

        # Get username for permission checking
        username = str(message.author)
        if '#' in username:
            username = username.split('#')[0]  # Remove discriminator if present

        # Get guild ID if available (None for DMs)
        guild_id = str(message.guild.id) if message.guild else None

        # Prepare state for LangGraph
        state = {
            "messages": [{"role": "user", "content": content}],
            "user_id": str(message.author.id),
            "channel_id": str(message.channel.id),
            "guild_id": guild_id,
            "username": username
        }

        # Create unique thread ID for this user/channel combination
        thread_id = f"{message.author.id}_{message.channel.id}"
        config = {"configurable": {"thread_id": thread_id}}

        print(f"   🧵 Thread ID: {thread_id}")
        print(f"   👤 Username: {username}")
        print(f"   🔐 Role: {PermissionManager.get_user_role(username)}")
        print(f"   🏢 Guild ID: {guild_id or 'DM'}")

        # Run through LangGraph
        result = self.graph.invoke(state, config)

        # Get AI response from result
        ai_message = result["messages"][-1].content

        print(f"   ✅ Response generated ({len(ai_message)} chars)")

        return ai_message

    def fetch_user_sheet_data(self, employee_username: str, requester_username: str = None):
        """
        Fetch sheet data for an employee (for command usage)

        Args:
            employee_username: Employee to fetch sheet for
            requester_username: Username requesting (for permission check)

        Returns:
            Tuple of (success: bool, message: str)
        """
        # If no requester specified, they're fetching their own
        if requester_username is None:
            requester_username = employee_username

        # Use the sheets service directly
        try:
            result = self.ai.sheets_service.get_employee_sheet(
                employee_username=employee_username,
                requester_username=requester_username,
                query="tracking"  # Default to tracking sheet
            )

            if result is None:
                return (False, "❌ You don't have permission to view that sheet.")

            if "data" not in result:
                worksheets = result.get("worksheets", [])
                worksheet_list = "\n".join([f"  • {ws}" for ws in worksheets])
                return (True, f"📊 Available worksheets:\n{worksheet_list}\n\nUse `!sheet {employee_username} <worksheet_name>` to view a specific sheet.")

            data = result["data"]
            worksheet_name = result.get("worksheet_name", "unknown")

            if not data:
                return (True, f"📊 {employee_username}'s {worksheet_name} sheet is empty.")

            # Format the data
            formatted = self.ai.sheets_service.format_sheet_data(data, limit=30)

            return (True, f"📊 **{employee_username}'s {worksheet_name} Sheet**\n\n```\n{formatted}\n```")

        except Exception as e:
            print(f"   ❌ Error fetching sheet: {e}")
            import traceback
            traceback.print_exc()
            return (False, f"❌ Error fetching sheet: {str(e)}")
