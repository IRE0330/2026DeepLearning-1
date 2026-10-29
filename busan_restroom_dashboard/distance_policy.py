"""Presentation policy only; no detector, masking, count or CSV changes."""
import math

OVERFLOW_LABEL = '화면 범위 초과'
OVERFLOW_WAIT = '15분 이상'
OVERFLOW_NOTE = '시연 추정 · 화면 범위 초과 시 대기 15분 이상은 MVP 가정입니다. 실제 15m 또는 검증된 대기시간 하한이 아닙니다.'


def active_meters(room):
    return (5, 10) if room in ('south', 'east') else (5, 10, 15)


def overflow_seconds(setting):
    value = setting.get('overflow_seconds', 3.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not .5 <= value <= 30:
        raise ValueError('범위 초과 확정·해제의 유효 연속 관측은 0.5~30초로 지정하세요.')
    return float(value)


def validate_boundary(boundary):
    from distance_demo import point
    try:
        a, b = [point(p) for p in boundary]
        if math.dist(a, b) < .025:
            raise ValueError('화면 경계 구간의 양 끝점을 충분히 떨어뜨리세요.')
        if not any(abs(a[axis]-edge) <= .02 and abs(b[axis]-edge) <= .02
                   for axis in (0, 1) for edge in (0, 1)):
            raise ValueError('대기 동선이 화면 밖으로 이어지는 같은 화면 가장자리의 구간을 지정하세요.')
        return None
    except (ValueError, TypeError, IndexError):
        return '대기 동선이 화면 밖으로 이어지는 같은 화면 가장자리의 구간을 지정하세요.'


def segment_distance(p, segment):
    a, b = segment
    dx, dy = b[0]-a[0], b[1]-a[1]
    u = max(0., min(1., ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.dist(p, (a[0]+u*dx, a[1]+u*dy))


def overflow_evidence(result, confirmed, setting):
    """Only visible confirmed queue feet at a HUMAN-marked continuation edge.

    Two distinct confirmed waiters beyond 10m must include the observed tail.
    Disappearance, candidates, age and count alone are never positive evidence.
    A vanished queue cannot clear a latched overflow: a visible inside tail is
    required. Missing/occluded observations are rejected before this function.
    """
    from distance_demo import point, signed
    boundary = setting.get('overflow_boundary')
    if not boundary or validate_boundary(boundary):
        return None, '화면 경계 미설정 · 범위 초과 자동 판정 불가'
    line = setting['lines']['10']
    origin = point(setting['origin'])
    beyond = [o for o in confirmed if signed(point(o['point']), line)*signed(origin, line) < -1e-9]
    tail = result.get('tail')
    if tail is None or result.get('tail_kind') != '확정 대기자':
        return None, '확정 대기열 끝의 유효 관측 없음 · 범위 초과 확정·해제 보류'
    contact = segment_distance(point(tail), boundary) <= .02
    ids = {o.get('track_id') for o in beyond if o.get('track_id') is not None}
    if contact:
        if len(ids) >= 2 and result.get('tail_track_id') in ids:
            return True, '10m 너머 복수 확정 대기자 + 지정된 화면 경계의 확정 줄 끝 접촉'
        return None, '경계 접촉만 관측됨 · 연속된 확정 대기열 근거 부족'
    if segment_distance(point(tail), boundary) > .04:
        return False, '화면 안쪽의 확정 줄 끝을 유효 관측'
    return None, '화면 경계 인접 구간 · 확정·해제 보류'


def rank_value(distance):
    # An open-ended waiting bound must never be treated as an exact 15 minutes.
    if distance.get('held') or distance.get('overflow') or distance.get('reached_m') is None:
        return float('inf')
    return distance['reached_m']


def total_wait_label(distance, walk_seconds):
    """Optional bound arithmetic; the current signage keeps walk/wait separate."""
    if distance.get('wait_lower_bound_minutes') is None:
        return None
    total = distance['wait_lower_bound_minutes'] + float(walk_seconds)/60
    return f'{total:g}분 이상'
