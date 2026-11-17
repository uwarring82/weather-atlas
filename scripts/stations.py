"""Select and export up to seven nearest currently reporting monitors per place."""
import csv
from community import distance, timestamp
from freshness import latest_observation_time, observation_limit_hours
from datetime import timedelta

MAX_STATIONS = 7

def official_stations(location):
    obs = location['observations']
    if obs.get('nearby_stations') is not None:
        return obs['nearby_stations']
    sources = {s['id']: s for s in obs.get('sources', [])}
    groups = {}
    for row in obs.get('rows', []):
        source = sources.get(row['source_id'])
        if not source:
            continue
        station_id = source.get('station_id') or source.get('dwd_station_id') or str(source['id'])
        groups.setdefault(station_id, {'rows': []})['rows'].append(row)
        groups[station_id]['source'] = source
    result = []
    for station_id, group in groups.items():
        s = group['source']
        result.append({'id': station_id, 'name': s['station_name'], 'provider': s.get('provider', 'DWD'),
            'official': True, 'latitude': s['lat'], 'longitude': s['lon'], 'height': s.get('height'),
            'distance': distance(location['latitude'], location['longitude'], s['lat'], s['lon']),
            'distance_method': 'great-circle', 'url': obs.get('dataset_url') or obs.get('url', 'https://brightsky.dev/'),
            'fetched_at': obs.get('fetched_at'), 'status': obs['status'], 'rows': group['rows'],
            'observation_stale_after_hours': observation_limit_hours(obs),
            'quality': 'Official weather station observations'})
    return result

def nearby_stations(location, now):
    candidates = [*official_stations(location), *location.get('community', {}).get('stations', [])]
    active = {}
    for s in candidates:
        latest = latest_observation_time(s)
        limit = s.get('observation_stale_after_hours', 2)
        if s.get('status') != 'ok' or not latest or not now-timedelta(hours=limit) <= timestamp(latest) <= now:
            continue
        current_row = next(r for r in reversed(s['rows']) if r['time'] == latest)
        active[(s['provider'], s['id'])] = {**s, 'rows': [current_row], 'latest_observation_at': latest}
    return sorted(active.values(), key=lambda s: (s['distance'], s['provider'], s['id']))[:MAX_STATIONS]

def export_csv(path, data):
    columns = ['location', 'station_id', 'provider', 'station_name', 'distance_m', 'distance_km', 'distance_method', 'coordinates_approximate', 'latitude', 'longitude',
               'latest_observation_utc', 'temperature_c', 'humidity_percent', 'wind_kmh', 'url']
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for location in data['locations']:
            for station in location['nearby_stations']:
                row = next(r for r in reversed(station['rows']) if r['time'] == station['latest_observation_at'])
                record = {'location': location['name'], 'station_id': station['id'], 'provider': station['provider'],
                    'station_name': station['name'], 'distance_m': station['distance'], 'distance_km': round(station['distance']/1000, 3),
                    'distance_method': 'great-circle', 'coordinates_approximate': station.get('coordinates_approximate', ''),
                    'latitude': station.get('latitude'), 'longitude': station.get('longitude'),
                    'latest_observation_utc': row['time'], 'temperature_c': row['temperature'], 'humidity_percent': row['humidity'],
                    'wind_kmh': row['wind'], 'url': station['url']}
                writer.writerow({k: "'"+v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v for k,v in record.items()})
