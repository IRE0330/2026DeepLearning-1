"""Column-name independent tabular model comparison. No network/API calls."""
import io
import time
import warnings
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, ExtraTreesRegressor, ExtraTreesClassifier
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.dummy import DummyRegressor, DummyClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, f1_score, accuracy_score
from feature_selector import make_selector
from model_catalog import catalog, load_optional, OPTIONAL
from sklearn.exceptions import ConvergenceWarning
from search_space import make_trials, selection_label
from calendar_features import calendar_features


def read_csv(data):
    for encoding in ['utf-8-sig', 'cp949', 'utf-16']:
        try:
            df = pd.read_csv(io.BytesIO(data), encoding=encoding, sep=None, engine='python')
            if not df.columns.is_unique:
                raise ValueError('중복 컬럼명을 수정해 주세요.')
            return df
        except UnicodeError:
            continue
    raise ValueError('CSV 인코딩을 확인해 주세요. UTF-8로 저장하면 됩니다.')


def excel_sheets(data):
    with pd.ExcelFile(io.BytesIO(data)) as book:
        return book.sheet_names


def read_table(data, filename, sheet_name=0):
    if filename.lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet_name)
        if df.empty or len(df.columns) == 0:
            raise ValueError('선택한 시트에 데이터가 없습니다.')
        return df
    return read_csv(data)


class TypeAdapter(BaseEstimator, TransformerMixin):
    """Learn numeric/categorical schema only from training rows; dates are explicit."""
    def __init__(self, dates=(), holiday_country='KR'):
        self.dates = dates
        self.holiday_country=holiday_country

    def fit(self, X, y=None):
        self.columns_ = list(X.columns)
        self.numeric_ = [c for c in X if c not in self.dates and pd.api.types.is_numeric_dtype(X[c])]
        return self

    def transform(self, X):
        missing = set(self.columns_) - set(X.columns)
        if missing:
            raise ValueError('새 데이터에 필요한 컬럼이 없습니다: ' + ', '.join(sorted(missing)))
        out = pd.DataFrame(index=X.index)
        for i, c in enumerate(self.columns_):
            s = X[c]
            key = f'f{i}'
            if c in self.dates:
                d = pd.to_datetime(s, errors='coerce')
                if not (pd.api.types.is_datetime64_any_dtype(d) or isinstance(d.dtype,pd.DatetimeTZDtype)):
                    d = pd.to_datetime(s, errors='coerce', utc=True)
                for part in ['year', 'month', 'day', 'dayofweek', 'hour', 'minute']:
                    out[key + '_' + part] = getattr(d.dt, part).astype(float)
                out[key+'_weekend']=(d.dt.dayofweek>=5).astype(float)
                out[key+'_hour_sin']=np.sin(2*np.pi*(d.dt.hour+d.dt.minute/60)/24)
                out[key+'_hour_cos']=np.cos(2*np.pi*(d.dt.hour+d.dt.minute/60)/24)
                out[key+'_weekday_sin']=np.sin(2*np.pi*d.dt.dayofweek/7)
                out[key+'_weekday_cos']=np.cos(2*np.pi*d.dt.dayofweek/7)
                calendar_rows=[calendar_features(ts,getattr(self,'holiday_country','KR')) if pd.notna(ts) else {} for ts in d]
                calendar=pd.DataFrame(calendar_rows,index=X.index)
                for column in calendar:
                    out[key+'_'+column]=calendar[column]
            elif c in self.numeric_:
                out[key] = pd.to_numeric(s, errors='coerce').replace([np.inf, -np.inf], np.nan)
            else:
                out[key] = s.map(lambda v: str(v) if pd.notna(v) else np.nan).astype(object)
        return out


def numeric_cols(X):
    return list(X.select_dtypes(include='number').columns)


def category_cols(X):
    return list(X.select_dtypes(exclude='number').columns)


def pipeline(model, dates, selection='all', task='regression', force_include=(), force_exclude=(), holiday_country='KR'):
    prep = ColumnTransformer([
        ('numeric', Pipeline([('impute', SimpleImputer(strategy='median', keep_empty_features=True)), ('scale', StandardScaler())]), numeric_cols),
        ('category', Pipeline([('impute', SimpleImputer(strategy='constant', fill_value='(missing)', keep_empty_features=True)),
                              ('encode', OneHotEncoder(handle_unknown='ignore', max_categories=40, sparse_output=False))]), category_cols)
    ])
    return Pipeline([('select', make_selector(mode='all' if selection=='all' else 'auto', task=task, keep_fraction={'top25':.25,'top50':.5,'top75':.75}.get(selection,.5), force_include=force_include, force_exclude=force_exclude,date_columns=dates)), ('types', TypeAdapter(dates,holiday_country)), ('prepare', prep), ('model', model)])


def compare(df, target, features, task='regression', time_col=None, dates=(), gap=0, extras=False, progress=None, selected_models=None, auto_search=False, force_include=(), force_exclude=(), optimize=False, search_budget=24, holiday_country='KR'):
    if not features or target in features:
        raise ValueError('정답을 제외한 입력 컬럼을 하나 이상 선택해 주세요.')
    d = df.dropna(subset=[target]).copy()
    if task == 'regression':
        if pd.to_numeric(d[target],errors='coerce').isna().any():
            raise ValueError('예측할 항목에 숫자로 읽을 수 없는 값이 있습니다. 숫자 항목을 고르거나 종류를 맞히는 방식으로 바꿔 주세요.')
        d[target] = pd.to_numeric(d[target], errors='coerce').replace([np.inf, -np.inf], np.nan)
        d = d.dropna(subset=[target])
    else:
        d[target] = d[target].astype(str)
    if len(d) < 40:
        raise ValueError('정답이 있는 유효 데이터가 40행 이상 필요합니다.')
    if d[target].nunique() < 2:
        raise ValueError('정답 값이 모두 같습니다. 다른 데이터나 정답 컬럼을 선택해 주세요.')
    encoder = None
    if task == 'classification':
        encoder = LabelEncoder().fit(d[target])
        d[target] = encoder.transform(d[target])
    if time_col:
        ts = pd.to_datetime(d[time_col], errors='coerce', utc=True)
        if ts.isna().any():
            raise ValueError('시간 컬럼에 날짜로 읽을 수 없는 값이 있습니다.')
        d = d.assign(__sort_time=ts).sort_values('__sort_time').reset_index(drop=True)
        unique = d['__sort_time'].drop_duplicates().to_numpy()
        a, b = int(len(unique)*.6), int(len(unique)*.8)
        if a < 1 or b <= a or b >= len(unique):
            raise ValueError('서로 다른 시각이 충분하지 않습니다.')
        # Timestamp blocks are never shared between splits. gap is in minutes.
        t1, t2 = pd.Timestamp(unique[a]), pd.Timestamp(unique[b])
        dt = pd.Timedelta(minutes=gap)
        train = d[d.__sort_time < t1-dt]
        val = d[(d.__sort_time >= t1) & (d.__sort_time < t2-dt)]
        test = d[d.__sort_time >= t2]
    else:
        strat = d[target] if task == 'classification' else None
        try:
            train, rest = train_test_split(d, test_size=.4, random_state=42, stratify=strat)
            val, test = train_test_split(rest, test_size=.5, random_state=42, stratify=rest[target] if strat is not None else None)
        except ValueError as e:
            raise ValueError('데이터 분리가 어렵습니다. 분류라면 각 정답 범주의 행 수를 늘려 주세요.') from e
    if min(len(train), len(val), len(test)) < 5:
        raise ValueError('분리 후 각 구간에 최소 5행이 필요합니다. 데이터 수나 제외 간격을 확인해 주세요.')
    if task == 'classification' and (train[target].nunique() < 2 or not set(d[target]).issubset(set(train[target]))):
        raise ValueError('학습 구간에 모든 정답 범주가 있어야 합니다. 기간 또는 데이터를 조정해 주세요.')
    reg = task == 'regression'
    available = catalog(task)
    defaults = ['기준 모델', 'Random Forest', 'Extra Trees', 'Ridge' if reg else 'Logistic Regression']
    requested = list(defaults if selected_models is None else selected_models)
    if extras:
        requested += ['XGBoost', 'LightGBM']
    requested = list(dict.fromkeys(requested))
    if not requested:
        raise ValueError('비교할 모델을 하나 이상 선택해 주세요.')
    models, notices = {}, []
    for name in requested:
        if name in available:
            models[name] = available[name]
        elif name in OPTIONAL:
            try:
                models[name] = load_optional(name, task)
            except Exception as e:
                notices.append(f'{name} 제외 (선택 패키지 설치 확인): {e}')
        else:
            raise ValueError('지원하지 않는 모델: ' + name)
    rows, fitted = [], {}
    variants=['all','auto'] if auto_search else ['all']
    if optimize:
        trials=make_trials(list(models),task,search_budget)
    else:
        trials=[{'name':name,'selection':mode,'params':{},'id':''} for name in models for mode in variants]
    jobs=[(t,models[t['name']]) for t in trials]
    for i, (trial, model) in enumerate(jobs):
        name,mode,params=trial['name'],trial['selection'],trial['params']
        label=(trial['id']+' · ' if optimize else '')+name+(' · '+selection_label(mode) if auto_search or optimize else '')
        if progress:
            progress(i / len(jobs), label)
        start = time.perf_counter()
        try:
            p = pipeline(clone(model).set_params(**params), dates, mode, task, force_include, force_exclude,holiday_country)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always', ConvergenceWarning)
                p.fit(train[features], train[target])
            for warning in caught:
                if issubclass(warning.category, ConvergenceWarning):
                    notices.append(f'{label}: 수렴 경고 — 설정값 조정이 필요할 수 있습니다.')
            pred = p.predict(val[features])
            metrics = score(val[target], pred, task)
            rows.append({'모델': label, '모델종류':name, '사용 항목':', '.join(p.named_steps['select'].columns_), '설정값':str(params), **metrics, '사용 항목 수':len(p.named_steps['select'].columns_), '학습초': round(time.perf_counter()-start, 3)})
            fitted[label] = p
        except Exception as e:
            notices.append(f'{label} 실패: {e}')
    subset_trace=[]
    if optimize and reg:
        from subset_search import search_subsets
        ranking=make_selector(mode='auto',task=task,force_include=force_include,force_exclude=force_exclude,date_columns=dates).fit(train[features],train[target])
        universe=tuple(c for c in features if (c in ranking.scores_ or c in force_include) and c not in force_exclude)
        ranked=sorted(universe,key=lambda c:ranking.scores_.get(c,0.),reverse=True)
        for family in models:
            if family=='기준 모델':continue
            pool=[r for r in rows if r.get('모델종류')==family]
            if not pool:continue
            parent=min(pool,key=lambda r:r['MAE']);template=clone(fitted[parent['모델']])
            if progress:progress(.94,family+' · 컬럼 추가·제거 검증 중')
            def evaluate(columns):
                model=clone(template).set_params(select__mode='all',select__columns=tuple(columns))
                start=time.perf_counter();model.fit(train[features],train[target])
                metrics=score(val[target],model.predict(val[features]),task)
                label='컬럼탐색 · '+family+' · '+str(len(subset_trace)+1)
                rows.append({'모델':label,'모델종류':family,'설정값':parent['설정값'],**metrics,
                    '사용 항목 수':len(columns),'사용 항목':', '.join(columns),'학습초':round(time.perf_counter()-start,3)})
                fitted[label]=model
                subset_trace.append({'모델':family,'후보':label,'사용항목':list(columns),'MAE':metrics['MAE']})
                return metrics['MAE']
            try:
                _,_,trace=search_subsets(universe,ranked,force_include,evaluate,budget=24)
                for row in trace:
                    matches=[v for v in subset_trace if v['모델']==family and v['사용항목']==row['사용항목']]
                    if matches:matches[0].update(row)
                    if '오류' in row:notices.append(family+' 컬럼탐색 제외: '+row['오류'])
            except Exception as exc:notices.append(family+' 컬럼탐색 제외: '+str(exc))
    if not fitted:
        raise ValueError('모든 모델 학습이 실패했습니다. ' + '\n'.join(notices))
    metric = 'MAE' if reg else 'F1_macro'
    table = pd.DataFrame(rows).sort_values([metric,'사용 항목 수'], ascending=[reg,True]).reset_index(drop=True)
    best = table.iloc[0]['모델']
    # Freeze choice, refit on train+validation, evaluate held-out test once.
    final = clone(fitted[best])
    combined = pd.concat([train, val])
    final.fit(combined[features], combined[target])
    pred = final.predict(test[features])
    truth = test[target].to_numpy()
    selected = list(final.named_steps['select'].transform(combined[features]).columns)
    output = test[features].copy()
    output['실제값'] = encoder.inverse_transform(truth) if encoder is not None else truth
    output['예측값'] = encoder.inverse_transform(np.asarray(pred, dtype=int)) if encoder is not None else pred
    bundle = {'pipeline': final, 'features': features, 'selected_features': selected, 'target': target,
              'task': task, 'label_encoder': encoder, 'best_model': best}
    report = {'컬럼추가제거탐색':subset_trace,'최적모델': best, '문제유형': task, '선택기준': metric, '최종테스트': score(truth, pred, task),
              '행수': {'학습': len(train), '검증': len(val), '테스트': len(test)}, '선택컬럼': selected, '항목선택_상세': final.named_steps['select'].audit_, '항목선택_설명':'관련성 순위 후보·모델 설정을 비교하고, 회귀에서는 모델별 컬럼 추가·제거를 최대 24회 실제 검증 MAE로 비교합니다. 고정한 컬럼 조합으로 최종 평가합니다. 전수탐색은 아닙니다.' if optimize else ('전체 항목과 관련성 상위 절반 비교' if auto_search else '전체 항목'),
              '자동최적화':optimize,'탐색횟수':len(rows),'선택모델설정':final.named_steps['model'].get_params(),'요청모델': requested, '성공모델': list(fitted), '시간컬럼': time_col, '제외간격_분': gap, '알림': notices}
    if progress:
        progress(1., '완료')
    return bundle, table, output, report


def score(y, pred, task):
    if task == 'regression':
        return {'MAE': float(mean_absolute_error(y, pred)), 'RMSE': float(np.sqrt(mean_squared_error(y, pred))), 'R2': float(r2_score(y, pred)) if len(y)>1 else None}
    return {'F1_macro': float(f1_score(y, pred, average='macro', zero_division=0)), 'Accuracy': float(accuracy_score(y, pred))}


def predict(bundle, df):
    p = bundle['pipeline'].predict(df)
    enc = bundle['label_encoder']
    out = df.copy()
    out['예측값'] = enc.inverse_transform(np.asarray(p, dtype=int)) if enc is not None else p
    return out
