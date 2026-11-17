import sys
from pathlib import Path
import unittest
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from meteo_france import normalize, collect
from unittest.mock import patch
from urllib.error import HTTPError
import io
import gzip
import csv
from datetime import timedelta

class MeteoFranceTests(unittest.TestCase):
    def test_selects_nearest_station_and_preserves_quality_gaps(self):
        row={'NUM_POSTE':'88001','NOM_USUEL':'VOSGES','LAT':'48.08','LON':'6.92','ALTI':'700','AAAAMMJJHH':'2026111704',
             'T':'0','QT':'1','RR1':'2','QRR1':'9','FF':'5','QFF':'0','U':'80','QU':'2'}
        far={**row,'NUM_POSTE':'88002','LON':'6.8'}
        rows,sources,raw=normalize([far,row],{'latitude':48.0813,'longitude':6.9267},datetime(2026,11,17,12,tzinfo=timezone.utc))
        self.assertEqual(sources[0]['id'],'88001')
        self.assertEqual(rows[0]['temperature'],0)
        self.assertEqual(rows[0]['wind'],18)
        self.assertEqual(rows[0]['precipitation'],2)
        self.assertIsNone(rows[0]['humidity'])
        self.assertEqual(rows[0]['time'],'2026-11-17T04:00:00Z')
        self.assertEqual(raw,[row])

    def test_january_first_falls_back_to_previous_filename_on_404(self):
        now=datetime(2027,1,1,tzinfo=timezone.utc)
        row={'NUM_POSTE':'88001','NOM_USUEL':'VOSGES','LAT':'48.08','LON':'6.92','ALTI':'700','AAAAMMJJHH':'2026123123',
             'T':'0','QT':'1','RR1':'2','QRR1':'9','FF':'5','QFF':'0','U':'80','QU':'2'}
        csv_text=io.StringIO()
        writer=csv.DictWriter(csv_text,fieldnames=row.keys(),delimiter=';')
        writer.writeheader();writer.writerow(row)
        response=io.BytesIO(gzip.compress(csv_text.getvalue().encode()))
        response.headers={'Last-Modified':'Thu, 31 Dec 2026 23:30:00 GMT'}
        location={'id':'xonrupt-longemer','latitude':48.0813,'longitude':6.9267}
        with patch('meteo_france.urlopen',side_effect=[HTTPError('new',404,'Not Found',{},None),response]) as opener:
            item,raw=collect(location,{},now,'test')
        self.assertIn('2026-2027',opener.call_args_list[0].args[0].full_url)
        self.assertIn('2025-2026',opener.call_args_list[1].args[0].full_url)
        self.assertIn('2025-2026',item['url'])
        self.assertEqual(item['status'],'ok')
        self.assertEqual(item['rows'][0]['time'],'2026-12-31T23:00:00Z')
        self.assertEqual(raw['payload'],[row])

    def test_unchanged_file_preserves_retrieval_time_but_flags_frozen_measurements(self):
        now=datetime(2026,11,17,12,tzinfo=timezone.utc)
        url='https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/HOR/H_88_latest-2025-2026.csv.gz'
        previous={'provider':'Météo-France','status':'ok','url':url,'fetched_at':'2026-11-17T11:00:00Z',
                  'source_last_modified':'Sun, 15 Nov 2026 06:00:00 GMT','sources':[],
                  'rows':[{'time':'2026-11-15T23:00:00Z','temperature':5,'wind':None,'humidity':None,'precipitation':0}]}
        with patch('meteo_france.urlopen',side_effect=HTTPError(url,304,'Not Modified',{},None)) as opener:
            item,raw=collect({'id':'test'},previous,now,'test')
        self.assertEqual(opener.call_args.args[0].get_header('If-modified-since'),previous['source_last_modified'])
        self.assertEqual(item['fetched_at'],previous['fetched_at'])
        self.assertEqual(item['checked_at'],'2026-11-17T12:00:00Z')
        self.assertEqual(item['status'],'stale')
        self.assertEqual(item['observation_stale_after_hours'],36)
        self.assertIsNone(raw)

    def test_non_404_errors_do_not_fall_back(self):
        with patch('meteo_france.urlopen',side_effect=HTTPError('url',503,'Unavailable',{},None)) as opener:
            with self.assertRaises(HTTPError):
                collect({'id':'test'},{},datetime(2027,1,1,tzinfo=timezone.utc),'test')
        self.assertEqual(opener.call_count,1)
