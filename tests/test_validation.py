import copy
import json
from datetime import timedelta
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate import validate, stamp

class ValidationTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]
        self.data=json.loads((root/'site/data/latest.json').read_text())
        self.locations=self.data['locations']
        self.now=stamp(self.data['collected_at'])

    def test_rejects_stale_collection_when_freshness_is_requested(self):
        with self.assertRaisesRegex(AssertionError,'too old'):
            validate(self.data,self.locations,self.now+timedelta(hours=4),max_age_hours=3)
        self.assertTrue(validate(self.data,self.locations,self.now+timedelta(hours=4)))

    def test_fresh_download_cannot_hide_old_french_measurements(self):
        bad=copy.deepcopy(self.data)
        obs=next(l['observations'] for l in bad['locations'] if l['id']=='xonrupt-longemer')
        row=obs['rows'][-1]
        row['time']=(self.now-timedelta(hours=37)).isoformat(timespec='seconds').replace('+00:00','Z')
        obs.update(rows=[row],fetched_at=bad['collected_at'],status='ok')
        with self.assertRaisesRegex(AssertionError,'xonrupt-longemer: newest observation is too old'):
            validate(bad,self.locations,self.now,max_age_hours=3)
        row['time']=(self.now-timedelta(hours=35)).isoformat(timespec='seconds').replace('+00:00','Z')
        self.assertTrue(validate(bad,self.locations,self.now,max_age_hours=3))

    def test_fresh_collection_cannot_hide_frozen_dwd_observations(self):
        bad=copy.deepcopy(self.data)
        obs=bad['locations'][0]['observations']
        row=obs['rows'][-1]
        row['time']=(self.now-timedelta(hours=4)).isoformat(timespec='seconds').replace('+00:00','Z')
        obs.update(rows=[row],fetched_at=bad['collected_at'],status='ok')
        with self.assertRaisesRegex(AssertionError,'hasslinghausen: newest observation is too old'):
            validate(bad,self.locations,self.now,max_age_hours=3)

    def test_rejects_corrupt_community_values_and_duplicate_identities(self):
        bad=copy.deepcopy(self.data)
        bad['locations'][0]['community']['stations'][0]['rows'][0]['temperature']=float('nan')
        with self.assertRaisesRegex(AssertionError,'Invalid temperature'):
            validate(bad,self.locations,self.now)
        bad=copy.deepcopy(self.data)
        stations=bad['locations'][0]['community']['stations']
        stations.append(copy.deepcopy(stations[0]))
        with self.assertRaisesRegex(AssertionError,'Duplicate community'):
            validate(bad,self.locations,self.now)
