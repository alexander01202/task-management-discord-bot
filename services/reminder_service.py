"""
Reminder service for managing user-created reminders
"""
from typing import List, Dict, Optional
from datetime import datetime
from supabase import Client
from config.config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client


class ReminderService:
    """Handles reminder CRUD operations"""

    def __init__(self):
        """Initialize Supabase client"""
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def create_reminder(
            self,
            creator_user_id: str,
            creator_username: str,
            target_username: str,
            reminder_text: str,
            reminder_time: datetime,
            channel_id: str,
            guild_id: Optional[str] = None,
            target_user_id: Optional[str] = None
    ) -> Dict:
        """
        Create a new reminder

        Args:
            creator_user_id: Discord ID of user creating reminder
            creator_username: Username of creator
            target_username: Username of person to remind
            reminder_text: What to remind about
            reminder_time: When to send reminder (datetime object)
            channel_id: Discord channel ID
            guild_id: Discord server ID
            target_user_id: Discord ID of target user (optional)

        Returns:
            Created reminder dict
        """
        print(f"\n💾 Creating reminder...")
        print(f"   Creator: {creator_username}")
        print(f"   Target: {target_username}")
        print(f"   Time: {reminder_time}")
        print(f"   Text: {reminder_text}")

        try:
            data = {
                "creator_user_id": creator_user_id,
                "creator_username": creator_username,
                "target_user_id": target_user_id,
                "target_username": target_username,
                "reminder_text": reminder_text,
                "reminder_time": reminder_time.isoformat(),
                "channel_id": channel_id,
                "guild_id": guild_id,
                "status": "pending"
            }

            result = self.client.table("reminders").insert(data).execute()
            print(f"   ✅ Reminder created with ID: {result.data[0]['id']}")
            return result.data[0]

        except Exception as e:
            print(f"   ❌ Error creating reminder: {e}")
            raise

    def get_pending_reminders(self) -> List[Dict]:
        """
        Get all pending reminders that should be sent now

        Returns:
            List of reminder dictionaries
        """
        try:
            now = datetime.now().isoformat()

            response = self.client.table("reminders") \
                .select("*") \
                .eq("status", "pending") \
                .lte("reminder_time", now) \
                .order("reminder_time") \
                .execute()

            return response.data if response.data else []

        except Exception as e:
            print(f"   ❌ Error fetching pending reminders: {e}")
            return []

    def mark_reminder_sent(self, reminder_id: int) -> bool:
        """
        Mark a reminder as sent

        Args:
            reminder_id: ID of reminder

        Returns:
            True if successful
        """
        try:
            self.client.table("reminders") \
                .update({
                "status": "sent",
                "sent_at": datetime.now().isoformat()
            }) \
                .eq("id", reminder_id) \
                .execute()

            print(f"   ✅ Marked reminder {reminder_id} as sent")
            return True

        except Exception as e:
            print(f"   ❌ Error marking reminder as sent: {e}")
            return False

    def cancel_reminder(self, reminder_id: int, username: str) -> bool:
        """
        Cancel a reminder (only if user is creator or target)

        Args:
            reminder_id: ID of reminder to cancel
            username: Username requesting cancellation

        Returns:
            True if successful, False otherwise
        """
        try:
            # First check if user has permission
            response = self.client.table("reminders") \
                .select("*") \
                .eq("id", reminder_id) \
                .execute()

            if not response.data:
                print(f"   ❌ Reminder {reminder_id} not found")
                return False

            reminder = response.data[0]

            # Check permission
            if reminder["creator_username"] != username and reminder["target_username"] != username:
                print(f"   ❌ User {username} doesn't have permission to cancel this reminder")
                return False

            # Cancel it
            self.client.table("reminders") \
                .update({"status": "cancelled"}) \
                .eq("id", reminder_id) \
                .execute()

            print(f"   ✅ Reminder {reminder_id} cancelled by {username}")
            return True

        except Exception as e:
            print(f"   ❌ Error cancelling reminder: {e}")
            return False

    def get_user_reminders(self, username: str, include_past: bool = False) -> List[Dict]:
        """
        Get all reminders for a user (created by them or for them)

        Args:
            username: Username to fetch reminders for
            include_past: Whether to include sent/cancelled reminders

        Returns:
            List of reminder dictionaries
        """
        try:
            query = self.client.table("reminders") \
                .select("*") \
                .or_(f"creator_username.eq.{username},target_username.eq.{username}")

            if not include_past:
                query = query.eq("status", "pending")

            response = query.order("reminder_time", desc=True).execute()

            return response.data if response.data else []

        except Exception as e:
            print(f"   ❌ Error fetching user reminders: {e}")
            return []