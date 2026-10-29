"""Conservative schema inference; no target semantics or paid services."""
import re
import numpy as np
import pandas as pd


def parse_dates(s, name='', dayfirst=None):
    if pd.api.types.is_datetime64_any_dtype(s):return pd.to_datetime(s,errors='coerce')
    name=str(name).lower()
    if pd.api.types.is_numeric_dtype(s):
        v=pd.to_numeric(s,errors='coerce')
        # Never interpret counts or hours as nanoseconds since 1970.
        if not any(w in name for w in ('date','time','시각','일시','날짜','일자')):return None
        valid=v.dropna()
        if len(valid)==0:return None
        med=valid.median()
        if valid.between(19000101,21001231).all():
            return pd.to_datetime(v.astype('Int64').astype(str),format='%Y%m%d',errors='coerce')
        if 20000<=med<=80000:return pd.to_datetime(v,unit='D',origin='1899-12-30',errors='coerce')
        for lo,hi,unit in [(1e9,5e9,'s'),(1e12,5e12,'ms'),(1e15,5e15,'us'),(1e18,5e18,'ns')]:
            if lo<=med<=hi:return pd.to_datetime(v,unit=unit,errors='coerce')
        return None
    text=s.dropna().astype(str)
    if len(text)==0:return None
    # Require date-like syntax. A free-form ID or numeric string is not a date.
    if text.str.contains(r'\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{4}년',regex=True).mean()<.9:return None
    slash=text.str.extract(r'^(\d{1,2})/(\d{1,2})/(\d{4})')
    if dayfirst is None:
        dayfirst=not bool((pd.to_numeric(slash[1],errors='coerce')>12).any())
    return pd.to_datetime(s,errors='coerce',format='mixed',dayfirst=dayfirst)


def prepare_time(df):
    options=[]
    for c in df:
        d=parse_dates(df[c],c)
        if d is not None and d.notna().mean()>=.95:
            score=(0 if pd.api.types.is_numeric_dtype(df[c]) else 2)+int(d.nunique()>1)
            score+=3*int(any(w in str(c).lower() for w in ('date','time','시각','일시','날짜','일자')))
            score+=2*int((d.dropna()!=d.dropna().dt.normalize()).any())
            score-=4*int(any(w in str(c).lower() for w in ('종료','end')))
            options.append((score,c,d))
    if not options:raise ValueError('날짜·시간 항목을 자동으로 찾지 못했습니다. 날짜 형식을 확인해 주세요. 예: 2026-10-24 14:00 또는 날짜 열 + Hour 열.')
    _,source,d=max(options,key=lambda x:x[0])
    sources=[source]
    if d.notna().any() and (d.dropna()==d.dropna().dt.normalize()).all():
        for c in df:
            if c==source or not any(w in str(c).lower() for w in ('hour','시간','시각')):continue
            v=pd.to_numeric(df[c],errors='coerce')
            if v.notna().all() and v.between(0,23).all() and (v%1==0).all():
                d=d+pd.to_timedelta(v,unit='h');sources.append(c);break
    if d.isna().any():raise ValueError('자동으로 찾은 날짜 항목에 읽을 수 없는 값이 있습니다. 빈 값이나 날짜 형식을 정리해 주세요.')
    out=df.copy()
    generated='자동 날짜·시간'
    while generated in out:generated+='_' 
    out[generated]=d
    return out,generated,sources


def infer_group(df,time_col,target):
    if not df[time_col].duplicated().any():return None
    ranked=[]
    n=len(df)
    for c in df:
        if c in (time_col,target) or df[c].isna().any():continue
        k=df[c].nunique()
        if k<2 or k>min(5000,n//80):continue
        sizes=df.groupby(c,dropna=False).size()
        if sizes.min()<80 or df.duplicated([c,time_col]).any():continue
        hint=any(w in str(c).lower() for w in ('id','code','구분','위치','종류','매장','센서','화장실'))
        ranked.append((int(hint),-k,c))
    return max(ranked,key=lambda x:x[:2])[2] if ranked else None


def automatic_exclusions(df,time_col,target,group,time_sources):
    rows=[]
    for c in df:
        if c==target:reason='예측할 값'
        elif c==time_col:reason='날짜·시간으로 사용'
        elif c==group:reason='대상 구분으로 사용'
        elif c in time_sources:reason='날짜·시간으로 합쳐 사용'
        elif df[c].isna().mean()>.95:reason='빈 값이 너무 많아 제외'
        elif df[c].nunique(dropna=True)<=1:reason='변하지 않는 항목이라 제외'
        else:reason='미래 값이 제공되지 않아 기본 미래 예측에서 제외'
        rows.append({'항목':str(c),'자동 처리':reason})
    return rows
