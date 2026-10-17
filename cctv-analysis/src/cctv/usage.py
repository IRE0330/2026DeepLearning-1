"""Explicit capture-time metadata and assumption-based usage summaries."""
import csv
from datetime import datetime, timedelta
import hashlib
import math
from .config import resolve

WAITING_POLICY = "candidate_confirmed_observed_plus_confirmed_grace_v2"
USAGE_FIELDS = ["촬영시작시각", "촬영종료시각", "화장실ID", "화장실_영상ID",
                "구간_입장인원", "구간_퇴장인원", "내부잔류인원_추정", "현재대기인원_추정",
                "측정상태", "추정내부대기인원", "전체대기인원_추정", "현재이용가능칸수_추정",
                "외부대기인원_추정"]


def parse_capture_time(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("capture_start_time은 null 또는 시간대가 있는 ISO 시각이어야 합니다.")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("촬영 기준시각 형식 오류. 예: YYYY-MM-DDTHH:MM:SS+09:00") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("촬영 기준시각에는 +09:00 같은 시간대가 필요합니다.")
    return result


def validate_metadata(c):
    capture = parse_capture_time(c.get("capture_start_time"))
    kind = c.get("capture_time_kind")
    if kind not in (None, "real", "virtual") or (capture is not None and kind is None):
        raise ValueError("촬영 기준시각이 있으면 capture_time_kind=real 또는 virtual을 지정하세요.")
    stalls = c.get("available_stalls")
    if stalls is not None and (type(stalls) is not int or stalls < 0):
        raise ValueError("available_stalls는 null 또는 0 이상의 운영 가능 칸 수입니다.")
    mean = c.get("average_stall_use_s")
    if mean is not None and (type(mean) not in (int, float) or not math.isfinite(mean) or mean <= 0):
        raise ValueError("average_stall_use_s는 null 또는 양의 유한한 초입니다.")
    video_id = c.get("video_id")
    if video_id is not None and (not isinstance(video_id, str) or not video_id.strip()):
        raise ValueError("video_id는 null 또는 비어 있지 않은 문자열입니다.")
    digest = c.get("video_sha256")
    if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or
                               any(ch not in "0123456789abcdef" for ch in digest)):
        raise ValueError("video_sha256은 null 또는 소문자 SHA-256 값이어야 합니다.")
    if digest is not None and video_id is None:
        raise ValueError("원본 영상 해시를 등록하면 video_id도 필요합니다.")


def video_digest(c):
    with resolve(c["video"]).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def bind_video(c, requested_id=None):
    digest = video_digest(c)
    changed = c.get("video_sha256") is not None and c["video_sha256"] != digest
    if changed and requested_id is not None and requested_id == c.get("video_id"):
        raise ValueError("영상이 교체됐습니다. 이전과 다른 video_id를 지정하세요.")
    if requested_id is not None:
        c["video_id"] = requested_id
    elif changed or not c.get("video_id"):
        c["video_id"] = c["restroom_id"] + "_" + digest[:16]
    c["video_sha256"] = digest
    validate_metadata(c)
    return c


def queue_estimates(c, inside, external):
    stalls, mean = c.get("available_stalls"), c.get("average_stall_use_s")
    known = inside is not None and inside >= 0 and stalls is not None
    internal = max(inside - stalls, 0) if known else None
    free = max(stalls - inside, 0) if known else None
    q = internal + external if internal is not None and external is not None else None
    seconds = (q + 1) * mean / stalls if q is not None and mean is not None and stalls else None
    return {"internal_waiting_estimate": internal, "current_waiting_estimate": q,
            "total_queue_estimate": q, "available_stalls_estimate": free,
            "expected_wait_s": seconds}


def interval_capture_times(c, actual_start, actual_last):
    if (not math.isfinite(actual_start) or not math.isfinite(actual_last) or
            actual_start < 0 or actual_last < actual_start):
        raise ValueError("분석 구간의 시각 역전/잘못된 영상 오프셋입니다.")
    base = parse_capture_time(c.get("capture_start_time"))
    if base is None:
        return None, None
    try:
        start, last = base + timedelta(seconds=actual_start), base + timedelta(seconds=actual_last)
    except OverflowError as exc:
        raise ValueError("촬영 기준시각과 영상 오프셋의 합이 날짜 범위를 벗어납니다.") from exc
    if last < start:
        raise ValueError("촬영 종료시각이 시작시각보다 앞섭니다.")
    return start.isoformat(), last.isoformat()


def usage_row(c, final, actual_start, actual_last, mode="analysis", run_status="completed"):
    validate_metadata(c)
    start, last = interval_capture_times(c, actual_start, actual_last)
    is_analysis = mode == "analysis"
    inside = final.get("inside_estimate") if is_analysis else None
    external = final.get("waiting_total") if is_analysis else None
    estimates = queue_estimates(c, inside, external)
    statuses = final.get("measurement_status", "measuring").split(";")
    statuses.append("accuracy_not_validated")
    statuses.extend(c.get("measurement_status_tags", []))
    if not is_analysis:
        statuses.append("baseline_no_counts")
    if c.get("initial_inside") is None:
        statuses.append("initial_inside_unset")
    if inside is not None and inside < 0:
        statuses.append("negative_inside")
    if start is None:
        statuses.append("capture_time_unset")
    elif c.get("capture_time_kind") == "virtual":
        statuses.append("virtual_scenario_time")
    if not c.get("video_id"):
        statuses.append("video_id_unset")
    if c.get("available_stalls") is None:
        statuses.append("available_stalls_unset")
    elif c["available_stalls"] == 0:
        statuses.append("no_operating_stalls_wait_time_unavailable")
    if c.get("average_stall_use_s") is None:
        statuses.append("average_use_time_unset")
    if run_status != "completed":
        statuses.append("run_" + run_status)
    if estimates["expected_wait_s"] is not None:
        statuses.append("wait_time_user_assumption")
    values = [start, last, c["restroom_id"], c.get("video_id"),
              final.get("entries") if is_analysis else None,
              final.get("exits") if is_analysis else None, inside, estimates["current_waiting_estimate"],
              ";".join(dict.fromkeys(statuses)), estimates["internal_waiting_estimate"],
              estimates["total_queue_estimate"], estimates["available_stalls_estimate"], external]
    return dict(zip(USAGE_FIELDS, values))


def write_usage(path, row):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, USAGE_FIELDS)
        writer.writeheader()
        writer.writerow(row)
