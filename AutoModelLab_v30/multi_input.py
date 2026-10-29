"""Combine uploaded tables without silently inventing relationships."""
import re
import pandas as pd
from auto_setup import parse_dates


def same_schema(frames):
    return all(set(x.columns)==set(frames[0].columns) for x in frames[1:])


def suggest_keys(left,right):
    common=[c for c in left if c in right]
    keys=[]
    for c in common:
        name=str(c).lower()
        is_key=any(w in name for w in ('date','time','hour','날짜','시각','일시','일자','집계시작','촬영시작','집계종료','촬영종료')) or bool(re.search(r'(^id$|[_\s]id$|id$|code$|번호$)',name))
        if is_key and left[c].notna().all() and right[c].notna().all():keys.append(c)
    return keys


def _join_key(left,right,name):
    ldate=parse_dates(left,name);rdate=parse_dates(right,name)
    if ldate is not None and rdate is not None and ldate.notna().all() and rdate.notna().all():
        return ldate,rdate
    if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
        return pd.to_numeric(left),pd.to_numeric(right)
    return left.astype('string').str.strip(),right.astype('string').str.strip()


def combine_tables(frames,names,mode='auto',base=0,plans=None,drop_duplicates=True):
    if not frames:raise ValueError('파일을 하나 이상 올려 주세요.')
    if any(f.empty for f in frames):raise ValueError('비어 있는 파일 또는 시트가 있습니다.')
    if any(not f.columns.is_unique for f in frames):raise ValueError('중복된 항목 이름을 정리해 주세요.')
    reports=[]
    if len(frames)==1:
        result=frames[0].copy();reports.append({'처리':'단일 파일','파일':names[0],'행수':len(result)})
    else:
        if mode=='auto':mode='append' if same_schema(frames) else 'join'
        if mode=='append':
            result=pd.concat(frames,ignore_index=True,sort=False)
            reports.append({'처리':'행으로 합침','파일수':len(frames),'행수':len(result)})
        else:
            result=frames[base].copy()
            for i,other in enumerate(frames):
                if i==base:continue
                plan=(plans or {}).get(i)
                if plan is None:
                    keys=suggest_keys(result,other)
                    lk,rk=keys,keys
                else:lk,rk=plan
                if not lk or len(lk)!=len(rk):
                    raise ValueError(f'{names[i]}: 연결할 공통 항목을 확실히 찾지 못했습니다. 파일 연결 설정에서 기준 파일과 연결 항목을 지정하세요.')
                if not set(lk).issubset(result) or not set(rk).issubset(other):
                    raise ValueError('연결할 항목이 파일에 없습니다.')
                if result[lk].isna().any().any() or other[rk].isna().any().any():
                    raise ValueError(f'{names[i]}: 연결 항목에 빈 값이 있습니다. 정리 후 다시 올려 주세요.')
                left=result.copy();right=other.copy()
                temp=[]
                for k,(a,b) in enumerate(zip(lk,rk)):
                    key='__automl_join_'+str(k)
                    while key in left or key in right:key+='x'
                    left[key],right[key]=_join_key(left[a],right[b],a)
                    temp.append(key)
                if right.duplicated(temp).any():
                    raise ValueError(f'{names[i]}: 연결 항목이 중복되어 행이 여러 배로 늘어날 수 있습니다. 시간+ID처럼 구분 항목을 추가하거나 미리 집계해 주세요.')
                rename={c:f'{c} [파일{i+1}]' for c in other if c in result and c not in rk}
                # Drop duplicate key copies only when names match; differing names remain for transparency.
                right=right.drop(columns=[b for a,b in zip(lk,rk) if a==b]).rename(columns=rename)
                indicator='__automl_match'
                while indicator in left or indicator in right:indicator+='x'
                result=left.merge(right,on=temp,how='left',validate='many_to_one',indicator=indicator,sort=False)
                matched=int((result[indicator]=='both').sum())
                if matched==0:
                    raise ValueError(f'{names[i]}: 일치하는 기록이 없습니다. 날짜 범위·시각 단위·ID를 확인하세요.')
                reports.append({'처리':'항목 연결','파일':names[i],'기준항목':', '.join(map(str,lk)),
                                '연결항목':', '.join(map(str,rk)),'일치행':matched,'미일치행':len(result)-matched})
                result=result.drop(columns=temp+[indicator])
    before=len(result)
    if drop_duplicates:result=result.drop_duplicates().reset_index(drop=True)
    if before!=len(result):reports.append({'처리':'내용이 완전히 같은 중복 행 제거','제거행':before-len(result)})
    return result,reports
