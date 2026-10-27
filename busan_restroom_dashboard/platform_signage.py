from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import base64, html, math
import pandas as pd
import streamlit as st

ROOMS=[('TOILET_A','북쪽',1,2,'오른쪽'),('TOILET_B','동쪽',2,1,'왼쪽'),('TOILET_C','남쪽',3,4,'왼쪽')]

@st.fragment(run_every='1s')
def render_platform():
    from simulation_clock import now as simulation_now
    now=simulation_now()
    current=pd.Timestamp(now.replace(tzinfo=None,second=0,microsecond=0))
    result=st.session_state.get('forecast_result')
    values={}; reason='혼잡도 예측모델에서 대기시간(분)을 예측해 주세요.'
    if result:
        future,_,_,_,bundle=result
        target=str(bundle.get('target',''))
        if target!='대기거리구간_예측단계' or bundle.get('group')!='화장실ID':
            reason='예측 대상을 대기거리구간_예측단계로, 구분 항목을 화장실ID로 선택해 주세요.'
        else:
            frame=future.copy();frame['예측시각']=pd.to_datetime(frame['예측시각'],errors='coerce')
            if frame['예측시각'].dt.tz is not None: frame['예측시각']=frame['예측시각'].dt.tz_convert('Asia/Seoul').dt.tz_localize(None)
            for key,name,num,walk,direction in ROOMS:
                rows=frame[(frame['구분'].astype(str)==key)&(frame['예측시각']==current+pd.Timedelta(minutes=walk))]
                if len(rows)==1:
                    value=pd.to_numeric(rows['예측값'],errors='coerce').iloc[0]
                    if pd.notna(value) and math.isfinite(float(value)):values[key]=max(0,min(4,math.floor(float(value)+0.5)))
            reason='현재 시각과 각 도보시간에 해당하는 예측값이 없습니다. 해당 시점이 포함되도록 예측 기간을 다시 설정해 주세요.'
    if len(values)!=3:st.info(reason)
    available=[r for r in ROOMS if r[0] in values]
    lower=[0,0,5,10,15]
    recommendation=min(available,key=lambda r:(r[3]+lower[values[r[0]]],r[3],r[2])) if len(available)==3 else None
    if recommendation is None:
        st.caption('세 화장실의 도착 시 예상 대기시간이 준비되면 가장 빠른 경로를 자동으로 안내합니다.')
        return
    selected=recommendation
    def fmt(x):return f'{x:.1f}'.rstrip('0').rstrip('.')+'분'
    def wait(tier):return ['대기 없음','5분 미만','5분 이상','10분 이상','15분 이상'][tier]
    def total(walk,tier):
        if tier==0:return f'{walk}분'
        if tier==1:return f'{walk}분 이상 ~ {walk+5}분 미만'
        return f'{walk+lower[tier]}분 이상'
    def card(r):
        key,name,num,walk,direction=r
        if key not in values:return f'<div class="alt"><b>{num:02d} {name} 화장실</b><span>예측 정보 없음</span></div>'
        w=values[key];return f'<div class="alt"><b>{num:02d} {name} 화장실</b><span>총 {total(walk,w)}<small>도보 {walk}분 + 예상 대기 {wait(w)}</small></span></div>'
    key,name,num,walk,direction=selected
    w=values.get(key); total_text='예측 정보 없음' if w is None else total(walk,w)
    detail=f'도보 {walk}분 + 도착 시 예상 대기 '+('정보 없음' if w is None else wait(w))
    image_path=Path(__file__).parent/'assets'/f'platform_route_{num}.png'
    img=base64.b64encode(image_path.read_bytes()).decode()
    other=''.join(card(r) for r in ROOMS if r!=selected)
    markup=f'''<style>.platform{{font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;background:#eaf3f8;border-radius:12px;padding:28px;max-width:700px;margin:auto;color:#101d2a}}.platform header{{display:flex;justify-content:space-between;align-items:end}}.platform h1{{font-size:38px!important;margin:0}}.platform small{{display:block;font-size:12px;color:#718797}}.clock{{font-size:32px;font-weight:bold}}.hero{{background:#1766c9;color:white;border-radius:22px;padding:26px;margin:18px 0;font-size:42px;font-weight:800;line-height:1.1;display:flex;justify-content:space-between}}.hero small{{color:white;margin-bottom:10px}}.panel{{background:white;border-radius:22px;overflow:hidden}}.panel h2{{font-size:23px!important;padding:22px;margin:0}}.map{{height:300px;background-image:url(data:image/png;base64,{img});background-size:100% auto;background-position:center 56%;background-repeat:no-repeat}}.result{{background:#dff7ed;padding:20px;display:flex;justify-content:space-between;align-items:center;color:#008262;font-size:21px;font-weight:bold}}.result span{{text-align:right}}.result small{{color:#007c62;margin-top:5px}}.other{{background:white;margin-top:16px;border-radius:22px;padding:22px}}.alts{{display:flex;gap:10px}}.alt{{background:#edf5f8;border-radius:14px;padding:14px;flex:1;font-size:14px;display:flex;flex-direction:column;gap:14px}}.alt span{{color:#006ad9;font-weight:bold;font-size:18px}}.platform footer{{margin-top:15px;color:#718797;font-size:11px}}</style><div class="platform"><header><div><small>● RESTROOM GUIDE</small><h1>화장실 길 안내</h1><small>도착 시 예상 대기시간을 반영한 화장실 안내</small></div><div class="clock">{now:%H:%M:%S}</div></header><div class="hero"><div><small>현재 위치에서</small>직진 후<br>{direction}으로</div><span>↑</span></div><section class="panel"><h2>경로를 따라 이동하세요 <small>도보 {walk}분</small></h2><div class="map"></div><div class="result"><div>{num}번 {name} 화장실</div><span>{html.escape(total_text)}<small>{html.escape(detail)}</small></span></div></section><section class="other"><h2>다른 화장실 예상 소요시간</h2><small>도보 + 도착 시 예상 대기 기준</small><div class="alts">{other}</div></section><footer>거리구간 예측으로 안내합니다. 추천은 총 소요시간의 하한 기준이며 실제 시간은 다를 수 있습니다.</footer></div>'''
    st.html(markup)
