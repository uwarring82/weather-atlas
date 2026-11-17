"""Read the official daily-published hourly climate file for Vosges (88)."""
import csv
from datetime import datetime, timedelta, timezone
import gzip
import io
import math
from urllib.request import Request, urlopen
from community import distance, iso, timestamp

DATASET = 'https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-horaires'

def value(row, field):
    # 0: protected, 1: validated, 9: filtered. 2 is doubtful: leave blank.
    if row.get('Q' + field) not in {'0', '1', '9'}:
        return None
    try:
        v = float(row[field])
        return v if math.isfinite(v) else None
    except (ValueError, TypeError, KeyError):
        return None

def normalize(rows, location, now):
    stations = {}
    for row in rows:
        measured = datetime.strptime(row['AAAAMMJJHH'], '%Y%m%d%H').replace(tzinfo=timezone.utc)
        if not now-timedelta(days=7) <= measured <= now:
            continue
        lat, lon = float(row['LAT']), float(row['LON'])
        meters = distance(location['latitude'], location['longitude'], lat, lon)
        if meters > 50000:
            continue
        station_id = row['NUM_POSTE']
        if station_id not in stations:
            stations[station_id] = {'source': {'id': station_id, 'station_id': station_id, 'station_name': row['NOM_USUEL'],
                'observation_type': 'historical', 'lat': lat, 'lon': lon, 'height': float(row['ALTI']), 'distance': meters,
                'provider': 'Météo-France'}, 'rows': [], 'raw': []}
        wind = value(row, 'FF')
        stations[station_id]['rows'].append({'time': iso(measured), 'source_id': station_id, 'temperature': value(row, 'T'),
            'precipitation': value(row, 'RR1'), 'humidity': value(row, 'U'), 'wind': round(wind*3.6, 2) if wind is not None else None})
        stations[station_id]['raw'].append(row)
    usable = [s for s in stations.values() if any(r['temperature'] is not None for r in s['rows'])]
    if not usable:
        raise ValueError('No recent Météo-France station temperatures within 50 km')
    nearest = min(usable, key=lambda s: s['source']['distance'])
    return sorted(nearest['rows'], key=lambda r: r['time']), [nearest['source']], nearest['raw']

def collect(location, previous, now, user_agent):
    # The 10 MB departmental file is published daily, not hourly. Reuse it for
    # six hours, retaining the actual retrieval timestamp and measurement age.
    if previous.get('provider') == 'Météo-France' and previous.get('status') == 'ok' and now-timestamp(previous['fetched_at']) < timedelta(hours=6):
        return {**previous, 'rows': [r for r in previous['rows'] if timestamp(r['time']) >= now-timedelta(days=7)], 'checked_at': iso(now)}, None
    url = f"https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/HOR/H_88_latest-{now.year-1}-{now.year}.csv.gz"
    with urlopen(Request(url, headers={'User-Agent': user_agent}), timeout=90) as response:
        modified = response.headers.get('Last-Modified')
        reader = csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=response), encoding='utf-8-sig'), delimiter=';')
        rows, sources, raw = normalize(reader, location, now)
    item = {'provider': 'Météo-France', 'status': 'ok', 'fetched_at': iso(now), 'checked_at': iso(now), 'url': url,
        'dataset_url': DATASET, 'publication': 'Daily file of hourly observations', 'stale_after_hours': 24,
        'publication_note': 'Météo-France publishes this hourly station file daily; it is checked every six hours. Unmeasured parameters remain blank.',
        'source_last_modified': modified, 'rows': rows, 'sources': sources}
    return item, {'location': location['id'], 'source': 'Météo-France', 'url': url, 'payload': raw,
                  'note': 'Original CSV rows for the selected nearby station and seven-day window'}
