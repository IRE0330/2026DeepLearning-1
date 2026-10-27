"""Compact, presentation-only views; no changes to fitted models or metrics."""
from html import escape
import numpy as np
import pandas as pd
import streamlit as st

CSS='''
<style>
.stApp {background:linear-gradient(145deg,#edf8ff 0%,#e3f2fc 55%,#f4fbff 100%);color:#17384f;}
[data-testid="stHeader"] {background:rgba(237,248,255,.94);}
.block-container {max-width:1180px;padding-top:2.2rem;padding-bottom:3rem;}
h1,h2,h3,h4 {color:#123c58 !important;letter-spacing:-.025em;}
[data-testid="stExpander"] {background:#ffffffc9;border:1px solid #cce2f0;border-radius:14px;}
[data-testid="stMetric"] {background:white;padding:16px 18px;border-radius:14px;border:1px solid #d5e8f3;}
[data-testid="stMetricLabel"],[data-testid="stMetricValue"] {color:#16486b;}
[data-testid="stFileUploader"] {background:#ffffffbd;border-radius:16px;padding:8px;}
[data-testid="stMultiSelect"] [data-baseweb="select"]>div {max-height:100px;overflow-y:auto;}
.result-card {background:white;border:1px solid #cce2f0;border-radius:18px;padding:20px 22px;margin-bottom:12px;min-height:162px;}
.card-eyebrow {font-size:12px;font-weight:700;color:#407491;letter-spacing:.06em;margin-bottom:8px;}
.card-title {font-size:20px;line-height:1.45;color:#123c58;font-weight:750;overflow-wrap:anywhere;}
.card-sub {font-size:13px;color:#526e81;line-height:1.65;margin-top:9px;}
.feature-chip {display:inline-block;background:#eaf5fc;color:#225778;padding:5px 9px;border-radius:7px;font-size:12px;margin:3px 4px 3px 0;}
[data-testid="stDataFrame"] {border-radius:12px;overflow:hidden;}
.stButton>button,.stDownloadButton>button {border-radius:10px;}
</style>
'''


def feature_groups(columns):
    grouped={}
    for c in columns:
        if c=='series':label='대상 구분'
        elif c.startswith('known::'):label='미래 예정 정보'
        elif c.startswith('past::'):label='추가 입력 정보'
        elif c.startswith(('lag_','rolling_')) or c in ('recent_change','seasonal_lag_mean'):label='과거값·이동 패턴'
        elif c in ('year','month','day','weekday','hour','minute','weekday_hour','day_of_year','week_of_year','is_weekend','is_month_start','is_month_end') or c.endswith(('_sin','_cos')) or any(k in c for k in ('holiday','day_off','bridge')):label='날짜·요일·공휴일'
        else:label='원본 입력 컬럼'
        grouped.setdefault(label,[]).append(c)
    return grouped


def model_components(model):
    from .adaptive_models import WindowModel,AveragedModel
    rows=[]
    def visit(m,window=None):
        if isinstance(m,WindowModel):return visit(m.estimator_,m.window)
        if isinstance(m,AveragedModel):
            for child in m.estimators_:visit(child,window)
            return
        leaf=m.named_steps['model'] if hasattr(m,'named_steps') else m
        fields=m.named_steps['select'].columns_ if hasattr(m,'named_steps') else []
        rows.append({'구성':'모델 '+str(len(rows)+1),'모델':type(leaf).__name__,
                     '방식':getattr(leaf,'method','일반 머신러닝'),'사용 컬럼 수':len(fields),
                     '학습 기간':'전체' if window is None else str(window)+'개 기록'})
    if model is not None:visit(model)
    return rows


def render_combination(model,columns,settings,friendly,pipeline=None):
    columns=list(dict.fromkeys(columns));groups=feature_groups(columns)
    left,right=st.columns([1,1])
    parts=str(model).split(' · ')
    if parts and (parts[0].startswith(('T','R','D','E','F','G','H','M','W')) and parts[0][1:].isdigit()):parts=parts[1:]
    title=' · '.join(parts[:2])
    if str(model).startswith('컬럼탐색'):title=' · '.join(parts[:2])
    with left:
        window=settings.get('학습기간_칸')
        sub='전체 학습 기록 사용' if window is None else ('구성 모델별 학습 기간' if not isinstance(window,(int,float)) else f'대상별 최근 {window:,}개 기록 사용')
        st.markdown(f'<div class="result-card"><div class="card-eyebrow">최종 선택 모델</div><div class="card-title">{escape(title)}</div><div class="card-sub">{escape(sub)}<br>{escape(str(model))}</div></div>',unsafe_allow_html=True)
    with right:
        chips=''.join('<span class="feature-chip">'+escape(str(friendly(c)))+'</span>' for c in columns[:8])
        if len(columns)>8:chips+=f'<span class="feature-chip">외 {len(columns)-8}개 · 아래 상세 보기</span>'
        brief=' + '.join(f'{k} {len(v)}개' for k,v in groups.items())
        st.markdown(f'<div class="result-card"><div class="card-eyebrow">최종 컬럼 조합 · {len(columns)}개</div><div class="card-sub">{escape(brief)}</div>{chips}</div>',unsafe_allow_html=True)
    components=model_components(pipeline)
    if len(components)>1:
        st.caption('최종 예측에 함께 사용된 구성 모델')
        st.dataframe(pd.DataFrame(components),hide_index=True)
    with st.expander('최종 컬럼 조합·모델 설정 전체 보기'):
        table=pd.DataFrame([{'분류':label,'컬럼':str(friendly(c)),'원래 컬럼명':c} for label,cols in groups.items() for c in cols])
        st.dataframe(table,hide_index=True,height=min(320,40+35*len(table)))
        st.json(settings)
    return groups


def render_actual_comparison(test,context="past"):
    st.subheader('설정 기간 평가 결과' if context=='future' else '과거 내부 평가 결과')
    names=list(test['구분'].unique())
    group=st.selectbox('평가할 대상',names,key='evaluation_group_'+context) if len(names)>1 else names[0]
    check=test.loc[test['구분']==group].copy().sort_values('예측시각')
    actual=check['실제값'].to_numpy(dtype=float);pred=check['예측값'].to_numpy(dtype=float)
    absolute=np.abs(actual-pred);denominator=float(np.abs(actual).sum())
    wape=float(absolute.sum()/denominator*100) if denominator else None
    sst=float(((actual-actual.mean())**2).sum())
    r2=1-float(((actual-pred)**2).sum())/sst if sst else None
    a,b,c=st.columns(3)
    a.metric('평균 오차 MAE',f'{absolute.mean():,.2f}')
    b.metric('이용량 대비 오차율 WAPE','계산 불가' if wape is None else f'{wape:.2f}%')
    c.metric('결정계수 R²','계산 불가' if r2 is None else f'{r2:.3f}')
    st.caption(f"{group} · {'설정 기간 평가' if context=='future' else '과거 내부 평가'} {check['예측시각'].min()} ~ {check['예측시각'].max()} · {len(check):,}개 기록. {'업로드한 정답과 일치한 기록 기준입니다.' if context=='future' else '설정한 미래 예측 기간의 성능이 아닙니다.'}")
    st.line_chart(check.set_index('예측시각')[['실제값','예측값']],color=['#275d85','#16a5d8'],height=320)
    st.caption('실제값은 짙은 파랑, 예측값은 하늘색입니다. R²는 정확도 백분율이 아닙니다.')
    with st.expander('비교한 실제값·예측값 표 보기'):
        check['차이']=pred-actual;check['절대차이']=absolute
        st.dataframe(check,hide_index=True,height=280)
        st.download_button('실제값·예측값 비교 CSV 저장',check.to_csv(index=False).encode('utf-8-sig'),'forecast_period_comparison.csv' if context=='future' else 'heldout_comparison.csv','text/csv',key='comparison_download_'+context)
    return check
