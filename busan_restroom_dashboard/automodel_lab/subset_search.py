"""Budgeted, model-specific add/remove search using caller's chronological MAE."""
import numpy as np
from itertools import combinations


def search_subsets(columns, ranked, mandatory, evaluate, budget=14):
    columns=tuple(dict.fromkeys(columns));required=set(mandatory)&set(columns)
    order=list(dict.fromkeys([c for c in ranked if c in columns]+list(columns)))
    cache={};trace=[];best=None
    def check(items, action, changed):
        nonlocal best
        subset=tuple(c for c in columns if c in set(items)|required)
        if not subset or subset in cache or len(trace)>=budget:return None
        try:
            mae=float(evaluate(subset))
            if not np.isfinite(mae):raise ValueError('non-finite MAE')
            improved=best is None or mae < best[1]-1e-8
            if improved:best=(subset,mae)
            cache[subset]=mae
            trace.append({'조작':action,'변경항목':changed,'사용항목':list(subset),'MAE':mae,'갱신':improved})
            return mae
        except Exception as exc:
            cache[subset]=float('inf')
            trace.append({'조작':action,'변경항목':changed,'사용항목':list(subset),'MAE':None,'갱신':False,'오류':str(exc)})
    check(columns,'전체 기준','')
    half=order[:max(1,len(order)//2)]
    check(half,'시작 조합','관련성 상위 절반 + 필수 항목')
    # Group ablation tests redundant families together, rather than only MI-ranked singles.
    groups={
        '최근값 지연':[c for c in columns if c.startswith('lag_') and int(c.split('_')[-1])<24],
        '계절 지연':[c for c in columns if c.startswith('lag_') and int(c.split('_')[-1])>=24],
        '이동평균·변화':[c for c in columns if c.startswith('rolling_mean_') or c in ('recent_change','seasonal_lag_mean')],
        '변동성':[c for c in columns if c.startswith('rolling_std_')],
        '공휴일·연휴':[c for c in columns if any(k in c for k in ('holiday','day_off','bridge'))],
        '장기 달력':[c for c in columns if c in ('year','month','day','day_of_year','week_of_year','is_month_start','is_month_end','month_sin','month_cos')],
        '외부 참고 변수':[c for c in columns if c.startswith(('past::','known::'))]}
    for label,group in groups.items():
        if group and len(trace)<max(2,budget-6):check(set(columns)-set(group),'묶음 제거',label)
    if best is None:raise ValueError('유효한 컬럼 조합이 없습니다.')
    while len(trace)<budget:
        current=best[0];before=len(trace)
        # Weakest included and strongest omitted first; both directions compete.
        remove=[c for c in reversed(order) if c in current and c not in required]
        add=[c for c in order if c not in current]
        moves=[]
        pairs_remove=list(combinations(remove[:4],2));pairs_add=list(combinations(add[:4],2))
        swaps=[(r,a) for r in remove[:3] for a in add[:3]]
        for i in range(max(len(remove),len(add),len(swaps),len(pairs_remove),len(pairs_add))):
            if i<len(remove):moves.append(('제거',remove[i],set(current)-{remove[i]}))
            if i<len(add):moves.append(('추가',add[i],set(current)|{add[i]}))
            if i<len(swaps):
                r,a=swaps[i];moves.append(('교체',r+' → '+a,(set(current)-{r})|{a}))
            if i<len(pairs_remove):
                pair=pairs_remove[i];moves.append(('두 컬럼 제거',', '.join(pair),set(current)-set(pair)))
            if i<len(pairs_add):
                pair=pairs_add[i];moves.append(('두 컬럼 추가',', '.join(pair),set(current)|set(pair)))
        changed=False
        for action,c,subset in moves:
            prior=best[1]
            check(subset,action,c)
            if best[1]<prior-1e-8:
                changed=True;break
            if len(trace)>=budget:break
        if not changed or len(trace)==before:break
    return best[0],best[1],trace
