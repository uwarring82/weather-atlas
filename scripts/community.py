"""Outdoor citizen sensors and optional Weather Underground PWS ingestion."""
import math
import os
import json
import re
from datetime import datetime, timedelta, timezone

MAX_STATIONS = 7
SEARCH_RADIUS_M = 15000

def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))

def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def distance(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    h = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return round(6371000 * 2 * math.asin(min(1, math.sqrt(h))))

def reading(sensor, now, low, high):
    try:
        m = sensor['lastMeasurement']
        v, measured = float(m['value']), timestamp(m['createdAt'])
        if not math.isfinite(v) or not low <= v <= high or not now-timedelta(hours=2) <= measured <= now:
            return None
        return {'value': v, 'time': iso(measured)}
    except (KeyError, TypeError, ValueError):
        return None

def sensemap(raw, location, now):
    stations = []
    for box in raw:
        if box.get('exposure') != 'outdoor':
            continue
        coords = box.get('currentLocation', {}).get('coordinates', [])
        if len(coords) < 2:
            continue
        meters = distance(location['latitude'], location['longitude'], coords[1], coords[0])
        if meters > SEARCH_RADIUS_M:
            continue
        temp = next((reading(s, now, -35, 55) for s in box.get('sensors', [])
                     if s.get('unit') == '°C' and s.get('title', '').lower() in {'temperatur', 'temperature', 'lufttemperatur', 'air temperature'}
                     and reading(s, now, -35, 55)), None)
        if not temp:
            continue
        humidity = next((reading(s, now, 0, 100) for s in box.get('sensors', [])
                         if s.get('unit') == '%' and any(t in s.get('title', '').lower() for t in ['feucht', 'humidity'])
                         and reading(s, now, 0, 100)), None)
        row = {'time': temp['time'], 'temperature': temp['value'], 'humidity': humidity['value'] if humidity else None,
               'humidity_time': humidity['time'] if humidity else None, 'wind': None, 'precipitation': None}
        stations.append({'id': box['_id'], 'name': box['name'], 'provider': 'openSenseMap', 'distance': meters,
                         'latitude': coords[1], 'longitude': coords[0], 'distance_method': 'great-circle',
                         'url': 'https://opensensemap.org/explore/' + box['_id'], 'status': 'ok', 'fetched_at': iso(now),
                         'quality': 'Community sensor; range and freshness checks only', 'rows': [row]})
    return sorted(stations, key=lambda s: s['distance'])[:MAX_STATIONS]

def sensor_community(raw, location, now):
    """Use public outdoor temperature monitors, one sensor per deployment."""
    stations = {}
    for record in raw:
        try:
            loc = record['location']
            if loc.get('indoor') not in (0, False):
                continue
            lat, lon = float(loc['latitude']), float(loc['longitude'])
            meters = distance(location['latitude'], location['longitude'], lat, lon)
            measured = datetime.strptime(record['timestamp'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            if meters > SEARCH_RADIUS_M or not now-timedelta(hours=2) <= measured <= now:
                continue
            values = {v['value_type']: v['value'] for v in record['sensordatavalues']}
            temp = float(values['temperature'])
            if not math.isfinite(temp) or not -35 <= temp <= 55:
                continue
            humidity = float(values['humidity']) if 'humidity' in values else None
            if humidity is not None and (not math.isfinite(humidity) or not 0 <= humidity <= 100):
                humidity = None
            station_id = str(loc['id'])
            row = {'time': iso(measured), 'temperature': temp, 'humidity': humidity,
                   'humidity_time': iso(measured) if humidity is not None else None, 'wind': None, 'precipitation': None}
            sensor = record['sensor']
            station = {'id': station_id, 'name': 'Sensor.Community ' + station_id, 'provider': 'Sensor.Community',
                'sensor_id': str(sensor['id']), 'sensor_type': sensor['sensor_type']['name'],
                'latitude': lat, 'longitude': lon, 'distance': meters, 'distance_method': 'great-circle',
                'coordinates_approximate': not bool(loc.get('exact_location')),
                'url': f"https://data.sensor.community/airrohr/v1/sensor/{sensor['id']}/",
                'status': 'ok', 'fetched_at': iso(now), 'quality': 'Outdoor community monitor; range and freshness checks only', 'rows': [row]}
            if station_id not in stations or row['time'] > stations[station_id]['rows'][0]['time']:
                stations[station_id] = station
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(stations.values(), key=lambda s: s['distance'])[:MAX_STATIONS]

def wunderground(raw, location, now, errors=None, station_id=None):
    result = []
    errors = errors if errors is not None else []
    if not raw.get('observations'):
        errors.append(f'Weather Underground {station_id or "station"}: no current observation returned')
    for r in raw.get('observations', []):
        label = station_id or r.get('stationID', 'station')
        def reject(reason):
            errors.append(f'Weather Underground {label}: {reason}')
        try:
            measured = timestamp(r['obsTimeUtc'])
        except (KeyError, TypeError, ValueError):
            reject('invalid observation timestamp')
            continue
        m = r.get('metric', {})
        if station_id and r.get('stationID') != station_id:
            reject('returned station ID does not match requested station')
            continue
        if r.get('qcStatus') == 0:
            reject('provider quality-control check failed')
            continue
        if not now-timedelta(hours=2) <= measured <= now:
            reject('observation is older than two hours or in the future')
            continue
        if r.get('lat') is None or r.get('lon') is None:
            reject('station coordinates are missing')
            continue
        meters = distance(location['latitude'], location['longitude'], r['lat'], r['lon'])
        if meters > 15000:
            reject('station is outside the 15 km search radius')
            continue
        row = {'time': iso(measured), 'temperature': m.get('temp'), 'humidity': r.get('humidity'),
               'wind': m.get('windSpeed'), 'wind_gust': m.get('windGust'), 'precipitation': None,
               'precipitation_today': m.get('precipTotal'), 'qc_status': r.get('qcStatus')}
        result.append({'id': r['stationID'], 'name': r.get('neighborhood') or r['stationID'], 'provider': 'Weather Underground',
                       'latitude': r['lat'], 'longitude': r['lon'], 'distance_method': 'great-circle',
                       'distance': meters, 'url': 'https://www.wunderground.com/dashboard/pws/' + r['stationID'],
                       'status': 'ok', 'fetched_at': iso(now), 'quality': 'Personal weather station; provider QC ' + str(r.get('qcStatus')), 'rows': [row]})
    return result

def retain_history(stations, previous, now):
    """Retain all previously selected stations until their final row ages out."""
    old = {(s['provider'], s['id']): s for s in previous.get('stations', [])}
    current = {(s['provider'], s['id']): s for s in stations}
    retained = []
    for key in dict.fromkeys([*current, *old]):
        station = dict(current.get(key) or {**old[key], 'status': 'stale'})
        merged = {r['time']: r for r in old.get(key, {}).get('rows', [])}
        merged.update({r['time']: r for r in current.get(key, {}).get('rows', [])})
        station['rows'] = sorted((r for r in merged.values() if now-timedelta(days=7) <= timestamp(r['time']) <= now), key=lambda r: r['time'])
        if station['rows']:
            retained.append(station)
    return retained

def community_fallback(previous, now, message):
    return {**previous, 'stations': retain_history([], previous, now),
            'errors': [message], 'status': 'stale', 'search_radius_km': 15,
            'wunderground_status': previous.get('wunderground_status', 'not_configured')}

def parse_wu_stations(value):
    try:
        config = json.loads(value or '{}')
        if not isinstance(config, dict) or any(
            not isinstance(k, str) or not isinstance(ids, list) or any(
                not isinstance(s, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', s) for s in ids
            ) for k, ids in config.items()
        ):
            raise ValueError('invalid station mapping')
        return config, []
    except (ValueError, TypeError):
        return {}, ['Weather Underground: WU_STATIONS must be a JSON object mapping location IDs to arrays of station IDs']

def collect_community(location, previous, now, fetch):
    stations, responses, errors = [], [], []
    try:
        raw, url = fetch('https://api.opensensemap.org/boxes', {'near': f"{location['longitude']},{location['latitude']}",
                        'maxDistance': 15000, 'exposure': 'outdoor', 'full': 'true'})
        selected = sensemap(raw, location, now)
        stations.extend(selected)
        selected_ids = {s['id'] for s in selected}
        responses.append({'location': location['id'], 'source': 'openSenseMap', 'url': url, 'payload': [b for b in raw if b['_id'] in selected_ids]})
    except Exception as e:
        errors.append('openSenseMap: ' + str(e))
        stations.extend({**s, 'status': 'stale'} for s in previous.get('stations', []) if s['provider'] == 'openSenseMap')
    try:
        raw, url = fetch(f"https://data.sensor.community/airrohr/v1/filter/area={location['latitude']},{location['longitude']},15", {})
        selected = sensor_community(raw, location, now)
        stations.extend(selected)
        ids = {s['sensor_id'] for s in selected}
        responses.append({'location': location['id'], 'source': 'Sensor.Community', 'url': url,
                          'payload': [r for r in raw if str(r.get('sensor', {}).get('id')) in ids]})
    except Exception as error:
        errors.append('Sensor.Community: ' + str(error))
        stations.extend({**s, 'status': 'stale'} for s in previous.get('stations', []) if s['provider'] == 'Sensor.Community')
    key = os.environ.get('WU_API_KEY')
    config, config_errors = parse_wu_stations(os.environ.get('WU_STATIONS'))
    errors.extend(config_errors)
    requested = config.get(location['id'], [])
    wu_status = 'configuration_error' if config_errors else 'not_configured'
    if requested and not key:
        wu_status = 'unavailable'
        errors.append('Weather Underground: configured stations need the WU_API_KEY secret')
    if key and requested:
        wu_status = 'ok'
        wu_errors = []
        for station_id in requested[:MAX_STATIONS]:
            try:
                raw, _ = fetch('https://api.weather.com/v2/pws/observations/current', {'stationId': station_id,
                               'format': 'json', 'units': 'm', 'numericPrecision': 'decimal', 'apiKey': key})
                stations.extend(wunderground(raw, location, now, wu_errors, station_id))
            except Exception:
                wu_errors.append('Weather Underground: request failed for ' + station_id)
        errors.extend(wu_errors)
        if wu_errors:
            wu_status = 'partial' if any(s['provider'] == 'Weather Underground' for s in stations) else 'unavailable'
    stations = retain_history(stations, previous, now)
    return {'stations': stations, 'errors': errors, 'status': 'partial' if errors else 'ok', 'wunderground_status': wu_status,
            'fetched_at': iso(now), 'search_radius_km': 15}, responses
