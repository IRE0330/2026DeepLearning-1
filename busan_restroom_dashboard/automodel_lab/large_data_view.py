"""Bounded, opt-in history rendering. Never modifies training data."""
import numpy as np
import pandas as pd


def history_preview(df,time_col,target,group,start,end,max_rows=2000,max_groups=3):
    times=pd.to_datetime(df[time_col],errors='coerce')
    # Timestamp comparisons avoid creating millions of Python date objects.
    mask=(times>=pd.Timestamp(start)) & (times<pd.Timestamp(end)+pd.Timedelta(days=1))
    matched=int(mask.sum())
    if group:
        names=df.loc[mask,group].drop_duplicates().iloc[:max_groups]
        mask &= df[group].isin(names)
    part=df.loc[mask,[time_col,target]+([group] if group else [])].sort_values(time_col)
    if len(part)>max_rows:
        ids=np.linspace(0,len(part)-1,max_rows,dtype=int)
        part=part.iloc[ids]
    return pd.DataFrame({'예측시각':pd.to_datetime(part[time_col]).to_numpy(),
        '구분':part[group].astype(str).to_numpy() if group else '전체',
        '기록값':pd.to_numeric(part[target],errors='coerce').to_numpy()}),matched
