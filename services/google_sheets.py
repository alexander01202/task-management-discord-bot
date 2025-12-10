"""
Google Sheets service for fetching task data
"""
from typing import List, Dict, Optional
import gspread
from google.oauth2.service_account import Credentials
from config.config import GOOGLE_CREDENTIALS_PATH
from utils.permissions import PermissionManager


class GoogleSheetsService:
    """Handles all Google Sheets operations"""
    
    def __init__(self):
        """Initialize Google Sheets client"""
        print("🔌 Initializing Google Sheets service...")
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_PATH,
                scopes=scopes
            )
            
            self.client = gspread.authorize(creds)
            print("   ✅ Google Sheets client initialized")
            
        except Exception as e:
            print(f"   ❌ Google Sheets initialization failed: {e}")
            self.client = None
    
    def get_worksheet_names(self, sheet_id: str) -> Optional[List[str]]:
        """
        Get list of all worksheet names in a spreadsheet

        Args:
            sheet_id: Google Sheet ID

        Returns:
            List of worksheet names, or None if error
        """
        if not self.client:
            print("   ❌ Google Sheets client not initialized")
            return None

        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            worksheets = spreadsheet.worksheets()
            worksheet_names = [ws.title for ws in worksheets]

            print(f"   📋 Found {len(worksheet_names)} worksheets: {', '.join(worksheet_names)}")
            return worksheet_names

        except Exception as e:
            print(f"   ❌ Error fetching worksheet names: {e}")
            return None

    def get_employee_sheet(self, employee_username: str, requester_username: str, worksheet_name: str = None) -> Optional[Dict]:
        """
        Fetch sheet data for an employee with permission checking

        Args:
            employee_username: Username of employee whose sheet to fetch
            requester_username: Username of person requesting access
            worksheet_name: Specific worksheet to fetch (None = list worksheets first)

        Returns:
            Dict with 'data' (rows) or 'worksheets' (list of names), or None if no permission/error
        """
        print(f"\n📊 Fetching sheet for {employee_username}...")
        print(f"   Requester: {requester_username}")
        if worksheet_name:
            print(f"   Worksheet: {worksheet_name}")

        # Check permissions
        can_access, sheet_id = PermissionManager.can_access_sheet(
            requester_username,
            employee_username
        )

        if not can_access:
            print(f"   ❌ Access denied: {requester_username} cannot access {employee_username}'s sheet")
            return None

        if not sheet_id:
            print(f"   ❌ No sheet found for {employee_username}")
            return None

        print(f"   ✅ Permission granted")
        print(f"   Sheet ID: {sheet_id}")

        # If no worksheet specified, return list of worksheets
        if not worksheet_name:
            worksheet_names = self.get_worksheet_names(sheet_id)
            if worksheet_names:
                return {
                    "worksheets": worksheet_names,
                    "sheet_id": sheet_id
                }
            return None

        # Fetch specific worksheet data
        data = self.get_sheet_data(sheet_id, worksheet_name)
        if data is not None:
            return {
                "data": data,
                "worksheet_name": worksheet_name
            }
        return None

    def get_sheet_data(self, sheet_id: str, worksheet_name: str = None) -> Optional[List[Dict]]:
        """
        Fetch all data from a Google Sheet

        Args:
            sheet_id: Google Sheet ID
            worksheet_name: Name of worksheet (default: first worksheet)

        Returns:
            List of dictionaries with row data, or None if error
        """
        if not self.client:
            print("   ❌ Google Sheets client not initialized")
            return None

        print(f"   📄 Fetching data from sheet: {sheet_id}")

        try:
            # Open the spreadsheet
            spreadsheet = self.client.open_by_key(sheet_id)

            # Get the worksheet
            if worksheet_name:
                worksheet = spreadsheet.worksheet(worksheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(0)  # First worksheet

            # Get all values (including headers)
            all_values = worksheet.get_all_values()

            if not all_values or len(all_values) < 2:
                print(f"   ⚠️  Worksheet is empty or has no data rows")
                return []

            # Get headers and clean them up
            headers = all_values[0]
            data_rows = all_values[1:]

            # Find non-empty headers and their indices
            valid_columns = []
            for idx, header in enumerate(headers):
                if header and header.strip():  # Only keep non-empty headers
                    valid_columns.append((idx, header.strip()))

            if not valid_columns:
                print(f"   ⚠️  No valid column headers found")
                return []

            print(f"   📋 Found {len(valid_columns)} valid columns: {[h for _, h in valid_columns]}")

            # Build list of dictionaries using only valid columns
            data = []
            for row in data_rows:
                # Skip completely empty rows
                if not any(cell for cell in row):
                    continue

                row_dict = {}
                for col_idx, col_name in valid_columns:
                    if col_idx < len(row):
                        value = row[col_idx]
                        if value:  # Only add non-empty values
                            row_dict[col_name] = value

                # Only add row if it has at least one value
                if row_dict:
                    data.append(row_dict)

            print(f"   ✅ Retrieved {len(data)} rows from sheet")
            return data

        except Exception as e:
            print(f"   ❌ Error fetching sheet data: {e}")
            return None

    def format_sheet_data(self, data: List[Dict], limit: int = 50) -> str:
        """
        Format sheet data into a readable string for Claude

        Args:
            data: List of row dictionaries
            limit: Maximum number of rows to include

        Returns:
            Formatted string representation of data
        """
        if not data:
            return "No data found."

        # Limit the number of rows
        data_subset = data[:limit]

        # Format as a table-like string that Claude can understand
        formatted_rows = []

        for idx, row in enumerate(data_subset, 1):
            row_str = f"Row {idx}: " + " | ".join([f"{k}: {v}" for k, v in row.items() if v])
            formatted_rows.append(row_str)

        result = "\n".join(formatted_rows)

        if len(data) > limit:
            result += f"\n\n(Showing {limit} of {len(data)} total rows)"

        return result