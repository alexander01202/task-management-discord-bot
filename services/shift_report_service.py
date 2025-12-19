"""
Shift Report Service - Change detection and report generation
"""
from typing import List, Dict, Set, Tuple
from datetime import datetime, date
import discord

from database.snapshot_repository import SnapshotRepository
from services.google_sheets import GoogleSheetsService
from config.config import (
    EMPLOYEE_SHEETS,
    EMPLOYEE_FRIENDLY_NAMES,
    EMPLOYEE_DISCORD_IDS
)


class ChangeReport:
    """Data class for storing change analysis results"""

    def __init__(self, employee_username: str):
        self.employee_username = employee_username
        self.completions: List[Dict] = []  # Tasks completed
        self.vip_flags: List[Dict] = []  # Errors (changed to VIP)
        self.help_needed: List[Dict] = []  # Morning attention (changed to help)
        self.customers_updated: Set[str] = set()  # Unique customers with ANY change
        self.all_changes: List[Dict] = []  # All cell changes for debugging

    def get_friendly_name(self) -> str:
        """Get friendly name for employee"""
        for friendly, username in EMPLOYEE_FRIENDLY_NAMES.items():
            if username == self.employee_username:
                return friendly.title()
        return self.employee_username


class ShiftReportService:
    """Handles shift summary generation"""

    def __init__(self, sheets_service: GoogleSheetsService):
        """Initialize service"""
        self.sheets_service = sheets_service
        self.snapshot_repo = SnapshotRepository()

    async def take_baseline_snapshots(self):
        """
        Take morning baseline snapshots for all employees
        Called at 8 AM
        """
        print("\n" + "=" * 60)
        print(f"📸 TAKING BASELINE SNAPSHOTS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        for employee_username in EMPLOYEE_SHEETS.keys():
            try:
                print(f"\n📊 Processing {employee_username}...")

                # Check if baseline already exists today
                if self.snapshot_repo.get_baseline_exists_today(employee_username):
                    print(f"   ⚠️  Baseline already exists for today, skipping")
                    continue

                # Fetch current sheet data
                result = self.sheets_service.get_employee_sheet(
                    employee_username=employee_username,
                    requester_username=employee_username,
                    query="tracking"
                )

                if not result or "data" not in result:
                    print(f"   ❌ Could not fetch sheet for {employee_username}")
                    continue

                sheet_data = result["data"]

                # Store as baseline
                success = self.snapshot_repo.store_snapshot(
                    employee_username=employee_username,
                    worksheet_name="Tracking",
                    snapshot_data=sheet_data,
                    is_baseline=True,
                    notes="Morning baseline snapshot"
                )

                if success:
                    print(f"   ✅ Baseline snapshot saved ({len(sheet_data)} rows)")
                else:
                    print(f"   ❌ Failed to save baseline")

            except Exception as e:
                print(f"   ❌ Error processing {employee_username}: {e}")
                import traceback
                traceback.print_exc()

        print("=" * 60)
        print("✅ Baseline snapshot process completed")
        print("=" * 60)

    def _get_customer_columns(self, row: Dict) -> List[str]:
        """
        Identify customer columns in a row (skip metadata columns)

        Args:
            row: Sheet row dict

        Returns:
            List of customer column names
        """
        if not row:
            return []

        all_columns = list(row.keys())

        # Metadata keywords to skip
        METADATA_KEYWORDS = ['deposit', 'method', 'bet', 'type']
        CATEGORY_KEYWORDS = ['casino', 'slots', 'blackjack', 'sports', 'baccarat']

        customer_columns = []

        for col in all_columns:
            col_lower = col.lower()

            # Skip metadata columns
            if any(keyword in col_lower for keyword in METADATA_KEYWORDS):
                continue

            # Skip category headers
            if col_lower in CATEGORY_KEYWORDS:
                continue

            # Skip if it looks like a sportsbook name column (first column)
            col_value = row.get(col, "").strip().lower()
            if not col_value or any(keyword in col_value for keyword in ['$', 'debit', 'etransfer']):
                continue

            customer_columns.append(col)

        return customer_columns

    def _get_sportsbook_name(self, row: Dict) -> str:
        """
        Extract sportsbook name from a row

        Args:
            row: Sheet row dict

        Returns:
            Sportsbook name or "Unknown"
        """
        # Try to find sportsbook in first few columns
        for col in list(row.keys())[:6]:
            value = row.get(col, "").strip()
            col_lower = col.lower()

            # Skip if it's clearly metadata
            if any(keyword in col_lower for keyword in ['deposit', 'method', 'bet', 'type']):
                continue

            # Skip if value looks like metadata
            if any(keyword in value.lower() for keyword in ['$', 'debit', 'etransfer', 'rfb', 'lowhold']):
                continue

            # This looks like a sportsbook
            if value:
                return value

        return "Unknown"

    def _detect_changes(self, baseline_data: List[Dict], current_data: List[Dict]) -> ChangeReport:
        """
        Detect changes between baseline and current snapshots

        Args:
            baseline_data: Morning baseline sheet data
            current_data: Current sheet data

        Returns:
            ChangeReport with detected changes
        """
        # Extract employee username from the data (we'll pass it in)
        report = ChangeReport("unknown")

        # Handle empty data
        if not baseline_data or not current_data:
            return report

        # Get customer columns from first row
        if baseline_data and current_data:
            customer_columns = self._get_customer_columns(baseline_data[0])
        else:
            return report

        print(f"   📋 Tracking {len(customer_columns)} customers: {customer_columns}")

        # Build lookup for current data by sportsbook
        current_by_sportsbook = {}
        for row in current_data:
            sportsbook = self._get_sportsbook_name(row)
            if sportsbook and sportsbook != "Unknown":
                current_by_sportsbook[sportsbook] = row

        # Compare each baseline row with current
        for baseline_row in baseline_data:
            sportsbook = self._get_sportsbook_name(baseline_row)

            # Skip category rows
            sportsbook_clean = sportsbook.lower().rstrip(':').strip()
            CATEGORY_KEYWORDS = ['casino', 'slots', 'blackjack', 'sports', 'baccarat']
            if sportsbook_clean in CATEGORY_KEYWORDS:
                continue

            # Find matching row in current data
            current_row = current_by_sportsbook.get(sportsbook)
            if not current_row:
                continue

            # Compare each customer column
            for customer in customer_columns:
                old_status = baseline_row.get(customer, "").strip().lower()
                new_status = current_row.get(customer, "").strip().lower()

                # Detect change
                if old_status != new_status:
                    # Track this customer as updated
                    report.customers_updated.add(customer)

                    # Record the change
                    change = {
                        'sportsbook': sportsbook,
                        'customer': customer,
                        'old_status': old_status,
                        'new_status': new_status
                    }
                    report.all_changes.append(change)

                    # Categorize change type
                    if new_status in ['done', 'complete']:
                        report.completions.append(change)

                    if new_status == 'vip':
                        report.vip_flags.append(change)

                    if new_status == 'help':
                        report.help_needed.append(change)

        return report

    async def generate_shift_report(self, bot: discord.Client, channel_id: int):
        """
        Generate and post the evening shift report
        Called at 11 PM

        Args:
            bot: Discord bot instance
            channel_id: Channel ID to post report to
        """
        print("\n" + "=" * 60)
        print(f"📊 GENERATING SHIFT REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Get report channel
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"   ❌ Could not find channel with ID: {channel_id}")
            return

        # Collect reports for all employees
        all_reports: Dict[str, ChangeReport] = {}

        for employee_username in EMPLOYEE_SHEETS.keys():
            try:
                print(f"\n📊 Analyzing {employee_username}...")

                # Get today's baseline
                baseline = self.snapshot_repo.get_latest_baseline(
                    employee_username=employee_username,
                    worksheet_name="Tracking"
                )

                if not baseline:
                    print(f"   ⚠️  No baseline found for {employee_username} today")
                    continue

                # Fetch current sheet data
                result = self.sheets_service.get_employee_sheet(
                    employee_username=employee_username,
                    requester_username=employee_username,
                    query="tracking"
                )

                if not result or "data" not in result:
                    print(f"   ❌ Could not fetch current sheet for {employee_username}")
                    continue

                current_data = result["data"]

                # Detect changes
                report = self._detect_changes(baseline['snapshot_data'], current_data)
                report.employee_username = employee_username

                print(f"   ✅ Analysis complete:")
                print(f"      - Completions: {len(report.completions)}")
                print(f"      - Customers updated: {len(report.customers_updated)}")
                print(f"      - VIP flags: {len(report.vip_flags)}")
                print(f"      - Help needed: {len(report.help_needed)}")

                all_reports[employee_username] = report

                # Store current state as snapshot (for history)
                self.snapshot_repo.store_snapshot(
                    employee_username=employee_username,
                    worksheet_name="Tracking",
                    snapshot_data=current_data,
                    is_baseline=False,
                    notes="Evening snapshot for shift report"
                )

            except Exception as e:
                print(f"   ❌ Error analyzing {employee_username}: {e}")
                import traceback
                traceback.print_exc()

        # Format and send report
        if all_reports:
            await self._send_shift_report(channel, all_reports)
        else:
            print(f"   ⚠️  No reports generated")

        print("=" * 60)
        print("✅ Shift report process completed")
        print("=" * 60)

    async def _send_shift_report(self, channel: discord.TextChannel, all_reports: Dict[str, ChangeReport]):
        """
        Format and send the shift report to Discord

        Args:
            channel: Discord channel to send to
            all_reports: Dict of employee_username -> ChangeReport
        """
        # Calculate totals
        total_completions = sum(len(r.completions) for r in all_reports.values())
        total_customers = len(set().union(*[r.customers_updated for r in all_reports.values()]))
        total_vip_flags = sum(len(r.vip_flags) for r in all_reports.values())
        total_help_needed = sum(len(r.help_needed) for r in all_reports.values())

        # Create main embed
        embed = discord.Embed(
            title="📊 Daily Shift Summary",
            description=f"**{datetime.now().strftime('%B %d, %Y')}**",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # Add employee sections
        for employee_username, report in sorted(all_reports.items()):
            friendly_name = report.get_friendly_name()

            # Build value text
            value_lines = [
                f"✅ **{len(report.completions)}** tasks completed",
                f"👥 **{len(report.customers_updated)}** customers updated"
            ]

            value = "\n".join(value_lines)

            embed.add_field(
                name=f"{friendly_name}",
                value=value,
                inline=True
            )

        # Add spacing
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # Global alerts - VIP Flags (Errors)
        if total_vip_flags > 0:
            vip_lines = []
            for employee_username, report in all_reports.items():
                if report.vip_flags:
                    friendly_name = report.get_friendly_name()
                    for change in report.vip_flags:
                        vip_lines.append(
                            f"• **{friendly_name}** - {change['sportsbook']}/{change['customer']}"
                        )

            if vip_lines:
                vip_text = "\n".join(vip_lines[:10])  # Limit to 10
                if len(vip_lines) > 10:
                    vip_text += f"\n*... and {len(vip_lines) - 10} more*"

                embed.add_field(
                    name=f"⚠️ ERRORS FLAGGED ({total_vip_flags})",
                    value=vip_text,
                    inline=False
                )

        # Morning attention - Help needed
        if total_help_needed > 0:
            help_lines = []
            for employee_username, report in all_reports.items():
                if report.help_needed:
                    friendly_name = report.get_friendly_name()
                    for change in report.help_needed:
                        help_lines.append(
                            f"• **{friendly_name}** - {change['sportsbook']}/{change['customer']}"
                        )

            if help_lines:
                help_text = "\n".join(help_lines[:10])  # Limit to 10
                if len(help_lines) > 10:
                    help_text += f"\n*... and {len(help_lines) - 10} more*"

                embed.add_field(
                    name=f"🌅 MORNING ATTENTION ({total_help_needed})",
                    value=help_text,
                    inline=False
                )

        # Summary footer
        summary_parts = [
            f"{total_completions} tasks ✅",
            f"{total_customers} customers 👥"
        ]

        if total_vip_flags > 0:
            summary_parts.append(f"{total_vip_flags} errors ⚠️")

        if total_help_needed > 0:
            summary_parts.append(f"{total_help_needed} flags 🌅")

        embed.set_footer(text=f"Summary: {' | '.join(summary_parts)}")

        # Send the report
        try:
            await channel.send(embed=embed)
            print(f"   ✅ Shift report posted to channel {channel.name}")
        except Exception as e:
            print(f"   ❌ Error sending report: {e}")
            import traceback
            traceback.print_exc()
