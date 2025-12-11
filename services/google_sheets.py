"""
Google Sheets service for fetching task data
"""
from typing import List, Dict, Optional, Tuple
import gspread
from google.oauth2.service_account import Credentials
from config.config import GOOGLE_CREDENTIALS_PATH, SHEETS_GID
from utils.permissions import PermissionManager
from difflib import SequenceMatcher


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

    def _calculate_match_score(self, query: str, worksheet_name: str) -> float:
        """
        Calculate similarity score between query and worksheet name

        Args:
            query: User's query/request
            worksheet_name: Actual worksheet name

        Returns:
            Similarity score between 0 and 1
        """
        query_lower = query.lower()
        ws_lower = worksheet_name.lower()

        # Exact match
        if query_lower == ws_lower:
            return 1.0

        # Contains match
        if query_lower in ws_lower or ws_lower in query_lower:
            return 0.9

        # Use sequence matcher for fuzzy matching
        return SequenceMatcher(None, query_lower, ws_lower).ratio()

    def _find_best_worksheet_match(self, employee_username: str, query: str, available_worksheets: List[str]) -> Tuple[Optional[str], float]:
        """
        Find the best matching worksheet based on user query

        Args:
            employee_username: Employee's Discord username
            query: User's query about which worksheet they want
            available_worksheets: List of available worksheet names

        Returns:
            Tuple of (best_match_name, confidence_score)
        """
        if not query or not available_worksheets:
            return None, 0.0

        best_match = None
        best_score = 0.0

        for worksheet in available_worksheets:
            score = self._calculate_match_score(query, worksheet)
            if score > best_score:
                best_score = score
                best_match = worksheet

        print(f"   🔍 Best worksheet match: '{best_match}' with {best_score:.0%} confidence")
        return best_match, best_score

    def get_worksheet_gid(self, employee_username: str, worksheet_name: str) -> Optional[str]:
        """
        Get GID for a worksheet if configured

        Args:
            employee_username: Employee's Discord username
            worksheet_name: Worksheet name

        Returns:
            GID string if found, None otherwise
        """
        if employee_username not in SHEETS_GID:
            return None

        employee_gids = SHEETS_GID[employee_username]
        worksheet_lower = worksheet_name.lower()

        # Try exact match first
        if worksheet_lower in employee_gids:
            return employee_gids[worksheet_lower]

        # Try fuzzy match
        for key, gid in employee_gids.items():
            if self._calculate_match_score(worksheet_lower, key) > 0.8:
                return gid

        return None

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

    def get_employee_sheet(self, employee_username: str, requester_username: str, query: str = None) -> Optional[Dict]:
        """
        Fetch sheet data for an employee with permission checking and smart worksheet matching

        Args:
            employee_username: Username of employee whose sheet to fetch
            requester_username: Username of person requesting access
            query: User's query/request - used to intelligently match worksheet

        Returns:
            Dict with 'data' (rows) or 'worksheets' (list of names), or None if no permission/error
        """
        print(f"\n📊 Fetching sheet for {employee_username}...")
        print(f"   Requester: {requester_username}")
        if query:
            print(f"   Query: {query}")

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

        # Get list of worksheets
        worksheet_names = self.get_worksheet_names(sheet_id)
        if not worksheet_names:
            return None

        # If no query provided, return list of worksheets
        if not query:
            return {
                "worksheets": worksheet_names,
                "sheet_id": sheet_id
            }

        # Try to find best matching worksheet
        best_match, confidence = self._find_best_worksheet_match(employee_username, query, worksheet_names)

        if best_match and confidence >= 0.7:
            # High confidence match - fetch it automatically
            print(f"   ✅ Auto-selecting worksheet '{best_match}' ({confidence:.0%} confidence)")
            data = self.get_sheet_data_by_name_or_gid(sheet_id, employee_username, best_match)
            if data is not None:
                return {
                    "data": data,
                    "worksheet_name": best_match,
                    "confidence": confidence
                }

        # Low confidence or no match - ask user to clarify
        print(f"   ⚠️  No confident match found (best: {confidence:.0%})")
        return {
            "worksheets": worksheet_names,
            "sheet_id": sheet_id,
            "best_guess": best_match if best_match else None,
            "confidence": confidence
        }

    def get_sheet_data_by_name_or_gid(self, sheet_id: str, employee_username: str, worksheet_identifier: str) -> Optional[List[Dict]]:
        """
        Fetch sheet data using GID if available, otherwise use worksheet name

        Args:
            sheet_id: Google Sheet ID
            employee_username: Employee username (to look up GID mapping)
            worksheet_identifier: Worksheet name or identifier

        Returns:
            List of row dictionaries, or None if error
        """
        if not self.client:
            print("   ❌ Google Sheets client not initialized")
            return None

        print(f"   📄 Fetching data from sheet: {sheet_id}")

        try:
            spreadsheet = self.client.open_by_key(sheet_id)

            # Try to get GID first
            gid = self.get_worksheet_gid(employee_username, worksheet_identifier)

            if gid:
                print(f"   🔑 Using GID: {gid}")
                # Fetch by GID
                try:
                    worksheet = None
                    for ws in spreadsheet.worksheets():
                        if str(ws.id) == str(gid):
                            worksheet = ws
                            break

                    if not worksheet:
                        print(f"   ⚠️  GID {gid} not found, falling back to name")
                        worksheet = spreadsheet.worksheet(worksheet_identifier)
                except:
                    print(f"   ⚠️  Error with GID {gid}, falling back to name")
                    worksheet = spreadsheet.worksheet(worksheet_identifier)
            else:
                print(f"   📝 Using worksheet name: {worksheet_identifier}")
                worksheet = spreadsheet.worksheet(worksheet_identifier)

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

        # Get all unique column names
        all_columns = []
        seen = set()
        for row in data_subset:
            for col in row.keys():
                if col not in seen:
                    all_columns.append(col)
                    seen.add(col)

        # Format as a table-like structure
        formatted_rows = []

        # Add header row
        header = " | ".join(all_columns)
        formatted_rows.append(header)
        formatted_rows.append("-" * len(header))

        # Add data rows
        for idx, row in enumerate(data_subset, 1):
            row_values = []
            for col in all_columns:
                value = row.get(col, "")
                row_values.append(str(value))

            row_str = " | ".join(row_values)
            formatted_rows.append(row_str)

        result = "\n".join(formatted_rows)

        if len(data) > limit:
            result += f"\n\n(Showing {limit} of {len(data)} total rows)"

        return result