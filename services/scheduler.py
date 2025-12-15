"""
Scheduler service for automated daily task reminders
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import discord
from datetime import datetime
from typing import Dict, List

from services.google_sheets import GoogleSheetsService
from config.config import (
    EMPLOYEE_SHEETS,
    EMPLOYEE_FRIENDLY_NAMES,
    REMINDER_CHANNEL_ID,
    REMINDER_TIME_HOUR,
    REMINDER_TIME_MINUTE
)


class ReminderScheduler:
    """Handles scheduled daily task reminders"""

    def __init__(self, bot: discord.Client, sheets_service: GoogleSheetsService):
        """
        Initialize scheduler

        Args:
            bot: Discord bot instance
            sheets_service: Google Sheets service instance
        """
        self.bot = bot
        self.sheets_service = sheets_service
        self.scheduler = AsyncIOScheduler()

    def __del__(self):
        self.stop()

    def start(self):
        """Start the scheduler"""
        print("\n⏰ Initializing Daily Reminder Scheduler...")

        # Schedule daily reminders
        trigger = CronTrigger(
            hour=REMINDER_TIME_HOUR,
            minute=REMINDER_TIME_MINUTE,
            timezone='America/Toronto'  # Adjust to your timezone
        )

        self.scheduler.add_job(
            self.send_daily_reminders,
            trigger=trigger,
            id='daily_task_reminders',
            name='Daily Task Reminders',
            replace_existing=True
        )

        self.scheduler.start()

        print(f"   ✅ Scheduler started")
        print(f"   ⏰ Daily reminders scheduled for {REMINDER_TIME_HOUR:02d}:{REMINDER_TIME_MINUTE:02d}")
        print("=" * 60)

    async def send_daily_reminders(self):
        """Send daily task reminders to all employees"""
        print("\n" + "=" * 60)
        print(f"⏰ DAILY REMINDER CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Get reminder channel
        channel = self.bot.get_channel(REMINDER_CHANNEL_ID)
        if not channel:
            print(f"   ❌ Could not find channel with ID: {REMINDER_CHANNEL_ID}")
            return

        print(f"   📢 Sending reminders to channel: {channel.name}")

        # Process each employee
        for employee_username, sheet_id in EMPLOYEE_SHEETS.items():
            try:
                await self._send_employee_reminder(channel, employee_username)
            except Exception as e:
                print(f"   ❌ Error processing {employee_username}: {e}")
                import traceback
                traceback.print_exc()

        print("=" * 60)
        print("✅ Daily reminder check completed")
        print("=" * 60)

    async def _send_employee_reminder(self, channel: discord.TextChannel, employee_username: str):
        """
        Send reminder for a specific employee

        Args:
            channel: Discord channel to send reminder to
            employee_username: Employee's Discord username
        """
        print(f"\n   📊 Processing {employee_username}...")

        # Get friendly name
        friendly_name = None
        for name, username in EMPLOYEE_FRIENDLY_NAMES.items():
            if username == employee_username:
                friendly_name = name.title()
                break

        if not friendly_name:
            friendly_name = employee_username

        # Fetch Tracking sheet data
        result = self.sheets_service.get_employee_sheet(
            employee_username=employee_username,
            requester_username=employee_username,  # Employee checking their own sheet
            query="tracking"
        )

        if not result or "data" not in result:
            print(f"      ⚠️  Could not fetch Tracking sheet for {employee_username}")
            return

        data = result["data"]

        if not data:
            print(f"      ℹ️  No data in Tracking sheet for {employee_username}")
            return

        # Analyze data and group by customer
        pending_tasks = self._analyze_tracking_data(data)

        if not pending_tasks:
            print(f"      ✅ No pending tasks for {employee_username}")
            return

        # Format reminder message
        message = self._format_reminder_message(employee_username, friendly_name, pending_tasks)

        # Send to channel
        await channel.send(message)
        print(f"      ✅ Reminder sent for {employee_username}")

    def _analyze_tracking_data(self, data: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Analyze tracking sheet data and group pending tasks by customer

        Args:
            data: List of row dictionaries from Tracking sheet

        Returns:
            Dict mapping customer names to their pending tasks
        """
        # Get all customer columns (skip first 4: sportsbook, deposit, method, bet type)
        if not data:
            return {}

        first_row = data[0]
        all_columns = list(first_row.keys())

        # Identify customer columns (anything after the first few metadata columns)
        # Metadata columns typically: sportsbook name, DEPOSIT, METHOD, BET TYPE
        customer_columns = []
        metadata_keywords = ['deposit', 'method', 'bet', 'type', 'sports']

        for col in all_columns:
            col_lower = col.lower()
            # Skip if it's a metadata column
            if any(keyword in col_lower for keyword in metadata_keywords):
                continue
            # This is a customer column
            customer_columns.append(col)

        print(f"      📋 Found {len(customer_columns)} customer columns: {customer_columns}")

        # Group pending tasks by customer
        pending_by_customer = {}

        for row in data:
            # Get sportsbook name (usually first column that's not empty)
            sportsbook = None
            for col in all_columns[:4]:  # Check first few columns for sportsbook name
                if row.get(col) and not any(keyword in row.get(col, '').lower() for keyword in
                                            ['$', 'debit', 'etransfer', 'rfb', 'lowhold', 'baccarat']):
                    sportsbook = row.get(col)
                    break

            if not sportsbook:
                continue

            # Check each customer's status for this sportsbook
            for customer in customer_columns:
                status = row.get(customer, "").strip()

                # Skip if complete or done
                if status.lower() in ['complete', 'done']:
                    continue

                # This is a pending task
                if customer not in pending_by_customer:
                    pending_by_customer[customer] = []

                # Interpret the status
                interpreted_status = self._interpret_status(status)

                pending_by_customer[customer].append({
                    'sportsbook': sportsbook,
                    'status': status,
                    'interpreted': interpreted_status
                })

        return pending_by_customer

    def _interpret_status(self, status: str) -> str:
        """
        Interpret status code into human-readable text

        Args:
            status: Raw status from sheet

        Returns:
            Human-readable interpretation
        """
        if not status or status == "":
            return "Not started (blank)"

        status_lower = status.lower()

        # Direct interpretations
        if status_lower == "verify":
            return "Needs verification"
        elif status_lower == "verifyfix":
            return "Needs verification fix"
        elif status_lower == "ready":
            return "Ready to proceed"
        elif status_lower == "signed up ready":
            return "Account created, ready for deposit"
        elif status_lower == "vip":
            return "VIP status achieved"
        elif status_lower == "deposit":
            return "Needs deposit"
        elif "week" in status_lower:
            return f"{status} in progress"
        elif status_lower in ["1k", "1000", "500", "2000", "3000", "5000"]:
            # Dollar amounts
            amount = status_lower.replace('k', '000') if 'k' in status_lower else status_lower
            return f"Ready with ${amount}"
        elif status_lower.replace('k', '').replace('$', '').replace(',', '').isdigit():
            # Any other number
            return f"Ready with ${status}"
        else:
            # Return as-is if we don't recognize it
            return status

    def _format_reminder_message(self, employee_username: str, friendly_name: str,
                                 pending_tasks: Dict[str, List[Dict]]) -> str:
        """
        Format reminder message

        Args:
            employee_username: Employee's Discord username
            friendly_name: Employee's friendly name
            pending_tasks: Dict of customer -> list of pending tasks

        Returns:
            Formatted Discord message
        """
        # Count total tasks
        total_tasks = sum(len(tasks) for tasks in pending_tasks.values())

        message_parts = [
            f"<@{employee_username}> Daily Task Reminder - {friendly_name}'s Tracking Sheet",
            "",
            "📋 **Tasks Needing Attention:**",
            ""
        ]

        # Add each customer's tasks
        for customer, tasks in sorted(pending_tasks.items()):
            message_parts.append(f"**{customer}:**")
            for task in tasks:
                message_parts.append(f"• {task['sportsbook']} - {task['interpreted']}")
            message_parts.append("")  # Blank line between customers

        # Add summary
        message_parts.append(f"**Total:** {len(pending_tasks)} customers with {total_tasks} pending tasks")

        return "\n".join(message_parts)

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("⏰ Scheduler stopped")
