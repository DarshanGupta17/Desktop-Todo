"""
Date utilities: business day rolls at 3:00 AM local time, not midnight.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


def get_active_day() -> date:
    """
    Return the calendar date that counts as "today" for the widget.

    Before 03:00 local time, the active day is still the previous calendar day.
    At or after 03:00, the active day is the current calendar day.
    """
    now = datetime.now()
    if now.hour < 3:
        return (now - timedelta(days=1)).date()
    return now.date()


def format_display_date(d: date) -> str:
    """Human-readable date for the header."""
    return d.strftime("%A, %B %d, %Y")
