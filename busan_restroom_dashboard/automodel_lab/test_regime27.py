import io
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from forecast import row_at,forecast
from regime_model import RegimeMAEModel

t=pd.date_range('2025-01-01',periods=24*35,freq='h')
X=pd.DataFrame([row_at(ts,list(range(30)),'a') for ts in t])
y=10+8*np.sin(t.hour.to_numpy()*2*np.pi/24)+np.where(t.dayofweek>=5,15.,0.)
original=y.copy()
for scope in ('daytype','daytype_hour'):
    m=clone(RegimeMAEModel(scope=scope)).fit(X,y)
    assert len(m.inner_ranges_)==3
    assert all(pd.Timestamp(r['학습종료'])<pd.Timestamp(r['검증시작']) for r in m.inner_ranges_)
    assert np.array_equal(y,original)
    for row in m.route_audit_:
        if row['개별선택']:
            assert row['검증일수']>=2 and row['선택MAE']<row['기준MAE']*.98
    future=X.tail(24).copy();a=m.predict(future)
    for c in future:
        if c.startswith(('lag_','rolling_')) or c in ('recent_change','seasonal_lag_mean'):future[c]=999999
    assert np.allclose(a,m.predict(future))
    future['is_holiday']=1
    assert np.isfinite(m.predict(future)).all()  # Sparse/unseen holiday falls back to global expert.
    mem=io.BytesIO();joblib.dump(m,mem);mem.seek(0)
    assert np.allclose(m.predict(future),joblib.load(mem).predict(future))

d=pd.DataFrame({'t':t[:180],'y':y[:180]})
_,table,_,report,_=forecast(d,'t','y',None,60,6*60,['요일·시간 패턴'],optimize=True,search_budget=1)
assert sum(s.startswith('G') for s in table['모델'])==2
assert report['프로그램버전']=='2.9-sky-ui'
print('PASS: chronological expert selection, sparse holiday fallback, raw targets intact, lag independence, serialization, both regime candidates compete')
