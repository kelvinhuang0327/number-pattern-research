from __future__ import annotations

from datetime import datetime, timezone
import re
from zoneinfo import ZoneInfo


_TEAM_ALIASES = {
    "D-BACKS": "ARIZONA DIAMONDBACKS",
    "ARIZONA": "ARIZONA DIAMONDBACKS",
    "ATHLETICS": "OAKLAND ATHLETICS",
    "A'S": "OAKLAND ATHLETICS",
    "CHI CUBS": "CHICAGO CUBS",
    "CHI WHITE SOX": "CHICAGO WHITE SOX",
    "LA DODGERS": "LOS ANGELES DODGERS",
    "LA ANGELS": "LOS ANGELES ANGELS",
    "N.Y. YANKEES": "NEW YORK YANKEES",
    "N.Y. METS": "NEW YORK METS",
    "SD PADRES": "SAN DIEGO PADRES",
    "SF GIANTS": "SAN FRANCISCO GIANTS",
    "TB RAYS": "TAMPA BAY RAYS",
}


def canonical_team_name(name: str) -> str:
    token = re.sub(r"\s+", " ", (name or "").strip().upper())
    return _TEAM_ALIASES.get(token, token)


def iso_to_et_date_time(iso_utc: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    et = dt.astimezone(ZoneInfo("America/New_York"))
    return et.date().isoformat(), et.strftime("%I:%M %p").lstrip("0")


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
