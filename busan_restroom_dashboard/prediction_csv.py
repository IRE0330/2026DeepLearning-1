"""Validated minute-level uploaded forecasts; kept separate from CCTV observations."""
import io,json,html
from pathlib import Path
import pandas as pd
ROOM_IDS={'north':'TOILET_A','east':'TOILET_B','south':'TOILET_C'}
DISTANCES=['대기 없음','5m 미만','5m 이상 ~ 10m 미만','10m 이상 ~ 15m 미만','15m 이상']
WAITS=['0분','5분 미만','5분 이상','10분 이상','15분 이상']

def load_predictions(source, room=None, filename=None):
    """Accept per-room CSV/Excel and normalize it to the platform contract."""
    if room is not None:
        room=ROOM_IDS.get(room,room)
        if room not in ROOM_IDS.values():raise ValueError('등록할 화장실을 선택하세요.')
    name=filename or getattr(source,'name',str(source) if isinstance(source,(str,Path)) else '')
    raw=source if isinstance(source,bytes) else source.read() if hasattr(source,'read') else Path(source).read_bytes()
    excel=Path(name).suffix.lower() in ('.xlsx','.xls') or raw.startswith(b'PK') or raw.startswith(bytes.fromhex('D0CF11E0'))
    if excel:
        try:f=pd.read_excel(io.BytesIO(raw),dtype=str).fillna('')
        except ImportError as e:raise ValueError('엑셀 읽기 패키지가 필요합니다. requirements-dashboard.txt를 설치하세요.') from e
    else:
        try:f=pd.read_csv(io.BytesIO(raw),encoding='utf-8-sig',dtype=str).fillna('')
        except UnicodeDecodeError:f=pd.read_csv(io.BytesIO(raw),encoding='cp949',dtype=str).fillna('')
    f.columns=[str(c).replace('\ufeff','').strip() for c in f.columns]
    aliases={'date':'날짜','time':'시간','restroom_id':'화장실ID','화장실 ID':'화장실ID',
             '예상대기거리구간':'예상 대기거리 구간','예상 대기거리':'예상 대기거리 구간'}
    f=f.rename(columns={k:v for k,v in aliases.items() if k in f and v not in f})
    if f.empty:raise ValueError('예측 기록이 없습니다.')
    if '날짜' not in f or '시간' not in f:raise ValueError('날짜, 시간 열이 필요합니다.')
    if '화장실ID' not in f:
        if room is None:raise ValueError('화장실별 업로드 칸에 파일을 올리면 화장실ID가 자동으로 추가됩니다.')
        f['화장실ID']=room
    else:
        f['화장실ID']=f['화장실ID'].str.strip().str.upper().replace({'A':'TOILET_A','B':'TOILET_B','C':'TOILET_C'})
        if room is not None:
            f.loc[f['화장실ID']=='','화장실ID']=room
            if not (f['화장실ID']==room).all():raise ValueError('파일의 화장실ID가 선택한 화장실과 다릅니다. 해당 화장실 칸에 올려주세요.')
    if not f['화장실ID'].isin(ROOM_IDS.values()).all():raise ValueError('화장실ID는 TOILET_A, TOILET_B, TOILET_C만 사용할 수 있습니다.')
    if '예상 대기거리 구간' not in f:
        wait_col=next((c for c in ['예상 대기시간 (거리 환산)','예상 대기시간'] if c in f),None)
        if wait_col is None:raise ValueError('예상 대기거리 구간 열이 필요합니다.')
        f['예상 대기거리 구간']=f[wait_col].str.strip().map(dict(zip(WAITS,DISTANCES)))
    f['예상 대기거리 구간']=f['예상 대기거리 구간'].str.strip()
    if not f['예상 대기거리 구간'].isin(DISTANCES).all():raise ValueError('거리 구간은 '+', '.join(DISTANCES)+' 중 하나여야 합니다.')
    dates=pd.to_datetime(f['날짜'].str.strip(),errors='coerce')
    times=f['시간'].str.strip()
    # Excel numeric fractions represent a time of day.
    numeric=pd.to_numeric(times,errors='coerce')
    fraction=numeric.ge(0)&numeric.lt(1)
    times=times.copy()
    times.loc[fraction]=numeric[fraction].map(lambda v:f'{int(round(v*86400))//3600:02d}:{int(round(v*86400))//60%60:02d}:{int(round(v*86400))%60:02d}')
    stamp=pd.to_datetime(dates.dt.strftime('%Y-%m-%d')+' '+times,errors='coerce')
    if stamp.isna().any():raise ValueError('날짜 또는 시간을 읽을 수 없는 행이 있습니다.')
    # Match the existing minute-level lookup without shifting to another minute.
    stamp=stamp.dt.floor('min')
    f['날짜']=stamp.dt.strftime('%Y-%m-%d');f['시간']=stamp.dt.strftime('%H:%M:%S')
    f['시각']=stamp.dt.strftime('%Y-%m-%d %H:%M')
    if f.duplicated(['시각','화장실ID']).any():raise ValueError('같은 분·화장실의 예측값이 중복됩니다. 중복 행을 정리해주세요.')
    f['예상 대기시간 (거리 환산)']=f['예상 대기거리 구간'].map(dict(zip(DISTANCES,WAITS)))
    columns=['날짜','시간','화장실ID','예상 대기거리 구간','예상 대기시간 (거리 환산)','시각']
    return f[columns].sort_values(['시각','화장실ID']).reset_index(drop=True)


def resolve_prediction_path(path):
    from core import DATA
    p=Path(path).expanduser()
    if not p.is_absolute():return DATA/p
    if p.is_file():return p
    # Recover a moved project using its own predictions directory only.
    candidate=DATA/'predictions'/p.name
    return candidate if candidate.is_file() else p


def save_predictions(frame, data_dir=None):
    """Save a portable canonical CSV atomically; no Mac absolute path in settings."""
    from core import DATA
    root=Path(data_dir) if data_dir is not None else DATA
    target=root/'predictions'/'applied.csv';target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix('.tmp');frame.to_csv(tmp,index=False,encoding='utf-8-sig');tmp.replace(target)
    return 'predictions/applied.csv'


def merge_predictions(current, replacements):
    """Replace each uploaded room, preserving the other rooms and source dates."""
    frames=[]
    if current is not None and not current.empty:
        ids={ROOM_IDS.get(room,room) for room in replacements}
        frames.append(current[~current['화장실ID'].isin(ids)])
    frames.extend(replacements.values())
    if not frames:return pd.DataFrame()
    merged=pd.concat(frames,ignore_index=True)
    return load_predictions(merged.to_csv(index=False).encode('utf-8-sig'))

def payload(frame):
    out={}
    for _,r in frame.iterrows():out.setdefault(r['시각'],{})[r['화장실ID']]={'distance':r['예상 대기거리 구간'],'wait':r['예상 대기시간 (거리 환산)']}
    return out

def attach(cfg,path):
    out=dict(cfg);out['uploaded_predictions']={};out['prediction_error']=''
    if path:
        try:out['uploaded_predictions']=payload(load_predictions(resolve_prediction_path(path)))
        except FileNotFoundError:out['prediction_error']='저장된 예측 파일을 찾지 못했습니다. 화장실별 파일을 다시 등록해주세요.'
        except (OSError,ValueError,UnicodeError) as e:out['prediction_error']=str(e)
    return out

def panel(cfg,rooms,seconds=0):
    from core import ROOMS,cctv_stamp
    key=cctv_stamp(seconds,cfg).strftime('%Y-%m-%d %H:%M')
    rows=cfg.get('uploaded_predictions',{}).get(key,{})
    cards=[]
    for room in rooms:
        row=rows.get(ROOM_IDS[room],{})
        cards.append('<div style="background:white;border:1px solid #dce7f1;border-radius:10px;padding:14px"><b>'+ROOMS[room]+' · CSV 예측</b><div id="forecast-wait-'+room+'" style="font-size:24px;margin-top:8px">'+html.escape(row.get('wait','예측 정보 없음'))+'</div><small id="forecast-distance-'+room+'">'+html.escape(row.get('distance','해당 날짜·시간의 예측 없음'))+'</small></div>')
    return '<section style="margin:14px 0"><h3>CSV 예측 · 예상 대기시간 (거리 환산)</h3><div id="forecast-stamp">'+key+'</div><div style="display:grid;grid-template-columns:repeat('+str(len(rooms))+',1fr);gap:10px;margin-top:8px">'+''.join(cards)+'</div><p style="font-size:11px;color:#65788a">업로드한 모델 예측 · 거리 구간별 환산값 · 실제 CCTV 측정값과 별도 표시</p></section>'

def script(cfg,rooms):
    data=json.dumps(cfg.get('uploaded_predictions',{}),ensure_ascii=False).replace('</','<\\/')
    day=json.dumps(cfg.get('capture_date','2026-10-14'))
    ids=json.dumps({r:ROOM_IDS[r] for r in rooms})
    return """<script>(function(){const data=DATA,day=DAY,ids=IDS;
window.paintUploadedForecast=function(seconds){
 const d=new Date(day+'T14:00:00Z');d.setUTCSeconds(d.getUTCSeconds()+Math.floor(seconds));
 const key=d.toISOString().slice(0,16).replace('T',' ');
 document.getElementById('forecast-stamp').textContent=key+' · 재생 시각 기준';
 for(const [room,id] of Object.entries(ids)){
  const row=(data[key]||{})[id];
  document.getElementById('forecast-wait-'+room).textContent=row?row.wait:'예측 정보 없음';
  document.getElementById('forecast-distance-'+room).textContent=row?row.distance:'해당 날짜·시간의 예측 없음';
 }
};})();</script>""".replace('DATA',data).replace('DAY',day).replace('IDS',ids)

def add_panel(body,cfg,rooms,seconds=0):
    block=panel(cfg,rooms,seconds)+script(cfg,rooms)
    if '<script>' in body:return body.replace('<script>',block+'<script>',1)
    return body+block
