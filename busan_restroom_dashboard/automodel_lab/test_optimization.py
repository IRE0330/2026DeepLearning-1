import io
import joblib
import numpy as np
import pandas as pd
from forecast import forecast, normalize, recursive, row_at
from core import compare
from auxiliary import auxiliary_plan, project_column
from search_space import make_trials

rng=np.random.default_rng(17)
# Time-influenced covariate and target, with arbitrary field names.
n=240
t=pd.date_range('2026-10-01',periods=n,freq='h')
weather=10+5*np.sin(2*np.pi*t.hour.to_numpy()/24)+rng.normal(0,.1,n)
y=2*weather+8*(t.dayofweek.to_numpy()>=5)+rng.normal(0,.3,n)
df=pd.DataFrame({'recorded_at':t,'reading':y,'weather':weather,'noise':rng.normal(0,1,n),'constant':1,'code':['key'+str(i) for i in range(n)]})
f,tab,test,report,bundle=forecast(df,'recorded_at','reading',None,60,6*60,['Ridge','Random Forest'],auto_search=True,optimize=True,search_budget=12,auto_covariates=True,past_columns=('weather','noise','constant','code'))
assert len(tab)>=12,(len(tab),report['알림'])
assert report['검증구간수']==4 and len(f)==6
assert len(set(tab['설정값']))>1
assert len(set(tab['모델'].str.extract(r'(25|50|75)%')[0].dropna()))>=2
assert report['자동보조예측']
assert 'constant' not in report['과거참고항목'] and 'code' not in report['과거참고항목']
assert 24 in report['지연간격_칸']
row=row_at(pd.Timestamp('2026-10-24 14:00'),list(range(40)),'X')
assert row['is_weekend']==1 and row['weekday']==5
assert 'hour_sin' in row and 'rolling_mean_12' in row
# Auxiliary scenario is derived exclusively from pre-origin data.
data=normalize(df,'recorded_at','reading',None,60,['weather','noise'])
plan1,_=auxiliary_plan(data,140,6,60,('weather','noise'))
data['전체'].loc[140:,'raw::weather']=99999
plan2,_=auxiliary_plan(data,140,6,60,('weather','noise'))
assert np.allclose(plan1['weather'],plan2['weather'])
# Winning saved pipeline survives serialization with expanded date features.
mem=io.BytesIO();joblib.dump(bundle,mem);mem.seek(0)
restored=joblib.load(mem)
X=pd.DataFrame([row_at(t[-1]+pd.Timedelta(hours=1),y.tolist(),'전체',bundle['lags'])])
for c in report['과거참고항목']:X['past::'+c]=0.
assert np.allclose(bundle['pipeline'].predict(X),restored['pipeline'].predict(X))
# General table pipeline optimizes the same feature/config search.
g=pd.DataFrame({'x':rng.normal(size=200),'z':rng.normal(size=200)})
g['y']=5*g.x+rng.normal(size=200)
b,table,out,rep=compare(g,'y',['x','z'],selected_models=['Ridge','Random Forest'],auto_search=True,optimize=True,search_budget=12)
assert len(table)==12 and rep['자동최적화']
# Short and long requests have exact user-requested timestamps and honest validation coverage.
assert f['예측시각'].min()==t[-1]+pd.Timedelta(hours=1)
assert f['예측시각'].max()==t[-1]+pd.Timedelta(hours=6)
print('PASS: joint hyperparameter/feature search, multiple time folds, weekday/calendar/seasonal lags, auxiliary forecasts without future leakage, serialization, exact future dates')
