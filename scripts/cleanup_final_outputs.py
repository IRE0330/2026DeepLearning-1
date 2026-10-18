"""Delete only enumerated retired outputs after verified final assembly."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from finalize_handoff import ROOT,FINAL,AUDIT,load,dump,digest,relative


def plan():
 assert (FINAL/'manifest.json').exists()
 evidence=FINAL/'evidence/retired_output_metadata'
 mapping={}
 rows=[]
 for item in load(AUDIT/'output_inventory_before.json'):
  source=(ROOT/item['path']).resolve()
  assert source.parent==(ROOT/'outputs').resolve() and source.name!='final'
  if source.name.startswith('micc_'):
   rows.append(dict(path=item['path'],action='preserve',reason='Separate MICC RGB sequence validation; uncertain relevance, unique small evidence'))
   continue
  for f in source.rglob('*'):
   if not f.is_file():continue
   name=f.name.lower()
   # Keep unique install verification evidence whole (under 2 MiB), and small
   # measurement/config/result summaries from performance experiments.
   keep=source.name.startswith('package_handoff_') or (f.suffix.lower() in ['.json','.csv','.jsonl','.txt'] and
         any(k in name for k in ['summary','timing','latenc','experiment','verification','resource','measure','checks','config_used']))
   if not keep:continue
   dest=evidence/f.relative_to(ROOT/'outputs')
   dest.parent.mkdir(parents=True,exist_ok=True)
   shutil.copy2(f,dest)
   assert digest(f)==digest(dest)
   mapping[relative(f)]=relative(dest)
  rows.append(dict(path=item['path'],action='delete',bytes=item['bytes'],reason='Superseded/test output; final data and small unique measurement evidence verified'))
 # Obsolete build tree; runtime source and the one current wheel stay untouched.
 build=ROOT/'cctv-analysis/build'
 if build.exists():
  rows.append(dict(path=relative(build),action='delete',bytes=sum(f.stat().st_size for f in build.rglob('*') if f.is_file()),reason='Disposable build copy; wheel and runtime source retained'))
 dump(FINAL/'path_relocation.json',{'final_sources':{v:'outputs/final/'+k for k,v in __import__('finalize_handoff').SOURCES.items()},'preserved_measurement_files':mapping,'historical_docs':'Old experiment paths in earlier docs are provenance, not current commands.'})
 dump(AUDIT/'cleanup_plan.json',rows)
 print('Prepared explicit cleanup plan:',sum(r['action']=='delete' for r in rows),'targets;',sum(r['action']=='preserve' for r in rows),'exceptions')


def check_references():
 # Final artifact contents may retain provenance paths, but active output/CSV
 # references must exist. Do not mistake original video/config paths for outputs.
 missing=[]
 def walk(v,key=''):
  if isinstance(v,dict):
   for k,x in v.items():yield from walk(x,k)
  elif isinstance(v,list):
   for x in v:yield from walk(x,key)
  elif isinstance(v,str):yield key,v
 for room in ['north','south','east']:
  for name in ['summary.json','record_index.jsonl']:
   p=FINAL/room/name
   values=([load(p)] if p.suffix=='.json' else [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines()])
   for value in values:
    for key,v in walk(value):
     if key in ['source_run','source','reference','source_csv','usage_csv','path','shared_csv','usage_summary_csv'] and 'outputs' in v and ('final' not in Path(v).parts):
      if key=='source_run':continue
      # Relative provenance may be retained; operational CSV/video paths cannot.
      if v.endswith(('.csv','.mp4')):missing.append({'file':relative(p),'key':key,'value':v})
 assert not missing,missing[:3]


def execute():
 manifest=load(FINAL/'manifest.json')
 for room,data in manifest['rooms'].items():
  for rel,meta in data['files'].items():
   assert (ROOT/rel).is_file() and digest(ROOT/rel)==meta['sha256'],rel
  sample=ROOT/'cctv-analysis/examples/data'/f'{room}_2026-10-14_0000.csv'
  assert digest(sample)==digest(FINAL/room/'shared'/sample.name)
 check_references()
 deleted=[]
 planrows=load(AUDIT/'cleanup_plan.json')
 # Validate all fully resolved paths BEFORE any recursive deletion.
 targets=[]
 for row in planrows:
  if row['action']!='delete':continue
  target=(ROOT/row['path']).resolve()
  valid=(target.parent==(ROOT/'outputs').resolve() and target.name!='final') or target==(ROOT/'cctv-analysis/build').resolve()
  assert valid and target.is_dir() and not target.is_symlink(),str(target)
  targets.append((row,target))
 for row,target in targets:
  shutil.rmtree(target)
  assert not target.exists()
  deleted.append(row)
 protected=load(AUDIT/'protected_before.json')
 changed=[rel for rel,h in protected.items() if not (ROOT/rel).exists() or digest(ROOT/rel)!=h]
 assert not changed,changed
 for name,h in load(AUDIT/'originals_before.json').items():assert digest(ROOT/name)==h
 report={'deleted':deleted,'preserved_exceptions':[r for r in planrows if r['action']=='preserve'],
         'deleted_bytes':sum(r.get('bytes',0) for r in deleted),'protected_unchanged':len(protected),
         'original_videos_models_configs_truth_manual_reviews_unchanged':True,
         'source_code_and_current_wheel_not_deleted':True,'path_checks_before_recursive_delete':True}
 dump(FINAL/'cleanup_report.json',report)
 public={'deleted_roots':[{k:r[k] for k in ['path','reason']} for r in deleted],
         'preserved_exceptions':report['preserved_exceptions'],'deleted_bytes':report['deleted_bytes'],
         'protected_unchanged':len(protected),'local_details':'outputs/final/cleanup_report.json',
         'historical_measurements':'outputs/final/evidence/retired_output_metadata','all_final_files_verified_before_delete':True}
 dump(ROOT/'cctv-analysis/docs/cleanup_checks.json',public)
 print('Cleanup complete:',len(deleted),'targets;',round(report['deleted_bytes']/1024**2,1),'MiB removed')


if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8')
 p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','execute']);a=p.parse_args()
 {'plan':plan,'execute':execute}[a.action]()
