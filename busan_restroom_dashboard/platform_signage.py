"""Platform guidance from forecast at each destination's arrival minute."""
import base64,json,html
from pathlib import Path
from datetime import datetime,time

ROUTES=[
 {'number':1,'room':'north','id':'TOILET_A','name':'북쪽','direction':'직진 후 오른쪽으로','walk':2},
 {'number':2,'room':'east','id':'TOILET_B','name':'동쪽','direction':'직진 후 왼쪽으로','walk':1},
 {'number':3,'room':'south','id':'TOILET_C','name':'남쪽','direction':'직진 후 왼쪽으로','walk':4},
]

def js_data(x):return json.dumps(x,ensure_ascii=False).replace('</','<\\/')

def guidance_html(cfg,walks,day,start_time,urls=None,follow=False):
    root=Path(__file__).parent
    routes=[]
    for r in ROUTES:
        image=base64.b64encode((root/'assets'/f"platform_route_{r['number']}.png").read_bytes()).decode()
        routes.append({**r,'walk':walks[r['number']],'image':'data:image/png;base64,'+image})
    body='<style>'+(root/'platform_signage.css').read_text()+'</style>'+"""
<div class="wrap"><div id="play-controls"></div><header class="head"><div><span class="blue">● RESTROOM GUIDE</span><h1>화장실 길 안내</h1></div><div class="right"><small>현재 시간</small><div id="now"></div><small id="day"></small></div></header>
<section class="hero" id="hero"><div class="hero-copy"><small>현재 위치에서</small><h2 id="direction">예측 확인 중</h2><div id="walk"></div></div><div class="arrow" aria-hidden="true"><svg viewBox="0 0 180 210"><path d="M90 180V35M35 90L90 35L145 90" fill="none" stroke="white" stroke-width="25" stroke-linecap="round" stroke-linejoin="round"/></svg></div></section>
<div id="no-data" hidden></div><section class="route" id="route"><div class="routehead"><div><span class="blue">추천 경로</span><h2>경로를 따라 이동하세요</h2></div><strong id="route-walk"></strong></div><div class="route-window"><img id="route-image" alt="추천 화장실 경로 안내도"></div><div class="summary"><div class="destination-group"><span class="destination-number" id="destination-number"></span><div><small>목적지</small><h2 id="destination"></h2><div id="arrival"></div></div></div><div class="right total-group"><small>도착 시 예상 대기시간</small><div><strong id="total"></strong></div><div id="wait" class="meta"></div></div></div></section>
<section class="other"><header><h2>다른 화장실 대기시간</h2><small>각 화장실 도착 시각 기준</small></header><div class="list" id="alternatives"></div></section>
<footer class="footer"><span>도착 시 예측 대기시간을 기준으로 안내합니다.</span><span id="updated"></span></footer>
<details class="method"><summary>예측 시간 조회·추천 기준</summary><p>표시되는 값은 각 화장실에 도착했을 때의 예상 대기시간입니다. 도보시간은 대기시간에 더하지 않고, 예측을 조회할 도착 시각을 정하는 데 사용합니다.</p><p>현재 시각이 13:00이고 기본 도보시간을 사용하면, 1번 화장실(A)은 2분 후인 13:02의 A 값, 2번 화장실(B)은 1분 후인 13:01의 B 값, 3번 화장실(C)은 4분 후인 13:04의 C 값을 CSV에서 조회합니다. 도보시간 설정을 바꾸면 조회 시각도 함께 바뀝니다. CSV가 1분 단위이므로 해당 도착 시각이 속한 분의 기록을 사용합니다.</p><p>대기 없음 → 5분 미만 → 5분 이상(10분 미만) → 10분 이상(15분 미만) → 15분 이상 순으로 대기가 짧은 화장실을 추천합니다. 같은 대기 구간이면 도보시간이 짧은 곳을 선택하고, 도보시간도 같으면 번호순으로 선택합니다. 구간을 2.5분·7.5분 등의 정확한 시간으로 환산하지 않습니다.</p><p>혼잡도는 대기 없음(하늘색), 5분 미만=여유(초록), 5분 이상=보통(노랑), 10분 이상=혼잡(빨강), 15분 이상=매우 혼잡(짙은 빨강)으로 표시합니다. 어느 한 화장실이라도 도착 시각의 예측이 없으면 전체 추천을 보류합니다. 대기시간은 거리 구간 환산 기준이며 실제 대기시간 측정값은 아닙니다.</p></details></div>"""
    source=(root/'platform_signage.js').read_text()
    playback=''
    params={'routes':routes,'forecasts':cfg.get('uploaded_predictions',{}),'day':day,'start':start_time,'follow':follow,'urls':urls or {},'key':cfg.get('playback_key','default'),'limit':cfg.get('playback_end')}
    from signage_screen import screen
    return screen(body+'<script>'+playback+'\nconst platformConfig='+js_data(params)+';\n'+source+'</script>',platform=True)

def render_platform(cfg,urls):
    import streamlit as st
    st.caption('도보 도착 시각의 예측으로 추천합니다. 1번=북쪽(A), 2번=동쪽(B), 3번=남쪽(C).')
    with st.expander('플랫폼 도보시간·시연 시각 설정',expanded=not bool(cfg.get('uploaded_predictions'))):
        cols=st.columns(3);walks={}
        for col,r in zip(cols,ROUTES):
            walks[r['number']]=col.number_input(f"{r['number']}번 · {r['name']}까지 도보 (분)",min_value=0,max_value=60,value=r['walk'],step=1,key='platform_walk_'+r['room'])
        follow=st.radio('시간 기준',['CSV 시간 자동 재생','날짜·시간 직접 선택'],horizontal=True,key='platform_time_mode_csv')=='CSV 시간 자동 재생'
        day=st.date_input('플랫폼 시연 날짜',value=datetime.fromisoformat(cfg['capture_date']).date(),key='platform_date')
        start=st.time_input('현재 시각',value=time(14,0),key='platform_time')
    st.caption('CSV 자동 재생은 영상 길이와 무관합니다. 선택한 날짜의 CSV 시간 범위에서 재생하며, 도착 시각의 예측이 없으면 추천 정보 없음으로 표시합니다.')
    if not cfg.get('uploaded_predictions'):st.info('예측 CSV 등록 메뉴에서 파일을 적용하세요. 예측이 없으면 추천을 표시하지 않습니다.')
    st.iframe(guidance_html(cfg,walks,day.isoformat(),start.strftime('%H:%M:%S'),urls,follow),height='content',width='stretch')
