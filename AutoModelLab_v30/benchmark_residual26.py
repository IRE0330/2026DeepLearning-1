"""Development replay: three past weeks per dataset; no external answer file read."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from forecast import normalize, supervised, row_at
from direct_models import DirectCalendarModel
from residual_calendar import ResidualCalendarModel

root=Path(__file__).resolve().parent.parent
out=Path(__file__).resolve().parent/'benchmark26';out.mkdir(exist_ok=True)
results=[]
for name,file,target in [('parking',root/'parking_split/01_train.csv','시간당_입차기록수'),
                         ('busan',root/'BusanStation_Train_Answer/01_train.csv','하차인원')]:
    df=pd.read_csv(file);data=normalize(df,'일시',target,None,60);part=next(iter(data.values()));n=len(part)
    specs=[('calendar_tree',lambda:DirectCalendarModel(method='tree',separate_holidays=True,robust_mode='downweight')),
           ('calendar_profile',lambda:DirectCalendarModel(method='profile',separate_holidays=True)),
           ('count_basic',lambda:DirectCalendarModel(method='count_boost',feature_pack='basic')),
           ('count_extended',lambda:DirectCalendarModel(method='count_boost',feature_pack='extended')),
           ('squared_basic',lambda:DirectCalendarModel(method='squared_boost',feature_pack='basic')),
           ('squared_extended',lambda:DirectCalendarModel(method='squared_boost',feature_pack='extended')),
           ('residual_ridge_basic',lambda:ResidualCalendarModel(learner='ridge',feature_set='basic')),
           ('residual_ridge_extended',lambda:ResidualCalendarModel(learner='ridge',feature_set='extended')),
           ('residual_hgb_basic',lambda:ResidualCalendarModel(learner='hgb',feature_set='basic')),
           ('residual_hgb_extended',lambda:ResidualCalendarModel(learner='hgb',feature_set='extended'))]
    for origin in (n-3*168,n-2*168,n-168):
        X,y=supervised(data,origin)
        future_X=pd.DataFrame([row_at(ts,part.value.iloc[:origin].tolist(),'전체') for ts in part.time.iloc[origin:origin+168]])
        truth=part.value.iloc[origin:origin+168].to_numpy()
        for label,build in specs:
            model=build().fit(X,y);pred=model.predict(future_X)
            results.append({'dataset':name,'model':label,'start':str(part.time.iloc[origin]),
                'end':str(part.time.iloc[origin+167]),'MAE':float(np.mean(abs(truth-pred))),
                'RMSE':float(np.sqrt(np.mean((truth-pred)**2)))})
            print(name,origin,label,round(results[-1]['MAE'],3),flush=True)
pd.DataFrame(results).to_csv(out/'past_weeks.csv',index=False,encoding='utf-8-sig')
summary=pd.DataFrame(results).groupby(['dataset','model'],as_index=False).agg(MAE=('MAE','mean'))
summary.to_csv(out/'summary.csv',index=False,encoding='utf-8-sig')
print(summary.to_string(index=False))
(out/'README.txt').write_text('2.6 development replay, not untouched external validation. Each model was fixed before evaluation. Three non-overlapping past weeks in each training file. No external answer CSV read. Results compare individual models and do not establish final AutoML accuracy.\n',encoding='utf-8')
