import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from stations import nearby_stations, export_csv
from community import distance

class StationInventoryTests(unittest.TestCase):
    def test_nearest_seven_are_sorted_and_history_is_preserved(self):
        now=datetime(2026,11,17,12,tzinfo=timezone.utc)
        def station(i,age=1):
            return {'id':str(i),'provider':'test','name':f'Monitor {i}','latitude':51.33,'longitude':7.28+i*.001,
                    'distance':distance(51.33,7.28,51.33,7.28+i*.001),'distance_method':'great-circle','status':'ok',
                    'url':'https://example.org','rows':[{'time':(now-timedelta(hours=age)).isoformat().replace('+00:00','Z'),
                    'temperature':10,'humidity':80,'wind':None,'precipitation':None}]}
        stations=[station(i) for i in reversed(range(10))]+[station(0,age=4)]
        location={'name':'Test','latitude':51.33,'longitude':7.28,'observations':{'nearby_stations':[]},'community':{'stations':stations}}
        selected=nearby_stations(location,now)
        self.assertEqual([s['id'] for s in selected],[str(i) for i in range(7)])
        self.assertEqual(len(location['community']['stations']),11)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'stations.csv'
            export_csv(path,{'locations':[{**location,'nearby_stations':selected}]})
            with path.open() as handle:rows=list(csv.DictReader(handle))
            self.assertEqual(len(rows),7)
            self.assertEqual(rows[0]['distance_m'],'0')
            self.assertEqual(rows[1]['distance_km'],str(round(selected[1]['distance']/1000,3)))

    def test_official_daily_monitors_have_their_own_freshness_limit(self):
        now=datetime(2026,11,17,12,tzinfo=timezone.utc)
        station={'id':'fr','name':'French station','provider':'Météo-France','official':True,'status':'ok','distance':7000,
                 'observation_stale_after_hours':36,'rows':[{'time':'2026-11-17T04:00:00Z','temperature':8}]}
        location={'observations':{'nearby_stations':[station]},'community':{'stations':[]}}
        self.assertEqual(len(nearby_stations(location,now)),1)
        self.assertEqual(len(nearby_stations(location,now+timedelta(hours=40))),0)
