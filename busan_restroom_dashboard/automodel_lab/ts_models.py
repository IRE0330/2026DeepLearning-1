"""Native time-series candidates. All fitting uses the supplied training window."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.linear_model import Ridge

NATIVE_NAMES=['최근 값 기준','일간 반복 예측','주간 반복 예측','요일·시간 패턴','Fourier 계절 회귀','ETS 지수평활']


def timestamps(X):
    return pd.to_datetime(X[['year','month','day']])+pd.to_timedelta(X['hour'],unit='h')+pd.to_timedelta(X['minute'],unit='m')


class TimePatternPipeline(BaseEstimator):
    def __init__(self, method='요일·시간 패턴', interval=60, alpha=5., shrink=3., trend=True):
        self.method=method;self.interval=interval;self.alpha=alpha;self.shrink=shrink;self.trend=trend

    def fit(self,X,y):
        frame=X.copy();frame['_y']=np.asarray(y,dtype=float);frame['_time']=timestamps(X)
        self.series_={};self.used_=[]
        if self.method in ['최근 값 기준','일간 반복 예측','주간 반복 예측']:
            minutes={'최근 값 기준':self.interval,'일간 반복 예측':1440,'주간 반복 예측':10080}[self.method]
            lag=minutes/self.interval
            if not lag.is_integer():raise ValueError('기록 간격과 반복 주기가 맞지 않습니다.')
            self.lag_=int(lag);self.used_=[f'lag_{self.lag_}']
            if self.used_[0] not in X:raise ValueError('반복 패턴을 검증할 과거 기간이 부족합니다.')
        else:
            self.used_=['series','year','month','day','weekday','hour','minute']
            if self.method in ['요일·시간 패턴','Fourier 계절 회귀'] and 'is_holiday' in X:
                self.used_ += ['is_holiday','is_day_before_holiday','is_day_after_holiday']
        for name,g in frame.groupby('series',sort=False):
            g=g.sort_values('_time');values=g['_y'].to_numpy()
            state={'origin':g._time.iloc[-1],'mean':float(np.mean(values))}
            if self.method=='요일·시간 패턴':
                state['daily']=g.groupby(['hour','minute'])['_y'].agg(['mean','count'])
                state['weekly']=g.groupby(['weekday','hour','minute'])['_y'].agg(['mean','count'])
                if 'is_holiday' in g:
                    state['holiday']=g[g.is_holiday==1].groupby(['hour','minute'])['_y'].agg(['mean','count'])
            elif self.method=='Fourier 계절 회귀':
                state['t0']=g._time.iloc[0]
                model=Ridge(alpha=self.alpha)
                design=self._fourier(g._time,state['t0'])
                if 'is_holiday' in self.used_:
                    design=np.column_stack([design,g[['is_holiday','is_day_before_holiday','is_day_after_holiday']].to_numpy(dtype=float)])
                state['holiday_input']='is_holiday' in self.used_
                model.fit(design,values)
                state['model']=model
            elif self.method=='ETS 지수평활':
                from statsmodels.tsa.holtwinters import ExponentialSmoothing
                period=1440/self.interval
                period=int(period) if period.is_integer() and period>=2 else None
                if period is not None and (period>336 or len(values)<2*period):period=None
                state['model']=ExponentialSmoothing(values,trend='add' if self.trend else None,
                    damped_trend=self.trend,seasonal='add' if period else None,
                    seasonal_periods=period,initialization_method='estimated').fit(optimized=True,use_brute=False)
                state['forecast']=np.asarray(state['model'].forecast(10080),dtype=float)
            self.series_[str(name)]=state
        self.audit_=[{'항목':c,'사용 여부':'사용' if c in self.used_ else '제외',
                      '이유':'시간 패턴 전용 모델의 입력' if c in self.used_ else '이 시간 패턴 모델에서는 사용하지 않음',
                      '관련성 참고 점수':None} for c in X]
        return self

    def _fourier(self,t,t0):
        seconds=(pd.DatetimeIndex(t)-pd.Timestamp(t0)).total_seconds().to_numpy()/86400
        parts=[np.ones(len(seconds))]
        if self.trend:parts.append(seconds/30)
        for period,harmonics in [(1.,4),(7.,3),(365.25,2)]:
            for k in range(1,harmonics+1):
                angle=2*np.pi*k*seconds/period
                parts.extend([np.sin(angle),np.cos(angle)])
        return np.column_stack(parts)

    def predict(self,X):
        if self.method in ['최근 값 기준','일간 반복 예측','주간 반복 예측']:
            return X[self.used_[0]].to_numpy(dtype=float)
        t=timestamps(X)
        values=[]
        for pos,(_,row) in enumerate(X.iterrows()):
            state=self.series_[str(row['series'])]
            if self.method=='요일·시간 패턴':
                daily=state['daily'];weekly=state['weekly']
                base=state['mean'];key=(int(row['hour']),int(row['minute']))
                if key in daily.index:base=float(daily.loc[key,'mean'])
                wk=(int(row['weekday']),*key)
                if wk in weekly.index:
                    count=float(weekly.loc[wk,'count'])
                    base=(float(weekly.loc[wk,'mean'])*count+self.shrink*base)/(count+self.shrink)
                if row.get('is_holiday',0)==1 and 'holiday' in state and key in state['holiday'].index:
                    count=float(state['holiday'].loc[key,'count'])
                    base=(float(state['holiday'].loc[key,'mean'])*count+self.shrink*base)/(count+self.shrink)
                values.append(base)
            elif self.method=='Fourier 계절 회귀':
                design=self._fourier([t.iloc[pos]],state['t0'])
                if state.get('holiday_input',False):
                    design=np.column_stack([design,np.asarray([[row['is_holiday'],row['is_day_before_holiday'],row['is_day_after_holiday']]],dtype=float)])
                values.append(float(state['model'].predict(design)[0]))
            else:
                h=int(round((t.iloc[pos]-state['origin']).total_seconds()/(self.interval*60)))
                if h<1 or h>10080:raise ValueError('통계 모델 예측 범위를 벗어났습니다.')
                values.append(float(state['forecast'][h-1]))
        return np.asarray(values)

    @property
    def named_steps(self):
        return {'model':self,'select':SimpleNamespace(columns_=self.used_,audit_=self.audit_)}


def forecast_model_names():
    from .model_catalog import model_names
    return model_names('regression')+NATIVE_NAMES
