"""Cloneable training-window and validated equal-weight ensemble estimators."""
from types import SimpleNamespace
import numpy as np
from sklearn.base import BaseEstimator, clone


class WindowModel(BaseEstimator):
    def __init__(self, estimator, window=None):
        self.estimator = estimator
        self.window = window

    def fit(self, X, y):
        positions = np.arange(len(X))
        if self.window is not None:
            positions = np.concatenate([
                np.flatnonzero(X['series'].to_numpy() == name)[-self.window:]
                for name in X['series'].unique()
            ])
        self.estimator_ = clone(self.estimator).fit(X.iloc[positions], np.asarray(y)[positions])
        self.training_rows_ = len(positions)
        return self

    def predict(self, X):
        # Tiny recursive batches otherwise spawn tree workers at every timestamp.
        model=self.estimator_.named_steps['model'] if hasattr(self.estimator_,'named_steps') else self.estimator_
        if hasattr(model,'n_jobs') and len(X)<32:
            model.set_params(n_jobs=1)
        return self.estimator_.predict(X)

    @property
    def named_steps(self):
        return self.estimator_.named_steps


class AveragedModel(BaseEstimator):
    def __init__(self, estimators):
        self.estimators = estimators

    def fit(self, X, y):
        self.estimators_ = [clone(e).fit(X, y) for e in self.estimators]
        return self

    def predict(self, X):
        return np.mean([e.predict(X) for e in self.estimators_], axis=0)

    @property
    def named_steps(self):
        columns = list(dict.fromkeys(c for e in self.estimators_ for c in e.named_steps['select'].columns_))
        audit = [dict(row, 구성모델=i+1) for i,e in enumerate(self.estimators_) for row in e.named_steps['select'].audit_]
        # Shallow parameters keep the user report JSON serializable.
        return {'model': SimpleNamespace(get_params=lambda: {
            '결합방식': '동일 가중 평균',
            '구성': [str(e.get_params(deep=False)) for e in self.estimators]
        }), 'select': SimpleNamespace(columns_=columns, audit_=audit)}
