import io
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from residual_calendar import ResidualCalendarModel
from forecast import row_at,forecast
from subset_search import search_subsets

t=pd.date_range('2025-01-01',periods=24*40,freq='h')
y=20+4*np.sin(t.hour.to_numpy()*2*np.pi/24)+np.arange(len(t))*.01
X=pd.DataFrame([row_at(ts,list(range(30)),'a') for ts in t])
for learner in ('ridge','hgb'):
    for pack in ('basic','extended'):
        m=clone(ResidualCalendarModel(learner=learner,feature_set=pack)).fit(X,y)
        assert len(m.oof_ranges_)==3
        assert all(pd.Timestamp(r['학습종료'])<pd.Timestamp(r['오차시작']) for r in m.oof_ranges_)
        changed=X.tail(24).copy()
        for c in changed:
            if c.startswith(('lag_','rolling_')) or c in ('recent_change','seasonal_lag_mean'):changed[c]=999999
        assert np.allclose(m.predict(X.tail(24)),m.predict(changed))
        b=io.BytesIO();joblib.dump(m,b);b.seek(0)
        assert np.allclose(m.predict(changed),joblib.load(b).predict(changed))

# Pair moves cross a barrier a one-column local search cannot cross.
def interaction(c):
    return 0 if set(c)=={'id','x','y'} else 1 if set(c)=={'id','x','y','z','w'} else 5
cols,loss,trace=search_subsets(['id','x','y','z','w'],['x','z','y','w','id'],['id'],interaction,24)
assert loss==0 and set(cols)=={'id','x','y'}
assert any(r['조작']=='두 컬럼 제거' and r['갱신'] for r in trace)

d=pd.DataFrame({'t':t[:240],'y':y[:240]})
_,table,_,report,_=forecast(d,'t','y',None,60,6*60,['요일·시간 패턴'],optimize=True,search_budget=1)
assert sum(s.startswith('E') for s in table['모델'])==4
assert sum(s.startswith('F') for s in table['모델'])==4
assert report['프로그램버전']=='2.9-sky-ui'
print('PASS: strictly past-only residual labels, lag independence, both learners and feature packs, clone/serialization, pair search, all four residual candidates compete')
