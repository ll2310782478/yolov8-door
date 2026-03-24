"""Time utilities for SmartAccess.

All business timestamps use UTC+8 (East Asia timezone) as naive datetime
for compatibility with existing database DateTime columns.
"""

from datetime import datetime, timedelta

def now_utc8() -> datetime:
    """Return current UTC+8 datetime (naive)."""
    return datetime.utcnow() + timedelta(hours=8)

