"""Sequential analysis of explicitly registered videos with isolated run state."""
import math
from .config import clone, load, resolve, validate
from .stream_output import StreamOutput
from .output_config import output_settings
from .media import unique_dir, write_json
from .pipeline import analyze
from .profiles import load_profile, apply_profile
from .usage import video_digest

REQUIRED = {"restroom_id", "video", "config", "video_id", "capture_start_time", "initial_inside"}


def run_batch(registry_path, profile="operating", limit_seconds=None, device=None, output_dir="outputs",
              prediction_mode=None, csv_split_interval_s=None):
    if limit_seconds is not None and (not math.isfinite(limit_seconds) or limit_seconds <= 0):
        raise ValueError("짧은 실행 길이는 양의 유한한 초여야 합니다.")
    registry, chosen = load(registry_path), load_profile(profile)
    if registry.get("schema_version") != 1 or not isinstance(registry.get("videos"), list):
        raise ValueError("영상 목록은 schema_version=1, videos 목록이어야 합니다.")
    out = unique_dir(output_dir, "batch_" + chosen["name"])
    write_json(out / "registry_used.json", registry)
    write_json(out / "profile_used.json", chosen)
    options_config = dict(chosen.get('defaults', {}))
    if prediction_mode is not None:
        options_config['prediction_mode'] = prediction_mode
    if csv_split_interval_s is not None:
        options_config['csv_split_interval_s'] = csv_split_interval_s
    output = StreamOutput(out, options_config)
    summary = {"status": "running", "registry_source": str(resolve(registry_path)),
               "profile": chosen["name"], "scope": "development_video_only",
               "accuracy_evaluation": "not_performed_no_manual_truth",
               "limit_seconds_per_video": limit_seconds, "results": [], "shared_csv": [],
               "output_settings": output.options,
               "arrival_timing_note": "Sequential saved-video batch, not concurrent live CCTV; video-time records are not wall-clock paced."}
    seen_ids, seen_paths, seen_hashes = set(), set(), set()

    def save_progress():
        summary["shared_csv"] = output.manifest()
        summary['stream_output'] = output.stats()
        write_json(out / "batch_summary.json", summary)

    def persist(row, detail):
        path = output.last_ref['path']
        save_progress()
        print(f"구간 기록 저장: {path} (원본 {detail['interval_end_s']:.3f}s)", flush=True)

    save_progress()
    print(f"일괄 결과 폴더: {out}", flush=True)
    for index, entry in enumerate(registry["videos"], 1):
        item_dir = out / "videos" / f"entry_{index:04d}"
        item_dir.mkdir(parents=True)
        result = {"registry_index": index, "registration": entry, "status": "running",
                  "item_dir": str(item_dir)}
        summary["results"].append(result)
        save_progress()
        try:
            if not isinstance(entry, dict) or REQUIRED - entry.keys():
                raise ValueError("영상 등록 항목의 필수 정보가 누락됐습니다: " + ", ".join(sorted(REQUIRED)))
            for key in ("restroom_id", "video", "config", "video_id"):
                if not isinstance(entry[key], str) or not entry[key].strip():
                    raise ValueError(f"등록 항목 {key}가 비어 있습니다.")
            if entry["restroom_id"] not in ("north", "south", "east"):
                raise ValueError("등록 환경은 north/south/east만 지원합니다.")
            path_key = str(resolve(entry["video"]).resolve()).casefold()
            if entry["video_id"] in seen_ids or path_key in seen_paths:
                raise ValueError("duplicate_registration: 같은 영상 ID 또는 경로가 중복 등록됐습니다.")
            seen_ids.add(entry["video_id"])
            seen_paths.add(path_key)
            if not resolve(entry["video"]).is_file():
                raise FileNotFoundError(f"등록 영상이 없습니다: {resolve(entry['video'])}")
            c = clone(load(entry["config"]))
            if c["restroom_id"] != entry["restroom_id"]:
                raise ValueError("영상 등록 화장실ID와 환경 설정 ID가 다릅니다.")
            expected_hash = entry.get("video_sha256")
            if expected_hash is None and c.get("video_id") == entry["video_id"]:
                expected_hash = c.get("video_sha256")
            c.update({key: entry[key] for key in ("video", "video_id", "capture_start_time", "initial_inside")})
            c["capture_time_kind"] = entry.get("capture_time_kind", c.get("capture_time_kind"))
            if c["capture_start_time"] is None:
                c["capture_time_kind"] = None
            for key in ("available_stalls", "average_stall_use_s"):
                if key in entry:
                    c[key] = entry[key]
            c = apply_profile(c, chosen)
            if prediction_mode is not None:
                c['prediction_mode'] = prediction_mode
            if csv_split_interval_s is not None:
                c['csv_split_interval_s'] = csv_split_interval_s
            c.update(output_settings(c))
            if output_settings(c) != output.options:
                raise ValueError('All videos in a batch must share output settings; use a common profile/CLI override.')
            validate(c)
            digest = video_digest(c)
            if expected_hash is not None and expected_hash != digest:
                raise ValueError("영상 내용이 등록 해시와 다릅니다. 교체 영상에는 새 ID/해시를 등록하세요.")
            if digest in seen_hashes:
                raise ValueError("duplicate_registration: 다른 경로에 같은 영상 내용이 중복 등록됐습니다.")
            seen_hashes.add(digest)
            c["video_sha256"] = digest
            start = entry.get("start_s", 0)
            end = entry.get("end_s")
            if type(start) not in (int, float) or not math.isfinite(start) or start < 0:
                raise ValueError("start_s는 0 이상의 유한한 초여야 합니다.")
            if end is not None and (type(end) not in (int, float) or not math.isfinite(end) or end <= start):
                raise ValueError("end_s는 start_s보다 큰 유한한 초여야 합니다.")
            if limit_seconds is not None:
                end = min(end, start + limit_seconds) if end is not None else start + limit_seconds
            result["effective_metadata"] = {k: c.get(k) for k in
                                            ("restroom_id", "video_id", "video_sha256", "initial_inside",
                                             "capture_start_time", "capture_time_kind", "available_stalls",
                                             "average_stall_use_s", "record_interval_s")}
            # Every call creates its own Detector, ByteTrack, Counter and initial baseline.
            run = analyze(entry["config"], start, end, device=device, config_override=c,
                          output_base=item_dir, interval_sink=persist, record_output=output)
            result.update(status="completed", run_dir=str(run))
        except Exception as exc:
            result.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            partials = list(item_dir.glob("*/summary.json"))
            if partials:
                result["run_dir"] = str(partials[0].parent)
            print(f"항목 {index} 실패, 다음 영상 계속: {result['error']}", flush=True)
        write_json(item_dir / "result.json", result)
        save_progress()
    summary["completed_count"] = sum(r["status"] == "completed" for r in summary["results"])
    summary["failed_count"] = sum(r["status"] == "failed" for r in summary["results"])
    summary["status"] = "completed_with_failures" if summary["failed_count"] else "completed"
    output.close()
    save_progress()
    print(f"완료 {summary['completed_count']}개 / 실패 {summary['failed_count']}개: {out / 'batch_summary.json'}", flush=True)
    return out
