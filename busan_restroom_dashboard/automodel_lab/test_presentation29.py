from pathlib import Path
from streamlit.testing.v1 import AppTest
root=Path(__file__).resolve().parent
source='''
import sys,io,runpy,pandas as pd,numpy as np
from unittest.mock import patch
sys.path.insert(0,ROOT)
class Upload(io.BytesIO):name='data.csv'
t=pd.date_range('2026-01-01',periods=180,freq='h')
df=pd.DataFrame({'일시':t,'이용인원':10+np.sin(np.arange(180))})
f=Upload(df.to_csv(index=False).encode())
def mock_forecast(data,tc,yc,gc,interval,minutes,*args,**kwargs):
    dates=pd.date_range(data[tc].max()+pd.Timedelta(minutes=interval),periods=int(minutes/interval),freq=str(interval)+'min')
    future=pd.DataFrame({'구분':'전체','예측시각':dates,'예측값':11.})
    test=pd.DataFrame({'구분':'전체','예측시각':t[-12:],'実際':10.})
    test['실제값']=10.;test['예측값']=11.;test=test.drop(columns='実際')
    columns=['series','weekday','hour','is_holiday','lag_1','lag_24','rolling_mean_3','rolling_std_3','month','day','holiday_name','known::행사']
    audit=[{'항목':c,'사용 여부':'사용','이유':'검증 결과','관련성 참고 점수':None} for c in columns]
    report={'선택모델':'T001 · Extra Trees · 전체 항목','선택항목':columns,'선택설정값':{'학습기간_칸':None},
        '최종테스트':{'MAE':1.,'RMSE':1.,'R2':0.},'검증구간':[],'항목선택_상세':audit,'알림':[],
        '프로그램버전':'2.9-sky-ui','검증구간수':4,'탐색횟수':24}
    table=pd.DataFrame([{'모델':'Extra Trees','MAE':1.,'RMSE':1.,'사용 항목 수':len(columns)}])
    return future,table,test,report,{'pipeline':None,'auxiliary_plan':None}
with patch('streamlit.file_uploader',side_effect=lambda *a,**k:[f] if k.get('key')=='forecast_file' else None),patch('forecast.forecast',side_effect=mock_forecast):
    runpy.run_path(ROOT+'/app.py',run_name='__main__')
'''.replace('ROOT',repr(str(root)))
a=AppTest.from_string(source).run(timeout=30)
for widget in a.selectbox:
    if widget.label=='무엇을 예측할까요?':widget.set_value('이용인원')
a.run(timeout=30)
for button in a.button:
    if button.label=='최적 조합 찾고 예측하기':button.click()
a.run(timeout=30)
assert not a.exception,a.exception
assert not a.error,[e.value for e in a.error]
assert any(s.value=='과거 내부 평가 결과' for s in a.subheader)
assert any(m.label=='이용량 대비 오차율 WAPE' and m.value=='10.00%' for m in a.metric)
assert any(m.label=='결정계수 R²' and m.value=='계산 불가' for m in a.metric)
assert any('최종 선택 모델' in m.value for m in a.markdown)
assert any('최종 컬럼 조합 · 12개' in m.value for m in a.markdown)
assert any('외 4개' in m.value for m in a.markdown)
assert not any(e.label=='실제 기록과 예측이 얼마나 달랐나요?' for e in a.expander)
assert len(a.get('vega_lite_chart'))>=2
print('PASS: compact final model/column cards, default-visible actual comparison, WAPE, zero-variance R², separate future graph, app downloads render')
