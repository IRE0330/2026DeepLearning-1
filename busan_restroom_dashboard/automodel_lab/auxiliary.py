"""Forecast unavailable covariates from the origin's past only."""
import numpy as np
import pandas as pd


def _numeric_predict(method,t,y,future):
    clean=pd.to_numeric(y,errors='coerce').replace([np.inf,-np.inf],np.nan).ffill().bfill().fillna(0).to_numpy()
    if method=='last':return np.repeat(clean[-1],len(future))
    if method=='median':return np.repeat(np.median(clean[-min(48,len(clean)):]),len(future))
    if method=='trend':
        v=clean[-min(48,len(clean)):]
        slope,intercept=np.polyfit(np.arange(len(v)),v,1)
        pred=intercept+slope*np.arange(len(v),len(v)+len(future))
        span=max(np.std(clean)*4,np.ptp(clean),1.)
        return np.clip(pred,clean.min()-span,clean.max()+span)
    hist=pd.DataFrame({'value':clean,'weekday':t.dt.dayofweek.to_numpy(),'hour':t.dt.hour.to_numpy(),'minute':t.dt.minute.to_numpy()})
    keys=['hour','minute'] if method=='daily' else ['weekday','hour','minute']
    profiles=hist.groupby(keys)['value'].median()
    fallback=float(np.median(clean))
    return np.asarray([profiles.get(tuple(getattr(ts,k if k!='weekday' else 'dayofweek') for k in keys),fallback) for ts in future])


def project_column(times, values, future_times):
    times=pd.Series(pd.to_datetime(times)).reset_index(drop=True)
    values=pd.Series(values).reset_index(drop=True)
    if pd.api.types.is_numeric_dtype(values):
        cut=max(12,int(len(values)*.8))
        methods=['last','median','trend']
        span=times.iloc[-1]-times.iloc[0]
        if span>=pd.Timedelta(days=2):methods.append('daily')
        if span>=pd.Timedelta(days=14):methods.append('weekly')
        if cut<len(values) and pd.to_numeric(values.iloc[cut:],errors='coerce').notna().all():
            losses={m:np.mean(np.abs(_numeric_predict(m,times.iloc[:cut],values.iloc[:cut],times.iloc[cut:])-values.iloc[cut:].to_numpy())) for m in methods}
            chosen=min(losses,key=losses.get)
        else:chosen='median'
        pred=_numeric_predict(chosen,times,values,pd.DatetimeIndex(future_times))
        return pred,{'방법':chosen,'설명':'과거 내부 검증으로 보조 예측 방법 선택'}
    clean=values.fillna('(missing)').astype(str)
    counts=clean.value_counts()
    mode=counts.index[0] if len(counts) else '(missing)'
    h=pd.DataFrame({'value':clean,'weekday':times.dt.dayofweek,'hour':times.dt.hour})
    profiles=h.groupby(['weekday','hour'])['value'].agg(lambda s:s.mode().iloc[0])
    pred=[profiles.get((ts.dayofweek,ts.hour),mode) for ts in pd.DatetimeIndex(future_times)]
    return np.asarray(pred),{'방법':'요일·시간별 최빈값','설명':'과거 기록으로 추정한 범주이며 실제 예정 정보가 아님'}


def auxiliary_plan(data,start,steps,interval,columns):
    rows=[];audit=[]
    for name,p in data.items():
        future=pd.date_range(p.time.iloc[start-1]+pd.Timedelta(minutes=interval),periods=steps,freq=pd.Timedelta(minutes=interval))
        frame=pd.DataFrame({'__series':str(name),'__time':future})
        for c in columns:
            pred,info=project_column(p.time.iloc[:start],p['raw::'+str(c)].iloc[:start],future)
            frame[c]=pred
            audit.append({'대상':str(name),'항목':str(c),**info})
        rows.append(frame)
    return pd.concat(rows,ignore_index=True).set_index(['__series','__time']),audit
