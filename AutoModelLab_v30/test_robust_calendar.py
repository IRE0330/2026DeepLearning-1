import io
import joblib
import numpy as np
import pandas as pd
from direct_models import DirectCalendarModel
from robust_targets import treat_targets
from forecast import row_at,forecast

t=pd.date_range('2024-01-01 12:00',periods=80,freq='7D')
X=pd.DataFrame([row_at(ts,list(range(30)),'a') for ts in t])
X['is_holiday']=0;X.loc[::10,'is_holiday']=1
y=np.where(X.is_holiday,1000.,10.)
y[17]=5000.;original=y.copy()
clipped,w,audit=treat_targets(X,y,'clip')
assert np.array_equal(y,original)
assert clipped[17]<50 and audit['의심값수']==1
assert np.all(clipped[X.is_holiday==1]==1000.)
untouched,w,audit=treat_targets(X,y,'downweight')
assert np.array_equal(untouched,y) and w[17]==.1
small,_,_=treat_targets(X.iloc[:5],y[:5],'clip')
assert np.array_equal(small,y[:5])

# Changing holiday observations cannot change a non-holiday prediction in split candidates.
y=np.where(X.is_holiday,1000.,10.);y2=np.where(X.is_holiday,10000.,10.)
future=X.iloc[[1,0]].copy()
for method in ['profile','tree']:
    m=DirectCalendarModel(method=method,separate_holidays=True,robust_mode='clip').fit(X,y)
    m2=DirectCalendarModel(method=method,separate_holidays=True,robust_mode='clip').fit(X,y2)
    assert np.isclose(m.predict(future)[0],10.)
    assert np.isclose(m.predict(future)[0],m2.predict(future)[0])
    assert m2.predict(future)[1]>m.predict(future)[1]
    mem=io.BytesIO();joblib.dump(m,mem);mem.seek(0)
    assert np.allclose(m.predict(future),joblib.load(mem).predict(future))

# End-to-end candidate selection and report; input and raw evaluation targets remain intact.
t=pd.date_range('2025-01-01',periods=480,freq='h')
y=20+10*np.sin(t.hour.to_numpy()*2*np.pi/24);y[410]=10000.
d=pd.DataFrame({'t':t,'y':y});before=d.copy(deep=True)
f,tab,test,r,b=forecast(d,'t','y',None,60,48*60,['요일·시간 패턴'],optimize=True,search_budget=1)
assert any(label.startswith('R') for label in tab['모델'])
assert r['프로그램버전']=='2.9-sky-ui'
pd.testing.assert_frame_equal(d,before)
assert test['실제값'].max()==10000.
assert '이상치공휴일처리' in r
print('PASS: train-only robust clipping/weights, sparse groups retained, holiday isolation, raw held-out extreme retained, candidate selection, serialization')
