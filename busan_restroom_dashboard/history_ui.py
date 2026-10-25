"""Date/time exploration for the original one-minute usage records."""
from pathlib import Path
import pandas as pd
import altair as alt
import streamlit as st
from history import load_history
from distance_demo import BANDS, result_series, DISCLAIMER
from core import cctv_stamp
from distance_stability import timeline_events

@st.cache_data(show_spinner=False,max_entries=4)
def cached_history(path,modified):return load_history(path)


def draw_chart(frame,column,title,unit,color):
    hover=alt.selection_point(fields=['시각'],nearest=True,on='pointerover',empty=False)
    tooltips=[alt.Tooltip('시각:T',title='시각',format='%Y-%m-%d %H:%M'),alt.Tooltip('대기인원:Q',title='대기인원 · 명',format='.0f')]
    base=alt.Chart(frame).encode(x=alt.X('시각:T',axis=alt.Axis(title=None,format='%H:%M',labelAngle=0,grid=False)),y=alt.Y(column+':Q',axis=alt.Axis(title=unit),scale=alt.Scale(zero=True)))
    area=base.mark_area(color=color,opacity=.08)
    line=base.mark_line(color=color,strokeWidth=1.8).encode(tooltip=tooltips)
    selector=base.mark_point(opacity=0).encode(tooltip=tooltips).add_params(hover)
    point=base.mark_circle(color=color,size=38).encode(opacity=alt.condition(hover,alt.value(1),alt.value(0)))
    rule=alt.Chart(frame).mark_rule(color='#8da8c3',strokeDash=[4,4]).encode(x='시각:T').transform_filter(hover)
    chart=alt.layer(area,line,selector,point,rule).properties(height=360).configure_view(stroke=None).configure_axis(labelFontSize=11,titleFontSize=11,labelColor='#8092a5',titleColor='#8092a5',gridColor='#e4edf4',domainColor='#dbe5ed')
    st.altair_chart(chart,width='stretch')


def shift_date(key,dates,direction):
    day=st.session_state.get(key,dates[-1])
    choices=[d for d in dates if d<day] if direction<0 else [d for d in dates if d>day]
    if choices:st.session_state[key]=choices[-1] if direction<0 else choices[0]


@st.fragment
def render_history(room,cfg,records=None,analysis_cfg=None):
    st.markdown('**CCTV 거리 기반 예상 대기시간**')
    st.caption(DISCLAIMER+' · 현재 분석 실행의 영상 시점별 고정 구간입니다. 아래 과거 인원 기록의 날짜 필터와는 별도입니다.')
    timeline=distance_timeline(records or [],analysis_cfg or cfg,room)
    if timeline.empty:
        st.info('예상 대기시간: 측정 불가 · 거리 분석 기록이 없습니다.')
    else:
        chart=alt.Chart(timeline).mark_line(interpolate='step-after',point=True).encode(
            x=alt.X('시각:T',title='CCTV 시각'),
            y=alt.Y('예상 대기시간:O',sort=['측정 불가']+[band[2] for band in BANDS]),
            tooltip=['시각:T','혼잡도:N','예상 대기시간:N','판정표시:N','원시혼잡도:N','마지막유효관측초:Q','측정 안내:N','기준:N']).properties(height=220)
        st.altair_chart(chart,width='stretch')
    st.markdown('**날짜·시간별 대기 기록**')
    p=Path(cfg['history_path']).expanduser()
    if not p.is_file():st.info('시연 설정에서 화장실 이용 기록을 연결하세요.');return
    try:
        d=cached_history(str(p),p.stat().st_mtime_ns)
        source=d[d['room']==room].copy()
        if source.empty:st.info('선택한 화장실의 기록이 없습니다.');return
        dates=sorted(source['시각'].dt.date.unique());key='history_calendar_'+room
        if key not in st.session_state or st.session_state[key] is None:st.session_state[key]=dates[-1]
        day=st.session_state[key];hours=st.session_state.get('history_hours_'+room,(0,23))
        daily=source[(source['시각'].dt.date==day)&(source['시각'].dt.hour.between(*hours))]
        tabs=st.tabs(['대기인원','기록 표'])
        with tabs[0]:
            if daily.empty:st.info('이 날짜의 기록이 없습니다.')
            else:draw_chart(daily,'대기인원','대기인원','명','#0868e8')
        with tabs[1]:
            shown=daily[[c for c in ['시각','대기인원','내부잔류인원_추정','구간_입장인원','구간_퇴장인원','측정상태'] if c in daily]].copy()
            shown['예상 대기시간']='측정 불가'
            shown['기준']=DISCLAIMER
            st.dataframe(shown,hide_index=True,width='stretch',height=200)
            st.download_button('CSV 다운로드',shown.to_csv(index=False).encode('utf-8-sig'),f'{room}_{day}_history.csv','text/csv',key='history_download_'+room)
        # Below the graph: arrow buttons and a numeric, clickable calendar date.
        _,prev,cal,nxt,_=st.columns([4,1,3,1,4],vertical_alignment='center')
        prev.button('‹',key='history_prev_'+room,help='이전 날짜',width='stretch',disabled=day<=dates[0],on_click=shift_date,args=(key,dates,-1))
        cal.date_input('조회 날짜',value=None,min_value=dates[0],max_value=dates[-1],format='YYYY-MM-DD',key=key,label_visibility='collapsed')
        nxt.button('›',key='history_next_'+room,help='다음 날짜',width='stretch',disabled=day>=dates[-1],on_click=shift_date,args=(key,dates,1))
        with st.expander('시간대·기록 안내'):
            st.slider('조회 시간대',0,23,hours,format='%d시',key='history_hours_'+room)
            st.caption('1분 단위 모의 기록 · 대기인원은 시간별 합계가 아닙니다. A=북쪽 · B=동쪽 · C=남쪽.')
            st.caption('과거 인원 기록에는 거리 좌표가 없어 예상 대기시간은 측정 불가입니다. 인원 수로 대기시간을 추정하지 않습니다. · '+DISCLAIMER)
    except Exception as e:st.error(f'기록 파일 확인 필요: {e}')


def distance_timeline(records,cfg,room):
    results=result_series(records,cfg,room)
    return pd.DataFrame([{'시각':cctv_stamp(t,cfg),
                          '혼잡도':result['status'],'예상 대기시간':result['wait'],
                          '판정표시':result['stability'],'원시혼잡도':result['raw_status'],
                          '마지막유효관측초':result.get('last_valid_time_s'),
                          '측정 안내':result['reason'],'기준':DISCLAIMER}
                         for t,result in timeline_events(records,results)])
