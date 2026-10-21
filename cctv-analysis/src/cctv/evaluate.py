"""One-to-one event matching and exact-time sample evaluation."""
import csv
import json
import math
from pathlib import Path
from .config import resolve
from .media import unique_dir, write_json


def number(value, label):
    try:
        n = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}에는 숫자가 필요합니다.") from exc
    if not math.isfinite(n) or n < 0:
        raise ValueError(f"{label}는 0 이상의 유한한 수여야 합니다.")
    return n


def read_csv(path, required, restroom_id):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not set(required).issubset(reader.fieldnames or []):
            raise ValueError(f"{path.name}에 필요한 헤더가 없습니다: {required}")
        rows = list(reader)
    for row in rows:
        if row.get("restroom_id") != restroom_id:
            raise ValueError(f"{path.name}의 restroom_id가 실행 환경과 다릅니다.")
        row["video_time_s"] = number(row["video_time_s"], "video_time_s")
        for key in ("waiting_count", "inside_count"):
            if key in row:
                val = number(row[key], key)
                if not val.is_integer():
                    raise ValueError(f"{key}에는 정수가 필요합니다.")
                row[key] = int(val)
        if "direction" in row and row["direction"] not in ("entry", "exit"):
            raise ValueError("direction은 entry 또는 exit이어야 합니다.")
    return rows


def match_events(truth, prediction, tolerance=1.0):
    """Sorted interval matching maximizes cardinality; never reuses an event."""
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("매칭 허용 시간은 0 이상이어야 합니다.")
    results = {}
    for direction in ("entry", "exit"):
        gt = sorted((r for r in truth if r["direction"] == direction), key=lambda r: float(r["video_time_s"]))
        pr = sorted((r for r in prediction if r["direction"] == direction), key=lambda r: float(r["video_time_s"]))
        i = j = 0
        matches = []
        while i < len(gt) and j < len(pr):
            a, b = float(gt[i]["video_time_s"]), float(pr[j]["video_time_s"])
            if b < a - tolerance - 1e-9:
                j += 1
            elif a < b - tolerance - 1e-9:
                i += 1
            else:
                matches.append({"truth_time_s": a, "prediction_confirmation_time_s": b, "delta_s": b - a})
                i, j = i + 1, j + 1
        tp = len(matches)
        precision = tp / len(pr) if pr else None
        recall = tp / len(gt) if gt else None
        # F1 = 2TP/(#prediction + #truth), even when precision/recall denominator is zero.
        f1 = 2 * tp / (len(pr) + len(gt)) if pr or gt else None
        results[direction] = {"tp": tp, "fp": len(pr) - tp, "fn": len(gt) - tp,
                              "precision": precision, "recall": recall, "f1": f1, "matches": matches}
    return results


def sample_mae(truth, predictions, truth_key, prediction_key):
    by_time = {}
    for row in predictions:
        key = round(float(row["sample_time_s"]), 6)
        if key in by_time:
            raise ValueError("예측 표본 시각이 중복됩니다.")
        by_time[key] = row
    errors, seen, missing = [], set(), 0
    for row in sorted(truth, key=lambda r: r["video_time_s"]):
        key = round(row["video_time_s"], 6)
        if key in seen:
            raise ValueError("정답 표본 시각이 중복됩니다.")
        seen.add(key)
        predicted = by_time.get(key)
        if predicted is None or predicted.get(prediction_key) in (None, ""):
            missing += 1
            continue
        delta = float(predicted[prediction_key]) - row[truth_key]
        errors.append({"video_time_s": row["video_time_s"], "signed_error": delta, "absolute_error": abs(delta)})
    return {"mae": sum(x["absolute_error"] for x in errors) / len(errors) if errors else None,
            "matched_samples": len(errors), "missing_prediction_samples": missing,
            "unannotated_prediction_samples": len(set(by_time) - seen),
            "last_matched_signed_error": errors[-1]["signed_error"] if errors else None,
            "last_matched_time_s": errors[-1]["video_time_s"] if errors else None}


def evaluate(run_dir, truth_dir, tolerance=1.0):
    run, truth_dir = resolve(run_dir), resolve(truth_dir)
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    if summary["mode"] != "analysis" or not summary.get("final_state"):
        raise ValueError("확인된 구역으로 분석한 결과가 필요합니다. baseline은 집계 평가 대상이 아닙니다.")
    meta = json.loads((truth_dir / "metadata.json").read_text(encoding="utf-8-sig"))
    if meta.get("is_example") is not False:
        raise ValueError("예시 또는 미확인 정답은 평가할 수 없습니다. 실제 정답 metadata.is_example=false가 필요합니다.")
    rid = summary["restroom_id"]
    if meta.get("restroom_id") != rid:
        raise ValueError("정답 환경 ID가 실행 결과와 다릅니다.")
    predicted_events = read_csv(run / "events.csv", ["restroom_id", "video_time_s", "direction"], rid)
    with (run / "timeseries.csv").open(encoding="utf-8-sig", newline="") as f:
        samples = list(csv.DictReader(f))
    events = read_csv(truth_dir / "events.csv", ["restroom_id", "video_time_s", "direction"], rid)
    waits = read_csv(truth_dir / "waiting.csv", ["restroom_id", "video_time_s", "waiting_count"], rid)
    inside = read_csv(truth_dir / "inside.csv", ["restroom_id", "video_time_s", "inside_count"], rid)
    report = {"scope": "development_video_only", "event_time": "prediction_confirmation_time",
              "run": str(run), "truth_dir": str(truth_dir), "undefined_metric": "null means undefined/no ground truth",
              "event_metrics": None, "waiting": None, "inside": None, "notes": []}
    actual_start, actual_end = summary["actual_start_s"], summary["actual_last_frame_s"]
    def in_run(row):
        return actual_start - 1e-6 <= row["video_time_s"] <= actual_end + 1e-6
    # Ignore labels outside this run, but make the excluded counts explicit.
    report["outside_run_truth_rows"] = {"events": sum(not in_run(r) for r in events),
                                          "waiting": sum(not in_run(r) for r in waits),
                                          "inside": sum(not in_run(r) for r in inside)}
    events, waits, inside = ([r for r in rows if in_run(r)] for rows in (events, waits, inside))
    if events and meta.get("events_complete") is True:
        start = number(meta.get("annotated_start_s"), "annotated_start_s")
        end = number(meta.get("annotated_end_s"), "annotated_end_s")
        if end < start:
            raise ValueError("정답 구간 종료가 시작보다 빠릅니다.")
        low, high = max(start, actual_start), min(end, actual_end)
        gt = [r for r in events if low <= r["video_time_s"] <= high]
        pr = [r for r in predicted_events if low <= r["video_time_s"] <= high]
        if gt:
            report["event_metrics"] = match_events(gt, pr, tolerance)
            report["event_evaluation_interval_s"] = [low, high]
    if report["event_metrics"] is None:
        report["notes"].append("출입 정답이 없거나 해당 구간 전체 라벨링 확인이 없어 성능 수치를 생성하지 않았습니다.")
    if waits:
        policy = summary.get("waiting_count_policy")
        if policy is not None and meta.get("waiting_count_policy") != policy:
            raise ValueError("대기 정답의 집계 정책이 실행 결과와 다릅니다. 후보 포함 기준으로 정답을 확인한 뒤 metadata.waiting_count_policy를 맞추세요.")
        report["waiting"] = sample_mae(waits, samples, "waiting_count", "waiting_total")
    else:
        report["notes"].append("대기 정답이 비어 있어 MAE를 계산하지 않았습니다.")
    baseline = meta.get("initial_time_s")
    same_start = type(baseline) in (int, float) and abs(baseline - actual_start) < 1e-6
    initial_truth = meta.get("initial_inside")
    if initial_truth is not None and (type(initial_truth) is not int or initial_truth < 0):
        raise ValueError("정답 초기 내부 인원은 null 또는 0 이상의 정수여야 합니다.")
    initial_matches = initial_truth is not None and initial_truth == summary["initial_inside"]
    can_derive = (same_start and initial_matches and meta.get("events_complete") is True and bool(events)
                  and meta.get("annotated_start_s") is not None and meta["annotated_start_s"] <= actual_start
                  and meta.get("annotated_end_s") is not None and meta["annotated_end_s"] >= actual_end)
    if not inside and can_derive:
        inside = [{"video_time_s": float(r["sample_time_s"]),
                   "inside_count": initial_truth + sum((1 if e["direction"] == "entry" else -1)
                                                        for e in events if e["video_time_s"] <= float(r["sample_time_s"]))}
                  for r in samples]
        report["inside_truth_source"] = "initial_plus_complete_events"
    if inside and same_start and initial_matches and summary["initial_inside"] is not None:
        report["inside"] = sample_mae(inside, samples, "inside_count", "inside_estimate")
        # Ending error is only available at the real final frame, not a preceding integer sample.
        final = summary["final_state"]
        last_gt = next((r for r in inside if abs(r["video_time_s"] - actual_end) < 1e-6), None)
        final_truth = last_gt["inside_count"] if last_gt else (initial_truth + sum(1 if e["direction"] == "entry" else -1 for e in events) if can_derive else None)
        report["inside"]["end_signed_error"] = None if final_truth is None else final["inside_estimate"] - final_truth
        report["inside"]["end_time_s"] = actual_end
        report["inside_truth_source"] = report.get("inside_truth_source", "manual_inside_samples")
    else:
        report["notes"].append("내부 정답 또는 일치하는 초기 인원·기준 시각이 없어 내부 인원 평가를 생략했습니다.")
    out = unique_dir(run / "evaluations", "evaluation")
    write_json(out / "metrics.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"평가 파일: {out / 'metrics.json'}")
    return out
