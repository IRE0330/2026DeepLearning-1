"""CCTV-only presentation policy. Platform prediction logic is independent."""
import math
from distance_policy import rank_value
from signage_time import total_time as original_total, script as original_script


def label(value, cfg):
    status=value.get('distance',{}).get('status','측정 불가')
    colors={'여유':'#008b6a','보통':'#c28a00','혼잡':'#d7413e',
            '매우 혼잡':'#8e1b40','화면 범위 초과':'#8e1b40'}
    return status,colors.get(status,'#8393a5')


def recommendation(current, vals, cfg):
    ranks={room:rank_value(value.get('distance',{})) for room,value in vals.items()}
    if any(not math.isfinite(rank) for rank in ranks.values()):return None
    alternatives=[room for room in vals if room!=current and ranks[room]<ranks[current]]
    return min(alternatives,key=lambda r:(ranks[r],cfg['walk'][current][r])) if alternatives else None


def total_time(distance, walk_seconds):
    distance=distance or {}
    if distance.get('reached_m') is None:return '대기정보 확인 중'
    if not distance.get('overflow'):return original_total(distance,walk_seconds)
    if (isinstance(walk_seconds,bool) or not isinstance(walk_seconds,(int,float))
            or not math.isfinite(walk_seconds) or walk_seconds<0):return '측정 불가'
    seconds=900+walk_seconds
    minutes,remainder=divmod(seconds,60)
    return f'{int(minutes)}분'+(f' {remainder:g}초' if remainder else '')+' 이상'


def script():
    normal=original_script().replace('function signageTotal(', 'function originalSignageTotal(')
    return normal+'''
function signageTotal(d,walkSeconds){
 if(d?.reached_m==null)return '대기정보 확인 중';
 if(!d.overflow)return originalSignageTotal(d,walkSeconds);
 if(typeof walkSeconds!=='number'||!Number.isFinite(walkSeconds)||walkSeconds<0)return '측정 불가';
 const seconds=900+walkSeconds,minutes=Math.floor(seconds/60),rest=seconds%60;
 return minutes+'분'+(rest?' '+rest+'초':'')+' 이상';
}
'''
