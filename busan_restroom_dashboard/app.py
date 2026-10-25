from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import html, json, hashlib, mimetypes, subprocess, sys, io, importlib.metadata
import pandas as pd
import streamlit as st
from core import ROOT, DATA, ROOMS, COLS, TERMINAL, settings, save_settings, latest_run, run_data, at, values, common_end, label, wait_label, start_run, request_stop, cctv_stamp
from views import dashboard, signage, detail_video, live_signage
from train_ui import attach_train_events, render_train_page
from history_ui import render_history
from distance_ui import render_distance_settings
from distance_demo import DISCLAIMER
from distance_demo import result_series as distance_result_series

st.set_page_config(page_title='부산역 · 화장실 모니터링',page_icon='🚉',layout='wide')
st.markdown('''<style>
:root{color-scheme:light} .stApp{background:#f1f6fa;color:#172431} [data-testid="stSidebar"]{background:white;border-right:1px solid #e4edf5} [data-testid="stSidebar"] h1{font-size:25px;color:#0967df} .block-container{padding-top:2rem;padding-bottom:2rem;max-width:1800px} h1{letter-spacing:-1.3px;font-size:30px!important} h2{font-size:21px!important;letter-spacing:-.6px} h3{font-size:17px!important} [data-testid="stMetric"]{background:white;border:1px solid #e5edf4;border-radius:14px;padding:17px} [data-testid="stMetricLabel"]{color:#8393a4} .stButton>button{border-radius:8px} [data-testid="stSidebar"] [role="radiogroup"]>label{padding:10px 12px;border-radius:9px;margin-bottom:4px} [data-testid="stSidebar"] [role="radiogroup"]>label:has(input:checked){background:#eaf3ff;color:#0866df} .intro{color:#8193a4;font-size:13px;margin-bottom:20px}.eyebrow{color:#0867df;font-size:11px;font-weight:800;letter-spacing:1.8px}.summary-box{padding:20px;border-radius:14px;background:white;border:1px solid #e6edf4}.summary-box h3{margin-top:0}.summary-box p{font-size:13px;color:#7c8fa1}

[data-testid="stSidebar"]{min-width:225px;max-width:260px}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding:28px 18px}
[data-testid="stSidebar"] [role="radiogroup"]{gap:6px}
[data-testid="stSidebar"] [role="radiogroup"]>label{width:100%;min-height:45px;display:flex;align-items:center;gap:12px;padding:12px 14px;margin:0;color:#8796a6;transition:background .15s}
[data-testid="stSidebar"] [role="radiogroup"]>label>div:first-child{position:absolute;opacity:0;width:1px;height:1px;overflow:hidden}
[data-testid="stSidebar"] [role="radiogroup"]>label::before{content:'▦';font-size:17px;line-height:1;color:#a1adba}
[data-testid="stSidebar"] [role="radiogroup"]>label:nth-of-type(2)::before{content:'▤'}
[data-testid="stSidebar"] [role="radiogroup"]>label:nth-of-type(3)::before{content:'⇄'}
[data-testid="stSidebar"] [role="radiogroup"]>label:nth-of-type(4)::before{content:'▣'}
[data-testid="stSidebar"] [role="radiogroup"]>label:nth-of-type(5)::before{content:'⚙'}
[data-testid="stSidebar"] [role="radiogroup"]>label:has(input:checked){background:#eaf3ff;color:#0867df;font-weight:750}
[data-testid="stSidebar"] [role="radiogroup"]>label:has(input:checked)::before{color:#368ae7}
[data-testid="stSidebar"] [role="radiogroup"]>label:focus-within{outline:2px solid #6ca7ed;outline-offset:2px}
[data-testid="stSidebar"] [role="radiogroup"] p{font-size:13px}
.sidebar-footer{font-size:12px;line-height:2;color:#72859a;padding:12px}.sidebar-footer small{color:#9ca9b6}.connection-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#008b6a;margin-right:5px}
[data-testid="stSidebar"] h1{font-size:23px!important;margin:0}

.block-container{padding-top:1rem!important;padding-bottom:.7rem!important;max-width:1500px}
[data-testid="stHeader"]{height:0}
h1{font-size:23px!important;margin:0!important;padding-top:0!important;padding-bottom:4px!important}
h2{font-size:17px!important}h3{font-size:14px!important}
.intro{font-size:11px;margin-bottom:8px}.eyebrow{font-size:9px;letter-spacing:1.2px}
[data-testid="stMetric"]{padding:10px 12px;border-radius:10px}
[data-testid="stMetricValue"]{font-size:23px}
[data-testid="stMetricLabel"] p{font-size:11px}
.stButton>button{font-size:12px;min-height:32px;padding:4px 10px}
[data-testid="stWidgetLabel"] p{font-size:12px}
[data-testid="stCaptionContainer"]{font-size:10px}
[data-testid="stVerticalBlock"]{gap:.55rem}
[data-testid="stSidebar"]{min-width:195px;max-width:215px}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding:18px 14px}
[data-testid="stSidebar"] [role="radiogroup"]>label{min-height:36px;padding:8px 10px;gap:9px}
[data-testid="stSidebar"] [role="radiogroup"] p{font-size:12px}
[data-testid="stSidebar"] h1{font-size:20px!important}
[data-baseweb="tab"]{font-size:12px;padding:6px 9px}
[data-testid="stDateInput"] input{font-size:12px;text-align:center}

[data-testid="stSidebar"] .stButton>button{justify-content:flex-start;border:0;min-height:35px;font-size:12px;padding:7px 11px;color:#7d8fa0;border-radius:7px}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{background:#eaf3ff;color:#0867df;font-weight:750}
[data-testid="stSidebar"] .stButton>button:hover{background:#f1f6fb}
[data-testid="stSidebar"] .stButton>button span[data-testid="stIconMaterial"]{font-size:16px}
[data-testid="stDateInput"] [data-baseweb="input"]{min-height:32px;height:32px}
/* Keep icon and text anchored to a shared left edge in all sidebar buttons. */
[data-testid="stSidebar"] [data-testid="stButton"]>button{display:flex!important;justify-content:flex-start!important;text-align:left!important;gap:10px!important}
[data-testid="stSidebar"] [data-testid="stButton"]>button [data-testid="stMarkdownContainer"]{text-align:left!important;flex:1}
[data-testid="stSidebar"] [data-testid="stButton"]>button [data-testid="stMarkdownContainer"] p{text-align:left!important;width:100%;margin:0}
</style>''',unsafe_allow_html=True)

cfg=settings()
if not cfg.get('train_path'):cfg['train_path']=str(ROOT/'assets/train_schedule.csv')
run=latest_run()
records,jobs=run_data(run)
# Freeze interpretation settings with each run; edited thresholds/walk times remain UI settings.
run_cfg=json.loads(run['request']) if run else cfg
for key in ['walk','warning','crowded','minimum_gain','capture_date']:run_cfg[key]=cfg[key]
run_cfg['distance_demo']=cfg.get('distance_demo',{})
run_cfg['playback_key']=hashlib.sha256((str(ROOT)+(run['id'] if run else json.dumps(cfg['videos'],sort_keys=True))).encode()).hexdigest()[:24]
run_cfg['playback_end']=common_end(records) if run and run['status']=='completed' else None

def go_page(page):st.session_state['nav']=page

with st.sidebar:
    st.markdown('<div class="eyebrow">BUSAN STATION</div>',unsafe_allow_html=True)
    st.title('RESTROOM')
    st.caption('화장실 혼잡도 모니터링')
    nav=st.session_state.get('nav','메인 대시보드')
    for index,(page,icon) in enumerate([('메인 대시보드',':material/dashboard:'),('화장실 상세',':material/wc:'),('열차 정보',':material/train:'),('사이니지 보기',':material/monitor:'),('시연 설정',':material/settings:')]):
        st.button(page,icon=icon,key='nav_'+str(index),type='primary' if nav==page else 'tertiary',width='stretch',on_click=go_page,args=(page,))
    st.divider()
    st.markdown('<div class="sidebar-footer"><span class="connection-dot"></span> MVP · CCTV 시연<br><small>북쪽 · 동쪽 · 남쪽</small></div>',unsafe_allow_html=True)


def banner(title,sub):
    st.markdown('<div class="eyebrow">RESTROOM MONITORING</div>',unsafe_allow_html=True)
    st.title(title);st.markdown(f'<div class="intro">{html.escape(sub)}</div>',unsafe_allow_html=True)


def upload_save(upload,folder):
    target=DATA/folder;target.mkdir(parents=True,exist_ok=True)
    blob=upload.getvalue();suffix=Path(upload.name).suffix.lower()
    name=hashlib.sha256(blob).hexdigest()[:20]+suffix
    dest=target/name
    if not dest.exists():dest.write_bytes(blob)
    return str(dest)


@st.cache_data(show_spinner=False)
def compatible_media(path,size,modified):
    from preview import browser_preview
    return str(browser_preview(path,DATA/'previews'))


def media_urls():
    from streamlit.runtime import get_instance
    urls={}
    for r in ROOMS:
        source=run_cfg['videos'][r] if run else cfg['videos'][r]
        if not source or not Path(source).expanduser().is_file():source=cfg['videos'][r]
        if not source:continue
        original=Path(source).expanduser()
        if not original.is_file():continue
        p=original
        try:
            stat=original.stat()
            with st.spinner(ROOMS[r]+' CCTV 재생 준비 중… (최초 1회)'):
                p=Path(compatible_media(str(original.resolve()),stat.st_size,stat.st_mtime_ns))
        except Exception as error:
            st.warning(ROOMS[r]+' CCTV 재생 준비를 확인해 주세요: '+str(error))
        urls[r]=get_instance().media_file_mgr.add(str(p),mimetypes.guess_type(str(p))[0] or 'video/mp4',f'common-player-{r}')
    return urls


def record_df(room):
    rows=[]
    for rec,distance in zip(records[room],distance_result_series(records[room],run_cfg,room)):
        d=rec['csv_row']
        if isinstance(d,list):d=dict(zip(COLS,d))
        rows.append({'영상초':rec['interval_end_s'],'CCTV표시시각':cctv_stamp(rec['interval_end_s'],run_cfg).isoformat(),**d,
                     '거리시연혼잡도':distance['status'],'거리시연예상대기시간':distance['wait'],
                     '거리시연기준':DISCLAIMER,'거리시연측정안내':distance['reason'],
                     '판정표시':distance['stability'],'원시혼잡도':distance['raw_status'],
                     '마지막유효관측초':distance.get('last_valid_time_s')})
    return pd.DataFrame(rows)


def pick_time(key):
    end=common_end(records)
    if end is None:
        st.info('세 화장실의 분석 기록이 모두 있어야 동일 시점으로 비교할 수 있습니다. 메인 상단에서 분석을 시작하고 완료 후 결과를 불러오세요.')
        return None
    return st.slider('비교할 영상 시점 · 초',0.0,float(end),float(end),.1,key=key)


def begin_analysis(selection):
    request=json.loads(json.dumps(selection))
    for field in ['videos','configs']:
        request[field]={r:str(Path(v).expanduser().resolve()) if v else '' for r,v in request[field].items()}
    request['model']=str(Path(request['model']).expanduser().resolve())
    start_run(request);save_settings(request)


@st.fragment(run_every=2)
def analysis_status():
    rr=latest_run()
    if not rr:return
    _,jj=run_data(rr)
    if rr['status']=='completed':
        prior=st.session_state.get('analysis_terminal')
        st.session_state['analysis_terminal']=True
        if prior is False:st.rerun()
        st.caption('● CCTV 분석 완료 · 북쪽 / 동쪽 / 남쪽 3곳')
        return
    done=sum(j.get('status')=='completed' for j in jj.values())
    names={'preparing':'준비 중','running':'분석 중','completed':'전체 분석 완료','failed':'분석 실패','stopped':'분석 중지','interrupted':'프로세스 종료'}
    st.progress(done/3,text=f'{names.get(rr["status"],rr["status"])} · 완료 {done}/3곳')
    cols=st.columns(3)
    for c,r in zip(cols,ROOMS):
        j=jj.get(r,{})
        phase={'completed':'완료','preparing':'준비 중','running':'분석 중','failed':'실패','stopped':'중지'}.get(j.get('status'),'대기')
        c.caption(f'{ROOMS[r]} CCTV · {phase} · {j.get("processed_frames",0):,}프레임')
        if j.get('progress') is not None:c.progress(max(0.,min(1.,float(j['progress']))))
    if rr.get('error'):st.error(rr['error'])
    prior=st.session_state.get('analysis_terminal')
    now=rr['status'] in TERMINAL
    st.session_state['analysis_terminal']=now
    if prior is False and now:st.rerun()


def analysis_controls():
    rr=latest_run();active=bool(rr and rr['status'] not in TERMINAL)
    with st.container(border=True):
        st.markdown('**CCTV 영상 분석**')
        a,b,c,d=st.columns([2.5,2,1,1.5],vertical_alignment="bottom")
        mode=a.selectbox('분석 범위',['전체 영상','처음 5초 확인'],index=0,key='main_analysis_mode',disabled=active)
        if b.button('세 CCTV 분석 시작',type='primary',width='stretch',disabled=active):
            try:
                request=json.loads(json.dumps(cfg));request['end']=0. if mode=='전체 영상' else 5.
                begin_analysis(request);st.rerun()
            except Exception as e:st.error(f'분석 시작 실패: {e}')
        if c.button('분석 중지',width='stretch',disabled=not active):
            request_stop(rr['id']);st.rerun()
        if d.button('결과 불러오기',width='stretch'):st.rerun()
        analysis_status()
        st.caption('북쪽 → 동쪽 → 남쪽 순차 분석 · CCTV 표시 시각 14:00:00부터 시작')
        with st.expander('영상·모델 분석 설정'):
            editable=json.loads(json.dumps(cfg))
            for r in ROOMS:
                editable['videos'][r]=st.text_input(ROOMS[r]+' CCTV 원본 경로',value=cfg['videos'][r],key='main_video_'+r,disabled=active).strip().strip('"').strip("'")
                video=st.file_uploader(ROOMS[r]+' 영상 변경',type=['mp4','mov','m4v'],key='main_upload_'+r,disabled=active)
                if video:editable['videos'][r]=upload_save(video,'videos')
                editable['configs'][r]=st.text_input(ROOMS[r]+' 구역 JSON · 기본 구역은 비우기',value=cfg['configs'][r],key='main_config_'+r,disabled=active).strip()
            editable['model']=st.text_input('YOLO 모델 경로',value=cfg['model'],key='main_model',disabled=active).strip()
            editable['device']=st.selectbox('분석 장치',['cpu','cuda:0'],index=0 if cfg['device']=='cpu' else 1,key='main_device',disabled=active)
            day=st.date_input('CCTV 시연 날짜',value=datetime.fromisoformat(cfg['capture_date']).date(),key='capture_date',disabled=active)
            editable['capture_date']=day.isoformat()
            editable['save_video']=st.checkbox('추적 박스 결과 영상도 저장',value=cfg['save_video'],key='main_save_video',disabled=active)
            if st.button('분석 설정 저장',key='save_analysis_cfg',disabled=active):
                save_settings(editable);st.rerun()
            st.caption('시작 시각은 14:00:00입니다. 새 분석의 원본 CSV에도 이 시연 시각을 저장합니다. 이전 분석의 CSV 시각은 보존하고 화면 표시만 14시 기준으로 맞춥니다.')

if nav=='메인 대시보드':
    banner('화장실 실시간 모니터링','저장 영상 3곳의 분석 결과를 같은 영상 시점으로 확인합니다.')
    analysis_controls()
    train_run_cfg=attach_train_events(cfg,run_cfg)
    st.iframe(dashboard(records,media_urls(),train_run_cfg),height='content')
    with st.expander('열차 알림·시스템 상태'):
        left,right=st.columns([1.2,1])
        with left:
            st.subheader('열차 DB 연결')
            if train_run_cfg['train_db_status']=='connected':
                st.success('MySQL 연결됨 · 열차_운행정보 조회 성공')
                if not train_run_cfg['train_day_available']:
                    st.info('영상 기준일의 열차 기록이 없습니다. railway_system_v5에서 해당 날짜를 DB에 저장해주세요.')
                st.caption('도착·출발 예정 열차는 CCTV 아래에서 재생 시각에 맞춰 표시합니다. DB 시간표는 30초 동안 재사용하며 다시 실행할 때 갱신됩니다.')
            else:
                st.error(train_run_cfg['train_db_message'])
                st.caption('열차 정보 탭에서 MySQL 연결 설정을 적용해주세요.')
            if st.button('열차 DB 다시 불러오기',key='main_train_refresh'):
                st.session_state.pop('_train_schedule_cache',None);st.rerun()
        with right:
            st.subheader('시스템 연결 상태')
            st.write('CCTV 분석: 설치된 0.3.2 모듈을 직접 호출')
            st.write('저장: 분석 원본 CSV + 대시보드 SQLite')
            st.write('열차: MySQL 예정 시간표 조회 · '+('연결됨' if train_run_cfg['train_db_status']=='connected' else '연결 확인 필요'))
            st.caption('예측모델 미연동 · 미측정값을 0명으로 대체하지 않습니다.')

elif nav=='화장실 상세':
    banner('화장실 상세','CCTV 영상과 현재 대기 상태, 날짜·시간별 이용 기록을 확인합니다.')
    room=st.radio('화장실 선택',list(ROOMS),format_func=lambda r:ROOMS[r]+' 화장실',horizontal=True)
    urls=media_urls()
    st.iframe(detail_video(room,records[room],urls.get(room,''),run_cfg),height='content')
    render_history(room,cfg,records[room],run_cfg)
    with st.expander('CCTV 모델 분석 기록'):
        df=record_df(room)
        if df.empty:st.info('메인 상단에서 CCTV 분석을 시작하세요. 위의 날짜별 엑셀 기록은 분석 전에도 조회할 수 있습니다.')
        else:
            st.dataframe(df,hide_index=True,width='stretch')
            st.download_button('CCTV 분석 기록 CSV 다운로드',df.to_csv(index=False).encode('utf-8-sig'),f'{room}_cctv.csv','text/csv')
            st.caption('CCTV표시시각은 14:00:00 시작 기준입니다. 기존 촬영시작시각/촬영종료시각은 원본 그대로 보존합니다.')
            # Raw job metadata includes legacy module-only wait values; keep it in files.
            job=jobs.get(room,{})
            st.json({k:job[k] for k in ['status','phase','processed_frames','run_dir','error'] if k in job})

elif nav=='열차 정보':
    banner('열차 운행 정보','MySQL에 저장된 부산역 시간표를 날짜·운행구분·열차종류로 조회합니다.')
    render_train_page(cfg,save_settings)

elif nav=='사이니지 보기':
    banner('사이니지 보기','CCTV 재생 위치를 이어받아 대기 상태와 추천 경로를 표시합니다.')
    current=st.radio('현재 사이니지 위치',list(ROOMS),format_func=lambda r:ROOMS[r]+' 화장실',horizontal=True)
    # Signage-only full-width layout
    st.markdown('<style>.block-container{max-width:none!important;width:100%!important;padding-left:1rem!important;padding-right:1rem!important}</style>',unsafe_allow_html=True)
    st.iframe(live_signage(records,current,media_urls(),run_cfg),height='content')
    with st.expander('마지막 분석 시점 화면 저장'):
        end=common_end(records) or 0.
        body=signage(records,current,end,run_cfg)
        st.download_button('마지막 분석 시점 HTML',('<!doctype html><html lang="ko"><meta charset="utf-8"><title>부산역 화장실 안내</title>'+body+'</html>').encode(),f'signage_{current}.html','text/html')
        st.caption('저장 파일은 마지막 공통 분석 시점의 정적 화면입니다.')

else:
    banner('시연 설정','이용 기록과 사이니지 표시 기준을 설정합니다.')
    active=run is not None and run['status'] not in TERMINAL
    st.info('영상 분석과 모델·영상 경로 설정은 메인 대시보드 상단에서 할 수 있습니다.')
    new=json.loads(json.dumps(cfg))
    render_distance_settings(cfg,save_settings,disabled=active)
    st.subheader('화장실 이용 기록')
    st.caption('기본 엑셀의 모의 기록 125,280행이 포함되어 있습니다. 파일을 바꾸려면 아래에서 업로드하세요.')
    history_upload=st.file_uploader('화장실 이용 엑셀 또는 CSV',type=['xlsx','csv'],key='history_upload')
    if history_upload:
        history_candidate=upload_save(history_upload,'history')
        if st.button('이 화장실 기록 적용'):
            try:
                from history import load_history
                checked=load_history(history_candidate)
                cfg['history_path']=history_candidate;save_settings(cfg);st.success(f'{len(checked):,}개 기록을 적용했습니다.');st.rerun()
            except Exception as e:st.error(str(e))
    st.caption('TOILET_A=북쪽 · TOILET_B=동쪽 · TOILET_C=남쪽 / 과거 인원 기록으로 대기시간을 계산하지 않습니다. 거리 좌표가 없으면 측정 불가입니다.')
    st.subheader('02 / 사이니지 도보 안내')
    st.caption('도보시간은 이동 안내에만 사용합니다. 예상 대기시간·혼잡도는 저장된 거리 기준선의 고정 결과이며, 도보시간과 합산하지 않습니다.')
    for r in ROOMS:
        cols=st.columns(3)
        for i,other in enumerate(ROOMS):
            new['walk'][r][other]=cols[i].number_input(f'{ROOMS[r]} → {ROOMS[other]} · 도보 초',min_value=0,value=int(cfg['walk'][r][other]),step=10,disabled=r==other,key='walk_'+r+other)
    if st.button('설정 저장',width='stretch',disabled=active):
        new['videos']={r:str(Path(p).expanduser().resolve()) if p else '' for r,p in new['videos'].items()}
        save_settings(new);st.success('설정을 저장했습니다.')
    if active:st.warning('분석이 진행 중입니다. 메인 상단에서 진행률을 확인하거나 중지할 수 있습니다. 완료 후 결과 불러오기를 누르세요.')
    st.subheader('03 / 영상 호환성과 설치 확인')
    st.caption('브라우저에서 MOV가 검게 보이거나 재생되지 않으면 아래에서 미리보기용 H.264 MP4를 만드세요. 분석에는 원본 영상을 그대로 사용합니다.')
    conv_room=st.selectbox('변환할 영상',list(ROOMS),format_func=lambda r:ROOMS[r],key='convert_room')
    if st.button('미리보기용 MP4 만들기',disabled=active):
        source=cfg['videos'][conv_room]
        if not source or not Path(source).is_file():st.error('먼저 영상 경로를 저장하세요.')
        else:
            out=DATA/'previews'/f'{hashlib.sha256(source.encode()).hexdigest()[:16]}.mp4';out.parent.mkdir(exist_ok=True)
            with st.spinner('브라우저용 영상 변환 중…'):
                result=subprocess.run([sys.executable,str(ROOT/'transcode.py'),source,str(out)],capture_output=True,text=True)
            if result.returncode:st.error(result.stderr[-2000:])
            else:
                cfg.setdefault('previews',{})[source]=str(out);save_settings(cfg);st.success('변환했습니다. 메인 대시보드에서 재생해 보세요.')
    with st.expander('현재 실행 환경'):
        st.code(sys.executable)
        for pkg in ['busan-cctv-analysis','streamlit','ultralytics','torch','lap','av']:
            try:st.write(pkg+' : '+importlib.metadata.version(pkg))
            except importlib.metadata.PackageNotFoundError:st.write(pkg+' : 미설치')
        if run:
            st.json({k:run[k] for k in ['id','status','error']})
            path=DATA/run['id']/'worker.log'
            if path.is_file():st.code(path.read_text(errors='replace')[-8000:])
