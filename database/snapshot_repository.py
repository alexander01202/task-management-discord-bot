"""
Snapshot Repository - Handles sheet snapshot storage and retrieval
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
from supabase import Client, create_client
from config.config import SUPABASE_URL, SUPABASE_KEY
import json


class SnapshotRepository:
    """Manages sheet snapshot persistence"""

    def __init__(self):
        """Initialize Supabase client"""
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def store_snapshot(
            self,
            employee_username: str,
            worksheet_name: str,
            snapshot_data: List[Dict],
            is_baseline: bool = False,
            notes: str = None
    ) -> bool:
        """
        Store a sheet snapshot

        Args:
            employee_username: Employee's Discord username
            worksheet_name: Name of worksheet (e.g., "Tracking")
            snapshot_data: List of row dictionaries from sheet
            is_baseline: Whether this is the morning baseline
            notes: Optional notes

        Returns:
            True if successful
        """
        print(f"\n💾 Storing snapshot for {employee_username}/{worksheet_name}...")
        print(f"   Baseline: {is_baseline}")
        print(f"   Rows: {len(snapshot_data)}")

        try:
            data = {
                "employee_username": employee_username,
                "worksheet_name": worksheet_name,
                "snapshot_data": json.dumps(snapshot_data),  # Convert to JSON string
                "is_baseline": is_baseline,
                "notes": notes,
                "snapshot_time": datetime.now().isoformat()
            }

            result = self.client.table("sheet_snapshots").insert(data).execute()
            print(f"   ✅ Snapshot stored (ID: {result.data[0]['id']})")
            return True

        except Exception as e:
            print(f"   ❌ Error storing snapshot: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_latest_baseline(
            self,
            employee_username: str,
            worksheet_name: str = "Tracking",
            target_date: date = None
    ) -> Optional[Dict]:
        """
        Get the most recent baseline snapshot for an employee

        Args:
            employee_username: Employee's Discord username
            worksheet_name: Name of worksheet
            target_date: Specific date to get baseline for (defaults to today)

        Returns:
            Snapshot dict with 'id', 'snapshot_data', 'snapshot_time', or None
        """
        print(f"\n📖 Fetching baseline for {employee_username}/{worksheet_name}...")

        try:
            if target_date is None:
                target_date = date.today()

            # Get start and end of target date
            start_of_day = datetime.combine(target_date, datetime.min.time())
            end_of_day = datetime.combine(target_date, datetime.max.time())

            response = self.client.table("sheet_snapshots") \
                .select("*") \
                .eq("employee_username", employee_username) \
                .eq("worksheet_name", worksheet_name) \
                .eq("is_baseline", True) \
                .gte("snapshot_time", start_of_day.isoformat()) \
                .lte("snapshot_time", end_of_day.isoformat()) \
                .order("snapshot_time", desc=True) \
                .limit(1) \
                .execute()

            if response.data:
                snapshot = response.data[0]
                # Parse JSON string back to list
                snapshot['snapshot_data'] = json.loads(snapshot['snapshot_data'])
                print(f"   ✅ Found baseline (ID: {snapshot['id']})")
                return snapshot
            else:
                print(f"   ⚠️  No baseline found for {target_date}")
                return None

        except Exception as e:
            print(f"   ❌ Error fetching baseline: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_snapshots_for_date_range(
            self,
            employee_username: str,
            worksheet_name: str,
            start_date: date,
            end_date: date
    ) -> List[Dict]:
        """
        Get all snapshots for an employee within a date range

        Args:
            employee_username: Employee's Discord username
            worksheet_name: Name of worksheet
            start_date: Start date
            end_date: End date

        Returns:
            List of snapshot dicts
        """
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            response = self.client.table("sheet_snapshots") \
                .select("*") \
                .eq("employee_username", employee_username) \
                .eq("worksheet_name", worksheet_name) \
                .gte("snapshot_time", start_datetime.isoformat()) \
                .lte("snapshot_time", end_datetime.isoformat()) \
                .order("snapshot_time", desc=True) \
                .execute()

            snapshots = response.data if response.data else []

            # Parse JSON strings
            for snapshot in snapshots:
                snapshot['snapshot_data'] = json.loads(snapshot['snapshot_data'])

            return snapshots

        except Exception as e:
            print(f"   ❌ Error fetching snapshots: {e}")
            return []

    def delete_old_snapshots(self, days_to_keep: int = 30) -> int:
        """
        Delete snapshots older than specified days

        Args:
            days_to_keep: Number of days to keep snapshots

        Returns:
            Number of snapshots deleted
        """
        print(f"\n🗑️  Cleaning up snapshots older than {days_to_keep} days...")

        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            response = self.client.table("sheet_snapshots") \
                .delete() \
                .lt("snapshot_time", cutoff_date.isoformat()) \
                .execute()

            deleted_count = len(response.data) if response.data else 0
            print(f"   ✅ Deleted {deleted_count} old snapshots")
            return deleted_count

        except Exception as e:
            print(f"   ❌ Error deleting old snapshots: {e}")
            return 0

    def get_baseline_exists_today(self, employee_username: str, worksheet_name: str = "Tracking") -> bool:
        """
        Check if a baseline snapshot exists for today

        Args:
            employee_username: Employee's Discord username
            worksheet_name: Name of worksheet

        Returns:
            True if baseline exists for today
        """
        baseline = self.get_latest_baseline(employee_username, worksheet_name)
        return baseline is not None
    