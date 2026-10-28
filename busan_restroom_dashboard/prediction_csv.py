"""Validated minute-level uploaded forecasts; kept separate from CCTV observations."""
import io,json,html
from pathlib import Path
import pandas as pd
ROOM_IDS={'north':'TOILET_A','east':'TOILET_B','south':'TOILET_C'}
DISTANCES=['대기 없음','5m 미만','5m 이상 ~ 10m 미만','10m 이상 ~ 15m 미만','15m 이상']
WAITS=['0분','5분 미만','5분 이상','10분 이상','15분 이상']

def load_predictions(source):
    if isinstance(source,bytes):source=io.BytesIO(source)
    f=pd.read_csv(source,encoding='utf-8-sig',dtype=str).fillna('')
    needed=['날짜','시간','화장실ID','예상 대기거리 구간']
    if any(c not in f for c in needed):raise ValueError('필수 열: '+', '.join(needed))
    if f.empty:raise ValueError('예측 기록이 없습니다.')
    stamp=pd.to_datetime(f['날짜'].str.strip()+' '+f['시간'].str.strip(),errors='coerce')
    if stamp.isna().any():raise ValueError('날짜 또는 시간을 읽을 수 없는 행이 있습니다.')
    if ((stamp.dt.second!=0)|(stamp.dt.microsecond!=0)).any():raise ValueError('예측 시간은 1분 단위여야 합니다. 초는 00으로 맞춰 주세요.')
    f['화장실ID']=f['화장실ID'].str.strip()
    if not f['화장실ID'].isin(ROOM_IDS.values()).all():raise ValueError('화장실ID는 TOILET_A, TOILET_B, TOILET_C만 사용할 수 있습니다.')
    f['예상 대기거리 구간']=f['예상 대기거리 구간'].str.strip()
    if not f['예상 대기거리 구간'].isin(DISTANCES).all():raise ValueError('거리 구간이 올바르지 않습니다. AutoModelLab에서 내보낸 CSV를 사용해 주세요.')
    f['시각']=stamp.dt.strftime('%Y-%m-%d %H:%M')
    if f.duplicated(['시각','화장실ID']).any():raise ValueError('같은 시간·화장실의 예측값이 중복됩니다.')
    f['예상 대기시간 (거리 환산)']=f['예상 대기거리 구간'].map(dict(zip(DISTANCES,WAITS)))
    return f.sort_values(['시각','화장실ID']).reset_index(drop=True)

def payload(frame):
    out={}
    for _,r in frame.iterrows():out.setdefault(r['시각'],{})[r['화장실ID']]={'distance':r['예상 대기거리 구간'],'wait':r['예상 대기시간 (거리 환산)']}
    return out

def attach(cfg,path):
    out=dict(cfg);out['uploaded_predictions']={};out['prediction_error']=''
    if path:
        try:out['uploaded_predictions']=payload(load_predictions(path))
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
