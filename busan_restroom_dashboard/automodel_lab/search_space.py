"""Budgeted joint feature/configuration search, deterministic and reviewable."""
from itertools import product
import numpy as np
from .ts_models import NATIVE_NAMES


def parameter_options(name, task='regression'):
    space={
        'Random Forest':[{}, {'max_depth':8,'min_samples_leaf':4,'max_features':.8}, {'max_depth':None,'min_samples_leaf':1,'max_features':.7}],
        'Extra Trees':[{}, {'max_depth':10,'min_samples_leaf':3,'max_features':.8}, {'max_depth':None,'min_samples_leaf':1}],
        'Huber Regression':[{'epsilon':1.1,'alpha':.001},{'epsilon':1.35,'alpha':.01},{'epsilon':1.8,'alpha':.1}],
        'Bayesian Ridge':[{}],
        'Bagging':[{'n_estimators':40,'max_samples':.8},{'n_estimators':80,'max_samples':1.}],
        '요일·시간 패턴':[{'shrink':1.},{'shrink':5.},{'shrink':15.}],
        'Fourier 계절 회귀':[{'alpha':.1,'trend':False},{'alpha':5.,'trend':True},{'alpha':20.,'trend':False}],
        'ETS 지수평활':[{'trend':True},{'trend':False}],
        'Ridge':[{'alpha':.1},{'alpha':1.},{'alpha':10.}],
        'Lasso':[{'alpha':.01},{'alpha':.1},{'alpha':1.}],
        'ElasticNet':[{'alpha':.01,'l1_ratio':.2},{'alpha':.1,'l1_ratio':.5},{'alpha':1.,'l1_ratio':.8}],
        'Logistic Regression':[{'C':.1},{'C':1.},{'C':10.}],
        'Decision Tree':[{'max_depth':4},{'max_depth':8},{'max_depth':None,'min_samples_leaf':4}],
        'Gradient Boosting':[{'learning_rate':.05,'max_depth':2},{'learning_rate':.1,'max_depth':3},{'learning_rate':.05,'n_estimators':160}],
        'Hist Gradient Boosting':[{'learning_rate':.05,'max_leaf_nodes':15},{'learning_rate':.1,'max_leaf_nodes':31},{'l2_regularization':1.,'max_leaf_nodes':15}],
        'AdaBoost':[{'learning_rate':.05},{'learning_rate':.3},{'learning_rate':1.}],
        'KNN':[{'n_neighbors':3,'weights':'distance'},{'n_neighbors':7,'weights':'distance'},{'n_neighbors':12,'weights':'uniform'}],
        'SVR':[{'C':.5,'epsilon':.1},{'C':5.,'epsilon':.1},{'C':20.,'epsilon':.2}],
        'SVC':[{'C':.5},{'C':2.},{'C':10.}],
        'MLP (신경망)':[{'hidden_layer_sizes':(32,), 'alpha':.001},{'hidden_layer_sizes':(64,32),'alpha':.01}],
        'XGBoost':[{'max_depth':3,'learning_rate':.05},{'max_depth':5,'learning_rate':.08},{'max_depth':4,'n_estimators':200}],
        'LightGBM':[{'num_leaves':15,'learning_rate':.05},{'num_leaves':31,'learning_rate':.08},{'num_leaves':15,'n_estimators':200}],
        'CatBoost':[{'depth':4,'learning_rate':.05},{'depth':6,'learning_rate':.08},{'depth':5,'iterations':200}]
    }
    return space.get(name,[{}])


def make_trials(names, task='regression', budget=24):
    names=list(dict.fromkeys(names))
    if budget<len(names):budget=len(names)
    # Start with one full baseline per family, then balanced feature-size/config diversity.
    selected=[{'name':n,'selection':'all','params':parameter_options(n,task)[0]} for n in names]
    remaining=[]
    for n in names:
        params=parameter_options(n,task)
        for mode,p in product(['all'] if n in NATIVE_NAMES else ['all','top25','top50','top75'],params):
            trial={'name':n,'selection':mode,'params':p}
            if trial not in selected:remaining.append(trial)
    rng=np.random.default_rng(42)
    rng.shuffle(remaining)
    selected+=remaining[:max(0,budget-len(selected))]
    for i,t in enumerate(selected):
        t['id']=f'T{i+1:03d}'
    return selected


def selection_label(mode):
    return {'all':'전체 항목','auto':'자동 선택 50%','top25':'자동 선택 25%','top50':'자동 선택 50%','top75':'자동 선택 75%'}.get(mode,mode)
