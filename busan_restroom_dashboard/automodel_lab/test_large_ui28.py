from pathlib import Path
import time
import pandas as pd
from auto_setup import infer_group
from large_data_view import history_preview
from streamlit.testing.v1 import AppTest

root=Path(__file__).resolve().parent
source=root.parent/'Busan_AllStations_Train_Answer/01_train_all_stations.csv'
d=pd.read_csv(source);d['일시']=pd.to_datetime(d['일시'])
before=len(d);start=time.perf_counter()
assert infer_group(d,'일시','이용인원')=='역별_승하차구분'
preview,matched=history_preview(d,'일시','이용인원','역별_승하차구분','2026-01-02','2026-09-23')
assert len(preview)<=2000 and preview['구분'].nunique()<=3
assert matched==before and len(d)==before
print('PASS: real 1,424,640 rows, 224 groups auto detected, bounded preview, original rows preserved',round(time.perf_counter()-start,2),flush=True)

del d
import gc
gc.collect()
code='''
import sys,io,runpy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,ROOT)
class Upload(io.BytesIO):name='all.csv'
f=Upload(Path(SOURCE).read_bytes())
with patch('streamlit.file_uploader',side_effect=lambda *a,**k:[f] if k.get('key')=='forecast_file' else None):
    runpy.run_path(ROOT+'/app.py',run_name='__main__')
'''.replace('ROOT',repr(str(root))).replace('SOURCE',repr(str(source)))
a=AppTest.from_string(code).run(timeout=120)
for widget in a.selectbox:
    if widget.label=='무엇을 예측할까요?':widget.set_value('이용인원')
a.run(timeout=120)
assert not a.exception,a.exception
assert not a.error,[e.value for e in a.error]
assert next(w for w in a.selectbox if w.label=='대상을 나누는 항목').value=='역별_승하차구분'
assert next(w for w in a.checkbox if w.label=='과거 기록 보기 켜기').value is False
assert any(w.label=='시작 날짜' for w in a.date_input)
assert max(len(w.value) for w in a.dataframe)<100
print('PASS: full real upload reaches prediction date controls without rendering full history',flush=True)
for widget in a.radio:
    if widget.label=='학습 대상':widget.set_value('일부 대상 선택')
a.run(timeout=120)
for widget in a.multiselect:
    if widget.label=='학습할 대상 선택':widget.set_value(['113_부산역_하차'])
a.run(timeout=120)
assert not a.exception,a.exception
assert any('6,360행' in w.value for w in a.caption)
print('PASS: explicit group subset keeps 6,360 rows, whole original file retained',flush=True)
