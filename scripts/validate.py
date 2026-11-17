"""Validate structure independently of the optional publication freshness gate."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from freshness import latest_observation_time, observation_limit_hours
from community import distance

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('temperature', 'precipitation', 'wind', 'humidity')

def stamp(value):
    assert isinstance(value, str) and value.endswith('Z'), 'Expected explicit UTC timestamp'
    return datetime.fromisoformat(value.replace('Z', '+00:00'))

def validate_rows(rows):
    times = []
    for row in rows:
        stamp(row['time'])
        times.append(row['time'])
        for key in FIELDS:
            v = row[key]
            assert v is None or (type(v) in (int, float) and math.isfinite(v)), f'Invalid {key}'
    assert times == sorted(set(times)), 'Timestamps must be sorted and unique'

def validate(data, locations, now=None, max_age_hours=None):
    now = now or datetime.now(timezone.utc)
    collected = stamp(data['collected_at'])
    assert collected <= now + timedelta(minutes=5), 'Collection timestamp is in the future'
    if max_age_hours is not None:
        assert now - collected <= timedelta(hours=max_age_hours), 'Published collection is too old'
    assert data['schema_version'] == 1
    assert {l['id'] for l in data['locations']} == {l['id'] for l in locations}
    assert len(data['locations']) == len(locations), 'Duplicate location IDs'
    for location in data['locations']:
        if max_age_hours is not None:
            latest = latest_observation_time(location['observations'])
            assert latest is not None, f"{location['id']}: no valid station temperature observations"
            limit = observation_limit_hours(location['observations'], max_age_hours)
            assert now-stamp(latest) <= timedelta(hours=limit), f"{location['id']}: newest observation is too old (limit {limit} h)"
        assert {s['id'] for s in location['forecasts']} == {'dwd_icon', 'ecmwf_ifs025', 'gfs_seamless', 'met_no'}
        for source in [location['observations'], *location['forecasts']]:
            assert source['status'] in {'ok', 'stale', 'unavailable'}
            validate_rows(source['rows'])
        sources = {s['id']: s for s in location['observations']['sources']}
        for row in location['observations']['rows']:
            assert sources[row['source_id']]['observation_type'] != 'forecast'
            assert stamp(row['time']) <= collected
        community = location['community']
        assert isinstance(community['errors'], list) and all(isinstance(e, str) for e in community['errors'])
        assert community['wunderground_status'] in {'not_configured', 'configuration_error', 'ok', 'partial', 'unavailable'}
        keys = []
        for station in community['stations']:
            keys.append((station['provider'], station['id']))
            assert station['status'] in {'ok', 'stale'}
            assert station['rows'], 'Retained community stations need history'
            assert 0 <= station['distance'] <= 15000
            assert station['url'].startswith('https://')
            stamp(station['fetched_at'])
            validate_rows(station['rows'])
            for row in station['rows']:
                assert collected-timedelta(days=7) <= stamp(row['time']) <= collected
        assert len(keys) == len(set(keys)), 'Duplicate community station identities'
        nearby = location['nearby_stations']
        assert len(nearby) <= 7
        assert [s['distance'] for s in nearby] == sorted(s['distance'] for s in nearby)
        identities = []
        for station in nearby:
            identities.append((station['provider'], station['id']))
            assert 0 <= station['distance'] <= 50000
            assert station['distance_method'] == 'great-circle'
            assert abs(station['distance']-distance(location['latitude'], location['longitude'], station['latitude'], station['longitude'])) <= 1
            validate_rows(station['rows'])
        assert len(identities) == len(set(identities)), 'Duplicate nearby station identities'
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-age-hours', type=float)
    args = parser.parse_args()
    data = json.loads((ROOT/'site/data/latest.json').read_text())
    locations = json.loads((ROOT/'locations.json').read_text())
    validate(data, locations, max_age_hours=args.max_age_hours)
    print(f'Dataset valid for {len(locations)} locations, four forecasts and community history.')
