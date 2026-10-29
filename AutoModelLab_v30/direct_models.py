"""Forecast from known calendar inputs; predictions never feed back as inputs."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator

DIRECT_NAMES = ['직접 예측 · 최근 가중 패턴', '직접 예측 · 달력 트리']


class DirectCalendarModel(BaseEstimator):
    def __init__(self, method='profile', interval=60, half_life_days=28., shrink=0., calibrate=False, robust_mode='off', separate_holidays=False, statistic='mean', calibration_by_hour=False, feature_pack='extended'):
        self.method=method
        self.interval=interval
        self.half_life_days=half_life_days
        self.shrink=shrink
        self.calibrate=calibrate
        self.robust_mode=robust_mode
        self.separate_holidays=separate_holidays
        self.statistic=statistic
        self.calibration_by_hour=calibration_by_hour
        self.feature_pack=feature_pack

    def fit(self,X,y):
        X=X.reset_index(drop=True);y=np.asarray(y,dtype=float)
        # Only dates and covariates explicitly known at the forecast date.
        self.columns_=[c for c in X if not (c.startswith(('lag_','rolling_','past::')) or c in ('recent_change','seasonal_lag_mean'))]
        if self.method in ('profile','event_profile'): self.columns_=[c for c in (('series','weekday','hour','minute','is_holiday','holiday_name') if self.method=='event_profile' else ('series','weekday','hour','minute','is_holiday')) if c in X]
        if self.feature_pack=='basic' and self.method not in ('profile','event_profile'):
            self.columns_=[c for c in ('series','weekday','hour','minute','is_weekend','is_holiday','hour_sin','hour_cos','weekday_sin','weekday_cos') if c in X]
        self.corrections_={}
        if self.calibrate:
            positions=np.concatenate([np.flatnonzero(X.series.to_numpy()==s)[:int((X.series==s).sum()*.8)] for s in X.series.unique()])
            valid=np.setdiff1d(np.arange(len(X)),positions)
            self._fit_base(X.iloc[positions],y[positions])
            residual=y[valid]-self._predict_base(X.iloc[valid])
            self.correction_keys_=['series','weekday','is_holiday']+(['hour'] if self.calibration_by_hour else [])
            g=X.iloc[valid][self.correction_keys_].copy();g['error']=residual
            for key,part in g.groupby(self.correction_keys_):
                # Shrink sparse correction estimates towards no correction.
                self.corrections_[key]=float(part.error.sum()/(len(part)+24))
        self._fit_base(X,y)
        self.audit_=[{'항목':c,'사용 여부':'사용' if c in self.columns_ else '제외',
                     '이유':'미래 시점에 알려진 날짜·예정 정보로 직접 예측' if c in self.columns_ else '예측값 재입력에 의한 오차 누적 방지',
                     '관련성 참고 점수':None} for c in X]
        return self

    def _fit_base(self,X,y):
        from ts_models import timestamps
        from robust_targets import treat_targets
        cleaned,robust_weight,self.treatment_audit_=treat_targets(X,y,self.robust_mode,self.separate_holidays)
        frame=X.reset_index(drop=True).copy();frame['_y']=cleaned
        dates=timestamps(X)
        age=(dates.max()-dates).dt.total_seconds().to_numpy()/86400
        frame['_w']=np.exp2(-age/self.half_life_days)*robust_weight
        if self.method in ('tree','mae_boost','count_boost','squared_boost'):
            from core import pipeline
            from sklearn.ensemble import ExtraTreesRegressor
            self.models_={}
            regimes=(0,1) if self.separate_holidays else (None,)
            for regime in regimes:
                mask=np.ones(len(X),dtype=bool) if regime is None else X['is_holiday'].to_numpy()==regime
                if not mask.any():continue
                if self.method in ('mae_boost','count_boost','squared_boost'):
                    from sklearn.ensemble import HistGradientBoostingRegressor
                    loss={'mae_boost':'absolute_error','count_boost':'poisson','squared_boost':'squared_error'}[self.method]
                    if loss=='poisson' and (np.any(cleaned[mask]<0) or not np.any(cleaned[mask]>0)):
                        raise ValueError('건수 학습 후보는 0 이상이며 양수 관측이 있는 경우에만 사용')
                    learner=HistGradientBoostingRegressor(loss=loss,max_iter=120,max_leaf_nodes=15,l2_regularization=1. if self.method=='mae_boost' else 3.,random_state=42,early_stopping=False)
                else:learner=ExtraTreesRegressor(n_estimators=100,min_samples_leaf=3,random_state=42,n_jobs=-1)
                fitted=pipeline(learner,())
                fitted.fit(X.loc[mask,self.columns_],cleaned[mask],model__sample_weight=frame.loc[mask,'_w'].to_numpy())
                if hasattr(fitted.named_steps['model'],'n_jobs'):fitted.named_steps['model'].set_params(n_jobs=1)
                self.models_[regime]=fitted
        else:
            self.profiles_={}
            for name,g in frame.groupby('series'):
                normal=g[g.is_holiday==0] if self.separate_holidays else g
                if normal.empty:normal=g
                state={'mean':self._center(normal._y.to_numpy(),normal._w.to_numpy())}
                for label,keys in [('daily',['hour','minute']),('weekly',['weekday','hour','minute']),('holiday',['is_holiday','hour','minute'])]:
                    work=(normal if self.separate_holidays and label!='holiday' else g).copy();work['_wy']=work._w*work._y
                    stats=work.groupby(keys).agg(total=('_wy','sum'),weight=('_w','sum'))
                    if self.statistic=='median':
                        state[label]={key:(self._center(part._y.to_numpy(),part._w.to_numpy()),float(part._w.sum())) for key,part in work.groupby(keys)}
                    else:state[label]={key:(float(r.total/r.weight),float(r.weight)) for key,r in stats.iterrows()}
                if self.method=='event_profile':
                    # Same holiday identity first, then pooled holidays, then ordinary pattern.
                    # Sparse event groups shrink to pooled holiday values; never read future targets.
                    state['events']={key:(self._center(part._y.to_numpy(),part._w.to_numpy()),len(part))
                        for key,part in g[g.is_holiday==1].groupby(['holiday_name','hour','minute'])}
                self.profiles_[str(name)]=state

    def _center(self,values,weights):
        if self.statistic=='median':
            order=np.argsort(values);v=np.asarray(values)[order];w=np.asarray(weights)[order]
            return float(v[min(np.searchsorted(np.cumsum(w),w.sum()/2),len(v)-1)])
        return float(np.average(values,weights=weights))

    def _predict_base(self,X):
        if self.method in ('tree','mae_boost','count_boost','squared_boost'):
            out=np.empty(len(X))
            regimes=(0,1) if self.separate_holidays else (None,)
            for regime in regimes:
                mask=np.ones(len(X),dtype=bool) if regime is None else X['is_holiday'].to_numpy()==regime
                if not mask.any():continue
                fitted=self.models_.get(regime,next(iter(self.models_.values())))
                out[mask]=fitted.predict(X.loc[mask,self.columns_])
            return out
        out=[]
        for _,r in X.iterrows():
            s=self.profiles_[str(r.series)];key=(int(r.hour),int(r.minute))
            base=s['daily'].get(key,(s['mean'],0))[0]
            wk=s['weekly'].get((int(r.weekday),*key))
            if wk:base=(wk[0]*wk[1]+self.shrink*base)/(wk[1]+self.shrink)
            holiday=s['holiday'].get((1,*key))
            if r.get('is_holiday',0)==1 and holiday:
                base=(holiday[0]*holiday[1]+self.shrink*base)/(holiday[1]+self.shrink)
            if self.method=='event_profile' and r.get('is_holiday',0)==1:
                event=s.get('events',{}).get((r.get('holiday_name',''),*key))
                if event:base=(event[0]*event[1]+2*base)/(event[1]+2)
            out.append(base)
        return np.asarray(out)

    def predict(self,X):
        pred=self._predict_base(X)
        if self.corrections_:
            pred=pred+np.asarray([self.corrections_.get(tuple(r[k] for k in self.correction_keys_),0.) for _,r in X.iterrows()])
        return pred

    @property
    def named_steps(self):
        return {'model':self,'select':SimpleNamespace(columns_=self.columns_,audit_=self.audit_)}
