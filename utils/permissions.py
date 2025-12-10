"""
Role-based permission system
"""
from typing import Optional
from config.config import ADMIN_USERNAMES, EMPLOYEE_SHEETS, EMPLOYEE_FRIENDLY_NAMES


class Role:
    """User roles"""
    ADMIN = "admin"
    EMPLOYEE = "employee"
    USER = "user"


class PermissionManager:
    """Manages user permissions and access control"""
    
    @staticmethod
    def resolve_employee_name(name: str) -> Optional[str]:
        """
        Resolve a friendly name or Discord username to Discord username
        
        Args:
            name: Friendly name (e.g., "ignacio") or Discord username
            
        Returns:
            Discord username if found, None otherwise
        """
        if not name:
            return None
        
        name_lower = name.lower().strip()
        
        # Check if it's a friendly name
        if name_lower in EMPLOYEE_FRIENDLY_NAMES:
            return EMPLOYEE_FRIENDLY_NAMES[name_lower]
        
        # Check if it's already a Discord username
        if name_lower in [username.lower() for username in EMPLOYEE_SHEETS.keys()]:
            # Return the properly cased version
            for username in EMPLOYEE_SHEETS.keys():
                if username.lower() == name_lower:
                    return username
        
        return None
    
    @staticmethod
    def get_user_role(username: str) -> str:
        """
        Determine user role based on username
        
        Args:
            username: Discord username
            
        Returns:
            Role (admin, employee, or user)
        """
        if username in ADMIN_USERNAMES:
            return Role.ADMIN
        elif username in EMPLOYEE_SHEETS:
            return Role.EMPLOYEE
        else:
            return Role.USER
    
    @staticmethod
    def is_admin(username: str) -> bool:
        """Check if user is an admin"""
        return username in ADMIN_USERNAMES
    
    @staticmethod
    def is_employee(username: str) -> bool:
        """Check if user is an employee"""
        return username in EMPLOYEE_SHEETS
    
    @staticmethod
    def get_user_sheet_id(username: str) -> Optional[str]:
        """
        Get the Google Sheet ID for a user
        
        Args:
            username: Discord username
            
        Returns:
            Sheet ID if user is an employee, None otherwise
        """
        return EMPLOYEE_SHEETS.get(username)
    
    @staticmethod
    def get_employee_friendly_name(username: str) -> Optional[str]:
        """
        Get friendly name for an employee
        
        Args:
            username: Discord username
            
        Returns:
            Friendly name if found, None otherwise
        """
        for friendly, discord_username in EMPLOYEE_FRIENDLY_NAMES.items():
            if discord_username == username:
                return friendly
        return None
    
    @staticmethod
    def get_all_employee_names() -> list[str]:
        """
        Get list of all employee friendly names
        
        Returns:
            List of friendly names
        """
        return list(EMPLOYEE_FRIENDLY_NAMES.keys())
    
    @staticmethod
    def can_access_sheet(requester_username: str, target_username: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """
        Check if a user can access a specific sheet
        
        Args:
            requester_username: Username of person making the request
            target_username: Username of the sheet owner (None = their own sheet)
            
        Returns:
            Tuple of (can_access: bool, sheet_id: Optional[str])
        """
        # If no target specified, they want their own sheet
        if target_username is None:
            target_username = requester_username
        
        # Admins can access any employee's sheet
        if PermissionManager.is_admin(requester_username):
            sheet_id = EMPLOYEE_SHEETS.get(target_username)
            return (sheet_id is not None, sheet_id)
        
        # Employees can only access their own sheet
        if requester_username == target_username:
            sheet_id = EMPLOYEE_SHEETS.get(requester_username)
            return (sheet_id is not None, sheet_id)
        
        # No access
        return (False, None)
    
    @staticmethod
    def get_accessible_employees(username: str) -> list[str]:
        """
        Get list of employees whose sheets this user can access
        
        Args:
            username: Discord username
            
        Returns:
            List of employee usernames
        """
        if PermissionManager.is_admin(username):
            # Admins can access all employee sheets
            return list(EMPLOYEE_SHEETS.keys())
        elif PermissionManager.is_employee(username):
            # Employees can only access their own
            return [username]
        else:
            # Regular users can't access any sheets
            return []
