import io
import joblib
import numpy as np
import pandas as pd
from subset_search import search_subsets
from forecast import forecast
from core import compare

# Addition and removal must use actual callback scores, preserve mandatory fields,
# and handle an initially weak feature that helps in combination.
def loss(columns):
    return (0 if 'a' in columns and 'b' in columns else 10)+(5 if 'noise' in columns else 0)+(20 if 'junk' in columns else 0)
cols,mae,trace=search_subsets(['id','a','b','noise','junk'],['a','noise','id','b','junk'],['id'],loss,14)
assert set(cols)=={'id','a','b'} and mae==0
assert any(r['조작'] in ('추가','두 컬럼 추가','교체') and r['갱신'] for r in trace)
assert any(r['조작']=='제거' and r['갱신'] for r in trace)
assert all('id' in r['사용항목'] for r in trace)
assert len(trace)<=14

n=240;t=pd.date_range('2025-01-01',periods=n,freq='h')
d=pd.DataFrame({'t':t,'y':20+8*np.sin(np.arange(n)*2*np.pi/24)})
args=dict(time_col='t',target='y',group=None,interval=60,duration_minutes=6*60,names=['Ridge'],optimize=True,search_budget=1)
f,table,test,r,b=forecast(d,**args)
trace1=r['컬럼추가제거탐색']
assert trace1 and len(trace1)<=24
assert all(v['모델']=='Ridge' for v in trace1)
assert any(v.get('조작') in ('추가','제거') for v in trace1)
changed=d.copy();changed.loc[int(n*.8):,'y']=99999
_,_,_,r2,_=forecast(changed,**args)
assert r['선택모델']==r2['선택모델']
assert [(v['사용항목'],v['MAE']) for v in trace1]==[(v['사용항목'],v['MAE']) for v in r2['컬럼추가제거탐색']]
assert r2['최종테스트']['MAE']>1000
buf=io.BytesIO();joblib.dump(b,buf);buf.seek(0);loaded=joblib.load(buf)
assert loaded['pipeline'] is not None

rng=np.random.default_rng(42)
tab=pd.DataFrame(rng.normal(size=(200,4)),columns=['a','b','c','noise']);tab['target']=3*tab.a-tab.b
bundle,ranking,out,report=compare(tab,'target',['a','b','c','noise'],selected_models=['Ridge'],optimize=True,search_budget=1)
assert report['컬럼추가제거탐색']
assert len(bundle['selected_features'])>=1
assert np.isfinite(bundle['pipeline'].predict(tab.drop(columns='target'))).all()
print('PASS: accepted add/remove, mandatory fields, per-model MAE trace, forecast and table regression, final test cannot change subset choice, serialization')
