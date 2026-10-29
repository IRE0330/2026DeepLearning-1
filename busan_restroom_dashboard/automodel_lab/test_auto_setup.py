import pandas as pd
import numpy as np
from auto_setup import prepare_time, infer_group, automatic_exclusions, parse_dates
from easy_view import guess_interval
n=120
t=pd.date_range('2017-12-01',periods=n,freq='h')
df=pd.DataFrame({'Date':t.strftime('%d/%m/%Y'),'Hour':t.hour,'demand':np.arange(n)%30,'Temperature':np.sin(np.arange(n))})
p,tc,sources=prepare_time(df)
assert sources==['Date','Hour']
assert p[tc].tolist()==t.tolist()
assert guess_interval(p,tc)==60
assert parse_dates(pd.Series([0,1,2]),'Hour') is None
assert parse_dates(pd.Series([1,2,3]),'count') is None
assert infer_group(p,tc,'demand') is None
multi=pd.concat([df.assign(device='A'),df.assign(device='B')],ignore_index=True)
p,tc,sources=prepare_time(multi)
assert infer_group(p,tc,'demand')=='device'
assert any(r['항목']=='Temperature' and '미래 값' in r['자동 처리'] for r in automatic_exclusions(p,tc,'demand','device',sources))
# Text timestamp and YYYYMMDD numeric date are supported without ns-epoch mistakes.
p,tc,_=prepare_time(pd.DataFrame({'recorded_at':t,'value':np.arange(n)}))
assert p[tc].iloc[-1]==t[-1]
assert parse_dates(pd.Series([20261024,20261025]),'date').iloc[0]==pd.Timestamp('2026-10-24')
print('PASS: Date+Hour merge, real dates instead of 1970, automatic interval/group/exclusions')
