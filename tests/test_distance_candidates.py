"""Synthetic candidate evidence. This does not establish real-world precision."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard'))
from cctv.config import template
from cctv.core import Counter,Observation
from cctv.distance_candidates import DistanceCandidates
from distance_demo import evaluate


def config():
    c=template('north','synthetic.mp4')
    c.update(waiting_zone=[[0,0],[.9,0],[.9,1],[0,1]],transit_zone=[],excluded_zones=[],
             boundary=[[.95,0],[.95,1]],entry_direction=[[.8,.5],[1,.5]],
             inside_zone=[[.96,0],[1,0],[1,1],[.96,1]],outside_zone=[[0,0],[.94,0],[.94,1],[0,1]],initial_inside=0)
    return c


def observation(tid=1,x=500,y=600):
    return Observation(tid,(x-25,y-100,x+25,y),.9)


class Evidence(unittest.TestCase):
    def test_stationary_candidate_included_at_two_seconds_not_confirmed(self):
        counter=Counter(config(),1000,1000)
        for i in range(21):
            snap,_,_=counter.update(i/10,i,[observation()])
            candidate=snap['queue_geometry']['candidates'][0]
            self.assertEqual(candidate['included'],i>=20)
            self.assertEqual(counter.tracks[1].wait,'candidate')
            self.assertEqual(snap['waiting_total'],0)
            self.assertEqual((snap['entries'],snap['exits'],snap['inside_estimate']),(0,0,0))

    def test_fast_passer_not_included(self):
        engine=DistanceCandidates(config(),1000,1000)
        for i in range(31):
            rows=engine.update(i/10,[observation(x=100+20*i)],{1:SimpleNamespace(wait='candidate')})
        self.assertFalse(rows[0]['included'])
        self.assertEqual(rows[0]['reason'],'moving_without_queue_evidence')

    def test_outside_transit_and_excluded_people_removed(self):
        for alteration in [{'waiting_zone':[[0,0],[.1,0],[.1,1],[0,1]]},
                           {'transit_zone':[[0,0],[1,0],[1,1],[0,1]]},
                           {'excluded_zones':[[[0,0],[1,0],[1,1],[0,1]]]}]:
            c=config();c.update(alteration);engine=DistanceCandidates(c,1000,1000)
            for i in range(31):rows=engine.update(i/10,[observation()],{1:SimpleNamespace(wait='candidate')})
            self.assertEqual(rows,[])

    def test_gap_and_leave_roi_reset_evidence(self):
        engine=DistanceCandidates(config(),1000,1000);tracks={1:SimpleNamespace(wait='candidate')}
        for i in range(21):rows=engine.update(i/10,[observation()],tracks)
        self.assertTrue(rows[0]['included'])
        engine.update(2.1,[],tracks)
        self.assertFalse(engine.update(2.2,[observation()],tracks)[0]['included'])
        self.assertFalse(engine.update(3.,[observation()],tracks)[0]['included'])
        engine.update(3.1,[observation(x=990)],tracks)
        self.assertFalse(engine.update(3.2,[observation()],tracks)[0]['included'])

    def test_comoving_requires_confirmed_independent_anchor(self):
        for anchor_state,expected in [('confirmed',True),('candidate',False)]:
            engine=DistanceCandidates(config(),1000,1000)
            tracks={1:SimpleNamespace(wait='candidate'),2:SimpleNamespace(wait=anchor_state)}
            for i in range(21):
                rows=engine.update(i/10,[observation(1,x=200+5*i),observation(2,x=260+5*i)],tracks)
            candidate=next(x for x in rows if x['track_id']==1)
            self.assertEqual(candidate['included'],expected)
            if expected:self.assertEqual(candidate['reason'],'co_moving_with_confirmed_queue_2s')

    def test_snapshot_counts_unchanged_with_distance_sidecar_disabled(self):
        enabled=Counter(config(),1000,1000);disabled=Counter(config(),1000,1000)
        disabled.distance_candidates=SimpleNamespace(update=lambda *args:[],confirmed_roi_ids=[])
        for i in range(60):
            obs=[observation()]
            a,events_a,_=enabled.update(i/10,i,obs);b,events_b,_=disabled.update(i/10,i,obs)
            a.pop('queue_geometry');b.pop('queue_geometry')
            self.assertEqual(a,b);self.assertEqual(events_a,events_b)


class CandidateBands(unittest.TestCase):
    def test_pending_candidate_does_not_block_confirmed_or_outside_roi_person(self):
        setting={'origin':[.5,.1],'source_key':'video','lines':{str(m):[[0,y],[1,y]] for m,y in [(5,.3),(10,.5),(15,.7)]}}
        pending={'track_id':2,'point':[.5,.8],'confidence':.9,'included':False,'in_waiting_roi':True,'dwell_s':1.,'reason':'insufficient_continuous_dwell'}
        state={'source_time_s':2.,'waiting_total':2,'queue_geometry':{'version':2,
            'points':[{'track_id':1,'point':[.5,.4],'confidence':.9},{'track_id':3,'point':[.5,.9],'confidence':.9}],
            'confirmed_roi_ids':[1],'candidates':[pending],'candidate_count':1,'occluded_count':0,'suppressed_count':0}}
        r=evaluate({'interval_end_s':2.,'detail':{'state':state}},setting,'video')
        self.assertEqual(r['status'],'보통')
        self.assertEqual(r['confirmed_count'],1)
        self.assertEqual(r['included_candidate_count'],0)
        self.assertEqual(r['tail_track_id'],1)

    def test_perspective_does_not_require_point_within_remote_line_width(self):
        setting={'source_key':'video','origin':[.22,.37],'lines':{
            '5':[[.38,.52],[.43,.44]],'10':[[.57,.65],[.65,.55]],'15':[[.86,.88],[.90,.72]]}}
        candidate={'track_id':2,'point':[.44,.515],'confidence':.9,'included':True,'in_waiting_roi':True,'dwell_s':2.,'reason':'slow_roi_dwell_2s'}
        state={'source_time_s':2.,'waiting_total':0,'queue_geometry':{'version':2,'points':[],
            'confirmed_roi_ids':[],'candidates':[candidate],'candidate_count':1,'occluded_count':0,'suppressed_count':0}}
        self.assertEqual(evaluate({'interval_end_s':2.,'detail':{'state':state}},setting,'video')['status'],'보통')

    def test_candidate_and_confirmed_positions_combined_at_boundaries(self):
        setting={'origin':[.5,.1],'source_key':'video','lines':{str(m):[[0,y],[1,y]] for m,y in [(5,.3),(10,.5),(15,.7)]}}
        for y,status in [(.2,'여유'),(.3,'보통'),(.5,'혼잡'),(.7,'매우 혼잡')]:
            candidate={'track_id':2,'point':[.5,y],'confidence':.9,'included':True,'in_waiting_roi':True,'dwell_s':2.,'reason':'slow_roi_dwell_2s'}
            state={'source_time_s':2.,'waiting_total':1,'queue_geometry':{'version':2,'points':[{'track_id':1,'point':[.5,.15],'confidence':.9}],
                'confirmed_roi_ids':[1],'candidates':[candidate],'candidate_count':1,'occluded_count':0,'suppressed_count':0}}
            r=evaluate({'interval_end_s':2.,'detail':{'state':state}},setting,'video')
            self.assertEqual(r['status'],status);self.assertEqual(r['included_candidate_count'],1)
            self.assertEqual(r['tail_track_id'],2)
            self.assertEqual(r['tail_kind'],'조건부 후보자')
            candidate['dwell_s']=1.9
            self.assertEqual(evaluate({'interval_end_s':2.,'detail':{'state':state}},setting,'video')['status'],'측정 불가')


if __name__=='__main__':unittest.main()
