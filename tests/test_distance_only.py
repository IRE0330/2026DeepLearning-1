"""Dashboard time presentation must never fall back to module-only seconds."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard'))
from core import DEFAULTS, values, label, recommendation
from distance_demo import video_key, DISCLAIMER
from history_ui import distance_timeline
from views import playback_rows, signage


class DistanceOnly(unittest.TestCase):
    def test_counts_preserved_without_exposing_legacy_wait(self):
        rec={'csv_row':{'전체대기인원_추정':7,'내부잔류인원_추정':9,
                        '외부대기인원_추정':3,'구간_입장인원':2,'구간_퇴장인원':1},
             'detail':{'state':{'expected_wait_s':28}}}
        self.assertEqual(values(rec),{'inside':9,'queue':7,'outside':3,'free':None,'entry':2,'exit':1})
        self.assertNotIn('wait',values(None))

    def test_legacy_record_and_history_are_unknown_even_with_28_seconds(self):
        cfg=copy.deepcopy(DEFAULTS)
        records=[{'interval_end_s':1,'csv_row':{'전체대기인원_추정':0},
                  'detail':{'state':{'expected_wait_s':28,'source_time_s':1}}}]
        rows=playback_rows(records,cfg,'north')
        self.assertEqual(rows[0]['distance']['wait'],'측정 불가')
        self.assertNotIn('wait',rows[0])
        timeline=distance_timeline(records,cfg,'north')
        self.assertEqual(timeline['예상 대기시간'].tolist(),['측정 불가'])
        self.assertEqual(timeline['기준'].tolist(),[DISCLAIMER])
        body=signage({r:records for r in cfg['videos']},'north',1,cfg)
        self.assertIn('id="sign-wait-north">측정 불가',body)
        self.assertNotIn('28초',body)

    def test_distance_timeline_and_static_signage_use_exact_same_bands(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'synthetic.bin';source.write_bytes(b'fixture')
            cfg=copy.deepcopy(DEFAULTS)
            cfg['videos']={r:str(source) for r in cfg['videos']}
            annotation={'source_key':video_key(str(source)),'origin':[.5,.1],
                        'lines':{str(m):[[.1,y],[.9,y]] for m,y in [(5,.3),(10,.5),(15,.7)]}}
            cfg['distance_demo']={r:annotation for r in cfg['videos']}
            records=[]
            for i,y in enumerate([.2,.2,.3,.3,.5,.5,.7,.7],1):
                records.append({'interval_end_s':i,'csv_row':{'전체대기인원_추정':99},'detail':{'state':{
                    'expected_wait_s':28,'source_time_s':i,'waiting_total':1,'queue_geometry':{
                    'version':1,'points':[{'point':[.5,y],'confidence':.9}],
                    'candidate_count':0,'occluded_count':0,'suppressed_count':0}}}})
            for room in cfg['videos']:
                timeline=distance_timeline(records,cfg,room)
                self.assertEqual(timeline['예상 대기시간'].tolist(),['1분 미만','1분 미만','1분 미만','1분 이상','1분 이상','2분 이상','2분 이상','3분 이상'])
                for i,expected in enumerate(['여유','여유','여유','보통','보통','혼잡','혼잡','매우 혼잡'],1):
                    body=signage({r:records for r in cfg['videos']},room,i,cfg)
                    self.assertIn(f'id="sign-state-{room}">{expected}',body)
                    self.assertNotIn('28초',body)
                    self.assertIn(DISCLAIMER,body)
                body=signage({r:records for r in cfg['videos']},room,12,cfg)
                self.assertIn(f'id="sign-state-{room}">측정 불가',body)

    def test_count_thresholds_do_not_change_distance_status(self):
        cfg={'warning':1,'crowded':2}
        self.assertEqual(label({'queue':999,'distance':{'status':'여유'}},cfg)[0],'여유')
        self.assertEqual(label({'queue':0,'distance':{'status':'매우 혼잡'}},cfg)[0],'매우 혼잡')
        self.assertEqual(label({'queue':999},cfg)[0],'측정 불가')

    def test_recommendation_uses_bands_not_legacy_seconds(self):
        cfg=copy.deepcopy(DEFAULTS)
        vals={r:{'distance':{'reached_m':m},'wait':28} for r,m in [('north',15),('east',5),('south',10)]}
        self.assertEqual(recommendation('north',vals,cfg),'east')
        vals['south']['distance']['reached_m']=None
        self.assertIsNone(recommendation('north',vals,cfg))


if __name__=='__main__':unittest.main()
