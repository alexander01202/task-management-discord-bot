"""
Natural language time parser for reminder scheduling
"""
from datetime import datetime, timedelta
import re
from typing import Optional, Tuple


class TimeParser:
    """Parses natural language time expressions into datetime objects"""

    @staticmethod
    def parse(time_str: str, reference_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        Parse natural language time expression

        Args:
            time_str: Natural language time like "in 2 hours", "tomorrow at 3pm"
            reference_time: Reference time (defaults to now)

        Returns:
            datetime object or None if couldn't parse
        """
        if reference_time is None:
            reference_time = datetime.now()

        time_str = time_str.lower().strip()

        # Relative time patterns (in X hours/days/weeks)
        relative_result = TimeParser._parse_relative(time_str, reference_time)
        if relative_result:
            return relative_result

        # Specific day patterns (tomorrow, today, monday)
        day_result = TimeParser._parse_specific_day(time_str, reference_time)
        if day_result:
            return day_result

        # Time of day patterns (at 3pm, at 15:00)
        time_result = TimeParser._parse_time_of_day(time_str, reference_time)
        if time_result:
            return time_result

        # Combined patterns (tomorrow at 3pm, monday at 10am)
        combined_result = TimeParser._parse_combined(time_str, reference_time)
        if combined_result:
            return combined_result

        return None

    @staticmethod
    def _parse_relative(time_str: str, ref_time: datetime) -> Optional[datetime]:
        """Parse relative time expressions like 'in 2 hours', 'in 3 days'"""

        # Pattern: in X hours/minutes/days/weeks/months
        patterns = [
            (r'in (\d+) hour(?:s)?', 'hours'),
            (r'in (\d+) minute(?:s)?', 'minutes'),
            (r'in (\d+) day(?:s)?', 'days'),
            (r'in (\d+) week(?:s)?', 'weeks'),
            (r'in (\d+) month(?:s)?', 'months'),
            (r'(\d+) hour(?:s)? from now', 'hours'),
            (r'(\d+) minute(?:s)? from now', 'minutes'),
            (r'(\d+) day(?:s)? from now', 'days'),
        ]

        for pattern, unit in patterns:
            match = re.search(pattern, time_str)
            if match:
                value = int(match.group(1))

                if unit == 'hours':
                    return ref_time + timedelta(hours=value)
                elif unit == 'minutes':
                    return ref_time + timedelta(minutes=value)
                elif unit == 'days':
                    return ref_time + timedelta(days=value)
                elif unit == 'weeks':
                    return ref_time + timedelta(weeks=value)
                elif unit == 'months':
                    return ref_time + timedelta(days=value * 30)  # Approximate

        return None

    @staticmethod
    def _parse_specific_day(time_str: str, ref_time: datetime) -> Optional[datetime]:
        """Parse specific day expressions like 'tomorrow', 'today', 'monday'"""

        # Today
        if 'today' in time_str:
            return ref_time.replace(hour=9, minute=0, second=0, microsecond=0)

        # Tomorrow variations
        if 'tomorrow' in time_str or 'tmrw' in time_str or 'tom' in time_str:
            tomorrow = ref_time + timedelta(days=1)

            # Check for time of day hints
            if 'morning' in time_str:
                return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
            elif 'afternoon' in time_str:
                return tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
            elif 'evening' in time_str or 'night' in time_str:
                return tomorrow.replace(hour=18, minute=0, second=0, microsecond=0)
            else:
                return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

        # Day after tomorrow
        if 'day after tomorrow' in time_str or 'overmorrow' in time_str:
            day_after = ref_time + timedelta(days=2)
            return day_after.replace(hour=9, minute=0, second=0, microsecond=0)

        # Next week
        if 'next week' in time_str:
            next_week = ref_time + timedelta(days=7)
            return next_week.replace(hour=9, minute=0, second=0, microsecond=0)

        # This weekend
        if 'weekend' in time_str:
            days_until_saturday = (5 - ref_time.weekday()) % 7
            if days_until_saturday == 0 and ref_time.hour > 12:
                # If it's Saturday afternoon, assume next weekend
                days_until_saturday = 7
            saturday = ref_time + timedelta(days=days_until_saturday)
            return saturday.replace(hour=10, minute=0, second=0, microsecond=0)

        # Days of week
        weekdays = {
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6
        }

        for day_name, day_num in weekdays.items():
            if day_name in time_str:
                # Calculate days until that weekday
                current_weekday = ref_time.weekday()
                days_ahead = day_num - current_weekday

                if days_ahead <= 0:  # Target day already passed this week
                    days_ahead += 7

                target_date = ref_time + timedelta(days=days_ahead)
                return target_date.replace(hour=9, minute=0, second=0, microsecond=0)

        return None

    @staticmethod
    def _parse_time_of_day(time_str: str, ref_time: datetime) -> Optional[datetime]:
        """Parse time of day expressions like 'at 3pm', 'at 15:00'"""

        # Pattern: at HH:MM am/pm
        match = re.search(r'at (\d{1,2}):?(\d{2})?\s*(am|pm)?', time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            period = match.group(3)

            # Convert to 24-hour format
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0

            # Use today if time hasn't passed, otherwise tomorrow
            target_time = ref_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if target_time <= ref_time:
                target_time += timedelta(days=1)

            return target_time

        # Pattern: HHam/pm or HH:MMam/pm (without "at")
        match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)', time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            period = match.group(3)

            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0

            target_time = ref_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if target_time <= ref_time:
                target_time += timedelta(days=1)

            return target_time

        return None

    @staticmethod
    def _parse_combined(time_str: str, ref_time: datetime) -> Optional[datetime]:
        """Parse combined expressions like 'tomorrow at 3pm', 'monday at 10am'"""

        # First try to get the day
        day_result = TimeParser._parse_specific_day(time_str, ref_time)

        if day_result:
            # Now try to get the time
            time_match = re.search(r'at (\d{1,2}):?(\d{2})?\s*(am|pm)?', time_str)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                period = time_match.group(3)

                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0

                return day_result.replace(hour=hour, minute=minute, second=0, microsecond=0)

        return None

    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """Format datetime for human-readable display"""
        now = datetime.now()

        # If today
        if dt.date() == now.date():
            return f"today at {dt.strftime('%I:%M %p')}"

        # If tomorrow
        if dt.date() == (now + timedelta(days=1)).date():
            return f"tomorrow at {dt.strftime('%I:%M %p')}"

        # If within a week
        if dt.date() < (now + timedelta(days=7)).date():
            return f"{dt.strftime('%A at %I:%M %p')}"

        # Otherwise full date
        return dt.strftime('%B %d, %Y at %I:%M %p')


# Example usage and testing
if __name__ == "__main__":
    parser = TimeParser()

    test_cases = [
        "in 2 hours",
        "in 24 hours",
        "tomorrow",
        "tomorrow at 3pm",
        "monday at 10am",
        "at 3:30pm",
        "in 3 days",
        "friday at 5pm",
        "today at 2pm",
        "in 1 week"
    ]

    print("Testing TimeParser:")
    print("=" * 60)
    for test in test_cases:
        result = parser.parse(test)
        if result:
            formatted = parser.format_datetime(result)
            print(f"'{test}' -> {formatted}")
        else:
            print(f"'{test}' -> Could not parse")
