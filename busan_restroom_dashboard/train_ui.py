"""MySQL connection UI. Passwords live only in session state or local secrets."""
import os
from datetime import date
import streamlit as st
from train_db import available_dates,load_schedule,timeline_events

DEFAULT={'host':'127.0.0.1','port':3306,'database':'railway_system','user':'root'}

def connection_config(cfg):
    value={**DEFAULT,**cfg.get('train_db',{})}
    try:value.update(dict(st.secrets.get('mysql',{})))
    except Exception:pass
    for key,env in [('host','TRAIN_DB_HOST'),('port','TRAIN_DB_PORT'),('database','TRAIN_DB_NAME'),('user','TRAIN_DB_USER'),('password','TRAIN_DB_PASSWORD')]:
        if env in os.environ:value[key]=os.environ[env]
    value.update(st.session_state.get('train_mysql_connection',{}))
    password=st.session_state.get('train_mysql_session_password')
    if password is not None:value['password']=password
    return value

# Session-local cache avoids keeping passwords in a global cache key.
def cached_schedule(cfg,day,include_next=False):
    config=connection_config(cfg)
    key=(tuple(sorted(config.items())),str(day),include_next)
    import time
    cache=st.session_state.get('_train_schedule_cache')
    if cache and cache['key']==key and time.monotonic()-cache['time']<30:return cache['frame'].copy()
    frame=load_schedule(config,day,include_next)
    st.session_state['_train_schedule_cache']={'key':key,'time':time.monotonic(),'frame':frame}
    return frame

def attach_train_events(cfg,run_cfg):
    result=dict(run_cfg);day=run_cfg.get('capture_date',cfg.get('capture_date','2026-10-14'))
    try:
        df=cached_schedule(cfg,day,True)
        result['train_events']=timeline_events(df,day)
        result['train_db_status']='connected'
        result['train_day_available']=bool((df['날짜'].astype(str)==day).any())
        result['train_db_message']=''
    except Exception as exc:
        result.update(train_events=[],train_db_status='error',train_day_available=False,train_db_message=str(exc))
    return result

def render_train_page(cfg,save_settings):
    st.caption('MySQL railway_system · 열차_운행정보의 예정 시간표를 직접 조회합니다.')
    current=connection_config(cfg)
    with st.expander('MySQL 연결 설정',expanded=True):
        with st.form('train_mysql_connect'):
            a,b=st.columns([3,1]);host=a.text_input('호스트',value=str(current['host']));port=b.number_input('포트',min_value=1,max_value=65535,value=int(current['port']))
            a,b=st.columns(2);database=a.text_input('데이터베이스',value=str(current['database']));user=b.text_input('사용자',value=str(current['user']))
            password=st.text_input('MySQL 비밀번호',type='password',help='비워두면 현재 세션·로컬 secrets·환경변수의 비밀번호를 유지합니다. 코드나 설정 파일에 저장하지 않습니다.')
            submitted=st.form_submit_button('연결 확인 및 적용')
        if submitted:
            candidate={'host':host.strip(),'port':int(port),'database':database.strip(),'user':user.strip()}
            credentials={**candidate,'password':password if password else current.get('password','')}
            try:
                days=available_dates(credentials)
                st.session_state['train_mysql_connection']=candidate
                st.session_state['train_mysql_session_password']=credentials['password']
                st.session_state.pop('_train_schedule_cache',None)
                cfg['train_db']=candidate;save_settings(cfg)
                st.success(f'MySQL 연결 성공 · 시간표가 저장된 날짜 {len(days):,}일')
            except Exception as exc:st.error(str(exc))
        st.caption('영상 기준일의 데이터가 없다면 railway_system_v5에서 해당 날짜를 포함해 기록을 생성하고 DB에 저장해주세요.')
    if st.button('DB 새로고침',key='train_refresh'):
        st.session_state.pop('_train_schedule_cache',None)
    day=st.date_input('조회 날짜',value=date.fromisoformat(cfg.get('capture_date','2026-10-14')),key='mysql_train_day')
    try:
        frame=cached_schedule(cfg,day)
        if frame.empty:
            st.info(f'{day}의 열차 기록이 DB에 없습니다. railway_system_v5에서 날짜별 기록을 저장해주세요.')
            days=available_dates(connection_config(cfg))
            if days:st.caption(f'DB 수록 날짜 범위: {days[0]} ~ {days[-1]} (중간 날짜가 없을 수 있습니다.)')
            return
        st.success(f'MySQL 연결됨 · {day} 기록 {len(frame):,}건')
        a,b,c=st.columns(3)
        event=a.selectbox('운행구분',['전체']+sorted(frame['운행구분'].dropna().astype(str).unique()))
        kind=b.selectbox('열차종류',['전체']+sorted(frame['열차종류'].dropna().astype(str).unique()))
        hours=c.slider('시간 범위',0,23,(0,23))
        view=frame[frame['예정일시'].dt.hour.between(*hours)]
        if event!='전체':view=view[view['운행구분']==event]
        if kind!='전체':view=view[view['열차종류']==kind]
        a,b,c=st.columns(3);a.metric('조회 열차',len(view));b.metric('도착',int((view['운행구분']=='도착').sum()));c.metric('출발',int((view['운행구분']=='출발').sum()))
        st.dataframe(view,hide_index=True,width='stretch')
        st.download_button('조회 결과 다운로드',view.to_csv(index=False).encode('utf-8-sig'),'train_mysql.csv','text/csv')
        st.caption('DB에 저장된 예정 정보입니다. 실제 도착·지연 정보의 실시간 수신은 연결하지 않았습니다.')
    except Exception as exc:st.error(str(exc))
