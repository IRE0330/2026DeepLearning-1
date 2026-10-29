import pandas as pd
from future_evaluation import align_answers
from streamlit.testing.v1 import AppTest

s=pd.DataFrame({'구분':['A','A'],'예측시각':pd.to_datetime(['2023-11-23','2023-11-24']),'예측값':[12.,18.]})
a=pd.DataFrame({'날짜':['2023-11-23','2023-11-24','2023-09-22'],'시간':['00:00:00']*3,'실제값':[10,20,999]})
m,missing=align_answers(s,a,'시간','실제값',date_col='날짜')
assert len(m)==2 and missing.empty and m['절대차이'].mean()==2
m,missing=align_answers(s,a.iloc[:1],'시간','실제값',date_col='날짜')
assert len(m)==1 and len(missing)==1
for bad in [pd.concat([a,a.iloc[:1]]),a.assign(실제값=[None,20,999])]:
 try: align_answers(s,bad,'시간','실제값',date_col='날짜')
 except ValueError: pass
 else: raise AssertionError('invalid answers accepted')
b=s.copy();b['구분']=['A','B']
try: align_answers(b,a,'시간','실제값',date_col='날짜')
except ValueError: pass
else: raise AssertionError('multi-series requires key')
code='''
import pandas as pd
from presentation_ui import render_actual_comparison
from future_evaluation import render_future_evaluation
shown=pd.DataFrame({'구분':['전체']*2,'예측시각':pd.date_range('2023-11-23',periods=2,freq='h'),'예측값':[12.,18.]})
render_future_evaluation(shown,'이용량','없음',None,render_actual_comparison)
check=shown.assign(실제값=[10.,20.])
render_actual_comparison(check,context='future')
with __import__('streamlit').expander('과거 내부 평가'):
    render_actual_comparison(check,context='past')
'''
at=AppTest.from_string(code).run()
assert not at.exception,at.exception
assert len(at.get('vega_lite_chart'))==2
assert any('13.33%'==x.value for x in at.metric)
assert any('실제값' in x.value for x in at.info)
print('PASS: exact future dates, missing, duplicates, invalid values, group keys, UI metrics and charts')

source="""
import io
from unittest.mock import patch
import pandas as pd
from future_evaluation import render_future_evaluation
from presentation_ui import render_actual_comparison
s=pd.DataFrame({'구분':['전체']*2,'예측시각':pd.date_range('2023-11-23',periods=2,freq='h'),'예측값':[12.,18.]})
a=pd.DataFrame({'일시':pd.date_range('2023-11-23',periods=2,freq='h'),'이용량':[10.,20.]})
with patch('streamlit.file_uploader',return_value=io.BytesIO(b'test')):
    result=render_future_evaluation(s,'이용량','없음',lambda *args:(a,0),render_actual_comparison)
assert len(result)==2
"""
at=AppTest.from_string(source).run()
assert not at.exception,at.exception
assert not at.error,at.error
assert len(at.get('vega_lite_chart'))==1
print('PASS: uploaded answer workflow renders selected-period metrics without training')
