import io
import joblib
import numpy as np
import pandas as pd
from forecast import row_at,forecast
from weekly_reference import WeeklyReferenceModel
from direct_models import DirectCalendarModel

t=pd.date_range('2025-01-01',periods=24*42,freq='h')
y=np.arange(len(t),dtype=float)
X=pd.DataFrame([row_at(ts,list(range(30)),'a') for ts in t])
future_t=pd.date_range(t[-1]+pd.Timedelta(hours=1),periods=24*10,freq='h')
future=pd.DataFrame([row_at(ts,list(range(30)),'a') for ts in future_t])
for statistic in ['mean','median']:
    model=WeeklyReferenceModel(statistic=statistic).fit(X,y)
    pred=model.predict(future)
    expected=[]
    hist=dict(zip(t,y))
    for ts in future_t:
        delta=max(1,int(np.ceil((ts-t[-1])/pd.Timedelta(days=7))))
        refs=[hist[ts-pd.Timedelta(days=7*(delta+k))] for k in range(4)]
        expected.append(np.mean(refs) if statistic=='mean' else np.median(refs))
    assert np.allclose(pred,expected)
    changed=future.copy();changed['lag_1']=999999
    assert np.allclose(pred,model.predict(changed))
    b=io.BytesIO();joblib.dump(model,b);b.seek(0)
    assert np.allclose(pred,joblib.load(b).predict(future))

# Median profile resists a rare high observation and directly minimizes L1 within a cell.
cell=X.iloc[:9].copy()
for c in ['weekday','hour','minute','is_holiday']:cell[c]=0
values=np.array([10.]*8+[1000.])
median=DirectCalendarModel(statistic='median',half_life_days=1e9).fit(cell,values)
mean=DirectCalendarModel(statistic='mean',half_life_days=1e9).fit(cell,values)
assert np.isclose(median.predict(cell.iloc[[0]])[0],10.)
assert np.mean(abs(values-median.predict(cell)))<np.mean(abs(values-mean.predict(cell)))
mae=DirectCalendarModel(method='mae_boost',separate_holidays=True).fit(X,y)
assert next(iter(mae.models_.values())).named_steps['model'].loss=='absolute_error'

n=480;d=pd.DataFrame({'time':t[:n],'value':20+5*np.sin(np.arange(n)*2*np.pi/24)})
_,table,test,report,_=forecast(d,'time','value',None,60,24*60,['요일·시간 패턴'],optimize=True,search_budget=1)
assert report['검증구간수']==4
assert report['검증시점수_구분당']==[24]*4
assert any('최근 4주 같은 시간 평균' in v for v in table['모델'])
assert any('최근 4주 같은 시간 중앙값' in v for v in table['모델'])
assert any('MAE 중심 학습' in v for v in table['모델'])
folds=report['검증구간']
for i,f in enumerate(folds):
    assert pd.Timestamp(f['학습종료'])<pd.Timestamp(f['검증시작'])
    assert pd.Timestamp(f['검증종료'])<d['time'].iloc[int(n*.8)]
    if i:assert pd.Timestamp(folds[i-1]['검증종료'])<pd.Timestamp(f['검증시작'])
assert len(test)==24
print('PASS: exact four-week mean/median, fixed origin beyond seven days, no prediction feedback, L1 learner, spread non-overlapping folds, serialization')
