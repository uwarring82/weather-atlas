import sys
from pathlib import Path
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from community import sensemap, wunderground, collect_community

class CommunityTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,17,12,tzinfo=timezone.utc)
        self.location={'id':'test','latitude':51.33,'longitude':7.28}

    def box(self,value='7',exposure='outdoor',time='2026-11-17T11:50:00Z'):
        return {'_id':'test','name':'sensor','exposure':exposure,'currentLocation':{'coordinates':[7.28,51.33]},'sensors':[{'title':'Temperatur','unit':'°C','lastMeasurement':{'value':value,'createdAt':time}}]}

    def test_excludes_indoor_stale_and_faulty_sensors(self):
        stations=sensemap([self.box('-40'),self.box(exposure='indoor'),self.box(time='2025-01-01T00:00:00Z'),self.box('0')],self.location,self.now)
        self.assertEqual(len(stations),1)
        self.assertEqual(stations[0]['rows'][0]['temperature'],0)

    def test_wu_daily_rain_is_not_hourly_rain(self):
        raw={'observations':[{'stationID':'TEST','obsTimeUtc':'2026-11-17T11:50:00Z','lat':51.33,'lon':7.28,'qcStatus':1,'humidity':80,'metric':{'temp':8,'windSpeed':10,'windGust':20,'precipTotal':12}}]}
        row=wunderground(raw,self.location,self.now)[0]['rows'][0]
        self.assertIsNone(row['precipitation'])
        self.assertEqual(row['precipitation_today'],12)
        raw['observations'][0]['qcStatus']=0
        self.assertEqual(wunderground(raw,self.location,self.now),[])

    def test_wu_key_is_not_in_published_data_or_errors(self):
        def fetch(url,params):
            if 'weather.com' in url:raise RuntimeError('apiKey=private-test-key')
            return [],url
        with patch.dict('os.environ',{'WU_API_KEY':'private-test-key','WU_STATIONS':'{"test":["TEST"]}'}):
            result,raw=collect_community(self.location,{},self.now,fetch)
        self.assertNotIn('private-test-key',str((result,raw)))
        self.assertEqual(result['wunderground_status'],'unavailable')
