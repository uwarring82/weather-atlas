import sys
from pathlib import Path
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from community import sensemap, wunderground, collect_community, retain_history, sensor_community
from datetime import timedelta

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

    def test_sensor_community_selects_seven_nearest_outdoor_deployments(self):
        def record(i,indoor=0):
            return {'timestamp':'2026-11-17 11:50:00','location':{'id':i,'indoor':indoor,'latitude':51.33,'longitude':7.28+i*.001,'exact_location':0},
                    'sensor':{'id':i+100,'sensor_type':{'name':'BME280'}},
                    'sensordatavalues':[{'value_type':'temperature','value':'0'},{'value_type':'humidity','value':'80'}]}
        raw=[record(i) for i in reversed(range(10))]+[record(0,indoor=1),record(0)]
        stations=sensor_community(raw,self.location,self.now)
        self.assertEqual([s['id'] for s in stations],[str(i) for i in range(7)])
        self.assertEqual(stations[0]['rows'][0]['temperature'],0)
        self.assertEqual(stations[0]['distance'],0)
        self.assertTrue(stations[0]['coordinates_approximate'])
        self.assertEqual(stations[0]['rows'][0]['time'],'2026-11-17T11:50:00Z')

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

    def test_invalid_wu_config_does_not_break_other_sources(self):
        for setting in ['{typo', '[]', '{"test":"TEST"}', '{"test":[null]}']:
            with self.subTest(setting=setting), patch.dict('os.environ', {'WU_STATIONS':setting}):
                result,_=collect_community(self.location,{},self.now,lambda *args:([self.box()], 'https://example.org'))
            self.assertEqual(result['wunderground_status'],'configuration_error')
            self.assertEqual(len(result['stations']),1)
            self.assertIn('WU_STATIONS',result['errors'][0])

    def test_history_survives_selection_changes_and_expires_after_seven_days(self):
        first=sensemap([self.box()],self.location,self.now)
        previous={'stations':first}
        replacement={**first[0],'id':'replacement'}
        retained=retain_history([replacement],previous,self.now+timedelta(hours=3))
        self.assertEqual({s['id'] for s in retained},{'test','replacement'})
        original=next(s for s in retained if s['id']=='test')
        self.assertEqual(original['status'],'stale')
        self.assertEqual(original['rows'],first[0]['rows'])
        self.assertEqual(retain_history([],previous,self.now+timedelta(days=8)),[])

    def test_wu_skips_include_explanations_and_preserve_history(self):
        first=sensemap([self.box()],self.location,self.now)[0]
        first.update(id='TEST',provider='Weather Underground')
        for change,reason in [({'qcStatus':0},'quality-control'),({'lat':50},'15 km'),({'obsTimeUtc':'2026-11-16T00:00:00Z'},'two hours')]:
            r={'stationID':'TEST','obsTimeUtc':'2026-11-17T11:50:00Z','lat':51.33,'lon':7.28,'qcStatus':1,'metric':{'temp':8},**change}
            def fetch(url,params):
                return ({'observations':[r]} if 'weather.com' in url else []),url
            with self.subTest(reason=reason),patch.dict('os.environ',{'WU_API_KEY':'test','WU_STATIONS':'{"test":["TEST"]}'}):
                result,_=collect_community(self.location,{'stations':[first]},self.now,fetch)
            self.assertEqual(result['wunderground_status'],'unavailable')
            self.assertTrue(any(reason in e for e in result['errors']))
            self.assertEqual(result['stations'][0]['status'],'stale')
