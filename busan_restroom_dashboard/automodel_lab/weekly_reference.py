"""Fixed-origin weekly reference forecasts; no predicted values in the history."""
from types import SimpleNamespace
import math
import numpy as np
import pandas as pd
from .direct_models import DirectCalendarModel
from .ts_models import timestamps

REFERENCE_NAMES=['최근 4주 같은 시간 평균','최근 4주 같은 시간 중앙값']


class WeeklyReferenceModel(DirectCalendarModel):
    def __init__(self,weeks=4,statistic='mean',interval=60):
        self.weeks=weeks
        self.statistic=statistic
        self.interval=interval
        self.separate_holidays=False
        self.method='weekly_reference'

    def fit(self,X,y):
        dates=timestamps(X)
        frame=X[['series','weekday','hour','minute']].copy()
        frame['_time']=dates;frame['_value']=np.asarray(y,dtype=float)
        self.histories_={};self.origins_={};self.fallback_={};self.global_={}
        for name,g in frame.groupby('series',sort=False):
            name=str(name)
            self.histories_[name]=dict(zip(g['_time'],g['_value']))
            self.origins_[name]=g['_time'].max()
            reduce=np.median if self.statistic=='median' else np.mean
            self.global_[name]=float(reduce(g['_value']))
            self.fallback_[name]={key:float(reduce(part['_value'])) for key,part in g.groupby(['weekday','hour','minute'])}
        self.columns_=['series','year','month','day','weekday','hour','minute']
        self.audit_=[{'항목':c,'사용 여부':'사용' if c in self.columns_ else '제외',
                     '이유':'예측 시작 전에 관측한 최근 4주 동일 시각 기준','관련성 참고 점수':None} for c in X]
        self.treatment_audit_={'방식':'off','의심값수':None,'원본변경':False,
                              '설명':'4주가 부족하면 관측된 주만 사용하고, 없으면 학습 요일·시각 패턴으로 대체. 긴 예측은 시작점 이전의 최근 동일 요일·시각 기록으로 반복.'}
        return self

    def predict(self,X):
        dates=timestamps(X);out=[];week=pd.Timedelta(days=7)
        for i,(_,row) in enumerate(X.iterrows()):
            name=str(row['series']);ts=dates.iloc[i];origin=self.origins_[name]
            distance=max(1,math.ceil((ts-origin)/week))
            refs=[self.histories_[name].get(ts-week*(distance+k)) for k in range(self.weeks)]
            refs=[v for v in refs if v is not None]
            if refs:out.append(float(np.median(refs) if self.statistic=='median' else np.mean(refs)))
            else:out.append(self.fallback_[name].get((int(row.weekday),int(row.hour),int(row.minute)),self.global_[name]))
        return np.asarray(out)
