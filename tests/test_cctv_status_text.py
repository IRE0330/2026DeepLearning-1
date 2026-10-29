"""CCTV display wording must not change observations, bands or colors."""
import copy
import unittest
from test_cctv_overflow import record, series
from cctv_presentation import status_text, label
from distance_display import panel


class CctvStatusText(unittest.TestCase):
    def test_only_valid_total_zero_changes_wording(self):
        for queue,expected in [(0,'대기 인원 없음'),(1,'여유'),(3,'여유'),
                               (None,'여유'),(False,'여유'),('0','여유'),(float('nan'),'여유')]:
            d={'status':'여유','reached_m':0,'display_values':{'queue':queue,'outside':0,'inside':5}}
            before=copy.deepcopy(d)
            self.assertEqual(status_text(d),expected)
            self.assertEqual(label({'distance':d},{})[1],'#008b6a')
            self.assertEqual(d.keys(),before.keys())
            self.assertEqual(d['status'],before['status'])
        self.assertEqual(status_text({'status':'대기정보 확인 중','reached_m':None,
                                     'display_values':{'queue':0}}),'대기정보 확인 중')

    def test_normal_missing_and_held_observations(self):
        cases=[([(1,'empty')],'대기 인원 없음',False),
               ([(1,'inside')],'보통',False),
               ([(1,'invalid')],'대기정보 확인 중',False),
               ([(1,'empty'),(2,'invalid')],'대기 인원 없음',True),
               ([(1,'inside'),(2,'invalid')],'보통',True)]
        for items,expected,held in cases:
            records,results=series(items)
            d=results[-1];before=copy.deepcopy(d)
            self.assertEqual(status_text(d),expected)
            self.assertEqual(d['held'],held)
            self.assertIn(expected,panel(d))
            self.assertEqual(d,before)
            if held:
                self.assertEqual(d['last_valid_time_s'],1)
                self.assertEqual(d['stability'],'갱신 지연')

    def test_external_zero_with_internal_waiting_is_not_empty(self):
        from core import values, COLS
        r=record(1,'inside')
        r['csv_row'][COLS[9]]=3
        r['csv_row'][COLS[10]]=3
        r['csv_row'][COLS[12]]=0
        d={'status':'여유','reached_m':0,'display_values':values(r)}
        self.assertEqual(status_text(d),'여유')


if __name__=='__main__':unittest.main()
