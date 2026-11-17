import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collect', Path(__file__).resolve().parents[1] / 'scripts/collect.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class NormalizationTests(unittest.TestCase):
    def test_met_wind_conversion_and_rain_hour_end(self):
        raw = {'properties': {'timeseries': [
            {'time': '2026-01-01T00:00:00Z', 'data': {'instant': {'details': {'air_temperature': 4, 'wind_speed': 5}}, 'next_1_hours': {'details': {'precipitation_amount': 1.2}}}},
            {'time': '2026-01-01T01:00:00Z', 'data': {'instant': {'details': {'air_temperature': 5, 'wind_speed': 0}}}},
            {'time': '2026-01-01T03:00:00Z', 'data': {'instant': {'details': {}}}},
        ]}}
        rows = c.met_no(raw)
        self.assertEqual(rows[0]['wind'], 18)
        self.assertIsNone(rows[0]['precipitation'])
        self.assertEqual(rows[1]['precipitation'], 1.2)
        self.assertEqual(rows[1]['wind'], 0)
        self.assertIsNone(rows[2]['precipitation'])

    def test_forecasts_and_future_records_are_excluded_from_observations(self):
        raw = {'sources': [{'id': 1, 'observation_type': 'forecast'}, {'id': 2, 'observation_type': 'current'}],
               'weather': [
                   {'timestamp': '2026-01-01T00:00:00Z', 'source_id': 1, 'temperature': 9},
                   {'timestamp': '2026-01-01T00:00:00+00:00', 'source_id': 2, 'temperature': 0, 'precipitation': None},
                   {'timestamp': '2026-01-02T00:00:00Z', 'source_id': 2, 'temperature': 10},
               ]}
        rows, sources = c.observations(raw, datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['temperature'], 0)
        self.assertIsNone(rows[0]['precipitation'])
        self.assertEqual([s['id'] for s in sources], [2])

    def test_open_meteo_utc_and_nulls(self):
        raw = {'hourly': {'time': [1767225600], 'temperature_2m': [0], 'precipitation': [None], 'wind_speed_10m': [2], 'relative_humidity_2m': [80]}}
        row = c.open_meteo(raw)[0]
        self.assertEqual(row['time'], '2026-01-01T00:00:00Z')
        self.assertEqual(row['temperature'], 0)
        self.assertIsNone(row['precipitation'])

    def test_total_outage_keeps_published_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'latest.json'
            before = '{"locations":[]}\n'
            output.write_text(before)
            with patch.object(c, 'fetch', side_effect=OSError('offline')), patch.object(c, 'collect_community', return_value=({'stations': []}, [])):
                with self.assertRaises(RuntimeError):
                    c.collect(output, datetime(2026, 1, 1, tzinfo=timezone.utc))
            self.assertEqual(output.read_text(), before)


if __name__ == '__main__':
    unittest.main()
