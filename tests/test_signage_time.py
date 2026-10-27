"""Signage total-time bounds, origin selection and unchanged waiting views."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard'))
from core import DEFAULTS
from distance_demo import BANDS, video_key
from signage_time import total_time
from views import signage, playback_rows


class SignageTime(unittest.TestCase):
    def test_three_minute_examples_preserve_each_bound(self):
        for meters,expected in [(0,'8분 미만'),(5,'8분 이상'),(10,'13분 이상'),(15,'18분 이상')]:
            with self.subTest(meters=meters):
                self.assertEqual(total_time({'reached_m':meters},180),expected)

    def test_seconds_and_zero_walk_are_not_rounded_to_wrong_bounds(self):
        self.assertEqual(total_time({'reached_m':0},181),'8분 1초 미만')
        self.assertEqual(total_time({'reached_m':10},59),'10분 59초 이상')
        for meters,_,expected in BANDS:
            self.assertEqual(total_time({'reached_m':meters},0),expected)

    def test_unknown_wait_and_invalid_walk_remain_unknown(self):
        for distance in (None,{}, {'reached_m':None}, {'reached_m':5,'status':'측정 불가'}):
            self.assertEqual(total_time(distance,180),'측정 불가')
        for walk in (None,-1,True,'180',float('nan'),float('inf')):
            self.assertEqual(total_time({'reached_m':5},walk),'측정 불가')

    def test_all_origins_static_cards_and_map_use_total_only(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'synthetic.bin';source.write_bytes(b'signage total fixture')
            cfg=copy.deepcopy(DEFAULTS);cfg['videos']={r:str(source) for r in cfg['videos']}
            setting={'source_key':video_key(source),'origin':[.5,.1],
                     'lines':{str(m):[[.1,y],[.9,y]] for m,y in [(5,.3),(10,.5),(15,.7)]}}
            cfg['distance_demo']={r:copy.deepcopy(setting) for r in cfg['videos']}
            records={}
            for room,y in [('north',.8),('east',.4),('south',.6)]:
                records[room]=[{'interval_end_s':t,'csv_row':{},'detail':{'state':{
                    'source_time_s':t,'waiting_total':1,'queue_geometry':{'version':1,
                    'points':[{'point':[.5,y],'confidence':.9}],'candidate_count':0,
                    'occluded_count':0,'suppressed_count':0}}}} for t in (1,2)]
            before=copy.deepcopy((cfg,records))
            expected={
                'north':{'north':'15분 이상','east':'8분 이상','south':'14분 이상'},
                'east':{'north':'18분 이상','east':'5분 이상','south':'13분 이상'},
                'south':{'north':'19분 이상','east':'8분 이상','south':'10분 이상'}}
            for current in cfg['videos']:
                body=signage(records,current,2,cfg)
                for room,text in expected[current].items():
                    self.assertIn(f'id="sign-wait-{room}">{text}</div>',body)
                    self.assertIn(f'id="map-wait-{room}">{text}</text>',body)
                self.assertNotIn('도보 안내:',body)
                self.assertNotIn('대기시간과 별도',body)
                self.assertNotIn('예상 대기시간:',body)
                self.assertIn('최종 예상 소요시간',body)
                self.assertIn('시연용 범위',body)
                self.assertIn('임의 거리 기준 시연값',body)
            self.assertEqual((cfg,records),before)
            # Main/detail data keeps waiting time, without adding a walk.
            for room,wait in [('north','15분 이상'),('east','5분 이상'),('south','10분 이상')]:
                self.assertEqual(playback_rows(records[room],cfg,room)[-1]['distance']['wait'],wait)


if __name__=='__main__':unittest.main()
