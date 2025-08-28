from datetime import datetime, timedelta, date

WEEKLY_MAX_MINUTES = 52 * 60
DAILY_REGULAR_MINUTES = 8 * 60
NIGHT_START = 22
NIGHT_END = 6

def to_minutes(hhmm: str | None):
    if not hhmm: return None
    h,m = hhmm.split(':'); return int(h)*60 + int(m)

def minutes_to_hhmm(mins: int):
    if mins is None: return '0분'
    h = mins // 60; m = mins % 60
    return f"{h}시간 {m}분" if h>0 else f"{m}분"

def today_str(): return datetime.now().strftime('%Y-%m-%d')

def week_range_of(target: date):
    start = target - timedelta(days=target.weekday())
    end = start + timedelta(days=6)
    return start, end

def span_minutes(start_hhmm: str, end_hhmm: str):
    return to_minutes(end_hhmm) - to_minutes(start_hhmm)

def _night_minutes(in_time: str, out_time: str):
    s = to_minutes(in_time); e = to_minutes(out_time)
    if e < s: e += 24*60
    night=0
    for minute in range(s, e):
        h = (minute//60) % 24
        if h >= NIGHT_START or h < NIGHT_END:
            night += 1
    return night

def calc_work_buckets(in_time: str | None, out_time: str | None, lunch_minutes: int, d: date, is_holiday: bool) -> dict:
    if not in_time or not out_time:
        return dict(regular=0, overtime=0, night=0, holiday=0, total=0)
    total = span_minutes(in_time, out_time) - (lunch_minutes or 0)
    night = _night_minutes(in_time, out_time)
    holiday_minutes = total if is_holiday or d.weekday()>=5 else 0
    regular = min(total, DAILY_REGULAR_MINUTES) if not holiday_minutes else 0
    overtime = max(0, total-DAILY_REGULAR_MINUTES) if not holiday_minutes else 0
    return dict(regular=regular, overtime=overtime, night=night, holiday=holiday_minutes, total=total)
