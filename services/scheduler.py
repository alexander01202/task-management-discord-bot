"""
Scheduler service for:
- Automated daily task reminders
- User-created reminders
- Shift summary reports (baseline snapshots + evening report)
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import discord
from datetime import datetime
from typing import Dict, List

from services.google_sheets import GoogleSheetsService
from services.reminder_service import ReminderService
from services.shift_report_service import ShiftReportService
from config.config import (
    EMPLOYEE_SHEETS,
    EMPLOYEE_FRIENDLY_NAMES,
    REMINDER_CHANNEL_ID,
    REMINDER_TIME_HOUR,
    REMINDER_TIME_MINUTE,
    EMPLOYEE_DISCORD_IDS,
    SHIFT_REPORT_CHANNEL_ID,
    BASELINE_SNAPSHOT_HOUR,
    BASELINE_SNAPSHOT_MINUTE,
    SHIFT_REPORT_HOUR,
    SHIFT_REPORT_MINUTE
)


class ReminderScheduler:
    """Handles all scheduled jobs: reminders, shift reports, etc."""

    def __init__(
        self,
        bot: discord.Client,
        sheets_service: GoogleSheetsService,
        reminder_service: ReminderService = None,
        shift_report_service: ShiftReportService = None
    ):
        """
        Initialize scheduler

        Args:
            bot: Discord bot instance
            sheets_service: Google Sheets service instance
            reminder_service: Reminder service instance for user reminders
            shift_report_service: Shift report service instance
        """
        self.bot = bot
        self.sheets_service = sheets_service
        self.reminder_service = reminder_service or ReminderService()
        self.shift_report_service = shift_report_service or ShiftReportService(sheets_service)
        self.scheduler = AsyncIOScheduler()

    def start(self):
        """Start the scheduler with all jobs"""
        print("\n⏰ Initializing Scheduler...")

        # ==================== DAILY TASK REMINDERS ====================
        daily_trigger = CronTrigger(
            hour=REMINDER_TIME_HOUR,
            minute=REMINDER_TIME_MINUTE,
            timezone='America/Toronto'
        )

        self.scheduler.add_job(
            self.send_daily_reminders,
            trigger=daily_trigger,
            id='daily_task_reminders',
            name='Daily Task Reminders',
            replace_existing=True
        )

        print(f"   ✅ Daily sheet reminders scheduled for {REMINDER_TIME_HOUR:02d}:{REMINDER_TIME_MINUTE:02d}")

        # ==================== USER REMINDERS ====================
        user_reminder_trigger = IntervalTrigger(minutes=1)

        self.scheduler.add_job(
            self.check_user_reminders,
            trigger=user_reminder_trigger,
            id='user_reminders_check',
            name='User Reminders Check',
            replace_existing=True
        )

        print(f"   ✅ User reminder checks scheduled (every 1 minute)")

        # ==================== BASELINE SNAPSHOTS ====================
        baseline_trigger = CronTrigger(
            hour=BASELINE_SNAPSHOT_HOUR,
            minute=BASELINE_SNAPSHOT_MINUTE,
            timezone='America/Toronto'
        )

        self.scheduler.add_job(
            self.take_baseline_snapshots,
            trigger=baseline_trigger,
            id='baseline_snapshots',
            name='Baseline Snapshots',
            replace_existing=True
        )

        print(f"   ✅ Baseline snapshots scheduled for {BASELINE_SNAPSHOT_HOUR:02d}:{BASELINE_SNAPSHOT_MINUTE:02d}")

        # ==================== SHIFT REPORT ====================
        shift_report_trigger = CronTrigger(
            hour=SHIFT_REPORT_HOUR,
            minute=SHIFT_REPORT_MINUTE,
            timezone='America/Toronto'
        )

        self.scheduler.add_job(
            self.generate_shift_report,
            trigger=shift_report_trigger,
            id='shift_report',
            name='Shift Report',
            replace_existing=True
        )

        print(f"   ✅ Shift report scheduled for {SHIFT_REPORT_HOUR:02d}:{SHIFT_REPORT_MINUTE:02d}")

        # Start the scheduler
        self.scheduler.start()

        print(f"   ✅ Scheduler started")
        print("=" * 60)

    # ==================== SHIFT REPORT JOBS ====================

    async def take_baseline_snapshots(self):
        """Take morning baseline snapshots (called at 8 AM)"""
        try:
            await self.shift_report_service.take_baseline_snapshots()
        except Exception as e:
            print(f"❌ Error in baseline snapshot job: {e}")
            import traceback
            traceback.print_exc()

    async def generate_shift_report(self):
        """Generate evening shift report (called at 11 PM)"""
        try:
            await self.shift_report_service.generate_shift_report(
                bot=self.bot,
                channel_id=SHIFT_REPORT_CHANNEL_ID
            )
        except Exception as e:
            print(f"❌ Error in shift report job: {e}")
            import traceback
            traceback.print_exc()

    # ==================== USER REMINDERS ====================

    async def check_user_reminders(self):
        """Check for and send any pending user-created reminders"""
        try:
            # Get all pending reminders that should be sent now
            reminders = self.reminder_service.get_pending_reminders()

            if not reminders:
                return  # No reminders to send

            print(f"\n⏰ Found {len(reminders)} reminder(s) to send...")

            for reminder in reminders:
                try:
                    await self._send_user_reminder(reminder)
                except Exception as e:
                    print(f"   ❌ Error sending reminder {reminder['id']}: {e}")
                    import traceback
                    traceback.print_exc()

        except Exception as e:
            print(f"   ❌ Error checking user reminders: {e}")
            import traceback
            traceback.print_exc()

    async def _send_user_reminder(self, reminder: Dict):
        """
        Send a specific user-created reminder

        Args:
            reminder: Reminder dictionary from database
        """
        reminder_id = reminder['id']
        target_username = reminder['target_username']
        target_user_id = reminder.get('target_user_id')
        reminder_text = reminder['reminder_text']
        channel_id = reminder['channel_id']
        creator_username = reminder['creator_username']

        print(f"   📨 Sending reminder #{reminder_id} to {target_username}...")

        # Get the channel
        channel = self.bot.get_channel(int(channel_id))

        if not channel:
            print(f"      ❌ Could not find channel {channel_id}")
            # Still mark as sent to avoid repeated attempts
            self.reminder_service.mark_reminder_sent(reminder_id)
            return

        # Format the reminder message
        mention = f"<@{target_user_id}>" if target_user_id else f"@{target_username}"

        if creator_username == target_username:
            # Self-reminder
            message = f"⏰ {mention} Reminder: {reminder_text}"
        else:
            # Reminder from someone else
            from utils.permissions import PermissionManager
            creator_friendly = PermissionManager.get_employee_friendly_name(creator_username)
            creator_display = creator_friendly.title() if creator_friendly else creator_username
            message = f"⏰ {mention} Reminder from {creator_display}: {reminder_text}"

        try:
            await channel.send(message)
            print(f"      ✅ Reminder #{reminder_id} sent successfully")

            # Mark as sent
            self.reminder_service.mark_reminder_sent(reminder_id)

        except Exception as e:
            print(f"      ❌ Error sending reminder message: {e}")
            # Still mark as sent to avoid spam
            self.reminder_service.mark_reminder_sent(reminder_id)

    # ==================== DAILY TASK REMINDERS ====================

    async def send_daily_reminders(self):
        """Send daily task reminders to all employees (from sheets)"""
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
        Send reminder for a specific employee (from sheets)

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
        tasks_by_customer = self._analyze_tracking_data(data)

        if not tasks_by_customer:
            print(f"      ✅ No pending tasks for {employee_username}")
            return

        # Check if we should send blank tasks reminder (72-hour interval)
        should_send_signups = self._should_send_blank_reminder(employee_username)

        # Filter tasks based on reminder schedule
        filtered_tasks = {}
        for customer, action_groups in tasks_by_customer.items():
            filtered_actions = {}

            for action_type, tasks in action_groups.items():
                # Only include signup tasks if 72+ hours have passed
                if action_type == 'signup':
                    if should_send_signups:
                        filtered_actions[action_type] = tasks
                else:
                    # All other action types always included
                    filtered_actions[action_type] = tasks

            # Only add customer if they have tasks after filtering
            if filtered_actions:
                filtered_tasks[customer] = filtered_actions

        if not filtered_tasks:
            print(f"      ✅ No tasks to remind about today for {employee_username}")
            return

        # Format reminder message
        message = self._format_reminder_message(employee_username, friendly_name, filtered_tasks)

        # Send to channel
        if message is None:
            # Message too long, split by customer
            print(f"      ✂️  Splitting message by customer...")
            await self._send_split_reminders(channel, employee_username, friendly_name, filtered_tasks)
        else:
            await channel.send(message)
            print(f"      ✅ Reminder sent for {employee_username}")

        # Update blank task reminder timestamp if we sent them
        if should_send_signups:
            self._update_blank_reminder_timestamp(employee_username)

    def _analyze_tracking_data(self, data: List[Dict]) -> Dict[str, Dict]:
        """
        Analyze tracking sheet data and group pending tasks by customer

        Args:
            data: List of row dictionaries from Tracking sheet

        Returns:
            Dict with tasks grouped by action type for each customer
        """
        # Get all customer columns (skip first 4: sportsbook, deposit, method, bet type)
        if not data:
            return {}

        first_row = data[0]
        all_columns = list(first_row.keys())

        # Category keywords to filter out (these are section headers, not sportsbooks)
        CATEGORY_KEYWORDS = ['casino', 'slots', 'blackjack', 'sports', 'baccarat']

        # Identify customer columns (anything after the first few metadata columns)
        customer_columns = []
        metadata_keywords = ['deposit', 'method', 'bet', 'type']

        for col in all_columns:
            col_lower = col.lower()
            # Skip if it's a metadata column
            if any(keyword in col_lower for keyword in metadata_keywords):
                continue

            # Skip if it's a category keyword (SPORTS:, CASINO:, etc.)
            if col_lower in CATEGORY_KEYWORDS or any(
                    col_lower.startswith(keyword) for keyword in CATEGORY_KEYWORDS):
                continue

            # This is a customer column
            customer_columns.append(col)

        print(f"      📋 Found {len(customer_columns)} customer columns: {customer_columns}")

        # Group tasks by customer and action type
        tasks_by_customer = {}

        for row in data:
            # Get sportsbook details
            sportsbook = None
            deposit = ""
            method = ""
            bet_type = ""

            # Try to extract sportsbook details
            for col in all_columns[:6]:
                value = row.get(col, "").strip()
                col_lower = col.lower()

                if not value:
                    continue

                if 'deposit' in col_lower and '$' in value:
                    deposit = value
                elif 'method' in col_lower:
                    method = value
                elif 'bet' in col_lower or 'type' in col_lower:
                    bet_type = value
                elif not sportsbook and not any(keyword in value.lower() for keyword in ['$', 'debit', 'etransfer', 'rfb', 'lowhold', 'baccarat']):
                    sportsbook = value

            if not sportsbook:
                continue

            # Skip category rows (CASINO, SLOTS, BLACKJACK, SPORTS, etc.)
            sportsbook_clean = sportsbook.lower().rstrip(':').strip()
            if (sportsbook_clean in CATEGORY_KEYWORDS or
                    any(sportsbook_clean.startswith(keyword) for keyword in CATEGORY_KEYWORDS)
            ):
                continue

            # Check each customer's status for this sportsbook
            for customer in customer_columns:
                status = row.get(customer, "").strip()

                # Skip if complete or done
                if status.lower() in ['complete', 'done']:
                    continue

                # Initialize customer dict if needed
                if customer not in tasks_by_customer:
                    tasks_by_customer[customer] = {}

                # Determine action type
                action_type = self._get_action_type(status)

                # Initialize action type list if needed
                if action_type not in tasks_by_customer[customer]:
                    tasks_by_customer[customer][action_type] = []

                # Add sportsbook to this action type
                tasks_by_customer[customer][action_type].append({
                    'sportsbook': sportsbook,
                    'deposit': deposit,
                    'bet_type': bet_type,
                    'status': status
                })

        return tasks_by_customer

    def _get_action_type(self, status: str) -> str:
        """
        Determine the action type based on status

        Args:
            status: Task status

        Returns:
            Action type category
        """
        if not status or status == "":
            return "signup"

        status_lower = status.lower()

        # Verification
        if status_lower in ["verify", "verifyfix"]:
            return "verification"

        # Deposit
        if status_lower in ["deposit", "signed up ready"]:
            return "deposit"

        # Wager (ready with amount)
        if status_lower in ["ready", "1k", "1000", "500", "2000", "2500", "3000", "5000"]:
            return "wager"

        if status_lower.replace('k', '').replace('$', '').replace(',', '').isdigit():
            return "wager"

        # Week progress
        if "week" in status_lower:
            return "progress"

        # VIP
        if status_lower == "vip":
            return "vip"

        # Default - other
        return "other"

    def _format_reminder_message(self, employee_username: str, friendly_name: str, tasks_by_customer: Dict[str, Dict]) -> str:
        """
        Format reminder message with tasks grouped by action type

        Args:
            employee_username: Employee's Discord username
            friendly_name: Employee's friendly name
            tasks_by_customer: Dict with tasks grouped by action type per customer

        Returns:
            Formatted Discord message or None if too long
        """
        discord_id = EMPLOYEE_DISCORD_IDS.get(employee_username, employee_username)
        message_parts = [
            f"<@{discord_id}> \n\n"
            f"📋 Daily Task Reminder - {friendly_name}'s Tracking Sheet",
            ""
        ]

        # Define action type labels and order
        action_labels = {
            'signup': 'Need to signup for',
            'verification': 'Complete verification for',
            'deposit': 'Complete deposit for',
            'wager': 'Complete wager for',
            'progress': 'Continue progress for',
            'vip': 'VIP tasks',
            'other': 'Other tasks'
        }

        action_order = ['signup', 'verification', 'deposit', 'wager', 'progress', 'vip', 'other']

        # Add each customer's tasks grouped by action
        for customer, action_groups in sorted(tasks_by_customer.items()):
            if not action_groups:
                continue

            message_parts.append(f"**{customer}:**")

            for action_type in action_order:
                if action_type not in action_groups or not action_groups[action_type]:
                    continue

                # Get list of sportsbook names
                sportsbooks = [task['sportsbook'] for task in action_groups[action_type]]
                sportsbooks_str = ", ".join(sportsbooks)

                # Format the line
                label = action_labels.get(action_type, action_type)
                message_parts.append(f"• {label} {sportsbooks_str}")

            message_parts.append("")  # Blank line between customers

        full_message = "\n".join(message_parts)

        # Discord has a 2000 char limit for regular messages
        # Let's use 1900 to be safe
        MAX_LENGTH = 1900

        if len(full_message) > MAX_LENGTH:
            # Message too long - split by customer
            print(f"      ⚠️  Message too long ({len(full_message)} chars), splitting by customer...")
            return None  # Signal to split and send separately

        return full_message

    async def _send_split_reminders(self, channel: discord.TextChannel, employee_username: str, friendly_name: str, tasks_by_customer: Dict[str, Dict]):
        """
        Send reminders split by customer when message is too long

        Args:
            channel: Discord channel
            employee_username: Employee's Discord username
            friendly_name: Employee's friendly name
            tasks_by_customer: Dict with tasks grouped by action type per customer
        """
        # Send header message
        discord_id = EMPLOYEE_DISCORD_IDS.get(employee_username, employee_username)
        header = f"<@{discord_id}> Daily Task Reminder - {friendly_name}'s Tracking Sheet"
        await channel.send(header)

        # Define action type labels and order
        action_labels = {
            'signup': 'Need to signup for',
            'verification': 'Complete verification for',
            'deposit': 'Complete deposit for',
            'wager': 'Complete wager for',
            'progress': 'Continue progress for',
            'vip': 'VIP tasks',
            'other': 'Other tasks'
        }

        action_order = ['signup', 'verification', 'deposit', 'wager', 'progress', 'vip', 'other']

        # Send each customer's tasks as separate message
        for customer, action_groups in sorted(tasks_by_customer.items()):
            if not action_groups:
                continue

            customer_parts = [f"**{customer}:**"]

            for action_type in action_order:
                if action_type not in action_groups or not action_groups[action_type]:
                    continue

                # Get list of sportsbook names
                sportsbooks = [task['sportsbook'] for task in action_groups[action_type]]
                sportsbooks_str = ", ".join(sportsbooks)

                # Format the line
                label = action_labels.get(action_type, action_type)
                customer_parts.append(f"• {label} {sportsbooks_str}")

            customer_message = "\n".join(customer_parts)
            await channel.send(customer_message)

        print(f"      ✅ Sent {len(tasks_by_customer)} split messages for {employee_username}")

    def _should_send_blank_reminder(self, employee_username: str) -> bool:
        """
        Check if we should send blank task reminders (every 72 hours)

        Args:
            employee_username: Employee's Discord username

        Returns:
            True if 72+ hours since last blank reminder, False otherwise
        """
        import os
        from datetime import datetime, timedelta

        # Use a simple file to track last blank reminder time
        tracking_file = f"tmp/blank_reminder_{employee_username}.txt"

        if not os.path.exists(tracking_file):
            # Never sent before, send now
            return True

        try:
            with open(tracking_file, 'r') as f:
                last_sent_str = f.read().strip()
                last_sent = datetime.fromisoformat(last_sent_str)

            # Check if 72 hours have passed
            hours_since = (datetime.now() - last_sent).total_seconds() / 3600

            if hours_since >= 72:
                print(f"      ⏰ 72+ hours since last blank reminder ({hours_since:.1f}h), sending blanks")
                return True
            else:
                print(f"      ⏰ Only {hours_since:.1f}h since last blank reminder, skipping blanks")
                return False

        except Exception as e:
            print(f"      ⚠️  Error reading blank reminder timestamp: {e}, sending anyway")
            return True

    def _update_blank_reminder_timestamp(self, employee_username: str):
        """
        Update the timestamp for last blank task reminder

        Args:
            employee_username: Employee's Discord username
        """
        import os

        tracking_file = f"tmp/blank_reminder_{employee_username}.txt"

        # Ensure tmp directory exists
        os.makedirs('tmp', exist_ok=True)

        try:
            with open(tracking_file, 'w') as f:
                f.write(datetime.now().isoformat())
            print(f"      ✅ Updated blank reminder timestamp")
        except Exception as e:
            print(f"      ⚠️  Error updating blank reminder timestamp: {e}")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("⏰ Scheduler stopped")
