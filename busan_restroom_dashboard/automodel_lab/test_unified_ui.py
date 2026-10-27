from pathlib import Path
from streamlit.testing.v1 import AppTest

root=Path(__file__).resolve().parent

def check(kind,target):
    source='''
import sys,io,runpy,pandas as pd,numpy as np
from unittest.mock import patch
sys.path.insert(0,ROOT)
class Upload(io.BytesIO):name='data.csv'
if KIND=='time':
    t=pd.date_range('2026-10-01',periods=180,freq='h')
    df=pd.DataFrame({'Date':t.strftime('%d/%m/%Y'),'Hour':t.hour,'quantity':np.sin(np.arange(180)/4)*2+10,'temperature':np.sin(np.arange(180)/4)})
else:
    df=pd.read_csv(ROOT+'/samples/classification.csv')
f=Upload(df.to_csv(index=False).encode())
with patch('streamlit.file_uploader',side_effect=lambda *a,**k:f if k.get('key')=='forecast_file' else None):
    runpy.run_path(ROOT+'/app.py',run_name='__main__')
'''.replace('ROOT',repr(str(root))).replace('KIND',repr(kind))
    a=AppTest.from_string(source).run(timeout=30)
    assert len(a.tabs)==0
    for s in a.selectbox:
        if s.label=='무엇을 예측할까요?':s.set_value(target)
    a.run(timeout=30)
    if kind=='time':
        for widget in a.multiselect:
            if widget.label=='비교할 방법':widget.set_value(['Ridge','요일·시간 패턴'])
        a.run(timeout=30)
    for b in a.button:
        if b.label=='최적 조합 찾고 예측하기':b.click();break
    a.run(timeout=120)
    assert not a.exception,a.exception
    assert not a.error,[e.value for e in a.error]
    assert any(s.value=='탐색 결과: 최적 변수·모델 조합' for s in a.subheader)
    assert any(len(d.value)>=24 and '설정값' in d.value.columns for d in a.dataframe)
    assert len(a.metric)>=3
    print('PASS: no tabs, one-run '+kind+' optimization and predictions')

check('time','quantity')
check('table','이탈')
