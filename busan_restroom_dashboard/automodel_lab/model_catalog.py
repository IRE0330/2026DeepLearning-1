"""Estimator catalog; optional libraries loaded only when selected."""
from sklearn.ensemble import (RandomForestRegressor, RandomForestClassifier, ExtraTreesRegressor, ExtraTreesClassifier,
    GradientBoostingRegressor, GradientBoostingClassifier, HistGradientBoostingRegressor, HistGradientBoostingClassifier,
    AdaBoostRegressor, AdaBoostClassifier, BaggingRegressor, BaggingClassifier)
from sklearn.linear_model import Ridge, Lasso, ElasticNet, LinearRegression, LogisticRegression, HuberRegressor, BayesianRidge
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
from sklearn.svm import SVR, SVC
from sklearn.neural_network import MLPRegressor, MLPClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.dummy import DummyRegressor, DummyClassifier

OPTIONAL = ['XGBoost', 'LightGBM', 'CatBoost']


def catalog(task):
    reg = task == 'regression'
    models = {
        '기준 모델': DummyRegressor(strategy='mean') if reg else DummyClassifier(strategy='most_frequent'),
        'Random Forest': (RandomForestRegressor if reg else RandomForestClassifier)(n_estimators=120, min_samples_leaf=2, random_state=42, n_jobs=-1),
        'Extra Trees': (ExtraTreesRegressor if reg else ExtraTreesClassifier)(n_estimators=120, min_samples_leaf=2, random_state=42, n_jobs=-1),
        'Ridge' if reg else 'Logistic Regression': Ridge() if reg else LogisticRegression(max_iter=1500),
        'Decision Tree': (DecisionTreeRegressor if reg else DecisionTreeClassifier)(max_depth=10, min_samples_leaf=2, random_state=42),
        'Gradient Boosting': (GradientBoostingRegressor if reg else GradientBoostingClassifier)(n_estimators=100, random_state=42),
        'Hist Gradient Boosting': (HistGradientBoostingRegressor if reg else HistGradientBoostingClassifier)(max_iter=100, early_stopping=False, random_state=42),
        'AdaBoost': (AdaBoostRegressor if reg else AdaBoostClassifier)(n_estimators=80, random_state=42),
        'KNN': (KNeighborsRegressor if reg else KNeighborsClassifier)(n_neighbors=5, n_jobs=2),
        'SVR' if reg else 'SVC': SVR(max_iter=10000) if reg else SVC(max_iter=10000, random_state=42),
        'MLP (신경망)': (MLPRegressor if reg else MLPClassifier)(hidden_layer_sizes=(64,32), max_iter=300, random_state=42)
    }
    if reg:
        models.update({'Huber Regression':HuberRegressor(max_iter=1000), 'Bayesian Ridge':BayesianRidge(), 'Bagging':BaggingRegressor(n_estimators=50,random_state=42,n_jobs=2), 'Linear Regression': LinearRegression(), 'Lasso': Lasso(max_iter=3000), 'ElasticNet': ElasticNet(max_iter=3000)})
    else:
        models.update({'Bagging':BaggingClassifier(n_estimators=50,random_state=42,n_jobs=2), 'Gaussian Naive Bayes': GaussianNB(), 'Linear Discriminant Analysis': LinearDiscriminantAnalysis()})
    return models


def model_names(task):
    return list(catalog(task)) + OPTIONAL


def load_optional(name, task):
    reg = task == 'regression'
    if name == 'XGBoost':
        from xgboost import XGBRegressor, XGBClassifier
        return (XGBRegressor if reg else XGBClassifier)(n_estimators=120, max_depth=4, learning_rate=.05, random_state=42, n_jobs=2)
    if name == 'LightGBM':
        from lightgbm import LGBMRegressor, LGBMClassifier
        return (LGBMRegressor if reg else LGBMClassifier)(n_estimators=120, verbosity=-1, random_state=42, n_jobs=2)
    if name == 'CatBoost':
        from catboost import CatBoostRegressor, CatBoostClassifier
        return (CatBoostRegressor if reg else CatBoostClassifier)(iterations=120, depth=5, verbose=False, random_seed=42, thread_count=2, allow_writing_files=False)
    raise ValueError('지원하지 않는 모델: ' + name)
