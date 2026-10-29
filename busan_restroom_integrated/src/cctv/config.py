import copy
import json
import math
import os
import uuid
from pathlib import Path
from .geometry import validate_points, validate_polygon, line_distance, segments_intersect

DATA = Path(__file__).resolve().parent / 'data'
_source_root = Path(__file__).resolve().parents[3]
LEGACY_ROOT = _source_root if (_source_root / 'cctv-analysis/src/cctv').is_dir() and (_source_root / 'configs').is_dir() else None
ROOT = LEGACY_ROOT or Path.home() / '.busan-cctv'


def resolve(path):
    p = Path(path)
    return p if p.is_absolute() else (LEGACY_ROOT or Path.cwd()) / p


def template(restroom_id, video):
    return {
        "schema_version": 1, "restroom_id": restroom_id, "video": video,
        "video_id": restroom_id + "_" + uuid.uuid4().hex,
        "video_sha256": None, "capture_start_time": None, "capture_time_kind": None,
        "available_stalls": 27 if restroom_id == "north" else None,
        "average_stall_use_s": 105.0,
        "record_interval_s": record_interval_s({}),
        "configured": False, "reference_size": None,
        "camera_note": "구도 변경 시 다시 설정하세요.",
        "boundary": [], "entry_direction": [],
        "outside_zone": [], "inside_zone": [], "waiting_zone": [],
        "transit_zone": [], "excluded_zones": [],
        "model": "${CCTV_MODEL_PATH}", "device": "auto", "imgsz": 640,
        "confidence": 0.1, "iou": 0.7,
        "tracker": {"tracker_type": "bytetrack", "track_high_thresh": 0.25,
                    "track_low_thresh": 0.1, "new_track_thresh": 0.25,
                    "track_buffer": 30, "match_thresh": 0.8, "fuse_score": True},
        "rules": {"side_confirm_s": 0.2, "boundary_margin": 0.005,
                  "max_observation_gap_s": 0.25, "waiting_confirm_s": 3.5,
                  "occlusion_grace_s": 1.5, "zone_exit_s": 0.8,
                  "motion_window_s": 1.0, "motion_min_span_s": 0.3,
                  "slow_speed_body_heights_s": 0.35,
                  "duplicate_radius_body_heights": 0.7,
                  "forget_track_s": 60.0},
        "initial_inside": None, "output_dir": "outputs"}


def load(path):
    p = resolve(path)
    if not p.is_file() and not Path(path).is_absolute() and (DATA / path).is_file():
        p = DATA / path
    with p.open(encoding="utf-8-sig") as f:
        result = json.load(f)
    if all(k in result for k in ('model', 'video', 'output_dir')):
        base = LEGACY_ROOT if LEGACY_ROOT is not None and p.parent == LEGACY_ROOT / 'configs' else p.parent
        base = (base / result.get('path_base', '.')).resolve()
        for key in ('model', 'video', 'output_dir'):
            if key == 'model' and result[key] == '${CCTV_MODEL_PATH}':
                supplied = os.environ.get('CCTV_MODEL_PATH', '').strip()
                # Keep the marker until CLI/API overrides are applied. Never
                # resolve an unset weight path into site-packages.
                result[key] = str(Path(supplied).expanduser().resolve()) if supplied else result[key]
                continue
            value = Path(result[key]).expanduser()
            result[key] = str(value if value.is_absolute() else base / value)
    elif isinstance(result.get('videos'), list):
        base = LEGACY_ROOT if LEGACY_ROOT is not None and p.parent == LEGACY_ROOT / 'configs' else p.parent
        for entry in result['videos']:
            if not isinstance(entry, dict):
                continue
            for key in ('video', 'config'):
                if isinstance(entry.get(key), str):
                    value = Path(entry[key]).expanduser()
                    entry[key] = str(value if value.is_absolute() else base / value)
    return result


def preset_path(restroom_id):
    if restroom_id not in ('north', 'south', 'east'):
        raise ValueError('restroom_id must be north, south or east.')
    return DATA / 'configs' / f'{restroom_id}.json'


def save(config, path):
    p = resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(c, require_zones=True, video_size=None):
    from .usage import validate_metadata
    from .output_config import output_settings
    validate_metadata(c)
    output_settings(c)
    record_interval_s(c)
    if c.get("schema_version") != 1:
        raise ValueError("지원하지 않는 설정 버전입니다.")
    if not isinstance(c.get("restroom_id"), str) or not c["restroom_id"].strip():
        raise ValueError("restroom_id가 필요합니다.")
    initial = c.get("initial_inside")
    if initial is not None and (type(initial) is not int or initial < 0):
        raise ValueError("initial_inside는 null 또는 0 이상의 정수여야 합니다.")
    for name in ("model", "video", "output_dir", "device"):
        if not isinstance(c.get(name), str) or not c[name]:
            raise ValueError(f"{name} 경로/값이 필요합니다.")
    if type(c.get("imgsz")) is not int or c["imgsz"] < 32 or c["imgsz"] % 32:
        raise ValueError("imgsz는 32 이상의 32 배수 정수여야 합니다.")
    for key in ("confidence", "iou"):
        if type(c.get(key)) not in (int, float) or not 0 < c[key] <= 1:
            raise ValueError(f"{key}는 0 초과 1 이하이어야 합니다.")
    tr = c.get("tracker", {})
    if tr.get("tracker_type") != "bytetrack":
        raise ValueError("추적기는 bytetrack이어야 합니다.")
    for key in ("track_high_thresh", "track_low_thresh", "new_track_thresh", "match_thresh"):
        if type(tr.get(key)) not in (int, float) or not 0 < tr[key] <= 1:
            raise ValueError(f"tracker.{key}는 0 초과 1 이하이어야 합니다.")
    if tr["track_low_thresh"] >= tr["track_high_thresh"] or c["confidence"] > tr["track_low_thresh"]:
        raise ValueError("confidence <= track_low_thresh < track_high_thresh가 필요합니다.")
    if tr["new_track_thresh"] < tr["track_high_thresh"]:
        raise ValueError("new_track_thresh는 track_high_thresh 이상이어야 합니다.")
    if type(tr.get("track_buffer")) is not int or tr["track_buffer"] <= 0 or type(tr.get("fuse_score")) is not bool:
        raise ValueError("track_buffer는 양의 정수, fuse_score는 bool이어야 합니다.")
    defaults = template("x", "x")["rules"]
    for key in defaults:
        value = c.get("rules", {}).get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"rules.{key}는 양의 유한한 수여야 합니다.")
    r = c["rules"]
    if r["motion_min_span_s"] > r["motion_window_s"] or r["forget_track_s"] <= r["occlusion_grace_s"]:
        raise ValueError("이동 구간/기록 보관 시간이 올바르지 않습니다.")
    if not require_zones:
        return
    if c.get("configured") is not True:
        raise ValueError("구역이 미설정입니다. configure에서 사용자 확인 후 저장하세요.")
    size = c.get("reference_size")
    if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
        raise ValueError("reference_size에 기준 영상 [폭, 높이]가 필요합니다.")
    if video_size and abs(size[0] / size[1] - video_size[0] / video_size[1]) > 0.001:
        raise ValueError("영상 종횡비가 달라졌습니다. 구역을 다시 설정하세요.")
    validate_points(c["boundary"], 2)
    if math.dist(*c["boundary"]) < 0.01:
        raise ValueError("출입 경계 선분이 너무 짧습니다.")
    validate_points(c["entry_direction"], 2)
    d1, d2 = [line_distance(p, c["boundary"]) for p in c["entry_direction"]]
    if d1 * d2 >= 0:
        raise ValueError("입장 화살표는 경계의 외부에서 내부로 가로질러야 합니다.")
    if not segments_intersect(*c["entry_direction"], *c["boundary"]):
        raise ValueError("입장 화살표는 유한한 출입 경계 선분을 가로질러야 합니다.")
    for name in ("outside_zone", "inside_zone", "waiting_zone"):
        validate_polygon(c[name])
    if c.get("transit_zone"):
        validate_polygon(c["transit_zone"])
    for poly in c.get("excluded_zones", []):
        validate_polygon(poly)
    # Confirmation polygons must remain on their designated side of the buffer.
    for name, direction in (("outside_zone", d1), ("inside_zone", d2)):
        if any(line_distance(p, c["boundary"]) * (1 if direction > 0 else -1) < r["boundary_margin"] for p in c[name]):
            raise ValueError(f"{name}은 해당 방향의 경계 완충 구간 바깥에 있어야 합니다.")


def clone(c):
    return copy.deepcopy(c)


def record_interval_s(c):
    # The operating profile owns the default for legacy settings without this key.
    value = c["record_interval_s"] if "record_interval_s" in c else load(
        "configs/profiles/operating.json")["defaults"]["record_interval_s"]
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("record_interval_s는 양의 유한한 영상 시각 간격(초)이어야 합니다.")
    return value
