"""State injection only. No claim of real-video overflow accuracy."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard'))
from distance_demo import evaluate, result_series, validate_lines
from distance_policy import active_meters, rank_value, total_wait_label, validate_boundary
from distance_stability import stabilize, result_at
from distance_display import overlay, script
from core import COLS, DEFAULTS
from cctv_presentation import recommendation


def annotation():
    return {'source_key':'fixture-video','origin':[.5,.1],
            'lines':{'5':[[.1,.3],[.9,.3]],'10':[[.1,.5],[.9,.5]],'15':[[.1,.7],[.9,.7]]},
            'overflow_boundary':[[.3,1],[.7,1]],'overflow_seconds':3.}


def record(t, kind='inside', source=None):
    points={'inside':[[.5,.4]],'overflow':[[.5,.65],[.5,.99]],
            'single':[[.5,.99]],'empty':[], 'passer':[]}.get(kind,[[.5,.4]])
    observed=[{'track_id':i+1,'point':p,'confidence':.95} for i,p in enumerate(points)]
    if kind=='inside' and observed:observed[0]['track_id']=2
    geometry={'version':2,'points':observed,'confirmed_roi_ids':[p['track_id'] for p in observed],
              'candidates':[],'candidate_count':0,'occluded_count':int(kind=='occluded'),'suppressed_count':0}
    if kind=='passer':
        geometry['candidates']=[{'track_id':99,'point':[.5,.99],'included':False,'reason':'outside_waiting_roi','in_waiting_roi':False}]
    if kind=='invalid':geometry={}
    csv=[0]*13;csv[6]=0 if kind=='empty' else 3;csv[10]=csv[12]=len(observed)
    return {'interval_end_s':float(t),'csv_row':dict(zip(COLS,csv)),
            'detail':{'state':{'source_time_s':float(t if source is None else source),
                               'waiting_total':len(observed),'queue_geometry':geometry}}}


def series(items, room='east', setting=None, seconds=3.):
    setting=setting or annotation()
    records=[record(t,kind) for t,kind in items]
    raw=[evaluate(r,setting,'fixture-video',room) for r in records]
    from core import values
    raw=[{**d,'display_values':values(r)} for d,r in zip(raw,records)]
    return records,stabilize(records,raw,retain_last=True,
                             overflow_seconds=seconds if room!='north' else None)


class OverflowPresentation(unittest.TestCase):
    def test_cctv_lower_bound_total_and_export_are_separate(self):
        from cctv_presentation import total_time
        self.assertEqual(total_time({'reached_m':10,'overflow':True},120),'17분 이상')
        self.assertEqual(total_time({'reached_m':None},120),'대기정보 확인 중')
        s=annotation()
        cfg={'videos':{'east':'fixture.mp4'},'distance_demo':{'east':s}}
        records=[record(1,'inside'),record(2,'invalid'),record(10,'invalid')]
        with patch('distance_demo.settings_for',return_value=(s,'fixture-video')):
            shown=result_series(records,cfg,'east',retain_last=True)
            exported=result_series(records,cfg,'east')
        self.assertTrue(shown[-1]['held'])
        self.assertEqual(shown[-1]['last_valid_time_s'],1)
        self.assertIsNone(exported[-1]['reached_m'])
        self.assertFalse(exported[-1].get('held',False))

    def test_room_policy_disables_15_without_mutating_coordinates(self):
        s=annotation();before=copy.deepcopy(s)
        for room in ['east','south']:
            d=evaluate(record(1,'overflow'),s,'fixture-video',room)
            self.assertEqual(d['reached_m'],10)
            self.assertNotIn('15',d['reached'])
            self.assertEqual(active_meters(room),(5,10))
            cfg={'videos':{room:'fixture.mp4'},'distance_demo':{room:s}}
            with patch('distance_demo.video_key',return_value='fixture-video'):
                self.assertNotIn('>15m</text>',overlay(cfg,room))
        self.assertEqual(s,before)
        self.assertEqual(evaluate(record(1,'overflow'),s,'fixture-video','north')['reached_m'],15)
        self.assertIsNone(validate_lines(s))

    def test_normal_inside_and_valid_zero(self):
        recs,out=series([(1,'inside'),(2,'empty'),(3,'empty')])
        self.assertEqual(out[0]['wait'],'5분 이상')
        self.assertEqual(out[-1]['reached_m'],0)
        self.assertEqual(out[-1]['display_values']['inside'],0)
        self.assertFalse(out[-1]['held'])

    def test_passer_and_single_boundary_contact_never_confirm(self):
        for kind in ['passer','single']:
            _,out=series([(t,kind) for t in range(1,9)])
            self.assertFalse(any(d.get('overflow') for d in out))

    def test_no_user_boundary_means_no_automatic_claim(self):
        s=annotation();s.pop('overflow_boundary')
        d=evaluate(record(1,'overflow'),s,'fixture-video','east')
        self.assertIsNone(d['overflow_evidence'])
        self.assertIn('자동 판정 불가',d['overflow_reason'])
        self.assertTrue(validate_boundary([[.3,.8],[.7,.8]]))

    def test_short_contact_then_sustained_overflow(self):
        _,out=series([(1,'overflow'),(2,'overflow'),(3,'inside'),(4,'overflow'),(5,'overflow'),(6,'overflow'),(7,'overflow')])
        self.assertFalse(any(d.get('overflow') for d in out[:-1]))
        self.assertTrue(out[-1]['overflow'])
        self.assertEqual(out[-1]['wait'],'15분 이상')
        self.assertEqual(out[-1]['wait_lower_bound_minutes'],15)
        self.assertEqual(out[-1]['reached_m'],10)

    def test_release_needs_continuous_visible_inside_tail(self):
        _,out=series([(t,'overflow' if t<=4 else 'inside') for t in range(1,9)])
        self.assertTrue(all(d['overflow'] for d in out[3:7]))
        self.assertFalse(out[7]['overflow'])
        self.assertEqual(out[6]['last_valid_time_s'],4)

    def test_occlusion_cannot_accumulate_confirmation_or_release(self):
        _,out=series([(1,'overflow'),(2,'overflow'),(3,'occluded'),(4,'overflow'),(5,'overflow'),(6,'overflow'),(7,'overflow'),
                      (8,'inside'),(9,'occluded'),(10,'inside'),(11,'inside'),(12,'inside')])
        self.assertFalse(out[5]['overflow']);self.assertTrue(out[6]['overflow'])
        self.assertTrue(out[-1]['overflow']);self.assertTrue(out[-1]['held'])
        self.assertEqual(out[-1]['last_valid_time_s'],7)

    def test_disappearance_empty_scene_never_clears_overflow(self):
        _,out=series([(t,'overflow' if t<=4 else 'empty') for t in range(1,12)])
        self.assertTrue(out[-1]['overflow']);self.assertTrue(out[-1]['held'])
        self.assertEqual(out[-1]['last_valid_time_s'],4)

    def test_missing_old_tail_with_other_visible_waiter_cannot_clear(self):
        recs=[record(t,'overflow') for t in range(1,5)]
        for t in range(5,10):
            rec=record(t,'inside')
            rec['detail']['state']['queue_geometry']['points'][0]['track_id']=99
            rec['detail']['state']['queue_geometry']['confirmed_roi_ids']=[99]
            recs.append(rec)
        raw=[evaluate(r,annotation(),'fixture-video','east') for r in recs]
        out=stabilize(recs,raw,retain_last=True,overflow_seconds=3)
        self.assertTrue(out[-1]['overflow']);self.assertTrue(out[-1]['held'])
        self.assertEqual(out[-1]['last_valid_time_s'],4)

    def test_unknown_holds_normal_or_overflow_indefinitely(self):
        recs,out=series([(1,'inside'),(2,'invalid'),(3,'invalid'),(10,'invalid')])
        d=result_at(recs,out,90)
        self.assertEqual(d['wait'],'5분 이상');self.assertEqual(d['last_valid_time_s'],1)
        self.assertTrue(d['held']);self.assertEqual(d['stability'],'갱신 지연')
        recs,out=series([(1,'overflow'),(2,'overflow'),(3,'overflow'),(4,'overflow'),(5,'invalid')])
        self.assertEqual(result_at(recs,out,100)['wait'],'15분 이상')
        self.assertEqual(result_at(recs,out,100)['last_valid_time_s'],4)

    def test_first_unknown_waits_and_recovery_needs_two_samples(self):
        _,out=series([(1,'invalid'),(2,'inside'),(3,'invalid'),(4,'inside'),(5,'inside')])
        self.assertEqual(out[0]['wait'],'대기정보 확인 중')
        self.assertTrue(out[3]['held']);self.assertEqual(out[3]['last_valid_time_s'],2)
        self.assertFalse(out[4]['held']);self.assertEqual(out[4]['last_valid_time_s'],5)

    def test_gaps_and_duplicate_sources_do_not_accumulate(self):
        recs,out=series([(1,'overflow'),(2,'overflow'),(4,'overflow'),(5,'overflow'),(6,'overflow')])
        self.assertFalse(out[-1]['overflow'])
        recs=[record(1,'overflow'),record(2,'overflow',source=1),record(3,'overflow'),record(4,'overflow'),record(5,'overflow')]
        raw=[evaluate(r,annotation(),'fixture-video','east') for r in recs]
        out=stabilize(recs,raw,retain_last=True,overflow_seconds=3)
        self.assertFalse(out[-1]['overflow'])

    def test_video_seek_new_run_other_file_and_normal_eof(self):
        recs,out=series([(1,'overflow'),(2,'overflow'),(3,'overflow'),(4,'overflow'),(5,'invalid')])
        self.assertTrue(result_at(recs,out,5)['overflow'])
        self.assertFalse(result_at(recs,out,2)['overflow'])
        self.assertIsNone(result_at(recs,out,0)['reached_m'])
        self.assertEqual(result_at(recs,out,6,ended=True)['stability'],'재생 종료')
        fresh,values=series([(1,'invalid')]);self.assertIsNone(values[0]['reached_m'])
        cfg={'videos':{'east':'another.mp4'},'distance_demo':{'east':annotation()}}
        with patch('distance_demo.video_key',return_value='other-video'):
            self.assertTrue(all(d['reached_m'] is None for d in result_series(recs,cfg,'east')))

    def test_bounds_walk_and_recommendations(self):
        _,out=series([(t,'overflow') for t in range(1,5)])
        d=out[-1]
        self.assertEqual(total_wait_label(d,120),'17분 이상')
        self.assertEqual(rank_value(d),float('inf'))
        vals={r:{'distance':{'reached_m':0}} for r in ['north','east','south']}
        vals['east']['distance']=d
        self.assertIsNone(recommendation('east',vals,DEFAULTS))

    def test_north_15m_and_existing_count_csv_remain_unchanged(self):
        rec=record(1,'overflow');before=copy.deepcopy(rec)
        d=evaluate(rec,annotation(),'fixture-video','north')
        self.assertEqual((d['reached_m'],d['wait']),(15,'15분 이상'))
        self.assertEqual(len(COLS),13);self.assertEqual(rec,before)

    def test_per_room_configurable_confirmation(self):
        _,out=series([(1,'overflow'),(2,'overflow'),(3,'overflow')],seconds=2)
        self.assertTrue(out[-1]['overflow'])

    def test_incomplete_state_does_not_replace_a_normal_display(self):
        recs=[record(1),record(2),record(3)]
        recs[1]['detail']=None;recs[2]['detail']['state']=None
        raw=[evaluate(r,annotation(),'fixture-video','east') for r in recs]
        out=stabilize(recs,raw,retain_last=True,overflow_seconds=3)
        self.assertTrue(out[-1]['held']);self.assertEqual(out[-1]['last_valid_time_s'],1)
        self.assertEqual(out[-1]['wait'],'5분 이상')

    def test_edge_labels_stay_visible_without_moving_saved_geometry(self):
        from html.parser import HTMLParser
        tags=[]
        class Tags(HTMLParser):
            def handle_starttag(self,tag,attrs):tags.append((tag,dict(attrs)))
        s=annotation();s['origin']=[.98,.1]
        s['lines']={str(m):[[.96,y],[1.,y]] for m,y in [(5,.3),(10,.5),(15,.7)]}
        s['overflow_boundary']=[[1.,.8],[1.,1.]]
        before=copy.deepcopy(s)
        cfg={'videos':{'east':'fixture.mp4'},'distance_demo':{'east':s}}
        with patch('distance_demo.video_key',return_value='fixture-video'):
            Tags().feed(overlay(cfg,'east'))
        for tag,attrs in tags:
            if tag=='text' and 'x' in attrs:self.assertLessEqual(float(attrs['x']),940)
        boundary=next(attrs for tag,attrs in tags if tag=='line' and 'data-overflow-boundary' in attrs)
        self.assertEqual(float(boundary['x1']),1000)
        origin=next(attrs for tag,attrs in tags if tag=='circle' and 'data-distance-origin' in attrs)
        self.assertEqual(float(origin['cx']),980)
        self.assertEqual(s,before)

    def test_display_fallback_does_not_rebind_old_observations(self):
        s=annotation()
        cfg={'videos':{'east':'old-missing.mov'},'display_videos':{'east':'fixture.mp4'},
             'distance_video_keys':{'east':'old-source'},'distance_demo':{'east':s}}
        before=copy.deepcopy(cfg)
        with patch('distance_demo.video_key',side_effect=lambda p:'fixture-video' if p=='fixture.mp4' else ''):
            self.assertIn('data-overflow-boundary',overlay(cfg,'east'))
            results=result_series([record(1,'overflow')],cfg,'east')
            self.assertIsNone(results[0]['reached_m'])
            self.assertFalse(results[0].get('overflow'))
        self.assertEqual(cfg,before)


def write_browser_fixture(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    recs,out=series([(1,'inside'),(2,'overflow'),(3,'overflow'),(4,'overflow'),(5,'overflow'),(6,'occluded'),
                     (7,'inside'),(8,'inside'),(9,'inside'),(10,'inside'),(11,'invalid')])
    queries=[{'t':t,'expected':result_at(recs,out,t)} for t in [0,1,2,4.9,5,6,9,10,12,100]]
    (folder/'cases.json').write_text(json.dumps({'rows':[{'t':r['interval_end_s'],'distance':d} for r,d in zip(recs,out)],'queries':queries},ensure_ascii=False),encoding='utf-8')
    (folder/'distance.js').write_text(script(),encoding='utf-8')


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--fixtures':write_browser_fixture(sys.argv[2])
    else:unittest.main()
