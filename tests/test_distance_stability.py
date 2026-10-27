"""Video-time expiry and causal smoothing, independent of browser wall time."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard'))
from distance_demo import BANDS,unavailable
from distance_stability import stabilize,result_at,timeline_events


def raw(band):
    if band is None:return unavailable('일시적 관측 누락')
    meters,status,wait=next(b for b in BANDS if b[0]==band)
    return {'reached_m':meters,'status':status,'wait':wait,'tail':[.5,.5],'reason':'유효 관측'}


def timeline(items):
    records=[{'interval_end_s':t,'detail':{'state':{'source_time_s':source}}} for t,source,band in items]
    return records,stabilize(records,[raw(band) for t,source,band in items])


class Stability(unittest.TestCase):
    def test_graph_includes_expiry_between_saved_records(self):
        recs,out=timeline([(1,1,10),(2,2,None),(3,3,None),(4,4,None),(5,5,10)])
        events=timeline_events(recs,out)
        expired=[(t,r) for t,r in events if 4<t<5]
        self.assertTrue(expired)
        self.assertIsNone(expired[0][1]['reached_m'])
        self.assertLess(expired[0][0],4.001)

    def test_hold_exactly_three_seconds_then_expire(self):
        recs,out=timeline([(1,1,10),(2,2,None),(3,3,None),(4,4,None),(5,5,None)])
        self.assertEqual([x['reached_m'] for x in out],[10,10,10,10,None])
        for x in out[1:4]:
            self.assertTrue(x['held']);self.assertEqual(x['stability'],'최근 판정 유지')
            self.assertEqual(x['last_valid_time_s'],1)
        self.assertIsNone(result_at(recs,out,4.001)['reached_m'])
        self.assertIn('3초 초과',result_at(recs,out,4.001)['reason'])

    def test_expiry_uses_source_observation_not_sample_boundary(self):
        recs,out=timeline([(1,.5,10),(2,2,None),(3,3,None),(4,4,None)])
        self.assertEqual(result_at(recs,out,3.5)['reached_m'],10)
        self.assertIsNone(result_at(recs,out,3.5001)['reached_m'])

    def test_missing_rows_expire_without_new_record(self):
        recs,out=timeline([(1,1,10)])
        self.assertEqual(result_at(recs,out,4)['reached_m'],10)
        self.assertTrue(result_at(recs,out,3)['held'])
        self.assertIsNone(result_at(recs,out,4.0001)['reached_m'])

    def test_two_distinct_consecutive_observations_allow_decrease(self):
        recs,out=timeline([(1,1,10),(2,2,0),(3,3,0),(4,4,None)])
        self.assertEqual([x['reached_m'] for x in out],[10,10,0,0])
        self.assertTrue(out[1]['held']);self.assertFalse(out[2]['held'])
        self.assertEqual(out[2]['last_valid_time_s'],3)

    def test_boundary_alternation_is_not_accepted_as_change(self):
        recs,out=timeline([(1,1,10),(2,2,5),(3,3,10),(4,4,5),(5,5,10)])
        self.assertEqual([x['reached_m'] for x in out],[10]*5)

    def test_unknown_and_gap_break_consecutive_evidence(self):
        recs,out=timeline([(1,1,10),(2,2,5),(3,3,None),(4,4,5)])
        self.assertEqual(out[-1]['reached_m'],10)
        recs,out=timeline([(1,1,10),(2,2,5),(4,4,5)])
        self.assertEqual(out[-1]['reached_m'],10)

    def test_same_source_frame_cannot_count_twice(self):
        recs,out=timeline([(1,1,10),(2,1.5,5),(2.5,1.5,5)])
        self.assertEqual(out[-1]['reached_m'],10)
        self.assertEqual(out[-1]['last_valid_time_s'],1)

    def test_seeks_reset_pause_and_new_run_are_stateless(self):
        recs,out=timeline([(1,1,10),(2,2,None),(3,3,0),(4,4,0)])
        later=result_at(recs,out,4)
        self.assertEqual(later['reached_m'],0)
        self.assertEqual(result_at(recs,out,2)['reached_m'],10)
        self.assertIsNone(result_at(recs,out,0)['reached_m'])
        self.assertEqual(result_at(recs,out,2),result_at(recs,out,2))
        other_records,other=timeline([(1,1,None),(2,2,None)])
        self.assertIsNone(result_at(other_records,other,2)['reached_m'])

    def test_no_future_observation_and_no_input_mutation(self):
        items=[(1,1,None),(2,2,10),(3,3,5),(4,4,5)]
        records=[{'interval_end_s':t,'detail':{'state':{'source_time_s':source}}} for t,source,band in items]
        raws=[raw(band) for t,source,band in items];before=copy.deepcopy((records,raws))
        out=stabilize(records,raws)
        self.assertIsNone(result_at(records,out,1.999)['reached_m'])
        self.assertEqual(result_at(records,out,3.999)['reached_m'],10)
        self.assertEqual((records,raws),before)


if __name__=='__main__':unittest.main()
