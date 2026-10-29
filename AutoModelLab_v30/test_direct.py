import io
import joblib
import numpy as np
import pandas as pd
from direct_models import DirectCalendarModel
from forecast import row_at, normalize, recursive

t=pd.date_range('2025-01-01',periods=24*70,freq='h')
y=10+5*(t.dayofweek.to_numpy()<5)
y=y.astype(float);y[-24*21:]+=20
X=pd.DataFrame([row_at(ts,list(range(30)),'a') for ts in t])
for method in ('profile','tree'):
    for calibrate in (False,True):
        p=DirectCalendarModel(method=method,calibrate=calibrate).fit(X,y)
        future=X.tail(24).copy();changed=future.copy()
        for c in changed:
            if c.startswith(('lag_','rolling_')) or c=='recent_change':changed[c]=999999
        assert np.allclose(p.predict(future),p.predict(changed))
        assert not any(c.startswith('lag_') for c in p.named_steps['select'].columns_)
        b=io.BytesIO();joblib.dump(p,b);b.seek(0)
        assert np.allclose(p.predict(future),joblib.load(b).predict(future))
        data=normalize(pd.DataFrame({'t':t,'y':y,'g':'a'}),'t','y','g',60)
        out=recursive(p,data,len(t),24,60)
        expected=pd.DataFrame([row_at(t[-1]+pd.Timedelta(hours=i),y.tolist(),'a') for i in range(1,25)])
        assert np.allclose(out['예측값'],p.predict(expected))
recent=DirectCalendarModel(half_life_days=7).fit(X,y)
slow=DirectCalendarModel(half_life_days=1000).fit(X,y)
assert recent.predict(X.tail(24)).mean()>slow.predict(X.tail(24)).mean()
print('PASS: direct inputs independent of target lags, recent weights, calibration, audit, serialization')
