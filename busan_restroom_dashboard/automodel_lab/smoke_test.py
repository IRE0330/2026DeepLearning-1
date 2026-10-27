import io
import os
import joblib
import numpy as np
import pandas as pd
from core import compare, predict, read_csv

rng = np.random.default_rng(42)
os.makedirs('samples', exist_ok=True)
n = 220
x = rng.normal(size=n)
d = pd.DataFrame({'면적': x, '지역': rng.choice(['부산', '서울'], n), '빈열': np.nan, '가격': 200+30*x+rng.normal(0, 3, n)})
d.loc[3, '면적'] = np.nan
d.to_csv('samples/regression.csv', index=False, encoding='utf-8-sig')
b, table, out, report = compare(d, '가격', ['면적', '지역', '빈열'])
assert len(table) == 4 and report['최종테스트']['MAE'] < 15
new = d.head().copy(); new['지역'] = '새지역'
p1 = predict(b, new)
s = io.BytesIO(); joblib.dump(b, s); s.seek(0)
p2 = predict(joblib.load(s), new)
assert np.allclose(p1['예측값'], p2['예측값'])
try:
    predict(b, new.drop(columns='면적'))
    raise AssertionError('missing schema accepted')
except (KeyError, ValueError):
    pass
c = pd.DataFrame({'기간': x, '등급': rng.choice(['A', 'B'], n), '이탈': np.where(x > 0, '예', '아니오')})
c.to_csv('samples/classification.csv', index=False, encoding='utf-8-sig')
b, table, out, report = compare(c, '이탈', ['기간', '등급'], 'classification')
assert report['최종테스트']['F1_macro'] > .8
assert set(predict(b, c.head())['예측값']).issubset({'예', '아니오'})
times = pd.date_range('2026-01-01', periods=110, freq='min').repeat(2)
t = pd.DataFrame({'시각': times.astype(str), '위치': ['북', '남']*110, '현재인원': np.arange(220)%20, '5분후인원': rng.integers(0, 20, 220)})
t.to_csv('samples/time_regression.csv', index=False, encoding='utf-8-sig')
b, _, out, report = compare(t, '5분후인원', ['시각', '위치', '현재인원'], time_col='시각', dates=('시각',), gap=5)
assert report['행수'] == {'학습': 122, '검증': 34, '테스트': 44}, report['행수']
assert len(out['시각'].unique()) == 22
assert read_csv(d.to_csv(index=False).encode('utf-8')).shape == d.shape
print('PASS: regression / classification / temporal groups+gap / missing values / unknown categories / persistence / schema')
