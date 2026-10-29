"""Select experts by day type using strictly out-of-time MAE inside training."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
from direct_models import DirectCalendarModel
from weekly_reference import WeeklyReferenceModel
from ts_models import timestamps

REGIME_NAME='직접 예측 · 상황별 MAE 모델'


class RegimeMAEModel(DirectCalendarModel):
    def __init__(self, interval=60, scope='daytype', min_days=2, min_gain=.02):
        self.interval=interval;self.scope=scope;self.min_days=min_days;self.min_gain=min_gain
        self.method='regime_mae';self.separate_holidays=True

    def _keys(self,X):
        result=[]
        for _,row in X.iterrows():
            typ='공휴일' if row.get('is_holiday',0) else '주말' if row.get('is_weekend',int(row.weekday>=5)) else '평일'
            result.append((str(row.series),typ,int(row.hour)//6 if self.scope=='daytype_hour' else -1))
        return result

    def _pool(self):
        return [
            ('최근7일 가중 평균',DirectCalendarModel(interval=self.interval,half_life_days=7,separate_holidays=True)),
            ('최근28일 가중 평균',DirectCalendarModel(interval=self.interval,half_life_days=28,separate_holidays=True)),
            ('최근14일 가중 중앙값',DirectCalendarModel(interval=self.interval,half_life_days=14,statistic='median',separate_holidays=True)),
            ('달력 트리',DirectCalendarModel(interval=self.interval,method='tree',separate_holidays=True,robust_mode='downweight')),
            ('최근4주 평균',WeeklyReferenceModel(interval=self.interval,statistic='mean')),
            ('최근4주 중앙값',WeeklyReferenceModel(interval=self.interval,statistic='median'))]

    def fit(self,X,y):
        from sklearn.base import clone
        X=X.reset_index(drop=True);y=np.asarray(y,dtype=float);dates=timestamps(X)
        unique=sorted(dates.unique());n=len(unique)
        horizon=min(max(1,int(round(7*1440/self.interval))),n//6)
        if horizon<2 or n-3*horizon<20:raise ValueError('상황별 모델 선택을 위한 과거 기록 부족')
        pool=self._pool();observations=[];errors=[];self.inner_ranges_=[]
        for origin in (n-3*horizon,n-2*horizon,n-horizon):
            train=dates<unique[origin];valid=(dates>=unique[origin])&(dates<=unique[origin+horizon-1])
            predictions=[]
            for _,expert in pool:
                model=clone(expert).fit(X.loc[train],y[train])
                predictions.append(model.predict(X.loc[valid]))
            matrix=np.column_stack(predictions)
            # The median is another MAE-oriented candidate, not a forced blend.
            matrix=np.column_stack([matrix,np.median(matrix,axis=1)])
            errors.append(np.abs(matrix-y[valid,None]))
            part=X.loc[valid].copy();part['_date']=dates[valid].dt.date.to_numpy();observations.append(part)
            self.inner_ranges_.append({'학습종료':str(dates[train].max()),'검증시작':str(dates[valid].min()),'검증종료':str(dates[valid].max())})
        audit_X=pd.concat(observations).reset_index(drop=True);error=np.vstack(errors)
        labels=[label for label,_ in pool]+['전문가 중앙값 결합']
        self.global_index_=int(np.argmin(error.mean(axis=0)));self.routes_={};self.route_audit_=[]
        keys=self._keys(audit_X)
        for key in dict.fromkeys(keys):
            ids=np.flatnonzero([k==key for k in keys]);days=audit_X.iloc[ids]['_date'].nunique()
            means=error[ids].mean(axis=0);best=int(np.argmin(means));global_mae=float(means[self.global_index_])
            enough=days>=self.min_days and len(ids)>=12
            accepted=enough and means[best]<global_mae*(1-self.min_gain)
            choice=best if accepted else self.global_index_;self.routes_[key]=choice
            self.route_audit_.append({'대상':key[0],'상황':key[1],'시간블록':'전체' if key[2]<0 else f'{key[2]*6:02d}:00~{key[2]*6+5:02d}:59',
                '검증일수':int(days),'검증행수':len(ids),'전체기준모델':labels[self.global_index_],
                '선택모델':labels[choice],'기준MAE':global_mae,'선택MAE':float(means[choice]),
                '개별선택':bool(accepted),'설명':'상황별 MAE 개선' if accepted else '기록 부족 또는 개선폭 부족으로 전체 기준 사용'})
        used=set(self.routes_.values())|{self.global_index_}
        if len(pool) in used:used.update(range(len(pool)))
        used=sorted(i for i in used if i<len(pool))
        self.median_index_=len(pool)
        self.experts_={i:clone(pool[i][1]).fit(X,y) for i in used}
        self.columns_=list(dict.fromkeys(c for m in self.experts_.values() for c in m.named_steps['select'].columns_))
        self.columns_=list(dict.fromkeys(self.columns_+['series','weekday','hour','is_weekend','is_holiday']))
        self.audit_=[{'항목':c,'사용 여부':'사용' if c in self.columns_ else '제외',
            '이유':'상황 구분 또는 과거 검증에서 선택한 전문가 입력','관련성 참고 점수':None} for c in X]
        self.treatment_audit_={'방식':'상황별 MAE 선택','의심값수':None,'원본변경':False,
            '내부검증구간':self.inner_ranges_,'상황별선택':self.route_audit_,
            '최소검증일수':self.min_days,'최소개선비율':self.min_gain}
        return self

    def predict(self,X):
        choices=np.asarray([self.routes_.get(k,self.global_index_) for k in self._keys(X)])
        result=np.empty(len(X))
        for i in np.unique(choices):
            mask=choices==i;part=X.iloc[np.flatnonzero(mask)]
            result[mask]=np.median([self.experts_[j].predict(part) for j in range(self.median_index_)],axis=0) if i==self.median_index_ else self.experts_[int(i)].predict(part)
        return result

    @property
    def named_steps(self):
        return {'model':self,'select':SimpleNamespace(columns_=self.columns_,audit_=self.audit_)}
