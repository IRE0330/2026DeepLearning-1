from pathlib import Path
import numpy as np
import pandas as pd
from forecast import normalize,supervised,row_at
from regime_model import RegimeMAEModel

root=Path(__file__).resolve().parent.parent
out=Path(__file__).resolve().parent/'benchmark27';out.mkdir(exist_ok=True)
rows=[]
for name,folder,target in [('parking','parking_split','시간당_입차기록수'),('busan','BusanStation_Train_Answer','하차인원')]:
    d=pd.read_csv(root/folder/'01_train.csv');data=normalize(d,'일시',target,None,60)
    part=next(iter(data.values()));n=len(part)
    for origin in (n-3*168,n-2*168,n-168):
        X,y=supervised(data,origin)
        future=pd.DataFrame([row_at(ts,part.value.iloc[:origin].tolist(),'전체') for ts in part.time.iloc[origin:origin+168]])
        truth=part.value.iloc[origin:origin+168].to_numpy()
        for scope in ('daytype','daytype_hour'):
            model=RegimeMAEModel(scope=scope).fit(X,y);pred=model.predict(future)
            rows.append({'dataset':name,'model':'regime_'+scope,'start':str(part.time.iloc[origin]),
                'end':str(part.time.iloc[origin+167]),'MAE':float(np.mean(abs(truth-pred)))})
            print(rows[-1],flush=True)
pd.DataFrame(rows).to_csv(out/'past_weeks.csv',index=False,encoding='utf-8-sig')
baseline=pd.read_csv(root/'AutoModelLab/benchmark26/past_weeks.csv')
baseline=baseline[baseline.model.isin(['calendar_tree','calendar_profile'])]
combined=pd.concat([baseline,pd.DataFrame(rows)],ignore_index=True)
summary=combined.groupby(['dataset','model'],as_index=False).MAE.mean()
summary.to_csv(out/'summary.csv',index=False,encoding='utf-8-sig')
print(summary.to_string(index=False),flush=True)
(out/'README.txt').write_text('개발용 과거 3주 재현 비교. 외부 정답 파일 미사용. 최종 AutoML 성능이 아닌 고정 후보 비교.',encoding='utf-8')
