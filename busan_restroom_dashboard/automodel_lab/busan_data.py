"""Prepare the supplied Busan demonstration files at minute resolution."""
import io
import numpy as np
import pandas as pd
from .core import read_table


def prepare_busan(files):
    if len(files) != 2:
        raise ValueError('화장실 엑셀과 승하차 예매 엑셀 총 2개 파일을 올려 주세요.')
    restroom = booking = None
    for f in files:
        data=f.getvalue()
        if f.name.lower().endswith(('.xlsx','.xls')):
            x=pd.ExcelFile(io.BytesIO(data))
            if all(s in x.sheet_names for s in ['TOILET_A','TOILET_B','TOILET_C']):
                if restroom is not None: raise ValueError('화장실 엑셀 파일이 중복되었습니다.')
                restroom=pd.concat([pd.read_excel(x,sheet_name=s) for s in ['TOILET_A','TOILET_B','TOILET_C']],ignore_index=True)
            elif '승하차_예매정보' in x.sheet_names:
                if booking is not None: raise ValueError('승하차 엑셀 파일이 중복되었습니다.')
                booking=pd.read_excel(x,sheet_name='승하차_예매정보')
    if restroom is None or booking is None:
        raise ValueError('TOILET_A·B·C 시트가 있는 화장실 엑셀과 승하차_예매정보 시트가 있는 엑셀을 확인해 주세요.')
    keys=['예정일시','열차번호','운행구분']
    booking=booking.copy()
    booking['예정일시']=pd.to_datetime(booking['날짜'].astype(str)+' '+booking['예정시각'].astype(str),errors='coerce',format='mixed')
    if booking[keys].isna().any().any():raise ValueError('열차 날짜·시각·번호 또는 운행구분에 빈 값이 있습니다.')
    booking['열차번호']=booking['열차번호'].astype(str).str.strip()
    booking['운행구분']=booking['운행구분'].astype(str).str.strip()
    if booking.duplicated(keys).any():raise ValueError('날짜·시간·열차번호·운행구분이 같은 열차 기록이 중복됩니다. 원본을 확인해 주세요.')
    events=booking[keys+['예매율']].copy()
    matched=len(events);missing=0
    events['예매율']=pd.to_numeric(events['예매율'],errors='coerce')
    if '마지막대기자_거리구간' in restroom:
        tier={'대기 없음':0, '5m 미만':1, '5m 이상~10m 미만':2, '10m 이상~15m 미만':3, '15m 이상':4}
        restroom['대기거리구간_예측단계']=restroom['마지막대기자_거리구간'].astype(str).str.strip().map(tier)
        if restroom['대기거리구간_예측단계'].isna().any():raise ValueError('알 수 없는 대기 거리구간이 있습니다. 원본 항목을 확인해 주세요.')
        restroom=restroom.drop(columns=['마지막대기자_거리구간'])
    restroom['촬영종료시각']=pd.to_datetime(restroom['촬영종료시각'],errors='coerce')
    if restroom['촬영종료시각'].isna().any():raise ValueError('화장실 촬영종료시각에 빈 값이 있습니다.')
    # Dates outside the schedule period (including partially covered first-day windows) are unknown.
    start=booking['예정일시'].min().normalize()
    end=booking['예정일시'].max().normalize()+pd.Timedelta(days=1)
    t=restroom['촬영종료시각'].to_numpy(dtype='datetime64[ns]').astype('int64')
    for kind in ['도착','출발']:
        ev=events.loc[events['운행구분'].eq(kind)].sort_values('예정일시')
        ts=ev['예정일시'].to_numpy(dtype='datetime64[ns]').astype('int64')
        rates=ev['예매율'].to_numpy(dtype=float);valid=np.isfinite(rates)
        sums=np.r_[0.,np.cumsum(np.where(valid,rates,0.))];counts=np.r_[0,np.cumsum(valid)]
        hi=np.searchsorted(ts,t,side='right')
        for mins in (10,30):
            lo=np.searchsorted(ts,t-mins*60*1_000_000_000,side='right')
            complete=(t-mins*60*1_000_000_000>=start.value)&(t<end.value)
            n=hi-lo;restroom[f'직전{mins}분_{kind}열차수']=np.where(complete,n,np.nan)
            if kind=='도착':
                nvalid=counts[hi]-counts[lo];total=sums[hi]-sums[lo]
                avg=np.divide(total,nvalid,out=np.full(len(t),np.nan),where=nvalid>0)
                restroom[f'직전{mins}분_도착열차_평균예매율']=np.where(complete,avg,np.nan)
    # A time-varying video identifier and measurement note add no usable future information.
    restroom=restroom.drop(columns=['촬영시작시각','화장실_영상ID','측정상태'],errors='ignore')
    report=[{'항목':'화장실 A·B·C 기록','결과':f'{len(restroom):,}행'}, {'항목':'승하차 예매정보 열차 기록','결과':f'{matched:,}건'}]
    return restroom,report,missing
