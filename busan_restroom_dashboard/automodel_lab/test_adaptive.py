import io
import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from adaptive_models import WindowModel, AveragedModel
from forecast import forecast, row_at

# Each series has its own recent window, even with interleaved input rows.
X = pd.DataFrame({'series': ['a','b'] * 10, 'x': range(20)})
y = np.arange(20.)
w = WindowModel(DummyRegressor(), 3).fit(X,y)
assert w.training_rows_ == 6
assert np.isclose(w.predict(X)[0], np.mean([14,16,18,15,17,19]))
blend = AveragedModel((WindowModel(DummyRegressor(), 3), WindowModel(DummyRegressor()))).fit(X,y)
buf=io.BytesIO();joblib.dump(blend,buf);buf.seek(0)
assert np.allclose(blend.predict(X), joblib.load(buf).predict(X))

n=2400
t=pd.date_range('2025-01-01', periods=n, freq='h')
y=20+8*np.sin(t.hour.to_numpy()*2*np.pi/24)+5*(t.dayofweek.to_numpy()<5)
y[-1200:] += 10
d=pd.DataFrame({'time':t, 'value':y})
args=dict(time_col='time', target='value', group=None, interval=60,
          duration_minutes=168*60, names=['요일·시간 패턴','Fourier 계절 회귀'],
          optimize=True, search_budget=2, nonnegative=True)
f,table,test,r,b=forecast(d,**args)
assert r['검증시점수_구분당']==[168]*4
assert len(r['검증구간'])==4
assert r['요청기간전체검증']
assert len(r['학습기간후보_칸'])>=2
assert any('모델 결합' in label for label in table['모델'])
assert len(f)==168
changed=d.copy();changed.loc[int(n*.8):,'value']=99999.
_,table2,_,r2,_=forecast(changed,**args)
assert r['선택모델']==r2['선택모델']
assert np.allclose(table.MAE,table2.MAE)
buf=io.BytesIO();joblib.dump(b,buf);buf.seek(0);loaded=joblib.load(buf)
row=pd.DataFrame([row_at(t[-1]+pd.Timedelta(hours=1),y.tolist(),'전체',b['lags'])])
assert np.allclose(b['pipeline'].predict(row),loaded['pipeline'].predict(row))
assert row.weekday_hour.iloc[0]
print('PASS: per-series windows, full 168-hour folds, validated ensemble, held-out isolation, saved forecast')
