import csv
import importlib.metadata
import math
import platform
import time
import traceback
from .config import load, resolve, validate, clone, record_interval_s
from .core import Counter, SecondSampler
from .detector import Detector
from .media import probe, frames, unique_dir, write_json, verify_output
from .overlay import annotate
from .usage import WAITING_POLICY, video_digest, usage_row
from .intervals import IntervalSampler, IntervalCSVWriter

EVENT_FIELDS = ["restroom_id", "video_time_s", "frame_index", "track_id", "direction",
                "position_x", "position_y", "crossing_time_estimate_s", "reason"]
TIME_FIELDS = ["restroom_id", "sample_time_s", "source_time_s", "frame_index", "entries", "exits",
               "waiting_observed", "waiting_grace", "waiting_total", "grace_suppressed",
               "net_inflow", "inside_estimate", "measurement_status",
               "waiting_candidate_observed", "waiting_confirmed_observed",
               "internal_waiting_estimate", "total_queue_estimate", "expected_wait_s",
               "current_waiting_estimate", "available_stalls_estimate"]


def versions():
    return {"python": platform.python_version(), "os": platform.platform(),
            "packages": {name: importlib.metadata.version(name)
                         for name in ("ultralytics", "torch", "torchvision", "opencv-python", "numpy", "lap", "av")}}


def analyze(config_path, start=0, end=None, baseline=False, device=None,
            config_override=None, output_base=None, interval_sink=None):
    import cv2
    import json
    c = clone(load(config_path))
    if config_override is not None:
        c = clone(config_override)
    if device:
        c["device"] = device
    validate(c, require_zones=not baseline)
    if not baseline and (not c.get("video_id") or not c.get("video_sha256")):
        raise ValueError("원본 영상 ID 등록이 필요합니다. metadata --config ... --bind-video를 먼저 실행하세요.")
    if not math.isfinite(start) or start < 0 or (end is not None and (not math.isfinite(end) or end <= start)):
        raise ValueError("분석 구간은 0 <= start < end이어야 합니다.")
    out = unique_dir(output_base or c["output_dir"], c["restroom_id"] + ("_baseline" if baseline else ""))
    write_json(out / "config_used.json", c)
    summary = {"status": "starting", "mode": "baseline" if baseline else "analysis",
               "scope": "development_video_only", "config_source": str(resolve(config_path)),
               "restroom_id": c["restroom_id"], "requested_start_s": start, "requested_end_s": end,
               "initial_inside": c["initial_inside"], "event_evaluation_time": "confirmation_video_time_s",
               "inside_baseline_note": "initial_inside refers to actual analysis start, not original file start",
               "waiting_count_policy": WAITING_POLICY,
               "video_id": c.get("video_id"), "capture_start_time": c.get("capture_start_time"),
               "capture_time_kind": c.get("capture_time_kind"),
               "profile_name": c.get("profile_name", "operating"),
               "shared_csv_schema": "13_columns_configured_interval_snapshots_v5",
               "periodic_interval_s": record_interval_s(c),
               "wait_time_assumptions": {"available_stalls": c.get("available_stalls"),
                                         "average_stall_use_s": c.get("average_stall_use_s"),
                                         "formula": "(Q + 1) * average_stall_use_s / available_stalls",
                                         "is_user_assumption_not_validated_prediction": True},
               "versions": versions(), "processed_frames": 0}
    write_json(out / "summary.json", summary)
    print(f"결과 폴더: {out}", flush=True)
    writer, counter, last_snapshot, periodic = None, None, None, None
    interval_writer = None
    handles, failed = [], None
    begun = time.perf_counter()
    try:
        info = probe(c["video"])
        summary["input_video"] = info
        digest = video_digest(c)
        summary["source_video_sha256"] = digest
        summary["video_identity_bound"] = c.get("video_sha256") == digest
        if c.get("video_sha256") is not None and c["video_sha256"] != digest:
            raise ValueError("영상 파일이 교체됐습니다. metadata --bind-video로 새 영상 ID를 등록하세요.")
        if not info["cfr_verified"]:
            raise ValueError("가변 FPS 또는 불규칙 타임스탬프 영상입니다. CFR 변환 후 구역을 확인하세요. README의 변환 안내를 참고하세요.")
        fps, width, height = info["fps"], info["width"], info["height"]
        validate(c, require_zones=not baseline, video_size=(width, height))
        if start > info["last_frame_time_s"]:
            raise ValueError("시작 시각이 영상 범위를 벗어납니다.")
        detector = Detector(c, fps)
        summary["model"] = detector.metadata()
        summary["tracker_actual_lost_buffer_frames"] = getattr(detector.tracker, "max_frames_lost", getattr(detector.tracker, "max_time_lost", None))
        summary["tracker_lost_buffer_s"] = summary["tracker_actual_lost_buffer_frames"] / fps
        counter = None if baseline else Counter(c, width, height)
        sampler = SecondSampler(start)
        # OpenCV truncates odd dimensions; reject instead of silently changing resolution.
        if width % 2 or height % 2:
            raise ValueError("mp4v 출력은 짝수 해상도가 필요합니다. 입력 해상도를 짝수로 변환하세요.")
        writer = cv2.VideoWriter(str(out / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError("MP4 영상 쓰기를 열지 못했습니다.")
        events_file = (out / "events.csv").open("w", newline="", encoding="utf-8-sig")
        time_file = (out / "timeseries.csv").open("w", newline="", encoding="utf-8-sig")
        log_file = (out / "diagnostics.jsonl").open("w", encoding="utf-8")
        handles.extend([events_file, time_file, log_file])
        events_writer = csv.DictWriter(events_file, EVENT_FIELDS, extrasaction="ignore")
        times_writer = csv.DictWriter(time_file, TIME_FIELDS, extrasaction="ignore")
        events_writer.writeheader()
        times_writer.writeheader()
        interval_writer = IntervalCSVWriter(out, c)
        def persist_interval(row, detail):
            interval_writer.write(row, detail)
            if interval_sink is not None:
                interval_sink(row, detail)
        for index, frame in frames(c["video"]):
            t = index / fps
            if t < start - 1e-9:
                continue
            if end is not None and t >= end - 1e-9:
                break
            observations = detector.observe(frame)
            if summary["processed_frames"] == 0:
                summary["actual_start_s"] = t
                periodic = IntervalSampler(c, t, persist_interval, summary["mode"])
            if counter:
                snapshot, events, logs = counter.update(t, index, observations)
                events_writer.writerows(events)
                times_writer.writerows(sampler.push(snapshot))
            else:
                snapshot = {"source_time_s": t, "frame_index": index, "measurement_status": "baseline_zones_unconfirmed"}
                events = []
                logs = [{"kind": "baseline_tracks", "video_time_s": t,
                         "tracks": [{"track_id": o.track_id, "box": o.box,
                                     "confidence": o.confidence, "point": o.point} for o in observations]}]
            logs.insert(0, {"kind": "detector_boxes", "video_time_s": t,
                            "frame_index": index, "detections": detector.raw_detections})
            for row in logs:
                log_file.write(json.dumps({"restroom_id": c["restroom_id"], "frame_index": index, **row}, ensure_ascii=False) + "\n")
            # Baseline lifecycle is logged without making human identity claims.
            if baseline:
                current_ids = {o.track_id for o in observations}
                known = summary.setdefault("baseline_first_seen", {})
                prior = summary.pop("_previous_ids", [])
                for tid in current_ids:
                    kind = "first_observed" if str(tid) not in known else "reobserved_same_tracker_id" if tid not in prior else None
                    if kind:
                        log_file.write(json.dumps({"kind": kind, "track_id": tid, "video_time_s": t}) + "\n")
                    known.setdefault(str(tid), t)
                for tid in set(prior) - current_ids:
                    log_file.write(json.dumps({"kind": "tracker_id_not_observed", "track_id": tid, "video_time_s": t}) + "\n")
                summary["_previous_ids"] = list(current_ids)
            writer.write(annotate(frame, c, observations, counter, snapshot, mode="baseline" if baseline else "analysis"))
            summary["processed_frames"] += 1
            last_snapshot = snapshot
            periodic.push(snapshot, events)
            if summary["processed_frames"] % max(1, round(fps * 5)) == 0:
                print(f"처리 {t:.1f}s ({summary['processed_frames']} frames)", flush=True)
        if not summary["processed_frames"]:
            raise ValueError("선택 구간에 처리 가능한 프레임이 없습니다.")
        summary["status"] = "completed"
    except BaseException as exc:
        summary["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        summary["traceback"] = traceback.format_exc()
        failed = exc
    finally:
        if writer:
            writer.release()
        if periodic and last_snapshot:
            try:
                # A CFR frame covers one frame duration; end is exclusive in decoding.
                coverage = min(info["duration_s"], last_snapshot["source_time_s"] + 1 / fps,
                               end if end is not None else info["duration_s"])
                summary["analysis_coverage_end_s"] = coverage
                remainder = periodic.finish(coverage, summary["status"])
                write_json(out / "remainder.json", remainder)
                summary["remainder"] = remainder
                summary["regular_csv_rows"] = periodic.rows
            except Exception as exc:
                summary["periodic_export_error"] = str(exc)
                if failed is None:
                    summary["status"], failed = "failed_usage_export", exc
        for handle in handles:
            handle.close()
        if interval_writer is not None:
            interval_writer.close()
        summary.pop("_previous_ids", None)
        summary["elapsed_s"] = time.perf_counter() - begun
        summary["processing_fps"] = summary["processed_frames"] / summary["elapsed_s"]
        summary["final_state"] = last_snapshot
        summary["anomalies"] = counter.anomalies if counter else {}
        summary["anomaly_counting_unit"] = {"negative_inside_transitions": "nonnegative_to_negative_transitions",
                                             "observation_gap_resets": "per_track_observation_gaps",
                                             "grace_suppression_frames": "frames_with_any_suppression",
                                             "unconfirmed_crossings": "cancelled_or_unconfirmed_crossing_candidates"}
        if last_snapshot:
            write_json(out / "final_state.json", last_snapshot)
            summary["actual_last_frame_s"] = last_snapshot["source_time_s"]
        if summary["processed_frames"]:
            try:
                summary["output_video"] = verify_output(out / "annotated.mp4", width, height, fps, summary["processed_frames"])
            except Exception as exc:
                summary["output_verification_error"] = str(exc)
                if failed is None:
                    summary["status"], failed = "failed_output_verification", exc
        if last_snapshot:
            try:
                row = usage_row(c, last_snapshot, summary["actual_start_s"], summary["actual_last_frame_s"],
                                summary["mode"], summary["status"])
                if not summary.get("video_identity_bound"):
                    row["측정상태"] += ";video_identity_unbound"
                # The last frame belongs to detail, not an extra partial regular row.
                detail = {"last_frame_usage": row, "state": last_snapshot,
                          "actual_start_s": summary["actual_start_s"],
                          "actual_last_frame_s": summary["actual_last_frame_s"],
                          "available_stalls": c.get("available_stalls"),
                          "average_stall_use_s": c.get("average_stall_use_s")}
                write_json(out / "final_usage_detail.json", detail)
                summary["final_usage_detail"] = detail
            except Exception as exc:
                summary["usage_export_error"] = str(exc)
                if failed is None:
                    summary["status"], failed = "failed_usage_export", exc
        write_json(out / "summary.json", summary)
    if failed:
        raise RuntimeError(f"분석 {summary['status']}: {summary.get('error', str(failed))}. 완료 범위와 원인: {out / 'summary.json'}") from failed
    return out
