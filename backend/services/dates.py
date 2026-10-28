from datetime import datetime, timedelta, timezone

TAIPEI_TZ = timezone(timedelta(hours=8))


def today() -> str:
    return datetime.now(TAIPEI_TZ).date().isoformat()
