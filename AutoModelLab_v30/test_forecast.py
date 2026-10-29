import numpy as np
import pandas as pd
from forecast import forecast, normalize, recursive
from pandas.testing import assert_frame_equal

rng=np.random.default_rng(2)
n=180
t=pd.date_range('2026-10-01',periods=n,freq='min')
df=pd.concat([pd.DataFrame({'시각':t,'화장실':g,'대기인원':np.maximum(0,8+3*np.sin(np.arange(n)/12)+offset+rng.normal(0,.3,n))}) for g,offset in [('북',0),('남',3)]],ignore_index=True)
df.to_csv('samples/forecast_history.csv',index=False,encoding='utf-8-sig')
future,table,test,report,bundle=forecast(df,'시각','대기인원','화장실',1,30,['기준 모델','Ridge','Random Forest'],True)
assert len(future)==60
assert future['예측시각'].min()==t[-1]+pd.Timedelta(minutes=1)
assert future['예측시각'].max()==t[-1]+pd.Timedelta(minutes=30)
assert (future['예측값']>=0).all()
assert len(table)==3
assert report['테스트시점수_구분당']==30
# Predictions depend on supplied past, not observed future rows.
data=normalize(df,'시각','대기인원','화장실',1)
p1=recursive(bundle['pipeline'],data,100,10,1,True)
for p in data.values():
    p.loc[100:,'value']=99999
p2=recursive(bundle['pipeline'],data,100,10,1,True)
assert_frame_equal(p1,p2)
for bad in [pd.concat([df,df.iloc[[0]]]),df.drop(index=2)]:
    try:
        normalize(bad,'시각','대기인원','화장실',1)
        raise AssertionError('invalid data accepted')
    except ValueError:
        pass
f2,_,_,r2,_=forecast(df,'시각','대기인원','화장실',1,60,['기준 모델'],True)
assert len(f2)==120 and any('부족' in s for s in r2['알림'])
print('PASS: grouped horizons, timestamp boundaries, recursive no future values, invalid intervals/duplicates, validation coverage notice')
