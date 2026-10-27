"""Evaluate frozen future predictions against separately uploaded answers."""
import numpy as np
import pandas as pd
import streamlit as st


def align_answers(shown, answers, time_col, value_col, group_col=None, date_col=None):
    times=answers[time_col].astype(str)
    if date_col: times=answers[date_col].astype(str)+' '+times
    truth=pd.DataFrame({'예측시각':pd.to_datetime(times,errors='coerce'),
                        '실제값':pd.to_numeric(answers[value_col],errors='coerce')})
    if truth['예측시각'].isna().any(): raise ValueError('정답 파일에 읽을 수 없는 날짜·시간이 있습니다.')
    if not np.isfinite(truth['실제값'].to_numpy(dtype=float)).all(): raise ValueError('정답에 빈 값 또는 숫자가 아닌 값이 있습니다. 0으로 바꾸지 않습니다.')
    if group_col:
        if answers[group_col].isna().any(): raise ValueError('정답의 대상 구분에 빈 값이 있습니다.')
        truth['구분']=answers[group_col].astype(str).values
    elif shown['구분'].nunique()==1: truth['구분']=str(shown['구분'].iloc[0])
    else: raise ValueError('여러 대상을 예측한 경우 정답의 대상 구분 컬럼을 선택하세요.')
    keys=['구분','예측시각']
    if truth.duplicated(keys).any(): raise ValueError('정답에 동일 대상·시각이 중복됩니다. 중복을 정리하세요.')
    forecast=shown[['구분','예측시각','예측값']].copy()
    forecast['구분']=forecast['구분'].astype(str)
    forecast['예측시각']=pd.to_datetime(forecast['예측시각'])
    if forecast.duplicated(keys).any(): raise ValueError('예측 대상·시각이 중복됩니다.')
    joined=forecast.merge(truth,on=keys,how='left',validate='one_to_one')
    missing=joined.loc[joined['실제값'].isna(),keys]
    matched=joined.dropna(subset=['실제값']).copy()
    matched['차이']=matched['예측값']-matched['실제값']
    matched['절대차이']=matched['차이'].abs()
    return matched,missing


def render_future_evaluation(shown,target,group_name,loader,renderer):
    st.subheader('설정한 예측 기간의 실제값 비교')
    st.caption(f"평가할 기간: {shown['예측시각'].min()} ~ {shown['예측시각'].max()} · 정답은 학습·모델 선택에 사용하지 않습니다.")
    upload=st.file_uploader('정답 파일 추가 (CSV·엑셀)',type=['csv','xlsx','xls'],key='answer_only_upload')
    if upload is None:
        st.info('이 기간의 실제값 파일을 넣으면 그래프와 MAE·WAPE·R²가 표시됩니다. 아래 과거 내부 평가와 구분됩니다.')
        return None
    try:
        answers,_=loader(upload,'answer_only')
        cols=list(answers.columns)
        def pick(label,preferred,key):
            return st.selectbox(label,cols,index=next((cols.index(x) for x in preferred if x in cols),0),key=key)
        time_col=pick('정답의 날짜·시간 컬럼',['일시','예측시각','datetime','날짜'], 'answer_time')
        separate=st.checkbox('날짜와 시간이 별도 컬럼에 있음',value='날짜' in cols and '시간' in cols,key='answer_split')
        date_col=None
        if separate:
            date_col=pick('정답의 날짜 컬럼',['날짜','일자'],'answer_date')
            time_col=pick('정답의 시간 컬럼',['시간'],'answer_clock')
        value_col=pick('정답의 실제값 컬럼',[target,'실제값'],'answer_value')
        options=['없음']+cols
        group_col=st.selectbox('정답의 대상 구분 컬럼',options,index=next((options.index(x) for x in [group_name,'구분'] if x in cols),0),key='answer_group')
        matched,missing=align_answers(shown,answers,time_col,value_col,None if group_col=='없음' else group_col,date_col)
        st.caption(f'예측 {len(shown):,}건 중 정답 일치 {len(matched):,}건 · 정답 없는 기록 {len(missing):,}건')
        if len(missing):
            st.warning('일부 예측에 정답이 없습니다. 아래 성능은 일치한 기록만 평가한 부분 결과입니다.')
            with st.expander('정답이 없는 날짜·대상'): st.dataframe(missing,hide_index=True)
        if matched.empty:
            st.error('일치하는 날짜·시간·대상이 없습니다. 기간과 구분 값을 확인하세요.')
            return None
        renderer(matched,context='future')
        return matched
    except Exception as exc:
        st.error(str(exc))
        return None
