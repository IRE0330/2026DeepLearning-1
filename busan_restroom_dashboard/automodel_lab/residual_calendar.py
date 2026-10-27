"""Calendar baseline plus a residual learner trained on expanding-origin errors."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
from .direct_models import DirectCalendarModel
from .ts_models import timestamps

RESIDUAL_NAME='직접 예측 · 과거 오차 학습'


class ResidualCalendarModel(DirectCalendarModel):
    def __init__(self, interval=60, half_life_days=28., learner='ridge', feature_set='extended'):
        self.interval=interval;self.half_life_days=half_life_days
        self.learner=learner;self.feature_set=feature_set
        self.method='residual';self.separate_holidays=True

    def fit(self,X,y):
        from .core import pipeline
        from sklearn.linear_model import Ridge
        from sklearn.ensemble import HistGradientBoostingRegressor
        X=X.reset_index(drop=True);y=np.asarray(y,dtype=float)
        date=timestamps(X);unique=sorted(date.unique());n=len(unique)
        basic=['series','weekday','hour','minute','is_weekend','is_holiday','hour_sin','hour_cos','weekday_sin','weekday_cos']
        extended=[c for c in X if not c.startswith(('lag_','rolling_','past::')) and c not in ('recent_change','seasonal_lag_mean')]
        self.columns_=[c for c in (basic if self.feature_set=='basic' else extended) if c in X]
        self.oof_ranges_=[];parts=[];errors=[]
        cuts=sorted(set([max(1,int(n*f)) for f in (.5,.67,.84)]+[n]))
        def baseline():
            return DirectCalendarModel(method='event_profile',half_life_days=self.half_life_days,
                interval=self.interval,separate_holidays=True)
        for start,end in zip(cuts[:-1],cuts[1:]):
            train=date<unique[start];valid=(date>=unique[start]) & (date<=unique[end-1])
            if train.sum()<20 or not valid.any():continue
            # Each residual is an error on records the baseline had never seen.
            model=baseline().fit(X.loc[train],y[train])
            parts.append(X.loc[valid,self.columns_]);errors.append(y[valid]-model.predict(X.loc[valid]))
            self.oof_ranges_.append({'학습종료':str(date[train].max()),'오차시작':str(date[valid].min()),'오차종료':str(date[valid].max())})
        if not parts:raise ValueError('과거 오차 학습을 위한 기록 부족')
        residual_X=pd.concat(parts);residual=np.concatenate(errors)
        residual_dates=date.loc[residual_X.index]
        age=(date.max()-residual_dates).dt.total_seconds().to_numpy()/86400
        weights=np.exp2(-age/self.half_life_days)
        learner=Ridge(alpha=30.) if self.learner=='ridge' else HistGradientBoostingRegressor(
            loss='absolute_error',max_iter=100,max_leaf_nodes=7,min_samples_leaf=20,
            l2_regularization=5.,early_stopping=False,random_state=42)
        self.residual_=pipeline(learner,()).fit(residual_X,residual,model__sample_weight=weights)
        self.baseline_=baseline().fit(X,y)
        self.nonnegative_=bool(np.all(y>=0))
        self.audit_=[{'항목':c,'사용 여부':'사용' if c in self.columns_ or c in self.baseline_.columns_ else '제외',
            '이유':'과거 시간순 예측 오차 학습 + 달력 기준 패턴','관련성 참고 점수':None} for c in X]
        self.columns_=list(dict.fromkeys(self.columns_+self.baseline_.columns_))
        self.treatment_audit_={'방식':'과거 예측 오차 학습','원본변경':False,'의심값수':None,
            '오차학습행수':len(residual),'오차생성구간':self.oof_ranges_,'학습기':self.learner,'변수묶음':self.feature_set}
        return self

    def predict(self,X):
        values=self.baseline_.predict(X)+self.residual_.predict(X)
        return np.maximum(0,values) if self.nonnegative_ else values

    @property
    def named_steps(self):
        return {'model':self,'select':SimpleNamespace(columns_=self.columns_,audit_=self.audit_)}
