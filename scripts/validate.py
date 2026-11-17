"""Validate the published data contract without requiring upstream availability."""
import json
from pathlib import Path
from datetime import datetime

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'site/data/latest.json').read_text())
assert data['schema_version'] == 1
assert {l['id'] for l in data['locations']} == {'hasslinghausen', 'freiburg'}
for location in data['locations']:
    assert len(location['forecasts']) == 4
    for source in [location['observations'], *location['forecasts']]:
        assert source['status'] in {'ok', 'stale', 'unavailable'}
        timestamps = []
        for row in source['rows']:
            assert row['time'].endswith('Z')
            datetime.fromisoformat(row['time'].replace('Z', '+00:00'))
            timestamps.append(row['time'])
            for key in ['temperature', 'precipitation', 'wind', 'humidity']:
                assert row[key] is None or isinstance(row[key], (int, float))
        assert timestamps == sorted(set(timestamps)), 'Timestamps must be sorted and unique'
    sources = {s['id']: s for s in location['observations']['sources']}
    for row in location['observations']['rows']:
        assert sources[row['source_id']]['observation_type'] != 'forecast'
print('Dataset contract valid for both locations and all four forecasts.')
