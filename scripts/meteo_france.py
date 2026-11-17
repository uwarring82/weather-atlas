"""Read the official daily-published hourly climate file for Vosges (88)."""
import csv
from datetime import datetime, timedelta, timezone
import gzip
import io
import math
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from community import distance, iso, timestamp
from freshness import mark_observation_freshness

DATASET = 'https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-horaires'
PUBLICATION_NOTE = 'Météo-France publishes this hourly station file daily; it is checked hourly for changes. Measurements older than 36 hours are flagged as delayed. Unmeasured parameters remain blank.'

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
    # Check hourly, but transfer the 10 MB daily file only when it changes.
    # At New Year the publisher may still be using the previous filename.
    base = 'https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/HOR/'
    urls = [f'{base}H_88_latest-{year-1}-{year}.csv.gz' for year in [now.year, now.year-1]]
    for index, url in enumerate(urls):
        headers = {'User-Agent': user_agent}
        if previous.get('url') == url and previous.get('source_last_modified') and previous.get('rows'):
            headers['If-Modified-Since'] = previous['source_last_modified']
        try:
            with urlopen(Request(url, headers=headers), timeout=90) as response:
                modified = response.headers.get('Last-Modified')
                reader = csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=response), encoding='utf-8-sig'), delimiter=';')
                rows, sources, raw = normalize(reader, location, now)
            break
        except HTTPError as error:
            if error.code == 304 and previous.get('url') == url and previous.get('rows'):
                item = {**previous, 'status': 'ok', 'checked_at': iso(now),
                        'publication_note': PUBLICATION_NOTE,
                        'rows': [r for r in previous['rows'] if timestamp(r['time']) >= now-timedelta(days=7)]}
                item.pop('stale_after_hours', None)
                return mark_observation_freshness(item, now), None
            if error.code == 404 and index == 0:
                continue
            raise
    item = {'provider': 'Météo-France', 'status': 'ok', 'fetched_at': iso(now), 'checked_at': iso(now), 'url': url,
        'dataset_url': DATASET, 'publication': 'Daily file of hourly observations',
        'publication_note': PUBLICATION_NOTE,
        'source_last_modified': modified, 'rows': rows, 'sources': sources}
    return mark_observation_freshness(item, now), {'location': location['id'], 'source': 'Météo-France', 'url': url, 'payload': raw,
                  'note': 'Original CSV rows for the selected nearby station and seven-day window'}
