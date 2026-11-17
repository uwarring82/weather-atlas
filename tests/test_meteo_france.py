import sys
from pathlib import Path
import unittest
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from meteo_france import normalize

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
