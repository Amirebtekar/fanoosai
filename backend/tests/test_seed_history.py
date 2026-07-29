from datetime import date

from app.seed_history import history_dates, missing_history_dates


def test_history_dates_returns_the_seven_completed_days_before_today():
    assert history_dates(7, date(2026, 7, 27)) == [
        date(2026, 7, 20),
        date(2026, 7, 21),
        date(2026, 7, 22),
        date(2026, 7, 23),
        date(2026, 7, 24),
        date(2026, 7, 25),
        date(2026, 7, 26),
    ]


def test_missing_history_dates_skips_days_with_existing_runs():
    assert missing_history_dates(3, {date(2026, 7, 25)}, date(2026, 7, 27)) == [
        date(2026, 7, 24),
        date(2026, 7, 26),
    ]
