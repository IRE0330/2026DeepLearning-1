import pandas as pd
from easy_view import range_plan, result_table, guess_interval, suggest
last=pd.Timestamp('2026-10-01 12:00')
minutes,start,end=range_plan(last,'2026-10-01 12:17','2026-10-01 13:03',5)
assert minutes==60 and start==pd.Timestamp('2026-10-01 12:20') and end==pd.Timestamp('2026-10-01 13:00')
for s,e in [('2026-10-01 11:00','2026-10-01 13:00'),('2026-10-01 14:00','2026-10-01 13:00')]:
    try:
        range_plan(last,s,e,5)
        raise AssertionError('bad dates accepted')
    except ValueError:
        pass
frame=pd.DataFrame({'예측시각':pd.to_datetime(['2026-10-01 13:00']),'구분':['북'],'예측값':[2.3]})
out=result_table(frame,'예측값','예상 대기인원 (명)','화장실')
assert list(out)==['날짜','시간','화장실','예상 대기인원 (명)']
assert suggest(['측정상태','현재대기인원_추정'],['현재대기인원'])==1
print('PASS: calendar bounds, interval alignment, beginner output columns, suggestions')
