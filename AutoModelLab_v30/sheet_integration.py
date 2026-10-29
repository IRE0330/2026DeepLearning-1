"""Load all workbook sheets and conservatively align auxiliary time series."""
import io
import pandas as pd
from auto_setup import prepare_time

def load_all(upload):
    raw=upload.getvalue()
    if upload.name.lower().endswith(('.xlsx','.xls')):
        book=pd.read_excel(io.BytesIO(raw),sheet_name=None)
        return [(f'{upload.name} / {name}', df) for name,df in book.items() if not df.empty]
    from core import read_table
    return [(upload.name,read_table(raw,upload.name,0))]

def align_sheets(tables,base_index,interval_minutes=1):
    """Aggregate auxiliary numeric fields into base timestamps; never multiply base rows."""
    base_name,base=tables[base_index]
    base,tc,_=prepare_time(base)
    base=base.copy()
    base['__join_time']=pd.to_datetime(base[tc]).dt.floor(f'{interval_minutes}min')
    reports=[]
    for i,(name,frame) in enumerate(tables):
        if i==base_index:continue
        try:
            aux,at,_=prepare_time(frame)
            aux=aux.copy()
            aux['__join_time']=pd.to_datetime(aux[at]).dt.floor(f'{interval_minutes}min')
            nums=[c for c in aux.select_dtypes(include='number').columns if c!=at and not any(k in str(c).lower() for k in ('id','코드','번호','year','month','day','hour','minute'))]
            if not nums:raise ValueError('집계할 숫자 항목 없음')
            # Sum counts within a bucket; only one record per time bucket after aggregation.
            grouped=aux.groupby('__join_time',as_index=False)[nums].sum(min_count=1)
            renamed={c:f'{name} | {c}' for c in nums}
            grouped=grouped.rename(columns=renamed)
            base=base.merge(grouped,on='__join_time',how='left',validate='many_to_one',sort=False)
            matched=int(base[list(renamed.values())].notna().any(axis=1).sum())
            reports.append({'시트':name,'상태':'시간 기준 연결','연결된 기준 행':matched,'전체 기준 행':len(base)})
        except (ValueError,TypeError,KeyError) as e:
            reports.append({'시트':name,'상태':'연결 제외 (독립 시트로 사용 가능)','이유':str(e)})
    return base.drop(columns=['__join_time']),reports


def stack_and_align(tables, target_indices, auxiliary_indices, interval_minutes=1):
    """Stack explicitly selected target sheets, then align only selected auxiliaries."""
    if not target_indices:
        raise ValueError('학습할 대상 시트를 하나 이상 선택해 주세요.')
    parts=[]
    reports=[]
    schema=set(tables[target_indices[0]][1].columns)
    for i in target_indices:
        name,frame=tables[i]
        if set(frame.columns)!=schema:
            raise ValueError('세로로 합칠 대상 시트는 열 이름이 같아야 합니다: '+name)
        part=frame.copy()
        # Keep the real entity identifier when present; otherwise use sheet name.
        if '화장실ID' not in part:
            part['시트별 대상ID']=name
        parts.append(part)
        reports.append({'시트':name,'상태':'대상 기록 세로 합침','전체 기준 행':len(part)})
    combined=pd.concat(parts,ignore_index=True)
    auxiliaries=[tables[i] for i in auxiliary_indices if i not in target_indices]
    result,joined=align_sheets([('통합 대상',combined)]+auxiliaries,0,interval_minutes)
    return result,reports+joined
