from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.analytics.router import as_tehran, filters
from app.database.models import AIRun, Prompt


def test_naive_datetime_is_tehran_time():
    value = as_tehran(datetime(2026, 10, 30, 0, 0))
    assert value.utcoffset().total_seconds() == 3.5 * 3600
    assert value.astimezone(timezone.utc) == datetime(2026, 10, 29, 20, 30, tzinfo=timezone.utc)


def test_aware_datetime_is_kept():
    value = datetime(2026, 10, 29, 22, 0, tzinfo=timezone.utc)
    assert as_tehran(value) is value
    assert as_tehran(None) is None


def test_run_at_0135_tehran_falls_inside_that_tehran_day():
    run = datetime(2026, 10, 29, 22, 5, tzinfo=timezone.utc)
    start = as_tehran(datetime(2026, 10, 30, 0, 0, 0))
    end = as_tehran(datetime(2026, 10, 30, 23, 59, 59))
    assert start <= run <= end
    prev_start = as_tehran(datetime(2026, 10, 29, 0, 0, 0))
    prev_end = as_tehran(datetime(2026, 10, 29, 23, 59, 59))
    assert not (prev_start <= run <= prev_end)


def test_filters_use_tehran_bounds_in_sql():
    stmt = filters(select(AIRun.id).join(Prompt), 10, start=datetime(2026, 10, 30), end=datetime(2026, 10, 30, 23, 59, 59))
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "'2026-10-30 00:00:00+03:30'" in sql
    assert "'2026-10-30 23:59:59+03:30'" in sql
