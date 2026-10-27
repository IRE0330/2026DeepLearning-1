"""Recursive univariate/grouped forecasting, with multi-step held-out selection."""
import math
import time
import warnings
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.exceptions import ConvergenceWarning
from .core import pipeline, score
from .model_catalog import catalog, OPTIONAL, load_optional
from .search_space import make_trials, selection_label
from .auxiliary import auxiliary_plan
from .ts_models import NATIVE_NAMES, TimePatternPipeline
from .calendar_features import calendar_features
from .adaptive_models import WindowModel, AveragedModel
from .direct_models import DirectCalendarModel, DIRECT_NAMES
from .weekly_reference import WeeklyReferenceModel, REFERENCE_NAMES
from .residual_calendar import ResidualCalendarModel, RESIDUAL_NAME
from .regime_model import RegimeMAEModel, REGIME_NAME

LAGS = (1, 2, 3, 6, 12)
FEATURES = ['series', 'year', 'month', 'day', 'weekday', 'hour', 'minute'] + [f'lag_{i}' for i in LAGS]


def row_at(ts, values, series, lags=LAGS, holiday_country='KR'):
    minute_of_day=ts.hour*60+ts.minute
    row={'series':str(series),'year':ts.year,'month':ts.month,'day':ts.day,
         'weekday':ts.dayofweek,'hour':ts.hour,'minute':ts.minute,
         'weekday_hour':str(ts.dayofweek)+'_'+str(ts.hour)+'_'+str(ts.minute),
         'is_weekend':int(ts.dayofweek>=5),'day_of_year':ts.dayofyear,
         'week_of_year':int(ts.isocalendar().week),'is_month_start':int(ts.is_month_start),'is_month_end':int(ts.is_month_end),
         'hour_sin':float(np.sin(2*np.pi*minute_of_day/1440)),'hour_cos':float(np.cos(2*np.pi*minute_of_day/1440)),
         'weekday_sin':float(np.sin(2*np.pi*ts.dayofweek/7)),'weekday_cos':float(np.cos(2*np.pi*ts.dayofweek/7)),
         'month_sin':float(np.sin(2*np.pi*(ts.month-1)/12)),'month_cos':float(np.cos(2*np.pi*(ts.month-1)/12))}
    row.update(calendar_features(ts,holiday_country))
    row.update({f'lag_{i}':float(values[-i]) for i in lags})
    for window in (3,6,12):
        recent=np.asarray(values[-window:],dtype=float)
        row[f'rolling_mean_{window}']=float(recent.mean())
        row[f'rolling_std_{window}']=float(recent.std())
    seasonal=[values[-i] for i in lags if i>=24 and i<=len(values)]
    if seasonal: row['seasonal_lag_mean']=float(np.mean(seasonal))
    row['recent_change']=float(values[-1]-values[-2])
    return row


def normalize(df, time_col, target, group, interval, extra_columns=()):
    d = pd.DataFrame({'time': pd.to_datetime(df[time_col], errors='coerce'),
                      'value': pd.to_numeric(df[target], errors='coerce')})
    if group:
        if df[group].isna().any():
            raise ValueError('구분 컬럼에 빈 값이 있습니다.')
        d['series'] = df[group].astype(str)
    else:
        d['series'] = '전체'
    if d['time'].isna().any() or not np.isfinite(d['value']).all():
        raise ValueError('시간 또는 예측할 값에 빈 값·문자·무한대가 있습니다. 정리 후 다시 올려 주세요.')
    if d.duplicated(['series', 'time']).any():
        raise ValueError('같은 구분·시각에 여러 행이 있습니다. 구분 컬럼을 선택하거나 같은 시각을 먼저 집계해 주세요.')
    for c in extra_columns:
        d['raw::'+str(c)] = df[c]
    data = {}
    step = pd.Timedelta(minutes=interval)
    for name, part in d.groupby('series', sort=False):
        part = part.sort_values('time').reset_index(drop=True)
        if len(part) < 80:
            raise ValueError(f'{name}: 규칙적인 과거 기록이 최소 80개 필요합니다. 현재 {len(part)}개입니다.')
        if not part.time.diff().iloc[1:].eq(step).all():
            raise ValueError(f'{name}: 기록 간격이 지정한 {interval}분과 다르거나 누락 구간이 있습니다. 실제 간격을 확인하고 빈 구간을 정리해 주세요.')
        data[name] = part
    if not data:
        raise ValueError('예측할 기록이 없습니다.')
    # Common boundaries avoid training on one series' future to predict another's past.
    if len({p.time.iloc[0] for p in data.values()}) > 1 or len({p.time.iloc[-1] for p in data.values()}) > 1:
        raise ValueError('여러 구분을 함께 예측할 때는 시작·종료 시각을 동일하게 맞춰 주세요. 또는 한 구분만 선택해 실행하세요.')
    return data


def supervised(data, stop, past_columns=(), known_columns=(), auto_covariates=False, lags=LAGS, holiday_country='KR'):
    rows, y = [], []
    for name, p in data.items():
        values = p.value.tolist()
        for i in range(max(lags), stop):
            row=row_at(p.time.iloc[i], values[:i], name,lags,holiday_country)
            for c in past_columns: row['past::'+str(c)]=p['raw::'+str(c)].iloc[i if auto_covariates else i-1]
            for c in known_columns: row['known::'+str(c)]=p['raw::'+str(c)].iloc[i]
            rows.append(row)
            y.append(values[i])
    return pd.DataFrame(rows), np.asarray(y)


def recursive(model, data, start, steps, interval, nonnegative=False, past_columns=(), known_columns=(), future_known=None, auto_covariates=False, lags=LAGS, covariate_plan=None, holiday_country='KR'):
    if auto_covariates and past_columns and covariate_plan is None:
        covariate_plan,_=auxiliary_plan(data,start,steps,interval,past_columns)
    histories = {name: p.value.iloc[:start].tolist() for name, p in data.items()}
    names = list(data)
    last = {name: p.time.iloc[start-1] for name,p in data.items()}
    direct_model=model.estimator_ if isinstance(model,WindowModel) else model
    if isinstance(direct_model,DirectCalendarModel):
        # Direct candidates do not depend on any preceding predicted target.
        # A single batch is identical to stepping forward, without worker overhead.
        batch=[];keys=[]
        for i in range(1,steps+1):
            for name in names:
                ts=last[name]+pd.Timedelta(minutes=i*interval)
                row=row_at(ts,histories[name],name,lags,holiday_country)
                for c in known_columns:
                    row['known::'+str(c)]=data[name]['raw::'+str(c)].iloc[start+i-1] if future_known is None else future_known.loc[(str(name),ts),c]
                batch.append(row);keys.append((name,ts))
        pred=np.asarray(model.predict(pd.DataFrame(batch)),dtype=float)
        if nonnegative:pred=np.maximum(0,pred)
        if not np.isfinite(pred).all():raise ValueError('직접 예측에서 유효하지 않은 값이 발생했습니다.')
        return pd.DataFrame([{'구분':name,'예측시각':ts,'예측값':float(v)} for (name,ts),v in zip(keys,pred)])
    rows = []
    for i in range(1, steps+1):
        times = {name: last[name]+pd.Timedelta(minutes=i*interval) for name in names}
        batch=[]
        for name in names:
            row=row_at(times[name],histories[name],name,lags,holiday_country)
            for c in past_columns:
                row['past::'+str(c)]=covariate_plan.loc[(str(name),times[name]),c] if auto_covariates else data[name]['raw::'+str(c)].iloc[start-1]
            for c in known_columns:
                if future_known is None:
                    row['known::'+str(c)]=data[name]['raw::'+str(c)].iloc[start+i-1]
                else:
                    row['known::'+str(c)]=future_known.loc[(str(name),times[name]),c]
            batch.append(row)
        X=pd.DataFrame(batch)
        pred = np.asarray(model.predict(X), dtype=float)
        if nonnegative:
            pred = np.maximum(0, pred)
        if not np.isfinite(pred).all():
            raise ValueError('재귀 예측에서 유효하지 않은 값이 발생했습니다. 다른 모델이나 더 짧은 기간을 선택해 주세요.')
        for name, v in zip(names, pred):
            histories[name].append(float(v))
            rows.append({'구분': name, '예측시각': times[name], '예측값': float(v)})
    return pd.DataFrame(rows)


def actual_for(data, start, steps):
    return np.asarray([p.value.iloc[i] for i in range(start, start+steps) for p in data.values()])


def forecast(df, time_col, target, group, interval, duration_minutes, names, nonnegative=False, progress=None,
             auto_search=False, past_columns=(), known_columns=(), future_data=None, force_include=(),
             optimize=False, search_budget=24, auto_covariates=False, holiday_country='KR'):
    if target == time_col or group in (target, time_col):
        raise ValueError('시간·예측값·구분 컬럼은 서로 다르게 선택하세요.')
    if interval <= 0 or duration_minutes <= 0:
        raise ValueError('간격과 기간은 0보다 커야 합니다.')
    steps = math.ceil(duration_minutes / interval)
    if steps > 10080:
        raise ValueError('한 번에 최대 10,080개 미래 시점까지 예측합니다. 집계 간격을 늘리거나 기간을 줄여 주세요.')
    if not names:
        raise ValueError('비교할 모델을 선택하세요.')
    extra=list(dict.fromkeys(list(past_columns)+list(known_columns)))
    if set(past_columns)&set(known_columns):
        raise ValueError('같은 항목을 과거 정보와 미래 예정 정보에 동시에 넣지 마세요.')
    if set(extra)&{time_col,target,group}:
        raise ValueError('추가 참고 항목에서 시간·정답·구분을 제외하세요.')
    data = normalize(df, time_col, target, group, interval,extra)
    future_known=None
    if known_columns:
        if future_data is None:
            raise ValueError('미래 예정 항목을 사용하려면 미래 정보 파일을 올려 주세요.')
        required=[time_col]+([group] if group else [])+list(known_columns)
        missing=set(required)-set(future_data.columns)
        if missing:
            raise ValueError('미래 정보 파일에 필요한 항목이 없습니다: '+', '.join(sorted(missing)))
        f=future_data.copy()
        f['__time']=pd.to_datetime(f[time_col],errors='coerce')
        f['__series']=f[group].astype(str) if group else '전체'
        if f[['__time']+list(known_columns)].isna().any().any():
            raise ValueError('미래 예정 정보에 날짜 오류 또는 빈 값이 있습니다.')
        if f.duplicated(['__series','__time']).any():
            raise ValueError('미래 정보 파일에 같은 대상·시각의 중복 행이 있습니다.')
        future_known=f.set_index(['__series','__time'])
        for name,p in data.items():
            expected=[(str(name),p.time.iloc[-1]+pd.Timedelta(minutes=i*interval)) for i in range(1,steps+1)]
            if any(key not in future_known.index for key in expected):
                raise ValueError('미래 정보가 부족합니다. 마지막 기록 다음부터 예측 종료까지 모든 대상·시각의 예정 값을 넣어 주세요.')
    n = len(next(iter(data.values())))
    a, b = int(n*.6), int(n*.8)
    analysis=[]
    train_preview=pd.concat([p.iloc[:int(n*.35) if optimize else a] for p in data.values()],ignore_index=True)
    retained=[]
    for c in past_columns:
        v=train_preview['raw::'+str(c)]
        reason='보조 예측 후보'
        if c not in force_include:
            if v.isna().mean()>.95:reason='빈 값 95% 초과로 제외'
            elif v.nunique(dropna=True)<=1:reason='학습 기록에서 값이 변하지 않아 제외'
            elif not pd.api.types.is_numeric_dtype(v) and v.nunique()>20 and v.nunique()/len(v)>.9:reason='거의 매번 다른 문자값이라 제외'
        if reason=='보조 예측 후보':retained.append(c)
        analysis.append({'항목':str(c),'형식':str(v.dtype),'학습빈값비율':float(v.isna().mean()),'학습고유값수':int(v.nunique()),'처리':reason})
    if optimize or auto_covariates:past_columns=tuple(retained)

    lags=list(LAGS)
    if optimize:
        for minutes in (1440,10080,20160,40320):
            lag=minutes/interval
            if lag.is_integer() and int(lag)>0 and int(lag)<int(n*.5)/2:
                lags.append(int(lag))
    lags=tuple(sorted(set(lags)))
    candidates=catalog('regression')
    results,notices,fitted=[],[],{}
    if optimize:
        trials=make_trials(names,'regression',search_budget)
        # Full requested horizons, entirely before the untouched final test.
        minimum=max(max(lags)+30,int(n*.35))
        recent_minimum=max(minimum,max(lags)+max(80,int(28*1440/interval))+1)
        if b-2*steps>=recent_minimum:minimum=recent_minimum
        count=min(4,(b-minimum)//steps)
        if count>=2:
            # Spread non-overlapping horizons over different historical conditions.
            origins=np.linspace(minimum,b-steps,count,dtype=int)
            folds=[(int(origin),int(origin)+steps) for origin in origins]
        else:
            folds=[(int(n*.5),int(n*.65)),(int(n*.65),b)]
        windows=[None]
        for days in (28,84):
            size=max(80,int(days*1440/interval))
            if size < min(o for o,_ in folds)-max(lags): windows.append(size)
        trials=[dict(t,window=w) for t in trials for w in windows]
        for j,(method,half,correction) in enumerate([
            ('profile',14.,False),('profile',28.,False),('profile',84.,False),
            ('profile',28.,True),('tree',28.,False),('tree',84.,True)]):
            trials.append({'id':f'D{j+1:03d}','name':DIRECT_NAMES[method=='tree'],
                'selection':'all','params':{'method':method,'half_life_days':half,'calibrate':correction},'window':None})
        for j,(method,half,mode) in enumerate([
            ('profile',14.,'off'),('profile',28.,'off'),
            ('profile',14.,'clip'),('profile',28.,'clip'),
            ('profile',14.,'downweight'),('profile',28.,'downweight'),
            ('tree',28.,'clip'),('tree',28.,'downweight')]):
            trials.append({'id':f'R{j+1:03d}','name':DIRECT_NAMES[method=='tree'],
                'selection':'all','params':{'method':method,'half_life_days':half,'robust_mode':mode,'separate_holidays':True},'window':None})
        for j,statistic in enumerate(('mean','median')):
            trials.append({'id':f'W{j+1:03d}','name':REFERENCE_NAMES[j],'selection':'all',
                'params':{'weeks':4,'statistic':statistic},'window':None})
        for j,(method,half,robust) in enumerate([
            ('profile',14.,'off'),('profile',28.,'off'),('profile',28.,'downweight'),
            ('mae_boost',28.,'off'),('mae_boost',28.,'downweight')]):
            trials.append({'id':f'M{j+1:03d}','name':'직접 예측 · MAE 중심 학습','selection':'all',
                'params':{'method':method,'half_life_days':half,'robust_mode':robust,
                          'statistic':'median','separate_holidays':True},'window':None})
        # Calendar/event candidates compete on the same past-only validation horizons.
        for j,(method,half,correction) in enumerate([
            ('event_profile',84.,False),('event_profile',365.,False),
            ('tree',84.,True),('mae_boost',84.,True)]):
            trials.append({'id':f'H{j+1:03d}','name':'직접 예측 · 연휴·혼잡 보정','selection':'all',
                'params':{'method':method,'half_life_days':half,'separate_holidays':True,
                          'calibrate':correction,'calibration_by_hour':correction},'window':None})
        for j,(learner,feature_set) in enumerate([('ridge','basic'),('ridge','extended'),('hgb','basic'),('hgb','extended')]):
            trials.append({'id':f'E{j+1:03d}','name':RESIDUAL_NAME,'selection':'all',
                'params':{'learner':learner,'feature_set':feature_set},'window':None})
        for j,(method,pack) in enumerate([('count_boost','basic'),('count_boost','extended'),('squared_boost','basic'),('squared_boost','extended')]):
            trials.append({'id':f'F{j+1:03d}','name':'직접 예측 · 수요량 부스팅','selection':'all',
                'params':{'method':method,'feature_pack':pack,'half_life_days':28.,'separate_holidays':False},'window':None})
        for j,scope in enumerate(('daytype','daytype_hour')):
            trials.append({'id':f'G{j+1:03d}','name':REGIME_NAME,'selection':'all','params':{'scope':scope},'window':None})
    else:
        variants=['all','auto'] if auto_search else ['all']
        trials=[{'name':name,'selection':mode,'params':{},'id':''} for name in names for mode in variants]
        folds=[(a,b)]
    folds=[(origin,min(steps,end-origin)) for origin,end in folds]
    # Cached features and auxiliary forecasts are fitted only before each origin.
    fold_cache=[]
    for origin,count in folds:
        X,y=supervised(data,origin,past_columns,known_columns,auto_covariates,lags,holiday_country)
        plan,_=auxiliary_plan(data,origin,count,interval,past_columns) if auto_covariates and past_columns else (None,[])
        fold_cache.append((origin,count,X,y,plan))
    if optimize and min(len(X)//len(data) for _,_,X,_,_ in fold_cache)*interval<40320:
        notices.append('일부 검증 학습 구간은 4주 기록이 부족합니다. 최근 4주 기준 후보는 관측된 주만 사용하고, 동일 시각 기록이 없으면 학습 요일·시각 패턴으로 대체합니다.')
    forced=tuple(('past::'+str(c) if c in past_columns else 'known::'+str(c)) for c in force_include if c in extra)
    for i,trial in enumerate(trials):
        name,mode,params=trial['name'],trial['selection'],trial['params']
        label=(trial['id']+' · ' if optimize else '')+name+(' · 시간 패턴 전용' if name in NATIVE_NAMES else (' · '+selection_label(mode) if auto_search or optimize else ''))
        window=trial.get('window')
        if optimize: label+=' · '+('전체 기간' if window is None else f'최근 {window}개/대상')
        if params.get('separate_holidays'):
            label+=' · 공휴일 분리 · '+{'off':'원본 유지','clip':'극단값 완화','downweight':'극단값 가중치 축소'}[params.get('robust_mode','off')]
        if progress:progress(i/len(trials),label)
        begin=time.perf_counter()
        try:
            direct=name==REGIME_NAME or name==RESIDUAL_NAME or name in DIRECT_NAMES or name in REFERENCE_NAMES or name in ('직접 예측 · MAE 중심 학습','직접 예측 · 연휴·혼잡 보정','직접 예측 · 수요량 부스팅')
            native=name in NATIVE_NAMES or direct
            base=RegimeMAEModel(interval=interval) if name==REGIME_NAME else ResidualCalendarModel(interval=interval) if name==RESIDUAL_NAME else WeeklyReferenceModel(interval=interval) if name in REFERENCE_NAMES else DirectCalendarModel(interval=interval) if direct else TimePatternPipeline(method=name,interval=interval) if native else (candidates[name] if name in candidates else load_optional(name,'regression'))
            metrics=[];fold_errors=[]
            for origin,count,X,y,plan in fold_cache:
                p=clone(base).set_params(**params) if native else pipeline(clone(base).set_params(**params),(),mode,'regression',forced)
                if optimize: p=WindowModel(p,window)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always',ConvergenceWarning)
                    p.fit(X,y)
                if any(issubclass(w.category,ConvergenceWarning) for w in caught):
                    notices.append(label+': 수렴 경고')
                out=recursive(p,data,origin,count,interval,nonnegative,past_columns,known_columns,None,auto_covariates,lags,plan,holiday_country)
                m=score(actual_for(data,origin,count),out['예측값'],'regression')
                metrics.append(m);fold_errors.append(m['MAE'])
            results.append({'모델':label,'모델종류':name,'입력고정':native,'사용 항목':', '.join(p.named_steps['select'].columns_),'설정값':str(params),'MAE':float(np.mean(fold_errors)),
                            'RMSE':float(np.mean([m['RMSE'] for m in metrics])),
                            '검증별 오차':str([round(x,4) for x in fold_errors]),
                            '사용 항목 수':len(p.named_steps['select'].columns_),
                            '학습·평가초':round(time.perf_counter()-begin,3)})
            fitted[label]=p
        except Exception as e:
            notices.append(f'{label} 제외: {e}')
    subset_trace=[]
    if optimize:
        from .subset_search import search_subsets
        from .feature_selector import ColumnSelector
        # Rank only with the earliest fold's training rows. No validation/test targets in MI.
        first_X,first_y=fold_cache[0][2:4]
        mandatory=tuple(dict.fromkeys(('series',)+forced))
        ranking=ColumnSelector(mode='auto',force_include=mandatory).fit(first_X,first_y)
        universe=tuple(c for c in first_X if c in ranking.scores_ or c in mandatory)
        ranked=sorted(universe,key=lambda c:ranking.scores_.get(c,0.),reverse=True)
        for family in names:
            if family=='기준 모델':continue
            # Native reference/profile methods have a fixed mathematical definition.
            pool=[r for r in results if r.get('모델종류')==family and not r.get('입력고정',True)]
            if not pool:continue
            parent=min(pool,key=lambda r:r['MAE'])
            template=clone(fitted[parent['모델']])
            if progress:progress(.94,family+' · 컬럼 추가·제거 MAE 비교 중')
            def configured(columns):
                model=clone(template)
                model.estimator.set_params(select__mode='all',select__columns=tuple(columns))
                return model
            def evaluate(columns):
                model=configured(columns);metrics=[]
                for origin,count,X,y,plan in fold_cache:
                    model.fit(X,y)
                    out=recursive(model,data,origin,count,interval,nonnegative,past_columns,known_columns,None,auto_covariates,lags,plan,holiday_country)
                    metrics.append(score(actual_for(data,origin,count),out['예측값'],'regression'))
                label='컬럼탐색 · '+family+' · '+str(len(subset_trace)+1)
                mean=float(np.mean([m['MAE'] for m in metrics]))
                results.append({'모델':label,'모델종류':family,'입력고정':False,'설정값':parent['설정값'],
                    'MAE':mean,'RMSE':float(np.mean([m['RMSE'] for m in metrics])),
                    '검증별 오차':str([m['MAE'] for m in metrics]),'사용 항목 수':len(columns),
                    '사용 항목':', '.join(columns),'학습·평가초':0.})
                fitted[label]=model
                subset_trace.append({'모델':family,'후보':label,'사용항목':list(columns),'MAE':mean})
                return mean
            try:
                columns,mae,trace=search_subsets(universe,ranked,mandatory,evaluate,budget=24)
                # Preserve every attempted move, including failures, for review.
                for row in trace:row['모델']=family
                notices.extend(family+' 컬럼탐색 제외: '+row['오류'] for row in trace if '오류' in row)
                for row in trace:
                    matches=[v for v in subset_trace if v['모델']==family and v['사용항목']==row['사용항목']]
                    if matches:matches[0].update(row)
            except Exception as exc:notices.append(family+' 컬럼탐색 제외: '+str(exc))
    if not results:
        raise ValueError('실행 가능한 모델이 없습니다. ' + '\n'.join(notices))
    if optimize and len(results)>=2:
        ranked=sorted(results,key=lambda r:r['MAE'])
        # One candidate per model family so window variants cannot dominate a blend.
        selected=[];families=set()
        for r in ranked:
            key=r.get('모델종류') or (r['모델'].split(' · ')[1:3] if '직접 예측' in r['모델'] else r['모델'].split(' · ')[1])
            key=str(key)
            if key not in families:
                selected.append(r['모델']);families.add(key)
            if len(selected)==3:break
        for k in (2,3):
            if len(selected)<k:continue
            label=f'상위 {k}개 모델 결합'
            if progress:progress(.97,label+' 검증 중')
            try:
                blend=AveragedModel(tuple(clone(fitted[x]) for x in selected[:k]))
                metrics=[]
                for origin,count,X,y,plan in fold_cache:
                    blend.fit(X,y)
                    out=recursive(blend,data,origin,count,interval,nonnegative,past_columns,known_columns,None,auto_covariates,lags,plan,holiday_country)
                    metrics.append(score(actual_for(data,origin,count),out['예측값'],'regression'))
                results.append({'모델':label,'설정값':str(selected[:k]),'MAE':float(np.mean([m['MAE'] for m in metrics])),
                    'RMSE':float(np.mean([m['RMSE'] for m in metrics])),'검증별 오차':str([m['MAE'] for m in metrics]),
                    '사용 항목 수':len(blend.named_steps['select'].columns_),'학습·평가초':0.})
                fitted[label]=blend
            except Exception as e:notices.append(f'{label} 제외: {e}')
    table = pd.DataFrame(results).sort_values(['MAE','사용 항목 수']).reset_index(drop=True)
    best = table.iloc[0]['모델']
    p = clone(fitted[best])
    if progress:progress(.98,'선택한 조합으로 별도 최종 평가 중')
    X,y = supervised(data,b,past_columns,known_columns,auto_covariates,lags,holiday_country)
    p.fit(X,y)
    test_count = min(steps,n-b)
    test = recursive(p,data,b,test_count,interval,nonnegative,past_columns,known_columns,None,auto_covariates,lags,holiday_country=holiday_country)
    test['실제값'] = actual_for(data,b,test_count)
    test_metrics = score(test['실제값'],test['예측값'],'regression')
    # Refit the frozen winning family on every observed record for future output.
    if progress:progress(.99,'전체 과거 기록으로 재학습하고 미래 예측 중')
    X,y = supervised(data,n,past_columns,known_columns,auto_covariates,lags,holiday_country)
    final = clone(p).fit(X,y)
    final_plan,aux_audit=auxiliary_plan(data,n,steps,interval,past_columns) if auto_covariates and past_columns else (None,[])
    future = recursive(final,data,n,steps,interval,nonnegative,past_columns,known_columns,future_known,auto_covariates,lags,final_plan,holiday_country)
    if isinstance(final,TimePatternPipeline) or (isinstance(final,WindowModel) and isinstance(final.estimator,(TimePatternPipeline,DirectCalendarModel))):
        aux_audit=[];final_plan=None
    def treatment_details(model):
        if isinstance(model,WindowModel):return treatment_details(model.estimator_)
        if isinstance(model,AveragedModel):return [v for e in model.estimators_ for v in treatment_details(e)]
        if isinstance(model,DirectCalendarModel):return [dict(model.treatment_audit_,공휴일분리=model.separate_holidays,모델=model.method)]
        return []
    treatment=treatment_details(final)
    history_dates=sorted({ts.date() for part in data.values() for ts in part.time})
    seen={}
    for day in history_dates:
        cf=calendar_features(day,holiday_country)
        if cf['is_holiday']:seen[cf['holiday_name']]=seen.get(cf['holiday_name'],0)+1
    calendar_audit=[]
    for day in sorted({ts.date() for ts in future['예측시각']}):
        cf=calendar_features(day,holiday_country)
        calendar_audit.append({'날짜':str(day),'공휴일':cf['holiday_name'],'연속휴일수':cf['day_off_run_length'],
            '연휴중순서':cf['day_off_run_position'],'같은공휴일_학습일수':seen.get(cf['holiday_name'],0) if cf['is_holiday'] else None})
        if cf['is_holiday'] and not seen.get(cf['holiday_name'],0):
            notices.append(cf['holiday_name']+': 학습에 같은 공휴일 기록이 없어 다른 휴일 패턴으로 추정합니다. 전년도 같은 연휴 기록을 추가하면 비교할 수 있습니다.')

    report = {'상황별모델선택':[row for item in treatment for row in item.get('상황별선택',[])],'컬럼추가제거탐색':subset_trace,'컬럼탐색설명':'일반 ML 모델별 최선 설정·기간에서 전체/상위절반을 시작점으로 컬럼 추가·제거를 최대 24회 검증. 같은 시간순 검증 MAE가 개선되면 이동. 전수탐색 아님. 수학적 입력이 고정된 기준·패턴 모델은 별도 기준으로 비교.', '예측기간달력':calendar_audit,'이상치공휴일처리':treatment,'프로그램버전':'3.0-period-evaluation', '선택모델': best, '요청기간_분': duration_minutes, '예측간격_분': interval, '미래시점수_구분당': steps,
              '미래종료시각': str(future['예측시각'].max()), '과거기록수_구분당': n, '검증시점수_구분당': [count for _,count in folds] if optimize else min(steps,b-a),
              '테스트시점수_구분당': test_count, '최종테스트': test_metrics,
              '설명':'학습 구간 안에서 항목 선택과 모델 설정을 학습하고 이후 구간에서 비교합니다. 미래 값을 모르는 참고 항목은 자동보조예측 모드에서는 각 예측 시작 이전의 기록만으로 추정하며, 수동 모드에서는 마지막 값을 유지합니다. 재학습 시 선택 항목은 바뀔 수 있습니다.',
              '데이터분석':analysis,'자동최적화':optimize,'탐색횟수':len(results),'학습기간후보_칸':windows if optimize else [None],'요청기간전체검증':all(count==steps for _,count in folds),'검증구간수':len(folds),'검증구간':[{'학습종료':str(next(iter(data.values())).time.iloc[origin-1]),'검증시작':str(next(iter(data.values())).time.iloc[origin]),'검증종료':str(next(iter(data.values())).time.iloc[origin+count-1]),'시점수':count} for origin,count in folds],'선택설정값':dict(final.named_steps['model'].get_params(), 학습기간_칸=final.window if isinstance(final,WindowModel) else '구성 모델별 기간'),'자동보조예측':auto_covariates,'보조예측방법':aux_audit,'지연간격_칸':list(lags),'공휴일국가':holiday_country,'날짜특성':['연속 휴일 길이·순서','공휴일까지·이후 경과일(15일 한도)','공휴일명×시간','요일×시각 조합','공휴일·대체공휴일','공휴일명','휴일 전날·다음날','주말 또는 휴일','징검다리 평일','요일','주말','시각','월','연중일','주차','월초·월말','시간·요일·월의 주기 표현'],'알림':list(dict.fromkeys(notices)), '선택항목': final.named_steps['select'].columns_, '항목선택_상세': final.named_steps['select'].audit_, '과거참고항목':list(past_columns), '미래예정항목':list(known_columns)}
    if steps > min([count for _,count in folds]+[n-b]):
        report['알림'].append('요청한 기간 전체를 검증할 과거 데이터가 부족합니다. 실제 평가한 기간은 검증·테스트 시점수를 확인하세요.')
    bundle = {'pipeline': final, 'interval_minutes': interval, 'nonnegative': nonnegative, 'time_col': time_col,
              'target': target, 'group': group, 'model': best, 'kind': 'recursive_forecast', 'past_columns':list(past_columns), 'known_columns':list(known_columns),'auto_covariates':auto_covariates,'lags':lags,'auxiliary_plan':final_plan,'holiday_country':holiday_country,'forecast_origin':str(next(iter(data.values())).time.iloc[-1]),'target_history':{name:p.value.iloc[-max(lags):].tolist() for name,p in data.items()}}
    if progress:
        progress(1., '완료')
    return future, table, test, report, bundle
