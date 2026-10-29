import io
import joblib
import numpy as np
import pandas as pd
from feature_selector import ColumnSelector
from core import compare, predict
from forecast import forecast, normalize, supervised, recursive

rng=np.random.default_rng(8)
n=240
x=rng.normal(size=n)
df=pd.DataFrame({'signal':x,'noise':rng.normal(size=n),'empty':np.nan,'constant':4,'row_code':[f'row{i}' for i in range(n)],'target':10*x+rng.normal(0,.1,n)})
s=ColumnSelector(mode='auto').fit(df.drop(columns='target'),df.target)
assert 'signal' in s.columns_ and 'empty' not in s.columns_ and 'constant' not in s.columns_ and 'row_code' not in s.columns_
assert s.transform(df).columns.tolist()==s.columns_
b,table,out,report=compare(df,'target',[c for c in df if c!='target'],selected_models=['Ridge','Random Forest'],auto_search=True,force_include=('signal',))
assert len(table)==4 and 'signal' in report['선택컬럼']
assert len(report['항목선택_상세'])==5
buf=io.BytesIO();joblib.dump(b,buf);buf.seek(0)
assert np.allclose(predict(b,df)['예측값'],predict(joblib.load(buf),df)['예측값'])
cf=df.copy();cf.target=np.where(x>0,'yes','no')
_,ct,_,_=compare(cf,'target',['signal','noise','constant'],'classification',selected_models=['Logistic Regression'],auto_search=True)
assert len(ct)==2
# Known-ahead exogenous signal cannot be recovered solely from autoregression.
nt=160
t=pd.date_range('2026-10-01',periods=nt,freq='min')
load=rng.normal(size=nt)
history=pd.DataFrame({'tick':t,'entity':'A','scheduled_load':load,'capacity':2.,'target':5*load+2+rng.normal(0,.1,nt)})
future=pd.DataFrame({'tick':pd.date_range(t[-1]+pd.Timedelta(minutes=1),periods=12,freq='min'),'entity':'A','scheduled_load':np.linspace(-2,2,12)})
f,ft,test,r,bundle=forecast(history,'tick','target','entity',1,12,['Ridge','Random Forest'],auto_search=True,past_columns=('capacity',),known_columns=('scheduled_load',),future_data=future,force_include=('scheduled_load',))
assert len(ft)==4 and len(f)==12
assert 'known::scheduled_load' in r['선택항목']
assert r['최종테스트']['MAE']<1
# With a frozen model, changing genuinely future-known schedule changes the output.
data=normalize(history,'tick','target','entity',1,['capacity','scheduled_load'])
plan=future.assign(__series='A',__time=future.tick).set_index(['__series','__time'])
p1=recursive(bundle['pipeline'],data,nt,12,1,False,('capacity',),('scheduled_load',),plan)
plan2=plan.copy();plan2['scheduled_load']+=20
p2=recursive(bundle['pipeline'],data,nt,12,1,False,('capacity',),('scheduled_load',),plan2)
assert not np.allclose(p1['예측값'],p2['예측값'])
# Past-only exogenous inputs cannot read held-out actual future values.
data=normalize(history,'tick','target','entity',1,['capacity','scheduled_load'])
p1=recursive(bundle['pipeline'],data,100,8,1,False,('capacity',),('scheduled_load',))
data['A'].loc[100:,'raw::capacity']=99999
p2=recursive(bundle['pipeline'],data,100,8,1,False,('capacity',),('scheduled_load',))
assert np.allclose(p1['예측값'],p2['예측값'])
try:
    forecast(history,'tick','target','entity',1,12,['Ridge'],known_columns=('scheduled_load',),future_data=future.iloc[:2])
    raise AssertionError('missing future information accepted')
except ValueError:
    pass
history.to_csv('samples/automl_history.csv',index=False,encoding='utf-8-sig')
future.to_csv('samples/automl_future_schedule.csv',index=False,encoding='utf-8-sig')
print('PASS: train-only selection, force inclusion, all-vs-auto regression/classification, persistence, future known features, frozen past features, missing future guard')
