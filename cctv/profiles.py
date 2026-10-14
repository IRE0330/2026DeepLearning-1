"""Small metadata-only overlays; never change user geometry or behavior rules."""
from .config import clone, load

PROFILE_KEYS = {"capture_start_time", "capture_time_kind", "initial_inside", "available_stalls",
                "average_stall_use_s", "measurement_status_tags", "record_interval_s"}


def load_profile(name):
    data = load(f"configs/profiles/{name}.json") if name in ("operating", "demo") else load(name)
    if data.get("schema_version") != 1 or not isinstance(data.get("name"), str):
        raise ValueError("프로필 버전/이름이 올바르지 않습니다.")
    for section in [data.get("defaults", {}), *data.get("environments", {}).values()]:
        if not isinstance(section, dict) or set(section) - PROFILE_KEYS:
            raise ValueError("프로필은 촬영시각·초기값·칸 수·평균시간·기록 간격·상태 표시만 변경할 수 있습니다.")
        tags = section.get("measurement_status_tags", [])
        if not isinstance(tags, list) or any(not isinstance(t, str) or not t for t in tags):
            raise ValueError("프로필 상태 표시는 문자열 목록이어야 합니다.")
    return data


def apply_profile(config, profile):
    c = clone(config)
    tags = list(c.get("measurement_status_tags", []))
    for section in (profile.get("defaults", {}), profile.get("environments", {}).get(c["restroom_id"], {})):
        c.update({k: clone(v) for k, v in section.items() if k != "measurement_status_tags"})
        tags.extend(section.get("measurement_status_tags", []))
    c["measurement_status_tags"] = list(dict.fromkeys(tags))
    c["profile_name"] = profile["name"]
    return c
