"""Fixed, illustrative distance bands. Never infer positions from head counts."""
import hashlib
import math
from pathlib import Path

DISCLAIMER = '임의 거리 기준 시연값'
BANDS = ((0, '여유', '5분 미만'), (5, '보통', '5분 이상'),
         (10, '혼잡', '10분 이상'), (15, '매우 혼잡', '15분 이상'))


def video_key(source):
    """Bind annotations to a specific local file, including replacement at same path."""
    try:
        p = Path(source).expanduser().resolve()
        if not source or not p.is_file():
            return ''
        s = p.stat()
        return hashlib.sha256(f'{p}|{s.st_size}|{s.st_mtime_ns}'.encode()).hexdigest()
    except OSError:
        return ''


def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('영상 안의 점을 지정하세요.')
    if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) or not 0 <= x <= 1 for x in value):
        raise ValueError('좌표는 영상 안에 있어야 합니다.')
    return tuple(value)


def cross(a, b):
    return a[0]*b[1] - a[1]*b[0]


def sub(a, b):
    return a[0]-b[0], a[1]-b[1]


def signed(p, line):
    a, b = line
    return cross(sub(b, a), sub(p, a)) / math.dist(a, b)


def validate_lines(setting):
    """The start-to-15m axis must cross three finite, nonintersecting lines in order."""
    try:
        if not isinstance(setting, dict):
            raise ValueError('시작점과 기준선 설정이 올바르지 않습니다.')
        origin = point(setting.get('origin'))
        lines = [[point(p) for p in setting['lines'][str(m)]] for m in (5, 10, 15)]
        if any(len(line) != 2 or math.dist(*line) < .025 for line in lines):
            raise ValueError('각 기준선의 양 끝점을 충분히 떨어뜨려 지정하세요.')
        target = tuple(sum(p[i] for p in lines[-1])/2 for i in (0, 1))
        axis = sub(target, origin)
        cuts = []
        for line in lines:
            edge = sub(line[1], line[0])
            den = cross(axis, edge)
            if abs(den) < 1e-9 or abs(signed(origin, line)) < .01:
                raise ValueError('시작점과 기준선을 떨어뜨리고, 대기줄 진행 방향을 가로질러 그리세요.')
            offset = sub(line[0], origin)
            t, u = cross(offset, edge)/den, cross(offset, axis)/den
            if not (t > 0 and 0 <= u <= 1):
                raise ValueError('시작점에서 15m 선 중앙으로 향하는 경로가 모든 기준선을 지나야 합니다.')
            cuts.append(t)
        if not (cuts[0] + .01 < cuts[1] and cuts[1] + .01 < cuts[2]):
            raise ValueError('시작점 → 5m → 10m → 15m 순서로 지정하세요.')
        for i, line in enumerate(lines):
            for other in lines[i+1:]:
                if signed(other[0], line)*signed(other[1], line) <= 0 and signed(line[0], other)*signed(line[1], other) <= 0:
                    raise ValueError('기준선끼리 교차하거나 닿지 않게 지정하세요.')
        return None
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        return str(exc) if isinstance(exc, ValueError) else '시작점과 5m·10m·15m 기준선을 모두 지정하세요.'


def unavailable(reason):
    return {'status': '측정 불가', 'wait': '측정 불가', 'reached_m': None,
            'reached': None, 'tail': None, 'reason': reason, 'label': DISCLAIMER}


def evaluate(record, setting, source_key):
    """Use confirmed feet plus independently evidenced distance-only candidates."""
    issue = validate_lines(setting or {})
    if issue:
        return unavailable(issue)
    if not source_key or setting.get('source_key') != source_key:
        return unavailable('현재 영상에 저장된 기준선이 없습니다. 영상을 연결하고 다시 지정하세요.')
    if not record:
        return unavailable('이 시점의 분석 기록이 없습니다.')
    state = record.get('detail', {}).get('state', {})
    geometry = state.get('queue_geometry')
    if not isinstance(geometry, dict) or geometry.get('version') not in (1,2):
        return unavailable('대기자 좌표가 없는 이전 기록입니다. 영상을 다시 분석하세요.')
    try:
        age = float(record['interval_end_s']) - float(state['source_time_s'])
        if not math.isfinite(age) or not 0 <= age <= 1.1:
            return unavailable('좌표 관측 시각이 오래되었거나 올바르지 않습니다.')
        if geometry['occluded_count'] or geometry['suppressed_count']:
            return unavailable('대기 후보자 또는 가려진 대기자가 있어 마지막 위치가 불확실합니다.')
        confirmed = geometry['points']
        if not isinstance(confirmed, list) or len(confirmed) != state['waiting_total']:
            return unavailable('대기자 수와 관측 좌표가 일치하지 않습니다.')
        candidates=[]
        if geometry['version']==1:
            if geometry['candidate_count']:
                return unavailable('후보자 체류 근거가 없는 이전 기록입니다. 영상을 다시 분석하세요.')
        else:
            confirmed=[p for p in confirmed if p.get('track_id') in geometry['confirmed_roi_ids']]
            raw_candidates=geometry['candidates']
            if not isinstance(raw_candidates,list):
                return unavailable('후보자 체류 근거가 불완전합니다.')
            for candidate in raw_candidates:
                if candidate.get('included'):
                    if (candidate.get('in_waiting_roi') is not True or candidate.get('dwell_s',0)+1e-9<2.
                            or candidate.get('reason') not in ('slow_roi_dwell_2s','co_moving_with_confirmed_queue_2s')):
                        return unavailable('후보자 포함 조건의 근거를 확인할 수 없습니다.')
                    candidates.append(candidate)
            if not confirmed and not candidates and any(c.get('reason')=='insufficient_continuous_dwell' for c in raw_candidates):
                return unavailable('후보자의 연속 ROI 체류 근거를 수집 중입니다. (시연 기준 2초)')
        points=confirmed+candidates
        origin = point(setting['origin'])
        lines = [setting['lines'][str(m)] for m in (5, 10, 15)]
        target = tuple(sum(p[i] for p in lines[-1])/2 for i in (0, 1))
        axis = sub(target, origin)
        reached = [False]*3
        tail, tail_id, tail_kind, farthest = None, None, None, (-1, -math.inf)
        for observation in points:
            p = point(observation['point'])
            confidence = observation['confidence']
            if not isinstance(confidence, (float, int)) or not math.isfinite(confidence) or confidence < .5:
                return unavailable('대기자 위치의 감지 신뢰도가 낮습니다.')
            # Perspective makes distant cross-sections narrower/differently angled.
            # Check the person's local (nearest) finite cross-section, not every
            # remote segment; ROI membership was already checked by the producer.
            local_line=min(lines,key=lambda line:abs(signed(p,line)))
            a,b=local_line;edge=sub(b,a)
            projection=sum(x*y for x,y in zip(sub(p,a),edge))/sum(x*x for x in edge)
            if not 0 <= projection <= 1:
                return unavailable('대기자가 가까운 기준선의 판정 폭 밖에 있습니다. 선의 양 끝점을 확인하세요.')
            flags = []
            for line in lines:
                flags.append(signed(p, line)*signed(origin, line) <= 1e-12)
            if flags != sorted(flags, reverse=True):
                return unavailable('기준선과 대기줄 방향이 맞지 않아 도달 여부가 불확실합니다.')
            reached = [a or b for a, b in zip(reached, flags)]
            progress = (sum(flags), sum(x*y for x, y in zip(sub(p, origin), axis)))
            if progress > farthest:
                tail, farthest = list(p), progress
                tail_id=observation.get('track_id')
                tail_kind='조건부 후보자' if observation in candidates else '확정 대기자'
        band = sum(reached)
        meters, status, wait = BANDS[band]
        return {'status': status, 'wait': wait, 'reached_m': meters,
                'reached': {str(m): flag for m, flag in zip((5, 10, 15), reached)},
                'tail': tail, 'tail_track_id':tail_id, 'tail_kind':tail_kind,
                'confirmed_count':len(confirmed),'included_candidate_count':len(candidates),
                'reason': f'확정 {len(confirmed)}명 + 조건부 후보 {len(candidates)}명 · 발 위치 기준 (후보 체류 2초)' if points else '거리 분석 대상 대기자 없음',
                'label': DISCLAIMER}
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return unavailable('대기자 좌표 기록이 불완전합니다.')


def settings_for(cfg, room):
    from distance_reference import settings_for as resolve_settings
    return resolve_settings(cfg, room)


def result_series(records, cfg, room):
    setting, key = settings_for(cfg, room)
    from distance_stability import stabilize
    return stabilize(records,[evaluate(rec, setting, key) for rec in records])
