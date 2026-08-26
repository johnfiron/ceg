"""Deterministic core NYSE holiday calendar with explicit override support."""
from datetime import date, timedelta


def _observed(day):
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year, month, weekday, nth):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))


def _last_weekday(year, month, weekday):
    first_next = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    last = first_next - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter(year):
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def core_market_holidays(year):
    return {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed(date(year, 6, 19)),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }


def is_market_session(day, extra_closed=()):
    extra = {date.fromisoformat(str(value)[:10]) for value in extra_closed}
    return day.weekday() < 5 and day not in core_market_holidays(day.year) and day not in extra


def next_session_date(day, extra_closed=()):
    current = date.fromisoformat(str(day)[:10]) + timedelta(days=1)
    while not is_market_session(current, extra_closed):
        current += timedelta(days=1)
    return current.isoformat()


def add_sessions(day, count, extra_closed=()):
    current = date.fromisoformat(str(day)[:10])
    for _ in range(max(0, int(count))):
        current = date.fromisoformat(next_session_date(current, extra_closed))
    return current.isoformat()
