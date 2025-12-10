"""
Database operations using Supabase
"""
from typing import List, Dict, Optional
from datetime import datetime
from supabase import create_client, Client
from config.config import SUPABASE_URL, SUPABASE_KEY


class Database:
    """Handles all database operations"""
    
    def __init__(self):
        """Initialize Supabase client"""
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    def save_conversation(
        self, 
        user_id: str, 
        channel_id: str, 
        user_message: str, 
        bot_response: str
    ) -> bool:
        """
        Save a conversation to the database
        
        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            user_message: User's message
            bot_response: Bot's response
            
        Returns:
            True if successful, False otherwise
        """
        print(f"\n💾 Saving conversation to database...")
        print(f"   User: {user_id}")
        print(f"   Channel: {channel_id}")
        
        try:
            data = {
                "user_id": user_id,
                "channel_id": channel_id,
                "user_message": user_message,
                "bot_response": bot_response,
                "timestamp": datetime.now().isoformat()
            }
            
            result = self.client.table("conversation_history").insert(data).execute()
            print(f"   ✅ Conversation saved successfully")
            return True
            
        except Exception as e:
            print(f"   ❌ Error saving to database: {e}")
            return False
    
    def get_conversation_history(
        self, 
        user_id: str, 
        channel_id: str, 
        limit: int = 10
    ) -> List[Dict]:
        """
        Retrieve conversation history for a user in a specific channel
        
        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            limit: Maximum number of conversations to retrieve
            
        Returns:
            List of conversation dictionaries in chronological order
        """
        print(f"\n📖 Retrieving conversation history...")
        print(f"   User: {user_id}")
        print(f"   Channel: {channel_id}")
        print(f"   Limit: {limit} conversations")
        
        try:
            response = self.client.table("conversation_history")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("channel_id", channel_id)\
                .order("timestamp", desc=True)\
                .limit(limit)\
                .execute()
            
            # Reverse to get chronological order (oldest to newest)
            history = list(reversed(response.data)) if response.data else []
            
            print(f"   ✅ Retrieved {len(history)} past conversations")
            return history
            
        except Exception as e:
            print(f"   ❌ Error retrieving from database: {e}")
            return []
    
    def clear_conversation_history(
        self, 
        user_id: str, 
        channel_id: str
    ) -> bool:
        """
        Clear conversation history for a user in a specific channel
        
        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            
        Returns:
            True if successful, False otherwise
        """
        print(f"\n🗑️  Clearing conversation history...")
        print(f"   User: {user_id}")
        print(f"   Channel: {channel_id}")
        
        try:
            self.client.table("conversation_history")\
                .delete()\
                .eq("user_id", user_id)\
                .eq("channel_id", channel_id)\
                .execute()
            
            print(f"   ✅ Conversation history cleared successfully")
            return True
            
        except Exception as e:
            print(f"   ❌ Error clearing history: {e}")
            return False
    
    def get_conversation_count(self, user_id: str) -> int:
        """
        Get total conversation count for a user
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Number of conversations
        """
        try:
            response = self.client.table("conversation_history")\
                .select("*", count="exact")\
                .eq("user_id", user_id)\
                .execute()
            
            return len(response.data) if response.data else 0
            
        except Exception as e:
            print(f"   ❌ Error fetching count: {e}")
            return 0
