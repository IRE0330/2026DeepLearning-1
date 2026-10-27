"""Reproduce the benchmark; holdout answers are only opened after model selection."""
from pathlib import Path
import json
import argparse
import pandas as pd
from forecast import forecast
from core import score

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--train',default=str(root.parent/'parking_split/01_train.csv'))
parser.add_argument('--answer',default=str(root.parent/'parking_split/02_actual_do_not_train.csv'))
args=parser.parse_args()
train=pd.read_csv(args.train)
names=['Extra Trees','Hist Gradient Boosting','주간 반복 예측','요일·시간 패턴','Fourier 계절 회귀']
def progress(p,name):print(f'{p:.0%} {name}',flush=True)
f,table,test,report,bundle=forecast(train,'일시','시간당_입차기록수',None,60,168*60,names,
    nonnegative=True,optimize=True,search_budget=8,progress=progress)
# The external seven-day answer never participates in feature/model/parameter selection.
a=pd.read_csv(args.answer);a['예측시각']=pd.to_datetime(a['일시'])
m=f.merge(a,on='예측시각',validate='one_to_one')
e=abs(m['예측값']-m['시간당_입차기록수'])
metrics=score(m['시간당_입차기록수'],m['예측값'],'regression')
metrics['WAPE']=float(e.sum()/m['시간당_입차기록수'].sum()*100)
metrics['실제합계']=int(m['시간당_입차기록수'].sum());metrics['예측합계']=float(m['예측값'].sum())
(root/'benchmark').mkdir(exist_ok=True)
m.rename(columns={'시간당_입차기록수':'실제값'}).to_csv(root/'benchmark/parking_comparison.csv',index=False,encoding='utf-8-sig')
table.to_csv(root/'benchmark/model_comparison.csv',index=False,encoding='utf-8-sig')
(root/'benchmark/result.json').write_text(json.dumps({'version':report['프로그램버전'],'selected':report['선택모델'],'external_7day_metrics':metrics,'report':report},ensure_ascii=False,indent=2,default=str))
print('RESULT',report['선택모델'],metrics,flush=True)
