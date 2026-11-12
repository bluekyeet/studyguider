"""The time the study planner works from.

Normally the real time. For trying the planner across several days without waiting, a server started with
STUDYGUIDER_DEV_CLOCK=yes lets an administrator move this clock forward (PUT /dev/clock). Reviews, the daily plan, assessment
countdowns and the nightly lesson scheduler read it; other timestamps (uploads, sign-ins) keep the database's own clock.
"""
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NZ = ZoneInfo("Pacific/Auckland")
_offset = timedelta()


def enabled():
    return os.environ.get("STUDYGUIDER_DEV_CLOCK") == "yes"


def now():
    return datetime.now(timezone.utc) + _offset


def today():
    """Today's date in New Zealand."""
    return now().astimezone(NZ).date()


def offset_days():
    return _offset.total_seconds() / 86400


def set_offset_days(days):
    global _offset
    if not enabled():
        raise RuntimeError("The development clock is switched off")
    _offset = timedelta(days=days)
