"""Synthetic coordinates only: these tests do not validate CCTV detection accuracy."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard'))
from distance_demo import evaluate, validate_lines, DISCLAIMER
from cctv.config import template
from cctv.core import Counter, Observation
from cctv.intervals import IntervalSampler
from cctv.usage import USAGE_FIELDS


def setting():
    return {'source_key':'test-video', 'origin':[.5,.1],
            'lines':{str(m):[[.1,y],[.9,y]] for m,y in [(5,.3),(10,.5),(15,.7)]}}


def record(y=None):
    points = [] if y is None else [{'track_id':1,'point':[.5,y],'confidence':.9}]
    return {'interval_end_s':1., 'detail':{'state':{'source_time_s':1.,'waiting_total':len(points),
            'queue_geometry':{'version':1,'points':points,'candidate_count':0,'occluded_count':0,'suppressed_count':0}}}}


class DistanceBands(unittest.TestCase):
    def result(self, rec, annotation=None):
        return evaluate(rec, annotation or setting(), 'test-video')

    def test_fixed_bands_and_exact_boundaries(self):
        for y, status, wait, reached in [(.2,'여유','1분 미만',0),(.3,'보통','1분 이상',5),
                                        (.49,'보통','1분 이상',5),(.5,'혼잡','2분 이상',10),
                                        (.69,'혼잡','2분 이상',10),(.7,'매우 혼잡','3분 이상',15),
                                        (.95,'매우 혼잡','3분 이상',15)]:
            with self.subTest(y=y):
                result=self.result(record(y))
                self.assertEqual((result['status'],result['wait'],result['reached_m']),(status,wait,reached))
                self.assertEqual(result['label'],DISCLAIMER)

    def test_line_endpoint_direction_does_not_change_band(self):
        s=setting()
        for line in s['lines'].values():line.reverse()
        self.assertEqual(self.result(record(.6),s)['status'],'혼잡')

    def test_queue_direction_can_be_horizontal(self):
        s=setting();s['origin']=s['origin'][::-1]
        for m,line in s['lines'].items():s['lines'][m]=[p[::-1] for p in line]
        r=record(.6);r['detail']['state']['queue_geometry']['points'][0]['point']=[.6,.5]
        self.assertEqual(self.result(r,s)['status'],'혼잡')

    def test_last_confirmed_waiter_not_first_or_headcount(self):
        r=record(.2);state=r['detail']['state']
        state['queue_geometry']['points'].append({'track_id':2,'point':[.5,.8],'confidence':.9})
        state['waiting_total']=2
        result=self.result(r)
        self.assertEqual(result['reached_m'],15)
        self.assertEqual(result['tail'],[.5,.8])

    def test_measured_empty_queue(self):
        self.assertEqual(self.result(record())['status'],'여유')

    def test_candidate_occlusion_and_suppression_are_unknown(self):
        for key in ['candidate_count','occluded_count','suppressed_count']:
            r=record(.8);r['detail']['state']['queue_geometry'][key]=1
            self.assertEqual(self.result(r)['status'],'측정 불가')

    def test_missing_old_stale_and_inconsistent_data_are_unknown(self):
        cases=[None,{'interval_end_s':1,'detail':{'state':{'waiting_total':12}}}]
        for field,value in [('waiting_total',2),('source_time_s',-2),('source_time_s',float('nan'))]:
            r=record(.8);r['detail']['state'][field]=value;cases.append(r)
        r=record(.8);r['detail']['state']['queue_geometry']['points'][0]['confidence']=.2;cases.append(r)
        r=record(.8);r['detail']['state']['queue_geometry']['points'][0]['point']=[float('nan'),.8];cases.append(r)
        r=record(.8);r['detail']['state']['queue_geometry']['points'][0]['point']=[.99,.8];cases.append(r)
        for r in cases:self.assertEqual(self.result(r)['status'],'측정 불가')

    def test_draft_or_other_video_cannot_be_used(self):
        for signature in ['', 'different']:
            self.assertEqual(evaluate(record(.8),setting(),signature)['status'],'측정 불가')

    def test_bad_annotation_rejected(self):
        cases=[{}, {'origin':[.5,.1]}, setting(), setting(), setting(), setting()]
        cases[2]['lines']['10']=cases[2]['lines']['5']
        cases[3]['lines']['5'],cases[3]['lines']['15']=cases[3]['lines']['15'],cases[3]['lines']['5']
        cases[4]['origin']=[.5,.3]
        cases[5]['lines']['5']=[[.1,.3],[.1,.3]]
        for s in cases:self.assertTrue(validate_lines(s))

    def test_result_does_not_mutate_inputs(self):
        r,s=record(.8),setting();before=copy.deepcopy((r,s))
        self.result(r,s)
        self.assertEqual((r,s),before)


class SnapshotIntegration(unittest.TestCase):
    def test_confirmed_points_survive_interval_and_keep_csv_schema(self):
        c=template('north','synthetic.mp4')
        c.update(configured=True,reference_size=[1000,1000],initial_inside=0,
                 boundary=[[.5,.05],[.5,.95]],entry_direction=[[.3,.5],[.7,.5]],
                 outside_zone=[[0,0],[.49,0],[.49,1],[0,1]],inside_zone=[[.51,0],[1,0],[1,1],[.51,1]],
                 waiting_zone=[[0,0],[.49,0],[.49,1],[0,1]],transit_zone=[])
        counter=Counter(c,1000,1000);emitted=[]
        sampler=IntervalSampler(c,0,lambda row,detail:emitted.append((row,detail)))
        for i in range(151):
            snap,events,_=counter.update(i/10,i,[Observation(7,(200,400,300,600),.9)])
            sampler.push(snap,events)
        geometry=snap['queue_geometry']
        self.assertEqual(snap['waiting_total'],1)
        self.assertEqual(geometry['points'],[{'track_id':7,'point':[.25,.6],'confidence':.9}])
        row,detail=emitted[-1]
        self.assertEqual(list(row),USAGE_FIELDS)
        self.assertEqual(detail['state']['queue_geometry']['points'],geometry['points'])
        result=evaluate({'interval_end_s':detail['interval_end_s'],'detail':detail},setting(),'test-video')
        self.assertEqual(result['status'],'혼잡')
        missing,_,_=counter.update(15.1,151,[])
        self.assertEqual(missing['queue_geometry']['points'],[])
        self.assertGreater(missing['queue_geometry']['occluded_count'],0)


if __name__=='__main__':unittest.main()
