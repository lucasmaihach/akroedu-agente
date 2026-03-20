from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BRT = ZoneInfo("America/Sao_Paulo")
START_HOUR = 7
END_HOUR = 22


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def fit_business_hours(dt_utc: datetime) -> datetime:
    dt_brt = dt_utc.astimezone(BRT)
    if dt_brt.hour < START_HOUR:
        dt_brt = dt_brt.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    elif dt_brt.hour >= END_HOUR:
        next_day = dt_brt + timedelta(days=1)
        dt_brt = next_day.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    return dt_brt.astimezone(timezone.utc)


def is_within_business_hours(dt_utc: datetime | None = None) -> bool:
    dt_brt = (dt_utc or now_utc()).astimezone(BRT)
    return START_HOUR <= dt_brt.hour < END_HOUR
