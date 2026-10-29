import io
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from calendar_features import calendar_features
from direct_models import DirectCalendarModel
from forecast import row_at, forecast

# Long weekends include weekends on either side; country-disabled calendar still supports weekends.
cf=calendar_features('2026-03-02 15:00','KR')
assert cf['is_holiday']==1 and cf['day_off_run_length']>=3
assert cf['day_off_run_position']>=3 and cf['days_to_holiday']==0
assert cf['holiday_hour'].endswith('|15')
assert calendar_features('2026-03-02',None)['is_holiday']==0

t=pd.date_range('2025-01-01',periods=24*40,freq='h')
X=pd.DataFrame([row_at(ts,list(range(30)),'a') for ts in t])
# Artificial holiday identities test that the model distinguishes event categories.
X['is_holiday']=0;X['holiday_name']='공휴일 아님'
X.loc[:47,['is_holiday','holiday_name']]=[1,'행사A']
X.loc[48:95,['is_holiday','holiday_name']]=[1,'행사B']
y=np.where(X.holiday_name=='행사A',100.,np.where(X.holiday_name=='행사B',300.,20.))
m=DirectCalendarModel(method='event_profile',separate_holidays=True,half_life_days=365).fit(X,y)
future=X.iloc[[0,48,100]].copy()
pred=m.predict(future)
assert pred[0]<pred[1] and np.isclose(pred[2],20.)
future.loc[future.index[0],'holiday_name']='未観測'
assert np.isfinite(m.predict(future)).all()
for method in ('event_profile','tree','mae_boost'):
    model=clone(DirectCalendarModel(method=method,separate_holidays=True,calibrate=True,calibration_by_hour=True)).fit(X,y)
    assert model.correction_keys_==['series','weekday','is_holiday','hour']
    mem=io.BytesIO();joblib.dump(model,mem);mem.seek(0)
    assert np.allclose(model.predict(future),joblib.load(mem).predict(future))

d=pd.DataFrame({'t':t[:480],'y':20+5*np.sin(np.arange(480)*2*np.pi/24)})
before=d.copy(deep=True)
f,table,test,report,bundle=forecast(d,'t','y',None,60,24*60,['요일·시간 패턴'],optimize=True,search_budget=1)
assert sum(label.startswith('H') for label in table['모델'])==4
assert not any('연휴·혼잡 보정' in warning and '제외' in warning for warning in report['알림'])
assert report['프로그램버전']=='2.9-sky-ui' and len(report['예측기간달력'])>=1
pd.testing.assert_frame_equal(d,before)
print('PASS: extended calendar, distinct holidays/fallback, hourly calibration, serialization, all four new candidates compete, raw data unchanged')
