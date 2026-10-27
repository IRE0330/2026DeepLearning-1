import numpy as np
import pandas as pd
from calendar_features import calendar_features
from forecast import row_at, forecast
from core import pipeline
from sklearn.linear_model import Ridge

assert calendar_features('2026-01-01','KR')['is_holiday']==1
assert calendar_features('2026-03-02','KR')['is_holiday']==1
assert calendar_features('2026-03-03','KR')['is_day_after_holiday']==1
assert calendar_features('2026-05-04','KR')['is_day_before_holiday']==1
assert calendar_features('2026-05-20','KR')['is_holiday']==0
assert calendar_features('2026-03-02',None)['is_holiday']==0
row=row_at(pd.Timestamp('2026-03-02'),list(range(24)),'A')
assert row['is_holiday']==1 and row['is_weekend']==0 and row['is_day_off']==1
X=pd.DataFrame({'date':pd.date_range('2025-01-01',periods=100,freq='D').astype(str),'x':np.arange(100)})
p=pipeline(Ridge(),('date',))
p.fit(X,np.arange(100))
assert any('holiday' in c for c in p.named_steps['types'].transform(X).columns)
t=pd.date_range('2025-01-01',periods=420,freq='D')
y=100+np.asarray([30*calendar_features(ts,'KR')['is_holiday']+10*(ts.dayofweek>=5) for ts in t])
d=pd.DataFrame({'date':t,'value':y})
f,table,test,report,_=forecast(d,'date','value',None,1440,7*1440,['Ridge','요일·시간 패턴','Fourier 계절 회귀'],optimize=True,search_budget=6,holiday_country='KR')
assert len(table)>=6 and report['공휴일국가']=='KR'
assert 'is_holiday' in [r['항목'] for r in report['항목선택_상세']]
print('PASS: national/substitute holiday, before/after, weekend separation, disable calendar, tabular and future pipelines')
