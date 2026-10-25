"""Persistent run storage and unchanged 0.3.2 record interpretation."""
from pathlib import Path
import json, sqlite3, time, os, uuid, subprocess, sys, math, unicodedata

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
ROOMS = {'north': '북쪽', 'east': '동쪽', 'south': '남쪽'}
TERMINAL = {'completed', 'failed', 'stopped', 'force_terminated', 'interrupted'}
COLS = ['촬영시작시각','촬영종료시각','화장실ID','화장실_영상ID','구간_입장인원','구간_퇴장인원','내부잔류인원_추정','현재대기인원_추정','측정상태','추정내부대기인원','전체대기인원_추정','현재이용가능칸수_추정','외부대기인원_추정']
DEFAULTS = {'videos': {r:'' for r in ROOMS}, 'configs':{r:'' for r in ROOMS},
 'model': str(ROOT.parent/'models'/'yolo11n.pt'), 'device':'cpu', 'end':0.0,
 'walk': {'north':{'north':0,'east':180,'south':240}, 'east':{'north':180,'east':0,'south':180},'south':{'north':240,'east':180,'south':0}},
 'warning':1,'crowded':6,'minimum_gain':30,'train_path':'','save_video':False,
 'capture_date':'2026-10-14','history_path':'','history_average':105.,
 'history_stalls':{'north':27,'east':23,'south':19}}

def db():
    DATA.mkdir(exist_ok=True)
    c=sqlite3.connect(DATA/'dashboard.sqlite',timeout=20)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, created REAL, status TEXT, pid INTEGER, heartbeat REAL, request TEXT, error TEXT, stop INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS jobs(run TEXT, room TEXT, status TEXT, payload TEXT, PRIMARY KEY(run,room));
    CREATE TABLE IF NOT EXISTS records(run TEXT, room TEXT, rid TEXT, t REAL, payload TEXT, PRIMARY KEY(run,rid));''')
    return c

def discover_videos(root=None):
    """Find named source clips without scanning environments or analysis outputs."""
    root = Path(root or ROOT)
    aliases = {'north': ('북쪽', 'north'), 'east': ('동쪽', 'east'), 'south': ('남쪽', 'south')}
    found = {r: [] for r in ROOMS}
    candidates = []
    # App folder and its media folders; also support cctv032/media or videos.
    roots = [(root, 3), (root.parent, 0), (root.parent/'media', 3), (root.parent/'videos', 3)]
    skip = {'data', 'outputs', 'runs', 'analysis', 'previews', '__pycache__', 'node_modules'}
    for base, max_depth in roots:
        if not base.is_dir(): continue
        for folder, dirs, files in os.walk(base):
            depth = len(Path(folder).relative_to(base).parts)
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip] if depth < max_depth else []
            for filename in files:
                p = Path(folder)/filename
                if p.suffix.lower() not in {'.mp4', '.mov', '.m4v'}: continue
                name = unicodedata.normalize('NFC', p.stem).lower()
                matches = [r for r, words in aliases.items() if any(w in name for w in words)]
                if len(matches) == 1 and p.stat().st_size > 0:
                    candidates.append((matches[0], p.resolve(), depth))
    for room, p, depth in candidates:
        found[room].append((depth, len(p.name), str(p)))
    return {r: sorted(set(items))[0][2] for r, items in found.items() if items}

def discover_model(selected='', root=None):
    """Resolve explicit weights, then search only the app's enclosing project."""
    root=Path(root or ROOT).expanduser().resolve()
    project=root.parent
    def usable(path):
        try:return path.is_file() and path.stat().st_size>0
        except OSError:return False
    if selected:
        chosen=Path(str(selected)).expanduser()
        choices=[chosen] if chosen.is_absolute() else [root/chosen,project/chosen]
        for path in choices:
            if usable(path):return str(path.resolve())
    preferred=[root/'models/yolo11n.pt',project/'models/yolo11n.pt',
               project/'busan_restroom_integrated/models/yolo11n.pt',
               root/'yolo11n.pt',project/'yolo11n.pt']
    for path in preferred:
        if usable(path):return str(path.resolve())
    skip={'venv','env','node_modules','data','outputs','runs','analysis','previews','__pycache__'}
    found=[]
    for folder,dirs,files in os.walk(project,followlinks=False):
        depth=len(Path(folder).relative_to(project).parts)
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and d not in skip and not (Path(folder)/d).is_symlink()) if depth<4 else []
        if 'yolo11n.pt' in files:
            path=Path(folder)/'yolo11n.pt'
            if usable(path):found.append((depth,str(path.resolve())))
    return min(found)[1] if found else None


def settings():
    base=json.loads(json.dumps(DEFAULTS))
    p=DATA/'settings.json'
    if p.exists(): base.update(json.loads(p.read_text()))
    # Existing valid manual selections take priority. Empty or moved paths auto-connect.
    automatic = discover_videos()
    for room in ROOMS:
        selected = base['videos'].get(room, '')
        if not selected or not Path(selected).expanduser().is_file():
            base['videos'][room] = automatic.get(room, '')
    base['model']=discover_model(base.get('model','')) or base.get('model','')
    if not base.get('history_path') or not Path(base['history_path']).expanduser().is_file():
        base['history_path'] = str(ROOT/'assets/restroom_usage.csv.gz')
    return base

def save_settings(value):
    DATA.mkdir(exist_ok=True)
    tmp=DATA/'settings.tmp'
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    tmp.replace(DATA/'settings.json')

def number(x):
    if x is None or x=='': return None
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError):return None

def values(record):
    if not record:return {'inside':None,'queue':None,'outside':None,'entry':None,'exit':None,'free':None}
    row=record.get('csv_row',{})
    if isinstance(row,list):row=dict(zip(COLS,row))
    return {'inside':number(row.get(COLS[6])),'queue':number(row.get(COLS[10])),
        'outside':number(row.get(COLS[12])),'free':number(row.get(COLS[11])),
        'entry':number(row.get(COLS[4])),'exit':number(row.get(COLS[5]))}

def label(v,cfg):
    status=v.get('distance',{}).get('status','측정 불가')
    return status,{'여유':'#008b6a','보통':'#c28a00','혼잡':'#d7413e','매우 혼잡':'#8e1b40'}.get(status,'#8393a5')

def wait_label(sec):
    if sec is None:return '미측정'
    return f'{math.ceil(sec)}초' if sec<60 else f'{math.ceil(sec/60)}분'

def latest_run():
    with db() as c:
        r=c.execute('SELECT * FROM runs ORDER BY created DESC LIMIT 1').fetchone()
        if not r:return None
        d=dict(r)
        if d['status'] not in TERMINAL and time.time()-d['heartbeat']>20:
            try:
                if not d['pid']:raise ProcessLookupError
                os.kill(d['pid'],0)
            except ProcessLookupError:
                c.execute("UPDATE runs SET status='interrupted',error='분석 프로세스가 종료됐습니다. 로그를 확인한 뒤 새 분석을 시작하세요.' WHERE id=?",(d['id'],))
                d['status']='interrupted';d['error']='분석 프로세스가 종료됐습니다.'
        return d

def run_data(run):
    if not run:return {r:[] for r in ROOMS},{}
    with db() as c:
        rows=c.execute('SELECT room,payload FROM records WHERE run=? ORDER BY t',(run['id'],)).fetchall()
        jobs=c.execute('SELECT room,payload FROM jobs WHERE run=?',(run['id'],)).fetchall()
    records={r:[] for r in ROOMS}
    for row in rows:records[row['room']].append(json.loads(row['payload']))
    return records,{j['room']:json.loads(j['payload']) for j in jobs}

def at(records,t):
    chosen=None
    for r in records:
        if float(r['interval_end_s'])<=t+0.0001:chosen=r
        else:break
    return chosen

def common_end(records):
    if not all(records[r] for r in ROOMS):return None
    return min(float(records[r][-1]['interval_end_s']) for r in ROOMS)

def validate(cfg):
    for r in ROOMS:
        p=Path(cfg['videos'][r]).expanduser()
        if not cfg['videos'][r] or not p.is_file():raise ValueError(f'{ROOMS[r]} 영상 파일을 지정하세요.')
        if cfg['configs'][r] and not Path(cfg['configs'][r]).expanduser().is_file():raise ValueError(f'{ROOMS[r]} 구역 JSON을 찾을 수 없습니다.')
    resolved=discover_model(cfg.get('model',''))
    if not resolved:raise ValueError('프로젝트 안에서 yolo11n.pt를 찾지 못했습니다. 프로젝트의 models 폴더에 모델 파일을 넣고 다시 실행해주세요.')
    cfg['model']=resolved
    from importlib.metadata import version
    if version('busan-cctv-analysis')!='0.3.2':raise ValueError('이 앱은 busan-cctv-analysis 0.3.2와 연동됩니다.')
    for pkg in ['ultralytics','torch','torchvision','opencv-python','av','lap','streamlit']:version(pkg)

def start_run(cfg):
    validate(cfg)
    from distance_demo import video_key
    cfg['distance_video_keys']={r:video_key(cfg['videos'][r]) for r in ROOMS}
    rid=uuid.uuid4().hex
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT status FROM runs ORDER BY created DESC LIMIT 1').fetchone()
        if row and row['status'] not in TERMINAL:raise ValueError('이미 분석 중입니다. 완료 또는 중지 후 시작하세요.')
        c.execute('INSERT INTO runs(id,created,status,pid,heartbeat,request,error) VALUES(?,?,?,?,?,?,?)',
          (rid,time.time(),'preparing',0,time.time(),json.dumps(cfg,ensure_ascii=False),''))
    folder=DATA/rid;folder.mkdir()
    try:
        with (folder/'worker.log').open('wb') as log:
            p=subprocess.Popen([sys.executable,str(ROOT/'worker.py'),rid],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        with db() as c:c.execute('UPDATE runs SET pid=? WHERE id=?',(p.pid,rid))
    except Exception as e:
        with db() as c:c.execute("UPDATE runs SET status='failed',error=? WHERE id=?",(str(e),rid))
        raise
    return rid

def request_stop(rid):
    with db() as c:c.execute('UPDATE runs SET stop=1 WHERE id=?',(rid,))

def recommendation(current, vals,cfg):
    # Fixed time bands are not exact durations: suggest a lower congestion band,
    # without claiming a shortest total time or adding walking seconds to a bound.
    bands={r:vals[r].get('distance',{}).get('reached_m') for r in ROOMS}
    if any(bands[r] is None for r in ROOMS):return None
    others=[r for r in ROOMS if bands[r]<bands[current]]
    return min(others,key=lambda r:(bands[r],cfg['walk'][current][r])) if others else None


def cctv_stamp(seconds, cfg):
    from datetime import datetime, timedelta
    day=cfg.get('capture_date','2026-10-14')
    return datetime.fromisoformat(day+'T14:00:00+09:00')+timedelta(seconds=float(seconds))


def demo_profile(cfg):
    return {'schema_version':1,'name':'demo_cctv_1400',
      'defaults':{'record_interval_s':1,'capture_start_time':cctv_stamp(0,cfg).isoformat(),
       'capture_time_kind':'virtual','measurement_status_tags':['demo_assumptions','synthetic_material','mean_use_user_assumption','all_stalls_operating_assumed']},
      'environments':{'north':{'initial_inside':29,'measurement_status_tags':['initial_inside_assumed_29']},
       'east':{'initial_inside':3,'measurement_status_tags':['initial_inside_assumed_3']},
       'south':{'initial_inside':3,'measurement_status_tags':['initial_inside_assumed_3']}}}
