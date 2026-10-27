"""Signage-only addition of walking seconds to illustrative waiting bounds."""
import json
import math
import re
from distance_demo import BANDS


def _bounds():
    bounds = {}
    for meters, _, label in BANDS:
        match = re.fullmatch(r'(\d+)분 (미만|이상)', label)
        if match:
            bounds[str(meters)] = {'seconds': int(match[1]) * 60, 'relation': match[2]}
    return bounds


def total_time(distance, walk_seconds):
    """Preserve the original strict upper/lower bound; missing evidence stays unknown."""
    distance = distance or {}
    bound = _bounds().get(str(distance.get('reached_m')))
    if (bound is None or distance.get('status') == '측정 불가'
            or isinstance(walk_seconds, bool) or not isinstance(walk_seconds, (int, float))
            or not math.isfinite(walk_seconds) or walk_seconds < 0):
        return '측정 불가'
    seconds = bound['seconds'] + walk_seconds
    minutes, remainder = divmod(seconds, 60)
    value = f'{int(minutes)}분' + (f' {remainder:g}초' if remainder else '')
    return value + ' ' + bound['relation']


def script():
    # Share the current BANDS-derived bounds with the browser renderer.
    return '''
function signageTotal(distance, walkSeconds) {
 const bounds=BOUNDS, bound=bounds[String(distance?.reached_m)];
 if(!bound||distance?.status==='측정 불가'||typeof walkSeconds!=='number'||!Number.isFinite(walkSeconds)||walkSeconds<0)return '측정 불가';
 const seconds=bound.seconds+walkSeconds,minutes=Math.floor(seconds/60),remainder=seconds%60;
 return minutes+'분'+(remainder?' '+remainder+'초':'')+' '+bound.relation;
}
'''.replace('BOUNDS', json.dumps(_bounds(), ensure_ascii=False))
