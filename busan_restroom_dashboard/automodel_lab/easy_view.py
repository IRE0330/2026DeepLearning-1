"""Small presentation helpers independent from Streamlit."""
import math
import numpy as np
import pandas as pd


def suggest(columns, words, fallback=0):
    columns=list(columns)
    for word in words:
        for i,c in enumerate(columns):
            if word.lower() in str(c).lower():
                return i
    return min(fallback, max(0,len(columns)-1))


def time_values(df, column):
    return pd.to_datetime(df[column],errors='coerce')


def guess_interval(df, time_col, group=None):
    t=pd.DataFrame({'t':time_values(df,time_col)})
    t['g']=df[group].astype(str) if group else '전체'
    deltas=[]
    for _,p in t.groupby('g'):
        d=p.t.dropna().drop_duplicates().sort_values().diff().dt.total_seconds()/60
        deltas.extend(d[d>0].tolist())
    return max(1,min(10080,int(round(float(pd.Series(deltas).median()))))) if deltas else 1


def result_table(frame, value_col, label, group_label='구분'):
    ts=pd.to_datetime(frame['예측시각'])
    return pd.DataFrame({'날짜':ts.dt.strftime('%Y-%m-%d'), '시간':ts.dt.strftime('%H:%M:%S'),
                         group_label:frame['구분'].values, label:frame[value_col].values}).reset_index(drop=True)


def range_plan(last, start, end, interval):
    last,start,end=map(pd.Timestamp,(last,start,end))
    step=pd.Timedelta(minutes=interval)
    if start <= last:
        raise ValueError('미래 예측 시작은 마지막 기록보다 뒤여야 합니다. 과거 날짜는 위의 기록 보기에서 확인하세요.')
    if end < start:
        raise ValueError('끝나는 날짜·시간을 시작 이후로 선택해 주세요.')
    count=math.floor((end-last)/step)
    first=last+math.ceil((start-last)/step)*step
    if first>end:
        raise ValueError('선택한 기간에 기록 간격과 맞는 예측 시점이 없습니다. 기간을 늘려 주세요.')
    if count>10080:
        raise ValueError('마지막 기록부터 종료 시각까지 10,080개 시점을 넘습니다. 더 가까운 날짜를 선택하거나 기록을 더 큰 간격으로 집계해 주세요.')
    return count*interval,first,last+count*step


def friendly_metrics(table):
    return table.rename(columns={'MAE':'평균 오차 (작을수록 좋음)', 'RMSE':'큰 오차를 반영한 점수', 'R2':'설명력',
        'F1_macro':'범주별 균형 점수 (클수록 좋음)', 'Accuracy':'맞힌 비율', '학습초':'걸린 시간 (초)', '학습·평가초':'걸린 시간 (초)'})
