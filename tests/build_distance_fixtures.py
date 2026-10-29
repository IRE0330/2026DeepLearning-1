"""Build synthetic view fixtures for the JS unit test. No model or real CCTV."""
import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard'))
from core import DEFAULTS
from distance_demo import video_key, result_series
from distance_stability import result_at
from distance_display import script as browser_script
from views import dashboard, detail_video, live_signage, signage


def build(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        source=Path(temp)/'SYNTHETIC-NOT-A-VIDEO.bin';source.write_bytes(b'test-only')
        cfg=copy.deepcopy(DEFAULTS);cfg['videos']={r:str(source) for r in cfg['videos']}
        annotation={'origin':[.5,.1],'source_key':video_key(str(source)),
                    'lines':{str(m):[[.1,y],[.9,y]] for m,y in [(5,.3),(10,.5),(15,.7)]}}
        cfg['distance_demo']={r:copy.deepcopy(annotation) for r in cfg['videos']}
        cfg['playback_key']='synthetic-distance-test';cfg['train_db_status']='error'
        cfg['sim_clock_epoch_ms']=0
        records={r:[] for r in cfg['videos']}
        for r in records:
            for t,y in enumerate([.2,.2,.4,.4,.6,.6,.8,.8],1):
                records[r].append({'interval_end_s':t,
                    'csv_row':{'전체대기인원_추정':1,'내부잔류인원_추정':1,'외부대기인원_추정':1},
                    'detail':{'state':{'source_time_s':t,'waiting_total':1,'expected_wait_s':28,
                    'queue_geometry':{'version':1,'points':[{'point':[.5,y],'confidence':.9}],
                                      'candidate_count':0,'occluded_count':0,'suppressed_count':0}}}})
            # Old module-only value must never become a distance fallback.
            for t in range(9,13):
                records[r].append({'interval_end_s':t,'csv_row':{'전체대기인원_추정':99,'외부대기인원_추정':99},
                                   'detail':{'state':{'source_time_s':t,'expected_wait_s':28}}})
        bodies={'dashboard':dashboard(records,{},cfg), 'detail':detail_video('north',records['north'],'',cfg),
                'signage':live_signage(records,'north',{},cfg), 'static':signage(records,'north',8,cfg)}
        for r in ['east','south']:bodies['detail-'+r]=detail_video(r,records[r],'',cfg)
        for r in ['east','south']:
            bodies['signage-'+r]=live_signage(records,r,{},cfg)
            bodies['static-'+r]=signage(records,r,8,cfg)
        bodies['static-unknown']=signage(records,'north',12,cfg)
        for name,body in bodies.items():(folder/(name+'.html')).write_text(body,encoding='utf-8')
        rows = records['north']
        stable = result_series(rows, cfg, 'north')
        queries = sorted(set([i/10 for i in range(131)] + [4.001, 11.001, 11.999]))
        case = {'rows': [{'t': r['interval_end_s'], 'distance': d} for r,d in zip(rows,stable)],
                'queries': [{'t': t, 'expected': result_at(rows,stable,t)} for t in queries]}
        (folder/'browser-case.json').write_text(json.dumps(case,ensure_ascii=False),encoding='utf-8')
        (folder/'browser-distance.js').write_text(browser_script(),encoding='utf-8')


if __name__=='__main__':build(sys.argv[1] if len(sys.argv)>1 else '.local-run/distance-ui-test')
