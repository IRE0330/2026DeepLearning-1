"""Assemble and verify final saved results. Never run detection or change counts."""
import argparse
import collections
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cctv.usage import USAGE_FIELDS

SOURCES={
 'north':'outputs/paced_single_20261017_221517_1fc29ead/north/north_20261017_221518_36abe769',
 'south':'outputs/paced_single_20261017_223347_7040a3cd/south/south_20261017_223347_f2799172',
 'east':'outputs/paced_single_20261017_224801_b1147deb/east/east_20261017_224802_d4f81f69'}
NORTH_VIDEO='outputs/north_latency_ab_20261017_211718_82b9d4ed/A_video/north_20261017_211719_783c2efb'
FINAL=ROOT/'outputs/final'
AUDIT=ROOT/'inspections/final_handoff_20261018'


def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def csvread(p):
 assert p.read_bytes().startswith(b'\xef\xbb\xbf')
 with p.open(encoding='utf-8-sig',newline='') as f:
  r=csv.DictReader(f);return r.fieldnames,list(r)
def relative(p):return p.relative_to(ROOT).as_posix()


def inventory():
 AUDIT.mkdir(parents=True,exist_ok=True)
 items=[]
 for folder in sorted((ROOT/'outputs').iterdir()):
  if folder.name=='final' or not folder.is_dir():continue
  files=[p for p in folder.rglob('*') if p.is_file()]
  items.append({'path':relative(folder),'bytes':sum(p.stat().st_size for p in files),
                'files':[dict(path=relative(p),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(files)]})
 dump(AUDIT/'output_inventory_before.json',items)
 dump(AUDIT/'protected_before.json',{relative(p):digest(p) for base in ['configs','ground_truth','models','reviews']
                                    for p in (ROOT/base).rglob('*') if p.is_file()})
 dump(AUDIT/'originals_before.json',{p.name:digest(p) for p in ROOT.iterdir() if p.suffix.lower() in ['.mov','.mp4']})


def prepare():
 if FINAL.exists():raise FileExistsError('Final folder already exists; refusing overwrite')
 inventory()
 files=['config_used.json','summary.json','events.csv','diagnostics.jsonl','timeseries.csv','final_state.json',
        'final_usage_detail.json','interval_details.jsonl','remainder.json','csv_latency.csv','timing_summary.json',
        'timing_events.jsonl','record_index.jsonl','delivery_summary.json','record_latencies.csv',
        'input_timing.csv','input_simulation_summary.json']
 provenance={}
 for room,rel in SOURCES.items():
  source=ROOT/rel;target=FINAL/room;target.mkdir(parents=True)
  c,s=load(source/'config_used.json'),load(source/'summary.json')
  assert c['initial_inside']==({'north':29,'south':3,'east':3}[room])
  assert c['available_stalls']=={'north':27,'south':19,'east':23}[room]
  assert c['average_stall_use_s']==105
  assert c['capture_start_time']=='2026-10-14T00:00:00+09:00'
  assert s['processed_frames']==s['input_video']['frame_count'] and s['actual_start_s']==0
  assert s['actual_last_frame_s']==s['input_video']['last_frame_time_s']
  assert s['periodic_interval_s']==1 and s['csv_split_interval_s']==3600
  assert digest(ROOT/c['video'])==s['source_video_sha256']==c['video_sha256']
  preset=load(ROOT/'configs'/f'{room}.json')
  assert all(c[k]==preset[k] for k in ['boundary','entry_direction','outside_zone','inside_zone','excluded_zones','rules'])
  provenance[room]={}
  for name in files:
   p=source/name
   if p.exists():
    shutil.copy2(p,target/name)
    provenance[room][name]={'source':relative(p),'source_sha256':digest(p),'operation':'byte_copy'}
  shared=next((source/'shared').glob(f'{room}_2026-10-14_0000.csv'))
  assert shared.read_bytes()==(source/'usage_summary.csv').read_bytes()
  (target/'shared').mkdir()
  shutil.copy2(shared,target/'shared'/shared.name)
  provenance[room]['shared/'+shared.name]={'source':relative(shared),'source_sha256':digest(shared),'operation':'byte_copy; duplicate usage_summary.csv omitted'}
  if room=='north':
   prior=ROOT/NORTH_VIDEO
   assert all((prior/f).read_bytes()==(source/f).read_bytes() for f in ['events.csv','diagnostics.jsonl','timeseries.csv','interval_details.jsonl','final_state.json','usage_summary.csv'])
   shutil.copy2(prior/'annotated.mp4',target/'annotated.mp4')
   provenance[room]['annotated.mp4']={'source':relative(prior/'annotated.mp4'),'source_sha256':digest(prior/'annotated.mp4'),'operation':'byte_copy; latest full-run data match'}
  else:
   provenance[room]['annotated.mp4']={'source':rel+'/diagnostics.jsonl','source_sha256':digest(source/'diagnostics.jsonl'),'operation':'render original frames with latest saved observations; no detection/tracking rerun'}
 dump(AUDIT/'provenance.json',provenance)
 # Reuse the reviewed compact panel and make preview-before-render explicit.
 preview()
 print('Final data copied; south/east previews ready')


def replay_saved(room, preview_only):
 # config_used was saved with repository-relative material paths; it is not an
 # external user config rooted at the result directory. Resolve only those paths.
 from cctv import rerender
 from unittest.mock import patch
 original=rerender.load
 def rooted(path):
  if Path(path).name=='config_used.json':
   c=load(Path(path))
   for k in ['video','model','output_dir']:
    if c.get(k) and not Path(c[k]).is_absolute():c[k]=str(ROOT/c[k])
   return c
  return original(path)
 with patch.object(rerender,'load',side_effect=rooted):
  return rerender.replay(ROOT/SOURCES[room],FINAL,preview_only)


def preview():
 dump(AUDIT/'preview_manifest.json',[replay_saved(room,True) for room in ['south','east']])


def render():
 assert (AUDIT/'preview_manifest.json').exists()
 for room in ['south','east']:replay_saved(room,False)


def rewrite_value(v, room):
 source=(ROOT/SOURCES[room]).resolve()
 target=(FINAL/room).resolve()
 shared=target/'shared'/f'{room}_2026-10-14_0000.csv'
 if isinstance(v,dict):return {k:rewrite_value(x,room) for k,x in v.items()}
 if isinstance(v,list):return [rewrite_value(x,room) for x in v]
 if isinstance(v,str):
  v=v.replace(str(source),str(target)).replace(SOURCES[room],relative(target))
  if v.endswith('usage_summary.csv') and ('outputs' in v):v=str(shared)
 return v


def verify():
 from cctv.media import verify_output,frame_at,image_write
 from cctv.core import Counter,Observation
 audit={}
 provenance=load(AUDIT/'provenance.json')
 for room,rel in SOURCES.items():
  p=FINAL/room;c,s=load(p/'config_used.json'),load(p/'summary.json');v=s['input_video']
  fields,rows=csvread(p/'shared'/f'{room}_2026-10-14_0000.csv')
  assert fields==USAGE_FIELDS and len(fields)==13 and len(rows)==int(v['duration_s'])
  assert all(r['화장실ID']==room and r['화장실_영상ID']==c['video_id'] for r in rows)
  assert all('demo_assumptions' in r['측정상태'] for r in rows)
  assert len(list(p.rglob('*_2026-10-14*.csv')))==1 and not (p/'usage_summary.csv').exists()
  details=[json.loads(l) for l in (p/'interval_details.jsonl').read_text(encoding='utf-8').splitlines()]
  events=csvread(p/'events.csv')[1]
  assert len(rows)==len(details)==s['regular_csv_rows']
  base=datetime.fromisoformat(c['capture_start_time'])
  for i,(r,d) in enumerate(zip(rows,details)):
   assert d['interval_start_s']==i and d['interval_end_s']==i+1
   assert datetime.fromisoformat(r['촬영시작시각'])==base+timedelta(seconds=i)
   assert datetime.fromisoformat(r['촬영종료시각'])==base+timedelta(seconds=i+1)
   selected=[e for e in events if (float(e['video_time_s'])>=i if i==0 else float(e['video_time_s'])>i) and float(e['video_time_s'])<=i+1]
   assert int(r['구간_입장인원'])==sum(e['direction']=='entry' for e in selected)
   assert int(r['구간_퇴장인원'])==sum(e['direction']=='exit' for e in selected)
   state=d['state']
   assert int(r['내부잔류인원_추정'])==c['initial_inside']+state['entries']-state['exits']
   for k,key in [('외부대기인원_추정','waiting_total'),('추정내부대기인원','internal_waiting_estimate'),('전체대기인원_추정','total_queue_estimate'),('현재이용가능칸수_추정','available_stalls_estimate')]:
    assert int(r[k])==state[key]
  remainder=load(p/'remainder.json');final=load(p/'final_state.json')
  assert final==s['final_state']
  assert sum(int(r['구간_입장인원']) for r in rows)+remainder['entries']==final['entries']
  assert sum(int(r['구간_퇴장인원']) for r in rows)+remainder['exits']==final['exits']
  # Replay ALL saved frames and verify every periodic checkpoint, then verify video decode.
  groups=collections.defaultdict(list)
  for line in (p/'diagnostics.jsonl').open(encoding='utf-8'):
   r=json.loads(line);groups[r['frame_index']].append(r)
  counter=Counter(c,v['width'],v['height'])
  checkpoints={d['state']['frame_index']:d['state'] for d in details}
  for i,logs in sorted(groups.items()):
   obs=[Observation(r['track_id'],tuple(r['box']),r['confidence']) for r in logs if r['kind'] in ['observation','excluded_observation']]
   state,_,_=counter.update(i/v['fps'],i,obs)
   if i in checkpoints:assert state==checkpoints[i]
  assert state==final and len(counter.events)==len(events)
  video_check=verify_output(p/'annotated.mp4',v['width'],v['height'],v['fps'],v['frame_count'])
  for t in [0,v['duration_s']/2,v['last_frame_time_s']]:
   frame,actual=frame_at(p/'annotated.mp4',t)
   image_write(AUDIT/f'{room}_{actual:.3f}.jpg',frame)
  # Final references point at the one canonical CSV; original bytes remain in hashes/provenance.
  for name in ['summary.json','render_summary.json','preview_summary.json','delivery_summary.json','timing_summary.json']:
   if (p/name).exists():dump(p/name,rewrite_value(load(p/name),room))
  for name in ['record_index.jsonl']:
   if (p/name).exists():
    values=[rewrite_value(json.loads(l),room) for l in (p/name).read_text(encoding='utf-8').splitlines()]
    (p/name).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in values),encoding='utf-8')
  s=load(p/'summary.json');s['output_video']=rewrite_value(video_check,room);s['save_video']=True
  s['final_assembly']={'source_run':rel,'path_references_relocated':True,'shared_csv_only':True,'video_rerendered':room!='north','counts_modified':False}
  dump(p/'summary.json',s)
  sample=ROOT/'cctv-analysis/examples/data'/f'{room}_2026-10-14_0000.csv'
  sample.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p/'shared'/sample.name,sample)
  assert sample.read_bytes()==(p/'shared'/sample.name).read_bytes()
  audit[room]={'video_filename':Path(c['video']).name,'video_id':c['video_id'],'video_sha256':c['video_sha256'],
   'frames':v['frame_count'],'duration_s':v['duration_s'],'last_frame_s':v['last_frame_time_s'],
   'initial_inside':c['initial_inside'],'available_stalls':c['available_stalls'],'average_stall_use_s':105,
   'rows':len(rows),'csv_start':rows[0]['촬영시작시각'],'csv_end':rows[-1]['촬영종료시각'],
   'entries':final['entries'],'exits':final['exits'],'final_inside':final['inside_estimate'],
   'video_all_frames_decoded':video_check['all_frames_decoded'],'checkpoint_replay_matches':True,
   'video_rerendered':room!='north','inference_rerun':False,'recording_interval_s':1,'csv_split_s':3600,
   'files':{relative(f):{'sha256':digest(f),'bytes':f.stat().st_size,'provenance':provenance[room].get(f.relative_to(p).as_posix(),{'operation':'generated verification or reference relocation'})} for f in sorted(p.rglob('*')) if f.is_file()}}
 dump(FINAL/'manifest.json',{'version':'final-handoff-20261018','rooms':audit,'sources':SOURCES,'historical_output_roots':load(AUDIT/'output_inventory_before.json')})
 # Keep small public manifest, never publish local absolute paths or full output inventory.
 public={k:{a:b for a,b in v.items() if a!='files'} for k,v in audit.items()}
 dump(ROOT/'cctv-analysis/docs/final_output_checks.json',{'kind':'export_and_replay_consistency_not_human_accuracy','rooms':public,'automatic_counts_modified':False})
 print(json.dumps(public,ensure_ascii=False))


def wheel_check():
 wheel=next((ROOT/'cctv-analysis/dist').glob('*.whl'))
 with zipfile.ZipFile(wheel) as z:
  files=[p for p in (ROOT/'cctv-analysis/src/cctv').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
  for p in files:
   key=p.relative_to(ROOT/'cctv-analysis/src').as_posix()
   assert z.read(key)==p.read_bytes(),key
 dump(AUDIT/'wheel_source_check.json',{'path':relative(wheel),'sha256':digest(wheel),'runtime_source_assets_all_equal':True,'files':len(files),'rebuild_required':False})


if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8')
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','preview','render','verify','wheel'])
 args=parser.parse_args()
 {'prepare':prepare,'preview':preview,'render':render,'verify':verify,'wheel':wheel_check}[args.action]()
