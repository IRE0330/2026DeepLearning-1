"""Causal, video-time distance presentation. No detector or count changes."""
import math

HOLD_SECONDS = 3.0
CONSECUTIVE_OBSERVATIONS = 2
MAX_SAMPLE_GAP = 1.1


def unknown(reason, raw=None, last_valid=None):
    from distance_demo import unavailable
    result=unavailable(reason)
    result.update(held=False,stability='측정 불가',last_valid_time_s=last_valid,
                  raw_status=(raw or {}).get('status','측정 불가'),
                  raw_wait=(raw or {}).get('wait','측정 불가'),
                  raw_reason=(raw or {}).get('reason',reason))
    return result


def at_time(result, video_time, sample_time):
    """Age is measured from the actual source observation, never the UI clock."""
    result=dict(result)
    measured=result.get('last_valid_time_s')
    if result.get('reached_m') is None:
        return result
    if measured is None or not math.isfinite(video_time) or video_time<measured-1e-9:
        return unknown('현재 영상 시각 이전의 유효 판정이 없습니다.')
    age=video_time-measured
    if age>HOLD_SECONDS+1e-9:
        return unknown('마지막 유효 관측 이후 3초 초과 · '+result.get('raw_reason',''),result,measured)
    held=bool(result.get('held')) or age>MAX_SAMPLE_GAP+1e-9
    result.update(held=held,hold_age_s=max(0.,age),
                  stability='최근 판정 유지' if held else '유효 관측',
                  last_valid_time_s=measured)
    if held:
        cause=result.get('pending_change') or result.get('raw_reason','새 관측 없음')
        result['reason']=f'최근 판정 유지 · 마지막 유효 관측 {measured:.2f}초 · 경과 {age:.2f}초 · {cause}'
    return result


def stabilize(records, raw_results):
    """Band changes need two consecutive, distinct source observations.

    The first valid observation establishes a baseline immediately. Unknown rows
    and timestamp gaps break pending changes. Pending/unknown rows never renew
    the last-valid timestamp. A first valid sample after expiry may start fresh.
    """
    accepted=None;last_valid=None;previous_t=None
    pending_band=None;pending_count=0;pending_source=None
    output=[]
    for rec,raw in zip(records,raw_results):
        t=float(rec['interval_end_s'])
        if not math.isfinite(t) or (previous_t is not None and t<=previous_t):
            raise ValueError('안정화 기록은 유한한 영상 시각의 오름차순이어야 합니다.')
        gap=previous_t is not None and t-previous_t>MAX_SAMPLE_GAP
        expired=last_valid is not None and t-last_valid>HOLD_SECONDS+1e-9
        if expired:
            accepted=None
        if gap or expired:
            pending_band=None;pending_count=0;pending_source=None
        source=rec.get('detail',{}).get('state',{}).get('source_time_s')
        valid=(raw.get('reached_m') is not None and isinstance(source,(int,float))
               and math.isfinite(source) and 0<=t-source<=MAX_SAMPLE_GAP)
        pending_message=None
        if valid:
            band=raw['reached_m']
            if accepted is None or band==accepted['reached_m']:
                accepted=dict(raw);last_valid=float(source)
                pending_band=None;pending_count=0;pending_source=None
            else:
                if band!=pending_band:
                    pending_band=band;pending_count=1
                elif pending_source is not None and source>pending_source+1e-9:
                    pending_count+=1
                pending_source=float(source)
                if pending_count>=CONSECUTIVE_OBSERVATIONS:
                    accepted=dict(raw);last_valid=float(source)
                    pending_band=None;pending_count=0;pending_source=None
                else:
                    pending_message='단계 변경 연속 관측 확인 중 · 원시 판정 '+raw['status']
        else:
            pending_band=None;pending_count=0;pending_source=None
        if accepted is not None:
            result={**accepted,'last_valid_time_s':last_valid,
                    'held':not valid or pending_message is not None,
                    'raw_status':raw['status'],'raw_wait':raw['wait'],
                    'raw_reason':raw['reason'],'pending_change':pending_message}
            output.append(at_time(result,t,t))
        else:
            reason=('마지막 유효 관측 이후 3초 초과 · ' if expired else '')+raw['reason']
            output.append(unknown(reason,raw,last_valid))
        previous_t=t
    return output


def result_at(records, results, video_time):
    """Stateless as-of lookup: seeks, resets, pauses and new runs cannot leak state."""
    found=None
    for rec,result in zip(records,results):
        t=float(rec['interval_end_s'])
        if t>video_time+1e-9:
            break
        found=(result,t)
    return at_time(found[0],video_time,found[1]) if found else unknown('이 시점의 거리 분석 기록이 없습니다.')


def timeline_events(records, results):
    """Include between-record hold/expiry edges in step charts as well as playback."""
    if not records:return []
    end=float(records[-1]['interval_end_s'])
    times={float(rec['interval_end_s']) for rec in records}
    for result in results:
        source=result.get('last_valid_time_s')
        if source is None:continue
        for delay in (MAX_SAMPLE_GAP,HOLD_SECONDS):
            t=source+delay+1e-6
            if t>end:continue
            before=result_at(records,results,source+delay)
            after=result_at(records,results,t)
            if before.get('held')!=after.get('held') or before.get('reached_m')!=after.get('reached_m'):
                times.add(t)
    return [(t,result_at(records,results,t)) for t in sorted(times)]
