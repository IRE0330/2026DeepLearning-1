import pandas as pd
from multi_input import combine_tables, suggest_keys

a=pd.DataFrame({'Date':['2026-10-01','2026-10-01'],'Hour':[0,1],'value':[4,5]})
b=pd.DataFrame({'Date':['2026-10-01','2026-10-01'],'Hour':[1,2],'value':[5,6]})
r,log=combine_tables([a,b],['a.csv','b.xlsx'])
assert len(r)==3 and r.value.tolist()==[4,5,6]
w=pd.DataFrame({'Date':['2026-10-01','2026-10-01'],'Hour':[0,1],'weather':[20,21]})
r,log=combine_tables([a,w],['history.csv','weather.csv'])
assert len(r)==2 and r.weather.tolist()==[20,21]
assert suggest_keys(a,w)==['Date','Hour']
different=w.rename(columns={'Date':'day','Hour':'hour_index'})
r,_=combine_tables([a,different],['a','b'],'join',plans={1:(['Date','Hour'],['day','hour_index'])})
assert r.weather.tolist()==[20,21]
try:
    combine_tables([a,pd.concat([w,w.iloc[[0]]])],['a','b'])
    raise AssertionError('ambiguous merge accepted')
except ValueError:pass
bad=w.copy();bad.Date='2027-01-01'
try:
    combine_tables([a,bad],['a','b'])
    raise AssertionError('all-unmatched accepted')
except ValueError:pass
r,log=combine_tables([a,w.iloc[[0]]],['a','b'])
assert r.weather.isna().sum()==1 and log[0]['미일치행']==1
print('PASS: append, duplicate removal, automatic date/hour join, different key names, ambiguous and unmatched protection')
