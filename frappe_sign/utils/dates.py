"""Date and time helpers.

Sign Event timestamps are UTC (DESIGN 2.3); every other Datetime field uses the system time zone,
as Frappe does.
"""

from datetime import UTC, datetime, timedelta

from frappe.utils import add_to_date, convert_utc_to_system_timezone, get_system_timezone, now_datetime


def utc_now() -> datetime:
	"""Naive UTC with microseconds, the form Sign Event.at is stored in."""
	return datetime.now(UTC).replace(tzinfo=None)


def now() -> datetime:
	return now_datetime()


def after(minutes: float = 0, days: float = 0, start: datetime | None = None) -> datetime:
	return add_to_date(start or now_datetime(), days=days, minutes=minutes)


def is_past(moment: datetime | None) -> bool:
	return moment is not None and moment < now_datetime()


def seconds_since(moment: datetime | None) -> float:
	if moment is None:
		return float("inf")
	return (now_datetime() - moment) / timedelta(seconds=1)


def format_utc(moment: datetime) -> str:
	"""A UTC timestamp shown in the system time zone, with the zone name."""
	local = convert_utc_to_system_timezone(moment)
	return f"{local:%Y-%m-%d %H:%M:%S} {get_system_timezone()}"


def format_local(moment: datetime | None) -> str:
	if not moment:
		return ""
	return f"{moment:%Y-%m-%d %H:%M} {get_system_timezone()}"
