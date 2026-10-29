"""CCTV-only presentation policy. Platform prediction logic is independent."""
import math
import re
from signage_time import total_time as original_total, script as original_script


def status_text(distance):
    """Display wording only; use the accepted observation, including while held."""
    distance=distance or {}
    queue=distance.get('display_values',{}).get('queue')
    if (distance.get('reached_m') is not None and not isinstance(queue,bool)
            and isinstance(queue,(int,float)) and math.isfinite(queue) and queue==0):
        return '대기없음'
    if distance.get('reached_m') is not None:
        if distance.get('overflow'):return '매우 혼잡'
        match=re.fullmatch(r'(\d+)분 (미만|이상)',str(distance.get('wait','')))
        if match:
            minutes=int(match[1]);below=match[2]=='미만'
            if below:return '여유' if minutes<=5 else '보통' if minutes<=10 else '혼잡' if minutes<=15 else '매우 혼잡'
            return '매우 혼잡' if minutes>=15 else '혼잡' if minutes>=10 else '보통' if minutes>=5 else '여유'
    return distance.get('status','측정 불가')


def label(value, cfg):
    status=status_text(value.get('distance'))
    colors={'대기없음':'#0284c7','여유':'#008b6a','보통':'#c28a00','혼잡':'#dc2626',
            '매우 혼잡':'#991b1b','화면 범위 초과':'#991b1b'}
    return status_text(value.get('distance')),colors.get(status,'#8393a5')


def total_score(distance,walk_seconds):
    """Compare the displayed time-bound values; never invent interval midpoints."""
    if not isinstance((distance or {}).get('wait'),str):return math.inf
    shown=total_time(distance,walk_seconds)
    match=re.fullmatch(r'(\d+)분(?: ([\d.]+)초)?(?: (?:미만|이상))?',shown)
    return int(match[1])*60+float(match[2] or 0) if match else math.inf


def recommendation(current, vals, cfg):
    walks=cfg.get('walk',{}).get(current,{})
    scores={room:total_score(value.get('distance',{}),walks.get(room)) for room,value in vals.items()}
    if any(not math.isfinite(score) for score in scores.values()):return None
    alternatives=[room for room in vals if room!=current and scores[room]<scores[current]]
    numbers={'north':1,'south':2,'east':3}
    return min(alternatives,key=lambda r:(scores[r],walks[r],numbers.get(r,99))) if alternatives else None


def total_time(distance, walk_seconds):
    distance=distance or {}
    if distance.get('reached_m') is None:return '대기정보 확인 중'
    if (isinstance(walk_seconds,bool) or not isinstance(walk_seconds,(int,float))
            or not math.isfinite(walk_seconds) or walk_seconds<0):return '측정 불가'
    if status_text(distance)=='대기없음':
        minutes,remainder=divmod(walk_seconds,60)
        return f'{int(minutes)}분'+(f' {remainder:g}초' if remainder else '')
    if not distance.get('overflow'):return original_total(distance,walk_seconds)
    seconds=900+walk_seconds
    minutes,remainder=divmod(seconds,60)
    return f'{int(minutes)}분'+(f' {remainder:g}초' if remainder else '')+' 이상'


def script():
    normal=original_script().replace('function signageTotal(', 'function originalSignageTotal(')
    return normal+'''
function signageTotal(d,walkSeconds){
 if(d?.reached_m==null)return '대기정보 확인 중';
 if(typeof walkSeconds!=='number'||!Number.isFinite(walkSeconds)||walkSeconds<0)return '측정 불가';
 if(distanceStatus(d)==='대기없음'){const minutes=Math.floor(walkSeconds/60),rest=walkSeconds%60;return minutes+'분'+(rest?' '+rest+'초':'');}
 if(!d.overflow)return originalSignageTotal(d,walkSeconds);
 const seconds=900+walkSeconds,minutes=Math.floor(seconds/60),rest=seconds%60;
 return minutes+'분'+(rest?' '+rest+'초':'')+' 이상';
}
function signageTotalScore(d,walkSeconds){
 if(typeof d?.wait!=='string')return Infinity;
 const shown=signageTotal(d,walkSeconds),match=shown.match(/^([0-9]+)분(?: ([0-9.]+)초)?(?: (?:미만|이상))?$/);
 return match?Number(match[1])*60+Number(match[2]||0):Infinity;
}
function recommendSignageTotal(current,vals,cfg){
 const rooms=Object.keys(vals),walks=cfg.walk?.[current]||{},nums={north:1,south:2,east:3};
 const scores=Object.fromEntries(rooms.map(r=>[r,signageTotalScore(vals[r]?.distance,walks[r])]));
 if(rooms.some(r=>!Number.isFinite(scores[r])))return null;
 const alternatives=rooms.filter(r=>r!==current&&scores[r]<scores[current]);
 alternatives.sort((a,b)=>scores[a]-scores[b]||walks[a]-walks[b]||nums[a]-nums[b]);
 return alternatives[0]||null;
}
'''
