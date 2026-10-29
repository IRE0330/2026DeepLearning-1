"""Train-only raw-column selection. Works with arbitrary DataFrame column names."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_selection import mutual_info_regression, mutual_info_classif


class ColumnSelector(BaseEstimator, TransformerMixin):
    def __init__(self, columns=None, mode='all', task='regression', keep_fraction=.5, force_include=(), force_exclude=(), date_columns=()):
        self.columns=columns
        self.mode=mode
        self.task=task
        self.keep_fraction=keep_fraction
        self.force_include=force_include
        self.force_exclude=force_exclude
        self.date_columns=date_columns

    def fit(self,X,y=None):
        candidates=list(X.columns) if self.columns is None else list(self.columns)
        excluded=set(self.force_exclude)
        forced=set(self.force_include)-excluded
        if not set(candidates).issubset(X.columns):
            raise ValueError('입력 항목 목록을 확인해 주세요.')
        safe, reasons, encoded, discrete = [], {}, [], []
        for c in candidates:
            s=X[c]
            if c in excluded:
                reasons[c]='사용자가 제외';continue
            if self.mode=='all':
                safe.append(c);continue
            if c not in forced:
                if s.isna().mean()>.95:
                    reasons[c]='학습 기록의 95% 초과가 빈 값';continue
                if s.nunique(dropna=True)<=1:
                    reasons[c]='학습 기록에서 값이 변하지 않음';continue
                if c not in self.date_columns and not pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_datetime64_any_dtype(s):
                    if s.nunique()/len(s)>.9 and s.nunique()>20:
                        reasons[c]='거의 매번 다른 문자 값 (ID·긴 글 가능성)';continue
            safe.append(c)
            if c in self.date_columns or pd.api.types.is_datetime64_any_dtype(s):
                parsed=pd.to_datetime(s,errors='coerce',utc=True)
                v=parsed.astype('int64').astype(float)
                v[parsed.isna()]=np.nan;disc=False
            elif pd.api.types.is_numeric_dtype(s):
                v=pd.to_numeric(s,errors='coerce').replace([np.inf,-np.inf],np.nan);disc=False
            else:
                v=pd.Series(pd.factorize(s.fillna('(missing)').astype(str),sort=True)[0],index=s.index,dtype=float);disc=True
            v=v.fillna(v.median() if v.notna().any() else 0)
            encoded.append(v.to_numpy());discrete.append(disc)
        self.scores_={}
        if self.mode=='all':
            chosen=safe
        else:
            if not safe:
                raise ValueError('자동 선택할 항목이 없습니다. 값이 변하는 항목을 넣거나 반드시 포함할 항목을 지정하세요.')
            matrix=np.column_stack(encoded)
            # Fixed subsample is drawn only inside supplied training rows.
            if len(matrix)>4000:
                ids=np.random.default_rng(42).choice(len(matrix),4000,replace=False)
                matrix=matrix[ids];labels=np.asarray(y)[ids]
            else:
                labels=np.asarray(y)
            # MI can be undefined for singleton categories. Treat those columns as continuous ranks.
            disc=np.asarray(discrete)
            for i in np.where(disc)[0]:
                _,counts=np.unique(matrix[:,i],return_counts=True)
                if counts.min()<2:disc[i]=False
            fn=mutual_info_regression if self.task=='regression' else mutual_info_classif
            scores=fn(matrix,labels,discrete_features=disc,random_state=42,n_neighbors=min(3,len(labels)-1))
            self.scores_={c:float(v) for c,v in zip(safe,scores)}
            k=max(1,int(np.ceil(len(safe)*self.keep_fraction)))
            ranked=sorted(safe,key=lambda c:self.scores_[c],reverse=True)
            selected=set(ranked[:k])|forced
            chosen=[c for c in safe if c in selected]
            for c in safe:
                reasons[c]='사용자가 반드시 포함' if c in forced else ('학습 기록의 관련성 순위로 선택' if c in selected else '이번 선택 범위보다 관련성 순위가 낮음')
        if not chosen:
            raise ValueError('입력 항목을 하나 이상 남겨 주세요.')
        self.columns_=chosen
        self.audit_=[{'항목':c,'사용 여부':'사용' if c in chosen else '제외','이유':reasons.get(c,'전체 항목 비교'),
                      '관련성 참고 점수':self.scores_.get(c)} for c in candidates]
        if self.columns is not None:
            self.audit_.extend({'항목':c,'사용 여부':'제외','이유':'검증 MAE로 비교한 고정 컬럼 조합에서 제외','관련성 참고 점수':None} for c in X if c not in candidates)
        return self

    def transform(self,X):
        missing=set(self.columns_)-set(X.columns)
        if missing:
            raise ValueError('필요한 입력 항목이 없습니다: '+', '.join(sorted(missing)))
        return X.loc[:,self.columns_].copy()


def make_selector(**kwargs):
    return ColumnSelector(**kwargs)
