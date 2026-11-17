"""Freshness policies use measurement time, independent of HTTP retrieval."""
from datetime import timedelta
import math
from community import timestamp

def observation_limit_hours(source, default=3):
    return 36 if source.get('provider') == 'Météo-France' else default

def latest_observation_time(source):
    measured = [row['time'] for row in source.get('rows', [])
                if type(row.get('temperature')) in (int, float) and math.isfinite(row['temperature'])]
    return max(measured) if measured else None

def mark_observation_freshness(source, now):
    latest = latest_observation_time(source)
    limit = observation_limit_hours(source)
    status = source['status']
    if status == 'ok' and (latest is None or now-timestamp(latest) > timedelta(hours=limit)):
        status = 'stale'
    return {**source, 'status': status, 'latest_observation_at': latest, 'observation_stale_after_hours': limit}
