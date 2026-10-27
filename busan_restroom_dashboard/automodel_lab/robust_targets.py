"""Train-only, calendar-stratified target treatment; never rewrites source data."""
import numpy as np
import pandas as pd


def treat_targets(X,y,mode='off',separate_holidays=False):
    target=np.asarray(y,dtype=float).copy()
    weight=np.ones(len(target));flag=np.zeros(len(target),dtype=bool)
    if mode not in ('off','clip','downweight'):raise ValueError('지원하지 않는 이상치 처리')
    frame=X.reset_index(drop=True).copy();frame['_target']=target
    keys=['series','weekday','hour','minute']
    # Holiday status always protects special days from weekday outlier comparisons.
    if 'is_holiday' in frame:keys.append('is_holiday')
    if mode!='off':
        for _,part in frame.groupby(keys,dropna=False):
            if len(part)<8:continue
            values=part['_target'].to_numpy();median=float(np.median(values))
            mad=float(np.median(abs(values-median)))
            q25,q75=np.quantile(values,[.25,.75])
            scale=max(1.4826*mad,float(q75-q25)/1.349,np.sqrt(abs(median)+1),1e-6)
            lo,hi=median-6*scale,median+6*scale
            indices=part.index.to_numpy();bad=(values<lo)|(values>hi)
            flag[indices[bad]]=True
            if mode=='clip':target[indices]=np.clip(values,lo,hi)
            else:weight[indices[bad]]=.1
    positions=np.flatnonzero(flag)
    examples=[{'학습행':int(i),'원래값':float(np.asarray(y)[i]),'학습용값':float(target[i]),'가중치':float(weight[i])} for i in positions[:20]]
    audit={'방식':mode,'학습행수':len(target),'의심값수':int(flag.sum()) if mode!='off' else None,'원본변경':False,
           '비교그룹':'대상×요일×시각×공휴일 (8건 미만은 처리하지 않음)','기준':'중앙값±6×강건척도, 건수용 척도 하한 적용','예시':examples}
    return target,weight,audit
