"""Create BOM CSVs with no invented real ground truth. Never overwrite labels."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"events.csv": ["restroom_id", "video_time_s", "direction"],
           "waiting.csv": ["restroom_id", "video_time_s", "waiting_count"],
           "inside.csv": ["restroom_id", "video_time_s", "inside_count"]}


def create(folder, rid, example=False):
    folder.mkdir(parents=True, exist_ok=True)
    for name, fields in HEADERS.items():
        path = folder / name
        if path.exists():
            continue
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fields)
            writer.writeheader()
            if example:
                if name == "events.csv":
                    writer.writerows([dict(zip(fields, [rid, 4.0, "entry"])), dict(zip(fields, [rid, 8.0, "exit"]))])
                elif name == "waiting.csv":
                    writer.writerows([dict(zip(fields, [rid, 0, 3])), dict(zip(fields, [rid, 5, 2]))])
                else:
                    writer.writerows([dict(zip(fields, [rid, 0, 0])), dict(zip(fields, [rid, 5, 1]))])
    meta = folder / "metadata.json"
    if not meta.exists():
        meta.write_text(json.dumps({"restroom_id": rid, "is_example": example,
                                   "events_complete": False, "annotated_start_s": None,
                                   "waiting_count_policy": "candidate_confirmed_observed_plus_confirmed_grace_v2",
                                   "annotated_end_s": None, "initial_time_s": None,
                                   "initial_inside": None,
                                   "note": "실제 영상 정답을 작성한 뒤 기준 시각과 전체 출입 라벨링 구간을 입력하세요."}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for rid in ("north", "south", "east"):
        create(ROOT / "ground_truth" / rid, rid)
    create(ROOT / "ground_truth" / "example_only", "example_only", True)
    print("헤더 전용 실제 정답 양식과 별도 예시를 생성했습니다. 기존 파일은 보존했습니다.")
