import io
import joblib
import numpy as np
import pandas as pd
from forecast import forecast
from ts_models import NATIVE_NAMES
from core import compare
from model_catalog import catalog

n=24*42
t=pd.date_range('2026-01-01',periods=n,freq='h')
y=30+10*np.sin(2*np.pi*t.hour.to_numpy()/24)+20*(t.dayofweek.to_numpy()>=5)
df=pd.DataFrame({'timestamp':t,'count':y})
f,table,test,report,bundle=forecast(df,'timestamp','count',None,60,24*60,NATIVE_NAMES,optimize=True,search_budget=8)
assert len(table)>=8,(table,report['알림'])
assert report['최종테스트']['MAE']<.05,report['최종테스트']
assert report['선택모델'] # best native model can be persisted
b=io.BytesIO();joblib.dump(bundle,b);b.seek(0)
assert type(joblib.load(b)['pipeline']) is type(bundle['pipeline'])
assert len(f)==24
assert any('주간 반복' in x for x in table['모델'])
# Extra tabular regressors train and score under the existing joint-search engine.
rng=np.random.default_rng(5)
x=rng.normal(size=160)
g=pd.DataFrame({'x':x,'noise':rng.normal(size=160),'y':4*x+rng.normal(size=160)})
names=['Huber Regression','Bayesian Ridge','Bagging']
_,tt,_,rr=compare(g,'y',['x','noise'],selected_models=names,optimize=True,search_budget=6)
assert len(tt)==6,(tt,rr['알림'])
print('PASS: all six native time candidates, new regression models, weekly-pattern held-out accuracy, saved winner')
