"""Add requested export metadata while preserving user zones and truth rows."""
from pathlib import Path
import csv
import hashlib
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cctv.config import load,save,validate
from cctv.media import unique_dir,write_json
from cctv.usage import WAITING_POLICY,bind_video,video_digest

out=unique_dir('inspections','usage_metadata_setup')
report={}
zone_fields=('configured','reference_size','boundary','entry_direction','outside_zone','inside_zone',
             'waiting_zone','transit_zone','excluded_zones','rules','initial_inside')
for rid in ('north','south','east'):
    path=Path('configs')/(rid+'.json')
    original=load(path)
    (out/(rid+'_before.json')).write_bytes(path.read_bytes())
    c=load(path)
    c.setdefault('capture_start_time',None)
    c.setdefault('capture_time_kind',None)
    c.setdefault('available_stalls',27 if rid=='north' else None)
    c.setdefault('average_stall_use_s',105.0)
    if c.get('video_sha256') is not None and c['video_sha256']!=video_digest(c):
        raise ValueError('영상 교체를 metadata --bind-video로 먼저 등록해야 합니다: '+rid)
    bind_video(c)
    validate(c,require_zones=False)
    assert all(c[k]==original[k] for k in zone_fields)
    save(c,path)
    preview=path.with_suffix('.preview.jpg')
    report[rid]={'video_id':c['video_id'],'source_video_sha256':c['video_sha256'],
                 'user_zones_rules_initial_preserved':True,
                 'preview_sha256':hashlib.sha256(preview.read_bytes()).hexdigest() if preview.is_file() else None}
    truth=Path('ground_truth')/rid
    if not any(list(csv.DictReader(p.open(encoding='utf-8-sig'))) for p in truth.glob('*.csv')):
        meta=load(truth/'metadata.json')
        (out/(rid+'_truth_metadata_before.json')).write_bytes((truth/'metadata.json').read_bytes())
        meta['waiting_count_policy']=WAITING_POLICY
        write_json(truth/'metadata.json',meta)
        report[rid]['empty_truth_template_policy_updated']=True
    else:
        report[rid]['nonempty_truth_preserved_policy_not_assumed']=True
write_json(out/'setup_report.json',report)
print(out)
print(report)
