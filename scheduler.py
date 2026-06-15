"""
scheduler.py
============

All date / recurrence math for the home maintenance dashboard lives here so it
can be unit-tested in isolation and reasoned about in one place.

Frequencies and how `next_due` is computed after a task is completed:

    weekly        completion + 7 days, OR the next occurrence of
                  schedule.day_of_week if a schedule is present
    twice_weekly  next occurrence of any day in schedule.days_of_week
    monthly       completion + 1 month  (same day-of-month, clamped)
    quarterly     completion + 3 months
    biannual      completion + 6 months
    annual        completion + 12 months
    as_needed     no next_due -- cleared from active lists, logged only

Seeding (first run, relative to *today*, not a hard-coded date):

    * tasks with a schedule   -> next occurrence of the scheduled day(s) on/after today
    * tasks without a schedule -> today (so everything is visible to triage)
    * as_needed tasks          -> no next_due (hidden until manually triggered)
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

# Map weekday names (as they appear in the seed data) to Python's
# date.weekday() numbering, where Monday == 0 ... Sunday == 6.
WEEKDAYS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

# Month-based frequencies and how many months they advance.
MONTH_INTERVALS = {
    "monthly": 1,
    "quarterly": 3,
    "biannual": 6,
    "annual": 12,
}

RECURRING_FREQUENCIES = {
    "weekly",
    "twice_weekly",
    "monthly",
    "quarterly",
    "biannual",
    "annual",
}


def add_months(start: date, months: int) -> date:
    """Add `months` to `start`, clamping the day to the last valid day.

    e.g. Jan 31 + 1 month -> Feb 28 (or 29 in a leap year).
    """
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(start.day, last_day)
    return date(year, month, day)


def next_weekday(from_date: date, target_weekday: int, inclusive: bool) -> date:
    """Return the next date on/after (inclusive) or strictly after (exclusive)
    `from_date` that falls on `target_weekday` (Mon=0 .. Sun=6)."""
    days_ahead = (target_weekday - from_date.weekday()) % 7
    if days_ahead == 0 and not inclusive:
        days_ahead = 7
    return from_date + timedelta(days=days_ahead)


def _next_from_weekdays(from_date: date, weekday_names, inclusive: bool) -> date:
    """Earliest next occurrence among several named weekdays."""
    candidates = []
    for name in weekday_names:
        if name in WEEKDAYS:
            candidates.append(next_weekday(from_date, WEEKDAYS[name], inclusive))
    if not candidates:
        # Fall back to a simple weekly cadence if the schedule is malformed.
        return from_date + timedelta(days=7)
    return min(candidates)


def compute_next_due(task: dict, completion_date: date) -> date | None:
    """Compute the next due date for a recurring task given the date it was
    just completed. Returns None for as_needed tasks (no schedule)."""
    frequency = task.get("frequency")
    schedule = task.get("schedule") or {}

    if frequency == "as_needed":
        return None

    if frequency == "weekly":
        day_name = schedule.get("day_of_week")
        if day_name and day_name in WEEKDAYS:
            return next_weekday(completion_date, WEEKDAYS[day_name], inclusive=False)
        return completion_date + timedelta(days=7)

    if frequency == "twice_weekly":
        days = schedule.get("days_of_week") or []
        return _next_from_weekdays(completion_date, days, inclusive=False)

    if frequency in MONTH_INTERVALS:
        return add_months(completion_date, MONTH_INTERVALS[frequency])

    # Unknown frequency -- treat conservatively as weekly so it resurfaces.
    return completion_date + timedelta(days=7)


def seed_next_due(task: dict, today: date) -> date | None:
    """Compute the initial `next_due` for a task on first run.

    * scheduled tasks   -> next occurrence of the scheduled day(s) on/after today
    * unscheduled tasks -> today (visible immediately for triage)
    * as_needed tasks   -> None (hidden until manually triggered)
    """
    frequency = task.get("frequency")
    schedule = task.get("schedule") or {}

    if frequency == "as_needed":
        return None

    if frequency == "weekly":
        day_name = schedule.get("day_of_week")
        if day_name and day_name in WEEKDAYS:
            return next_weekday(today, WEEKDAYS[day_name], inclusive=True)
        return today

    if frequency == "twice_weekly":
        days = schedule.get("days_of_week") or []
        if days:
            return _next_from_weekdays(today, days, inclusive=True)
        return today

    # monthly / quarterly / biannual / annual with no schedule -> due today.
    return today
