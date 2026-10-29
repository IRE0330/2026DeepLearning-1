import io
import json
import hashlib
import zipfile
import joblib
import pandas as pd
from datetime import datetime, timedelta
from .easy_view import guess_interval, result_table, range_plan, friendly_metrics
import streamlit as st
from .core import read_table, excel_sheets, compare, predict
from .model_catalog import model_names
from .ts_models import forecast_model_names
from .multi_input import combine_tables, same_schema, suggest_keys
from .auto_setup import prepare_time, infer_group, automatic_exclusions
from .future_evaluation import render_future_evaluation
from .presentation_ui import CSS,render_combination,render_actual_comparison,model_components

@st.cache_data(show_spinner=False,max_entries=2)
def cached_read_table(data,filename,sheet):
    return read_table(data,filename,sheet)

def load_uploaded(upload, key):
    data = upload.getvalue()
    sheet = 0
    if upload.name.lower().endswith(('.xlsx', '.xls')):
        sheets = excel_sheets(data)
        sheet = st.selectbox('사용할 엑셀 시트', sheets, key=key + '_sheet')
    return cached_read_table(data, upload.name, sheet), sheet


def _excel_bytes(df):
    buf=io.BytesIO()
    df.to_excel(buf,index=False,engine='openpyxl')
    return buf


def friendly_feature(name):
    labels={'day_off_run_length':'연속 휴일 길이','day_off_run_position':'연휴 중 며칠째','days_to_holiday':'다음 공휴일까지 남은 날','days_since_holiday':'이전 공휴일 이후 지난 날','holiday_hour':'공휴일 이름×시간대','is_holiday':'공휴일·대체공휴일 여부','holiday_name':'공휴일 이름','is_day_before_holiday':'공휴일 전날','is_day_after_holiday':'공휴일 다음날','is_day_off':'주말 또는 공휴일','is_bridge_day':'징검다리 평일','series':'선택한 구분', 'year':'연도', 'month':'월', 'day':'일', 'weekday':'요일', 'hour':'시', 'minute':'분', 'is_weekend':'주말 여부','day_of_year':'연중 날짜','week_of_year':'연중 주차','is_month_start':'월초 여부','is_month_end':'월말 여부','hour_sin':'시간대 주기 (sin)','hour_cos':'시간대 주기 (cos)','weekday_sin':'요일 주기 (sin)','weekday_cos':'요일 주기 (cos)','month_sin':'월 주기 (sin)','month_cos':'월 주기 (cos)','recent_change':'최근 값 변화'}
    if name in labels:return labels[name]
    if name.startswith('lag_'):return name[4:]+'칸 전의 예측 대상 값'
    if name.startswith('rolling_mean_'):return name[13:]+'칸 이동평균'
    if name.startswith('rolling_std_'):return name[12:]+'칸 변동폭'
    if name.startswith('past::'):return name[6:]+' (미래 값 자동 추정 또는 수동 가정)'
    if name.startswith('known::'):return name[7:]+' (미래 예정 정보)'
    return name


def render_table_pipeline(df, raw, target, time_col=None, time_sources=()):
    st.caption('선택한 데이터를 분석해 변수 조합과 모델 설정을 함께 탐색합니다.')
    if time_col is None:
        st.info('날짜·시간 기록을 찾지 못해 일반 표 분석으로 진행합니다. 미래 날짜 예측에는 날짜·시간과 숫자 기록이 필요합니다.')
    default_task='regression' if pd.api.types.is_numeric_dtype(df[target]) and df[target].nunique()>2 else 'classification'
    features=[c for c in df if c!=target and c not in time_sources]
    with st.expander('자동 분석 설정 확인·수정'):
        kind=st.radio('예측 결과의 종류',['숫자','종류 (예/아니오 등)'],index=0 if default_task=='regression' else 1)
        task='regression' if kind=='숫자' else 'classification'
        table_country_choice=st.selectbox('공휴일 달력',['한국 (KR)','미국 (US)','일본 (JP)','공휴일 사용 안 함'],key='table_holiday_country')
        table_country={'한국 (KR)':'KR','미국 (US)':'US','일본 (JP)':'JP','공휴일 사용 안 함':None}[table_country_choice]
        features=st.multiselect('참고할 항목',features,default=features,key='unified_table_features')
        force=st.multiselect('반드시 사용할 항목',features,key='unified_table_force')
        budget=st.select_slider('변수·모델 설정 탐색 횟수',options=[12,24,48,96],value=24,key='unified_table_budget')
        defaults=['기준 모델','Random Forest','Extra Trees','Ridge' if task=='regression' else 'Logistic Regression','Hist Gradient Boosting']
        defaults += ['Huber Regression','Bayesian Ridge','Bagging'] if task=='regression' else ['Bagging']
        names=st.multiselect('비교할 모델',model_names(task),default=defaults,key='unified_table_models_'+task)
    sig=hashlib.sha256(b'3.0-period-evaluation'+raw+df.to_csv(index=False).encode()+repr((target,features,task,force,budget,names,time_col,table_country)).encode()).hexdigest()
    if st.button('최적 조합 찾고 예측하기',type='primary'):
        bar=st.progress(0.,text='자동 분석 준비 중')
        with st.spinner('데이터 정리·변수 조합·모델 설정을 함께 탐색 중입니다.'):
            r=compare(df,target,features,task,time_col,(time_col,) if time_col else (),progress=lambda p,n:bar.progress(p,text=n),selected_models=names,auto_search=True,force_include=tuple(force),optimize=True,search_budget=budget,holiday_country=table_country)
        st.session_state['unified_table_result']=r
        st.session_state['unified_table_signature']=sig
    if st.session_state.get('unified_table_signature')!=sig:return
    bundle,table,output,report=st.session_state['unified_table_result']
    st.subheader('탐색 결과: 최적 변수·모델 조합')
    render_combination(report['최적모델'],report['선택컬럼'],report['선택모델설정'],friendly_feature,bundle.get('pipeline'))
    metric='MAE' if task=='regression' else 'F1_macro'
    c1,c2,c3=st.columns(3)
    c1.metric('선택된 항목 수',len(report['선택컬럼']))
    c2.metric('검증 평균 오차' if task=='regression' else '검증 균형 점수',f"{table.iloc[0][metric]:.3f}")
    c3.metric('최종 평가 평균 오차' if task=='regression' else '최종 평가 균형 점수',f"{report['최종테스트'][metric]:.3f}")
    with st.expander('모델별 컬럼 추가·제거 탐색 기록'):
        st.dataframe(pd.DataFrame(report.get('컬럼추가제거탐색',[])),hide_index=True)
    audit=pd.DataFrame(report['항목선택_상세'])
    with st.expander('컬럼 사용·제외 내역'):
        st.dataframe(audit,use_container_width=True,hide_index=True)
    with st.expander('선택 모델 설정값·전체 탐색 결과'):
        st.json(report['선택모델설정'])
        st.dataframe(friendly_metrics(table),use_container_width=True,hide_index=True)
        st.json(report)
    st.subheader('최적 조합으로 예측한 평가 기록')
    st.dataframe(output,use_container_width=True,hide_index=True)
    if task=='regression':st.line_chart(output[['실제값','예측값']].reset_index(drop=True))
    summary={'컬럼추가제거탐색':report.get('컬럼추가제거탐색',[]),'상황별모델선택':report.get('상황별모델선택',[]),'모델':report['최적모델'],'선택항목':report['선택컬럼'],'모델설정값':report['선택모델설정'],'검증점수':float(table.iloc[0][metric]),'최종평가':report['최종테스트']}
    mem=io.BytesIO();joblib.dump(bundle,mem)
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('best_combination.json',json.dumps(summary,ensure_ascii=False,indent=2))
        z.writestr('model.joblib',mem.getvalue())
        z.writestr('comparison.csv',table.to_csv(index=False).encode('utf-8-sig'))
        z.writestr('selected_columns.csv',audit.to_csv(index=False).encode('utf-8-sig'))
        z.writestr('test_predictions.csv',output.to_csv(index=False).encode('utf-8-sig'))
    st.download_button('최적 조합·모델·예측 결과 저장',archive.getvalue(),'pipeline_results.zip','application/zip')
    with st.expander('같은 모델로 다른 파일의 값도 예측하기 (선택 사항)'):
        nf=st.file_uploader('새 데이터 (같은 입력 항목)',type=['csv','xlsx','xls'],key='unified_new_file')
        if nf:
            nd,_=load_uploaded(nf,'unified_new')
            if st.button('선택된 모델로 새 데이터 예측'):
                result=predict(bundle,nd)
                st.dataframe(result,use_container_width=True)
                st.download_button('새 예측 결과 저장',result.to_csv(index=False).encode('utf-8-sig'),'new_predictions.csv','text/csv')


def render():
    st.markdown(CSS, unsafe_allow_html=True)
    # dashboard-prediction-theme-v1
    st.markdown('''<style>
      .stApp {background:#f1f6fa!important;color:#172431!important}
      [data-testid="stHeader"] {background:transparent!important}
      .block-container {max-width:1500px!important;padding-top:5rem!important;padding-bottom:.7rem!important}
      [data-testid="stExpander"] {background:#fff!important;border:1px solid #e5edf4!important;border-radius:10px!important}
      [data-testid="stMetric"] {background:#fff!important;border:1px solid #e5edf4!important;border-radius:10px!important}
      [data-testid="stFileUploader"] {background:white!important;border-radius:12px!important;padding:12px!important}
      .stButton>button,.stDownloadButton>button {border-radius:8px!important}
      h1,h2,h3,h4 {color:#172431!important;line-height:1.35!important}
    </style>''',unsafe_allow_html=True)
    st.html('''<div style="display:block;padding:4px 0 12px">
      <div style="display:block;font-size:11px;line-height:16px;font-weight:800;letter-spacing:1.2px;color:#0867df;margin:0 0 12px">RESTROOM MONITORING</div>
      <div role="heading" aria-level="1" style="display:block;font-size:27px;line-height:36px;font-weight:800;letter-spacing:-0.8px;color:#172431;margin:0 0 10px">혼잡도 예측모델</div>
      <div style="font-size:12px;line-height:19px;color:#718797">화장실별 도착 시 혼잡도를 예측하고 모델을 비교합니다.</div>
    </div>''')
    st.caption('버전 3.0 · 설정한 예측 기간의 정답 비교')
    st.caption('파일 업로드 → 데이터 분석·특성 생성 → 변수·모델·설정 공동 탐색 → 최적 조합 → 예측')
    st.subheader('데이터를 올리면, 최적 조합부터 미래 예측까지')
    st.write('파일을 올리고 예측할 값과 기간만 정하세요. 날짜·시간·기록 간격·대상 구분과 사용할 예측 방법은 자동으로 준비합니다.')
    busan_mode=st.checkbox('부산역 데이터 2개 자동 연결 (화장실 A·B·C 전체)', value=True, key='busan_mode')
    if busan_mode:
        st.caption('화장실 엑셀과 승하차 예매 엑셀을 함께 선택하세요. 도착·출발 열차의 직전 10분·30분 정보를 생성합니다.')
    uploads = st.file_uploader('1. 기록 파일을 올려 주세요 (여러 엑셀·CSV 선택 가능)', type=['csv','xlsx','xls'], accept_multiple_files=True, key='forecast_file_'+str(st.session_state.get('forecast_uploader_version',0)))
    if uploads:
        st.session_state['_saved_forecast_uploads']=[(f.name,f.getvalue()) for f in uploads]
    elif st.session_state.get('_saved_forecast_uploads'):
        uploads=[]
        for filename, data in st.session_state['_saved_forecast_uploads']:
            f=io.BytesIO(data); f.name=filename; uploads.append(f)
        st.caption('이전에 올린 파일을 복원했습니다: '+', '.join(f.name for f in uploads))
    if st.session_state.get('_saved_forecast_uploads'):
        if st.button('예측 데이터와 결과 초기화',key='clear_forecast_data'):
            for key in ['_saved_forecast_uploads','forecast_result','forecast_signature','unified_table_result','unified_table_signature','_forecast_widget_snapshot']:
                st.session_state.pop(key,None)
            st.session_state['forecast_uploader_version']=st.session_state.get('forecast_uploader_version',0)+1
            st.rerun()
    if not uploads:
        st.info('처음이라면 samples 폴더의 forecast_history.csv로 연습할 수 있어요.')
    if uploads:
        try:
            if not isinstance(uploads,list):uploads=[uploads]
            if busan_mode:
                from .busan_data import prepare_busan
                fd, merge_report, unmatched = prepare_busan(uploads)
                file_names=[f.name for f in uploads]; fsheet=repr((file_names,'busan_all_rooms'))
                raw_data=b''.join(f.getvalue() for f in uploads)+fsheet.encode()
                st.success(f'A·B·C 세 화장실 연결 완료: {len(fd):,}개 기록')
                st.caption('시간 구간은 각 기록 시각을 포함하며, 시작 시각은 제외합니다. 첫날 자료가 없는 구간과 해당 열차가 없는 평균 예매율은 빈 값입니다.')
                st.caption('대기 거리구간을 0~4단계로 변환해 예측합니다. 예측값은 가장 가까운 단계로 반올림해 플랫폼 사이니지에 연결합니다. 승하차 파일의 예매율은 인원수가 아닙니다.')
                with st.expander('연결 결과 확인'):
                    st.dataframe(pd.DataFrame(merge_report),hide_index=True)
                    st.dataframe(fd.head(20),hide_index=True)
            else:
                frames=[];file_names=[];sheets=[]
                for i,file in enumerate(uploads):
                    st.caption(f'파일 {i+1}: {file.name}')
                    frame,sheet=load_uploaded(file,'forecast_'+str(i))
                    frames.append(frame);file_names.append(file.name);sheets.append(sheet)
                mode='auto';base=0;plans={};drop_duplicates=True
                if len(frames)>1:
                    with st.expander('파일 합치기 설정 (기본은 자동)'):
                        choice=st.radio('파일을 어떻게 사용할까요?',['자동','같은 종류의 기록을 행으로 합치기','서로 다른 정보를 항목으로 연결하기'])
                        mode={'자동':'auto','같은 종류의 기록을 행으로 합치기':'append','서로 다른 정보를 항목으로 연결하기':'join'}[choice]
                        if mode=='join' or (mode=='auto' and not same_schema(frames)):
                            base=st.selectbox('기준이 되는 파일',list(range(len(frames))),format_func=lambda i:file_names[i])
                            for i,frame in enumerate(frames):
                                if i==base:continue
                                common=suggest_keys(frames[base],frame)
                                st.write('연결할 파일: '+file_names[i])
                                lk=st.multiselect('기준 파일의 연결 항목',list(frames[base].columns),default=common,key='join_left_'+str(i))
                                rk=st.multiselect('이 파일의 연결 항목 (같은 순서)',list(frame.columns),default=common,key='join_right_'+str(i))
                                plans[i]=(lk,rk)
                            st.caption('기준 파일의 행을 유지하며 연결합니다. 한 기준 행에 여러 행이 붙는 모호한 연결은 중단합니다.')
                        drop_duplicates=st.checkbox('내용이 완전히 같은 중복 기록 제거',value=True)
                fd,merge_report=combine_tables(frames,file_names,mode,base,plans,drop_duplicates)
                fsheet=repr((file_names,sheets,mode,base,plans,drop_duplicates))
                raw_data=b''.join(f.getvalue() for f in uploads)+fsheet.encode()
                st.success(f'{len(frames)}개 파일 → {len(fd):,}개 기록 · {len(fd.columns)}개 항목으로 준비했습니다.')
                with st.expander('파일 합치기 결과 확인'):
                    st.dataframe(pd.DataFrame(merge_report),use_container_width=True,hide_index=True)
                    st.dataframe(fd.head(20),use_container_width=True)
                for item in merge_report:
                    if item.get('미일치행',0)>0:
                        st.warning(f"{item['파일']}: {item['미일치행']}개 기준 기록에 연결 정보가 없습니다. 해당 입력은 빈 값으로 남습니다.")
            if len(fd.columns)<2:
                raise ValueError('날짜·시간과 예측할 값이 각각 다른 항목에 있어야 합니다.')
            with st.expander('올린 파일 미리 보기'):
                st.dataframe(fd.head(20),use_container_width=True)
            time_problem=None
            try:
                fd,tc,time_sources=prepare_time(fd)
            except ValueError as error:
                tc=None;time_sources=[];time_problem=str(error)
            choices=[c for c in fd if c!=tc and c not in time_sources]
            if not choices:
                raise ValueError('예측할 항목을 찾지 못했습니다.')
            yc=st.selectbox('무엇을 예측할까요?',choices,index=choices.index('대기거리구간_예측단계') if busan_mode and '대기거리구간_예측단계' in choices else None,placeholder='예측할 항목 하나만 선택하세요',key='forecast_target')
            if yc is None:
                st.info('예측할 항목을 고르면 데이터 분석부터 최적 조합 탐색까지 자동으로 진행합니다.')
                st.stop()
            if tc is None or not pd.api.types.is_numeric_dtype(fd[yc]):
                render_table_pipeline(fd,raw_data,yc,tc,time_sources)
                st.stop()
            detected_group='화장실ID' if busan_mode and '화장실ID' in fd else infer_group(fd,tc,yc)
            gc=detected_group or '없음'
            interval=guess_interval(fd,tc,detected_group)
            st.caption('요일·주말과 한국 공휴일·대체공휴일, 휴일 전후를 자동으로 예측 후보에 넣습니다.')
            with st.expander('자동으로 찾은 설정 확인·수정'):
                holiday_choice=st.selectbox('공휴일 달력',['한국 (KR)','미국 (US)','일본 (JP)','공휴일 사용 안 함'])
                holiday_country={'한국 (KR)':'KR','미국 (US)':'US','일본 (JP)':'JP','공휴일 사용 안 함':None}[holiday_choice]
                st.write('날짜·시간: '+' + '.join(map(str,time_sources)))
                manual_time=st.selectbox('다른 날짜·시간 항목 사용', [tc]+list(time_sources), key='manual_time')
                date_order=st.selectbox('슬래시 날짜 읽는 순서', ['자동 (일/월/년 우선)','일/월/년','월/일/년'], key='auto_date_order')
                if manual_time!=tc or date_order!='자동 (일/월/년 우선)':
                    from .auto_setup import parse_dates
                    source=time_sources[0] if manual_time==tc else manual_time
                    changed=parse_dates(fd[source],source,dayfirst=False if date_order=='월/일/년' else True)
                    if manual_time==tc and len(time_sources)==2:
                        changed=changed+pd.to_timedelta(pd.to_numeric(fd[time_sources[1]],errors='coerce'),unit='h')
                    if changed is None or changed.isna().any():raise ValueError('선택한 항목은 날짜로 읽을 수 없습니다.')
                    fd[tc]=changed
                gchoices=['없음']+[c for c in fd if c not in [tc,yc] and c not in time_sources]
                gc=st.selectbox('대상을 나누는 항목',gchoices,index=gchoices.index(gc) if gc in gchoices else 0,key='auto_group')
                interval=st.number_input('기록 간격 (분)',min_value=1,max_value=10080,value=interval,key='forecast_interval')
                value_unit=st.text_input('값의 단위 (선택 사항)',value='',key='forecast_value_unit')
            st.success('자동 설정: 날짜·시간 '+ ' + '.join(map(str,time_sources)) + f' / 기록 간격 {interval}분 / 구분 '+str(gc))
            st.caption('미래 값을 모르는 항목은 과거 기록으로 보조 예측합니다. 그 추정 오차까지 포함해 변수 조합과 모델 설정을 검증합니다.')
            times=pd.to_datetime(fd[tc],errors='coerce')
            numbers=pd.to_numeric(fd[yc],errors='coerce')
            if times.isna().any():
                raise ValueError('선택한 날짜·시간 항목을 읽을 수 없습니다. 날짜와 시간이 함께 들어 있는 항목을 골라 주세요.')
            if numbers.isna().any():
                raise ValueError('선택한 값에 문자나 빈칸이 있습니다. 숫자가 들어 있는 항목을 고르거나 파일을 정리해 주세요.')
            last=times.max()
            group_label='구분' if gc=='없음' else str(gc)
            value_label='예상 '+str(yc)+(f' ({value_unit})' if value_unit.strip() else '')
            st.caption(f'기록 기간: {times.min():%Y-%m-%d %H:%M} ~ {last:%Y-%m-%d %H:%M} · {len(fd):,}개 기록')
            with st.expander('과거 날짜별 기록 확인 (선택 사항)'):
                show_history=st.checkbox('과거 기록 보기 켜기',value=False,key='show_history')
                if show_history:
                    hdates=st.date_input('기록을 확인할 날짜 범위',value=(max(times.min(),last-pd.Timedelta(days=6)).date(),last.date()),min_value=times.min().date(),max_value=last.date(),key='history_dates')
                    if len(hdates)==2:
                        from .large_data_view import history_preview
                        hist,matched=history_preview(fd,tc,yc,None if gc=='없음' else gc,hdates[0],hdates[1])
                        st.caption(f'선택 기간 {matched:,}행 중 미리보기 {len(hist):,}행 · 최대 3개 대상·2,000행. 학습 데이터는 줄이지 않습니다.')
                        if len(hist):
                            st.line_chart(hist.pivot_table(index='예측시각',columns='구분',values='기록값',aggfunc='mean'))
                            ht=result_table(hist,'기록값','기록된 '+str(yc),group_label)
                            st.dataframe(ht,use_container_width=True,hide_index=True)
                            st.download_button('미리보기 기록 CSV 저장',ht.to_csv(index=False).encode('utf-8-sig'),'history_preview.csv','text/csv')
                        else:st.info('선택한 날짜에 기록이 없습니다.')
            if gc!='없음':
                with st.expander('학습할 대상 범위 (전체 데이터 유지)'):
                    group_values=fd[gc].drop_duplicates().tolist()
                    subset_mode=st.radio('학습 대상',['전체 대상','일부 대상 선택'],horizontal=True,key='group_scope')
                    if subset_mode=='일부 대상 선택':
                        selected_groups=st.multiselect('학습할 대상 선택',group_values,default=[],key='selected_groups')
                        if not selected_groups:
                            st.info('학습할 대상을 하나 이상 선택하세요.');st.stop()
                        fd=fd.loc[fd[gc].isin(selected_groups)].copy()
                        times=pd.to_datetime(fd[tc],errors='coerce');numbers=pd.to_numeric(fd[yc],errors='coerce');last=times.max()
                        st.caption(f'선택한 {len(selected_groups):,}개 대상 · {len(fd):,}행으로 학습합니다.')
                    if len(fd)>200000:
                        st.warning(f'현재 {len(fd):,}행입니다. 날짜 설정 화면은 열 수 있지만 전체 모델·컬럼 탐색은 메모리와 시간이 많이 필요합니다. 노트북에서는 일부 대상을 명시적으로 선택해 먼저 실행할 수 있습니다.')
            extra=[c for c in fd if c not in [tc,yc,gc] and c not in time_sources]
            known=[];past=list(extra);forced_forecast=[]
            future_frame=None;future_bytes=b'';carry_ok=True;auto_covariates=True
            with st.expander('데이터 분석과 변수 설정 (자동 실행)'):
                st.caption(f'추가 입력 {len(extra)}개 · 날짜·시간·과거값 특성은 자동 생성합니다.')
                st.caption('빈 값·고유값·관련성을 학습 구간에서 분석합니다. 요일·주말·월·시간 주기·이동평균 등을 생성하고 변수 사용 비율 25/50/75/100%와 모델 설정을 함께 탐색합니다.')
                extra=st.multiselect('참고 항목 직접 수정',extra,default=extra,key='forecast_extra')
                st.caption('미래 값을 제공하지 않아도 자동 보조 예측으로 실행됩니다. 실제 미래 정보가 있으면 아래에서 제공할 수 있습니다. 기상·운영 정책처럼 예측하기 어려운 변수는 보조 추정의 오차가 큽니다.')
                known=st.multiselect('미래 예정 값을 파일로 제공할 항목 (선택 사항)',extra,key='forecast_known')
                past=[c for c in extra if c not in known]
                if known:
                    ff=st.file_uploader('미래 예정 정보 (CSV·엑셀)',type=['csv','xlsx','xls'],key='future_known_file')
                    if ff:
                        future_frame,_=load_uploaded(ff,'future_known')
                        future_bytes=ff.getvalue()+future_frame.to_csv(index=False).encode()
                forced_forecast=st.multiselect('반드시 사용할 추가 항목 (선택 사항)',extra,key='forecast_forced')
            st.markdown('**언제의 값을 예측할까요?**')
            mode=st.radio('기간 선택 방법',['원하는 날짜·시간 직접 선택','앞으로 몇 시간·며칠'],horizontal=True)
            first=last+pd.Timedelta(minutes=interval)
            if mode=='앞으로 몇 시간·며칠':
                c1,c2=st.columns(2)
                with c1:
                    amount=st.number_input('얼마나 앞까지 볼까요?',1,100000,1)
                with c2:
                    unit=st.selectbox('단위',['시간','분','일'])
                duration=amount*{'분':1,'시간':60,'일':1440}[unit]
                start=first
                end=last+pd.Timedelta(minutes=max(interval,duration))
                if duration<interval:
                    st.caption(f'선택한 기간이 기록 간격보다 짧아 다음 기록 시점인 {interval}분 뒤를 예측합니다.')
            else:
                st.caption('마지막 기록 이후의 날짜를 선택하세요. 시작일까지 떨어져 있으면 그 사이도 순서대로 예측합니다.')
                c1,c2=st.columns(2)
                with c1:
                    sd=st.date_input('시작 날짜',first.date(),min_value=last.date())
                    stime=st.time_input('시작 시간',first.time())
                with c2:
                    ed=st.date_input('종료 날짜',(last+pd.Timedelta(minutes=max(interval,60))).date(),min_value=last.date())
                    etime=st.time_input('종료 시간',(last+pd.Timedelta(minutes=max(interval,60))).time())
                start=pd.Timestamp(datetime.combine(sd,stime))
                end=pd.Timestamp(datetime.combine(ed,etime))
                if getattr(last,'tzinfo',None):
                    start=start.tz_localize(last.tzinfo)
                    end=end.tz_localize(last.tzinfo)
            st.caption(f'마지막 기록: {last:%Y-%m-%d %H:%M} · {interval}분 간격으로 예측')
            if known:
                try:
                    template_minutes,_,_=range_plan(last,start,end,interval)
                    template_times=pd.date_range(last+pd.Timedelta(minutes=interval),periods=int(template_minutes/interval),freq=pd.Timedelta(minutes=interval))
                    parts=[]
                    ids=fd[gc].drop_duplicates().tolist() if gc!='없음' else [None]
                    for ident in ids:
                        part=pd.DataFrame({tc:template_times})
                        if gc!='없음':part[gc]=ident
                        for c in known:part[c]=''
                        parts.append(part)
                    template=pd.concat(parts,ignore_index=True)
                    st.download_button('미래 예정 정보 입력 양식 받기 (엑셀)',_excel_bytes(template).getvalue(),'future_information_template.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    st.caption('양식의 빈칸에 미래에 미리 알 수 있는 값만 채우고, 위의 미래 예정 정보 업로드 칸에 올려 주세요.')
                except ValueError:
                    st.caption('기간을 올바르게 선택하면 미래 정보 입력 양식을 받을 수 있습니다.')
            with st.expander('예측 방법 설정 (처음에는 그대로 두세요)'):

                auto_forecast=True
                optimize_forecast=True
                search_budget=st.select_slider('기본 모델·설정 탐색 횟수',options=[12,24,48,96],value=24,help='기본 탐색 후 일반 ML 모델별 컬럼 추가·제거를 최대 24회 더 비교합니다. 많을수록 시간이 늘어납니다.')
                defaults=['기준 모델','Random Forest','Extra Trees','Ridge','Hist Gradient Boosting','Gradient Boosting','Huber Regression','Bayesian Ridge','최근 값 기준','요일·시간 패턴','Fourier 계절 회귀','ETS 지수평활']
                if 1440%interval==0 and len(fd)/(fd[gc].nunique() if gc!='없음' else 1)>4*(1440/interval):defaults.append('일간 반복 예측')
                if 10080%interval==0 and len(fd)/(fd[gc].nunique() if gc!='없음' else 1)>4*(10080/interval):defaults.append('주간 반복 예측')
                fm=st.multiselect('비교할 방법',forecast_model_names(),default=defaults,key='forecast_models')
                nonnegative=st.checkbox('예상 값이 음수가 되지 않게 하기',value=False,help='음수가 불가능한 값일 때만 켜세요. 온도·손익 등은 음수가 나올 수 있습니다.')
                st.caption('XGBoost·LightGBM·CatBoost는 추가 설치가 필요합니다. 여러 방법을 같은 과거 구간으로 비교해 평균 오차가 작은 방법을 고릅니다.')
            st.info('모델별로 컬럼 추가·제거·교체와 묶음 제외로 실제 검증 MAE가 개선되는 조합을 탐색합니다. 날짜 특성과 다른 변수, 모델 설정도 함께 비교합니다. 전체·최근 학습 기간을 비교하고, 요청한 예측 길이로 최대 네 과거 구간을 검증합니다. 데이터가 짧으면 검증 길이를 줄여 표시합니다. 상위 모델 결합도 비교한 뒤 별도 최종 평가를 합니다. 대상별 일정 간격 기록 80개 이상이 필요합니다.')
            signature=hashlib.sha256(b'3.0-period-evaluation'+raw_data+future_bytes+repr((fsheet,tc,yc,gc,interval,str(start),str(end),value_unit,nonnegative,fm,len(fd),extra,known,forced_forecast,auto_forecast,carry_ok,search_budget,holiday_country,tuple(fd[gc].drop_duplicates()) if gc!='없음' else None)).encode()).hexdigest()
            if st.button('최적 조합 찾고 예측하기',type='primary'):
                from .forecast import forecast
                minutes,actual_start,actual_end=range_plan(last,start,end,interval)
                bar=st.progress(0.,text='예측 준비 중')
                with st.spinner('과거 기록으로 여러 방법을 비교한 뒤 미래 값을 계산하고 있어요.'):
                    fr=forecast(fd,tc,yc,None if gc=='없음' else gc,interval,minutes,fm,nonnegative,lambda p,n:bar.progress(p,text='비교 중: '+n),auto_search=auto_forecast,past_columns=tuple(past),known_columns=tuple(known),future_data=future_frame,force_include=tuple(forced_forecast),optimize=True,search_budget=search_budget,auto_covariates=True,holiday_country=holiday_country)
                st.session_state['forecast_result']=fr
                st.session_state['forecast_signature']=signature
            if st.session_state.get('forecast_signature')==signature:
                future,ft,test,report,fbundle=st.session_state['forecast_result']
                shown=future[(future['예측시각']>=start)&(future['예측시각']<=end)]
                easy=result_table(shown,'예측값',value_label,group_label)
                st.subheader('탐색 결과: 최적 변수·모델 조합')
                render_combination(report['선택모델'],report['선택항목'],report['선택설정값'],friendly_feature,fbundle.get('pipeline'))
                st.download_button('실제값과 비교할 예측 결과 CSV 받기',easy.to_csv(index=False).encode('utf-8-sig'),'future_predictions.csv','text/csv',key='primary_forecast_download')
                st.caption(f"예측 결과 {len(easy):,}행 · {shown['예측시각'].min()} ~ {shown['예측시각'].max()}")
                summary1,summary2,summary3=st.columns(3)
                summary1.metric('선택된 항목 수',len(report['선택항목']))
                summary2.metric('시간순 검증 평균 오차',f"{ft.iloc[0]['MAE']:.3f}")
                summary3.metric('과거 내부 평가 MAE',f"{report['최종테스트']['MAE']:.3f}")
                period_comparison=render_future_evaluation(shown,yc,gc,load_uploaded,render_actual_comparison)
                with st.expander('과거 내부 평가 보기 · 설정한 예측 기간과 다름'):
                    render_actual_comparison(test)
                with st.expander('학습·검증 구간 상세'):
                    st.json(report['선택설정값'])
                    st.write('학습 기간 후보(대상별 기록 수, null은 전체):',report.get('학습기간후보_칸'))
                    st.dataframe(pd.DataFrame(report.get('검증구간',[])),hide_index=True)
                    st.write('요청 기간 전체 검증:', '완료' if report.get('요청기간전체검증') else '과거 데이터 부족으로 짧은 기간 검증')
                st.download_button('최종 컬럼·모델 요약 JSON 저장',json.dumps({'구성모델':model_components(fbundle.get('pipeline')),'예측대상':yc,'예측시작':str(shown['예측시각'].min()),'예측종료':str(shown['예측시각'].max()),'프로그램버전':report.get('프로그램버전'),'모델':report['선택모델'],'사용항목':report['선택항목'],'모델설정값':report['선택설정값'],'검증평균오차':float(ft.iloc[0]['MAE']),'과거내부평가':{'기간시작':str(test['예측시각'].min()),'기간종료':str(test['예측시각'].max()),'지표':report['최종테스트']},'설정기간평가':None if period_comparison is None else {'일치건수':len(period_comparison),'예측건수':len(shown),'기간시작':str(shown['예측시각'].min()),'기간종료':str(shown['예측시각'].max()),'부분평가':len(period_comparison)!=len(shown),'R2':1-float(((period_comparison['예측값']-period_comparison['실제값'])**2).sum()/((period_comparison['실제값']-period_comparison['실제값'].mean())**2).sum()) if ((period_comparison['실제값']-period_comparison['실제값'].mean())**2).sum() else None,'MAE':float(period_comparison['절대차이'].mean()),'WAPE':float(period_comparison['절대차이'].sum()/period_comparison['실제값'].abs().sum()*100) if period_comparison['실제값'].abs().sum() else None},'이상치공휴일처리':report.get('이상치공휴일처리',[]),'검증구간':report.get('검증구간',[]),'예측기간달력':report.get('예측기간달력',[]),'컬럼추가제거탐색':report.get('컬럼추가제거탐색',[]),'상황별모델선택':report.get('상황별모델선택',[])},ensure_ascii=False,indent=2),'best_combination.json','application/json')

                st.caption(f"자동 탐색 {report.get('탐색횟수',0)}회 · 시간순 검증 {report.get('검증구간수',1)}구간")
                with st.expander('모델별 컬럼 추가·제거 탐색 기록'):
                    st.caption(report.get('컬럼탐색설명',''))
                    st.dataframe(pd.DataFrame(report.get('컬럼추가제거탐색',[])),hide_index=True)
                with st.expander('평일·주말·공휴일별 선택 모델'):
                    if report.get('상황별모델선택'):
                        st.dataframe(pd.DataFrame(report['상황별모델선택']),hide_index=True)
                    else:
                        st.caption('상황별 모델도 비교했으며, 이번에는 다른 후보가 최종 선택됐습니다.')
                with st.expander('자동 인식한 공휴일·연휴'):
                    st.dataframe(pd.DataFrame(report.get('예측기간달력',[])),hide_index=True)
                with st.expander('이상치·공휴일 처리 내역'):
                    st.json(report.get('이상치공휴일처리',[]))
                    st.caption('학습 구간에서만 처리 기준을 계산합니다. 원본과 평가용 실제값은 바꾸지 않습니다. 공휴일 분리 후보에서는 일반 요일 패턴에서 공휴일을 제외합니다. 과거 검증에서 유리한 후보가 선택되므로 처리가 적용되지 않을 수도 있습니다.')
                with st.expander('자동 데이터 분석·보조 예측 내역'):
                    st.dataframe(pd.DataFrame(report.get('데이터분석',[])),use_container_width=True)
                    st.dataframe(pd.DataFrame(report.get('보조예측방법',[])),use_container_width=True)
                    st.caption('온도 등 미래 변수는 추정값입니다. 정확한 날씨·일정이 필요하면 실제 예보/예정 정보를 제공하세요. 국가별 공휴일은 선택한 달력으로 자동 생성합니다. 임시공휴일·지역 행사·운영 중단은 사용 중인 달력 버전이나 별도 예정 정보에 따라 반영 여부가 달라집니다.')
                audit=pd.DataFrame(report['항목선택_상세'])
                audit['항목']=audit['항목'].map(friendly_feature)
                with st.expander('컬럼 사용·제외 내역'):
                    st.dataframe(audit,use_container_width=True,hide_index=True)
                    st.caption('최종 재학습의 선택 결과입니다. 관련성 점수는 인과관계가 아닙니다.')
                st.caption(f'표시 기간: {shown["예측시각"].min():%Y-%m-%d %H:%M} ~ {shown["예측시각"].max():%Y-%m-%d %H:%M}. 기록 간격에 맞는 시각만 표시합니다.')
                st.subheader('선택한 기간의 미래 예측')
                future_group=st.selectbox('미래 예측을 볼 대상',list(shown['구분'].unique()),key='future_display_group') if shown['구분'].nunique()>1 else shown['구분'].iloc[0]
                future_view=shown.loc[shown['구분']==future_group]
                st.line_chart(future_view.set_index('예측시각')['예측값'],color='#16a5d8',height=260)
                with st.expander('미래 예측값 표 보기'):
                    st.dataframe(easy.head(500).round(2),use_container_width=True,hide_index=True)
                    st.caption('표는 최대 500행 미리보기이며 다운로드에는 전체 결과를 포함합니다.')
                st.metric('과거 기록을 맞혀봤을 때의 평균 차이',f'{report["최종테스트"]["MAE"]:.2f}'+value_unit)
                st.caption('작을수록 잘 맞았습니다. 미래의 정확도를 보장하는 수치는 아닙니다. 예측값의 소수는 예상 수준을 뜻합니다.')
                for note in report['알림']:
                    st.warning(note)
                with st.expander('어떤 예측 방법을 비교했나요?'):
                    st.dataframe(friendly_metrics(ft),use_container_width=True,hide_index=True)
                    st.json(report)
                st.download_button('날짜·시간별 예상 값 엑셀로 저장',data=_excel_bytes(easy).getvalue(),file_name='future_predictions.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                st.download_button('날짜·시간별 예상 값 CSV로 저장',easy.to_csv(index=False).encode('utf-8-sig'),'future_predictions.csv','text/csv')
                mem=io.BytesIO();joblib.dump(fbundle,mem)
                zb=io.BytesIO()
                with zipfile.ZipFile(zb,'w',zipfile.ZIP_DEFLATED) as z:
                    z.writestr('future_predictions.csv',easy.to_csv(index=False).encode('utf-8-sig'))
                    if period_comparison is not None:
                        z.writestr('forecast_period_comparison.csv',period_comparison.to_csv(index=False).encode('utf-8-sig'))
                    z.writestr('comparison.csv',ft.to_csv(index=False).encode('utf-8-sig'))
                    z.writestr('selected_columns.csv',audit.to_csv(index=False).encode('utf-8-sig'))
                    z.writestr('heldout_predictions.csv',test.to_csv(index=False).encode('utf-8-sig'))
                    z.writestr('report.json',json.dumps(report,ensure_ascii=False,indent=2))
                    if fbundle.get('auxiliary_plan') is not None:
                        z.writestr('estimated_future_inputs.csv',fbundle['auxiliary_plan'].reset_index().to_csv(index=False).encode('utf-8-sig'))
                    z.writestr('forecast_model.joblib',mem.getvalue())
                with st.expander('모델과 평가 자료도 함께 보관하기'):
                    st.download_button('전체 결과 저장',zb.getvalue(),'forecast_results.zip','application/zip')
        except Exception as e:
            st.error(str(e))


render()
