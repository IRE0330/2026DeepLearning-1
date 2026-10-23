"""Read the supplied usage workbook without changing its 1-minute observations."""
from pathlib import Path
import unicodedata
import pandas as pd

ROOM_MAP={'TOILET_A':'north','TOILET_B':'east','TOILET_C':'south','north':'north','east':'east','south':'south','북쪽':'north','동쪽':'east','남쪽':'south'}
SOURCE_COLUMNS=['촬영시작시각','촬영종료시각','화장실ID','화장실_영상ID','구간_입장인원','구간_퇴장인원','내부잔류인원_추정','현재대기인원_추정','측정상태']

def normalize_history(frame):
    d=frame.copy()
    d.columns=[unicodedata.normalize('NFC',str(c)).strip() for c in d.columns]
    required={'촬영시작시각','화장실ID','현재대기인원_추정'}
    if not required<=set(d):raise ValueError('필수 열: 촬영시작시각, 화장실ID, 현재대기인원_추정')
    d['시각']=pd.to_datetime(d['촬영시작시각'],errors='coerce')
    try:
        if d['시각'].dt.tz is not None:d['시각']=d['시각'].dt.tz_convert('Asia/Seoul').dt.tz_localize(None)
    except AttributeError:raise ValueError('촬영시작시각의 날짜/시간대 형식을 통일해 주세요.')
    d['room']=d['화장실ID'].astype(str).map(lambda x:ROOM_MAP.get(unicodedata.normalize('NFC',x).strip()))
    if d['시각'].isna().any():raise ValueError('날짜로 해석할 수 없는 촬영시작시각이 있습니다.')
    if d['room'].isna().any():raise ValueError('화장실ID는 TOILET_A/B/C 또는 north/east/south여야 합니다.')
    d['대기인원']=pd.to_numeric(d['현재대기인원_추정'],errors='coerce')
    if d['대기인원'].isna().any() or (d['대기인원']<0).any():raise ValueError('대기인원에 누락·문자·음수 값이 있습니다.')
    if d.duplicated(['room','시각']).any():raise ValueError('같은 화장실과 시각에 중복 기록이 있습니다. 원본을 확인해 주세요.')
    return d.sort_values(['room','시각']).reset_index(drop=True)

def load_history(path):
    p=Path(path)
    if p.suffix.lower()=='.xlsx':
        x=pd.ExcelFile(p)
        sheets=[]
        for name in x.sheet_names:
            # The supplied workbook has a separate methodology sheet.
            head=pd.read_excel(x,sheet_name=name,nrows=0)
            if {'촬영시작시각','화장실ID','현재대기인원_추정'}<=set(head.columns):
                sheets.append(pd.read_excel(x,sheet_name=name))
        if not sheets:raise ValueError('분석할 화장실 기록 시트를 찾지 못했습니다.')
        d=pd.concat(sheets,ignore_index=True)
    else:
        try:d=pd.read_csv(p,encoding='utf-8-sig')
        except UnicodeDecodeError:d=pd.read_csv(p,encoding='cp949')
    return normalize_history(d)

def with_waits(frame,stalls,average):
    d=frame.copy()
    # Same positive-queue formula as the CCTV module; no queue means no waiting.
    divisor=d['room'].map(stalls)
    if divisor.isna().any() or (divisor<=0).any():raise ValueError('화장실별 운영 칸 수는 양수여야 합니다.')
    if average<=0:raise ValueError('평균 이용시간은 양수여야 합니다.')
    d['대기시간_초']=((d['대기인원']+1)*average/divisor).where(d['대기인원']>0,0.)
    d['대기시간_분']=d['대기시간_초']/60
    return d
