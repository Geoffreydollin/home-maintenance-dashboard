"""
Unit tests for the recurrence / due-date logic.

Run:  python -m unittest test_scheduler   (no extra dependencies needed)
"""

import unittest
from datetime import date

import scheduler


class TestNextDue(unittest.TestCase):
    def test_weekly_with_schedule_lands_on_weekday(self):
        task = {"frequency": "weekly", "schedule": {"day_of_week": "Monday"}}
        # Completed on a Monday -> next Monday (7 days later, exclusive).
        self.assertEqual(
            scheduler.compute_next_due(task, date(2026, 6, 15)), date(2026, 6, 22)
        )
        # Completed on a Wednesday -> the following Monday.
        self.assertEqual(
            scheduler.compute_next_due(task, date(2026, 6, 17)), date(2026, 6, 22)
        )

    def test_weekly_without_schedule_is_plus_7(self):
        task = {"frequency": "weekly"}
        self.assertEqual(
            scheduler.compute_next_due(task, date(2026, 6, 15)), date(2026, 6, 22)
        )

    def test_twice_weekly_next_occurrence(self):
        task = {"frequency": "twice_weekly",
                "schedule": {"days_of_week": ["Monday", "Thursday"]}}
        # Completed Monday -> next is Thursday of the same week.
        self.assertEqual(
            scheduler.compute_next_due(task, date(2026, 6, 15)), date(2026, 6, 18)
        )
        # Completed Thursday -> next is the following Monday.
        self.assertEqual(
            scheduler.compute_next_due(task, date(2026, 6, 18)), date(2026, 6, 22)
        )

    def test_monthly_clamps_to_last_day(self):
        task = {"frequency": "monthly"}
        # Jan 31 + 1 month -> Feb 28 (2026 is not a leap year).
        self.assertEqual(
            scheduler.compute_next_due(task, date(2026, 1, 31)), date(2026, 2, 28)
        )

    def test_quarterly_biannual_annual(self):
        self.assertEqual(
            scheduler.compute_next_due({"frequency": "quarterly"}, date(2026, 6, 15)),
            date(2026, 9, 15),
        )
        self.assertEqual(
            scheduler.compute_next_due({"frequency": "biannual"}, date(2026, 6, 15)),
            date(2026, 12, 15),
        )
        self.assertEqual(
            scheduler.compute_next_due({"frequency": "annual"}, date(2026, 6, 15)),
            date(2027, 6, 15),
        )

    def test_as_needed_has_no_next_due(self):
        self.assertIsNone(
            scheduler.compute_next_due({"frequency": "as_needed"}, date(2026, 6, 15))
        )


class TestSeeding(unittest.TestCase):
    def test_scheduled_task_seeds_to_next_weekday(self):
        # 2026-06-16 is a Tuesday; a Monday task seeds to the next Monday.
        task = {"frequency": "weekly", "schedule": {"day_of_week": "Monday"}}
        self.assertEqual(scheduler.seed_next_due(task, date(2026, 6, 16)), date(2026, 6, 22))

    def test_scheduled_task_due_today_if_today_matches(self):
        task = {"frequency": "weekly", "schedule": {"day_of_week": "Monday"}}
        # 2026-06-15 is a Monday -> inclusive, seeds to today.
        self.assertEqual(scheduler.seed_next_due(task, date(2026, 6, 15)), date(2026, 6, 15))

    def test_unscheduled_task_seeds_to_today(self):
        self.assertEqual(
            scheduler.seed_next_due({"frequency": "monthly"}, date(2026, 6, 15)),
            date(2026, 6, 15),
        )

    def test_as_needed_seeds_to_none(self):
        self.assertIsNone(
            scheduler.seed_next_due({"frequency": "as_needed"}, date(2026, 6, 15))
        )


if __name__ == "__main__":
    unittest.main()
