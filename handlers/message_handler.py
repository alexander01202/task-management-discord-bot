"""
Discord message handling
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
        
        # Generate AI response (with username for permission checking)
        ai_response = self.ai.generate_response(
            current_message=current_message,
            conversation_history=history,
            username=state["username"]
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
        
        # Prepare state for LangGraph
        state = {
            "messages": [{"role": "user", "content": content}],
            "user_id": str(message.author.id),
            "channel_id": str(message.channel.id),
            "username": username
        }
        
        # Create unique thread ID for this user/channel combination
        thread_id = f"{message.author.id}_{message.channel.id}"
        config = {"configurable": {"thread_id": thread_id}}
        
        print(f"   🧵 Thread ID: {thread_id}")
        print(f"   👤 Username: {username}")
        print(f"   🔐 Role: {PermissionManager.get_user_role(username)}")
        
        # Run through LangGraph
        result = self.graph.invoke(state, config)
        
        # Get AI response from result
        ai_message = result["messages"][-1].content
        
        print(f"   ✅ Response generated ({len(ai_message)} chars)")
        
        return ai_message
