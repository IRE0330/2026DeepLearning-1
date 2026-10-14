"""Video-time snapshots and immediately persisted room/date CSVs."""
import csv
import json
from datetime import datetime, timedelta, timezone
import math
import os
from pathlib import Path
from .config import record_interval_s
from .usage import USAGE_FIELDS, usage_row

KOREA = timezone(timedelta(hours=9))
EPS = 1e-9


class IntervalSampler:
    def __init__(self, config, actual_start, sink, mode="analysis"):
        self.config, self.start, self.sink, self.mode = config, actual_start, sink, mode
        self.interval_s = record_interval_s(config)
        self.previous_boundary = actual_start
        self.next_boundary = actual_start + self.interval_s
        self.last = None
        self.events = []
        self.rows = 0

    def _emit(self, run_status):
        boundary = self.next_boundary
        if self.last is None or self.last["source_time_s"] > boundary + EPS:
            raise ValueError("기록 경계 이하의 소스 프레임이 없습니다.")
        selected = [e for e in self.events if e["video_time_s"] <= boundary + EPS]
        self.events = [e for e in self.events if e["video_time_s"] > boundary + EPS]
        state = dict(self.last)
        state["entries"] = sum(e["direction"] == "entry" for e in selected)
        state["exits"] = sum(e["direction"] == "exit" for e in selected)
        row = usage_row(self.config, state, self.previous_boundary, boundary, self.mode, run_status)
        detail = {"restroom_id": self.config["restroom_id"], "video_id": self.config.get("video_id"),
                  "record_index": self.rows + 1, "record_interval_s": self.interval_s,
                  "interval_start_s": self.previous_boundary, "interval_end_s": boundary,
                  "source_time_s": self.last["source_time_s"], "state": dict(self.last),
                  "interval_entries": state["entries"], "interval_exits": state["exits"]}
        self.sink(row, detail)
        self.rows += 1
        self.previous_boundary = boundary
        self.next_boundary = self.start + (self.rows + 1) * self.interval_s

    def push(self, snapshot, events):
        t = snapshot["source_time_s"]
        if not math.isfinite(t) or t < self.start - EPS or (self.last and t <= self.last["source_time_s"]):
            raise ValueError("구간 기록의 소스 프레임 시각 역전/중복")
        if self.last is None and abs(t - self.start) > EPS:
            raise ValueError("구간 기록 시작은 실제 첫 처리 프레임과 같아야 합니다.")
        if any(e["video_time_s"] < (self.last["source_time_s"] if self.last else self.start) - EPS
               or e["video_time_s"] > t + EPS for e in events):
            raise ValueError("확정 이벤트가 해당 프레임의 관측 범위 밖에 있습니다.")
        self.events.extend(dict(e) for e in events)
        # Flush strictly past boundaries BEFORE installing the future frame.
        while self.last and self.next_boundary < t - EPS:
            self._emit("completed")
        self.last = dict(snapshot)
        if abs(self.next_boundary - t) <= EPS:
            self._emit("completed")

    def finish(self, coverage_end, run_status="completed"):
        if self.last is None:
            return None
        if not math.isfinite(coverage_end) or coverage_end < self.last["source_time_s"] - EPS:
            raise ValueError("분석 종료 시각 역전")
        while self.next_boundary <= coverage_end + EPS:
            self._emit(run_status)
        return {"interval_start_s": self.previous_boundary, "coverage_end_s": coverage_end,
                "record_interval_s": self.interval_s,
                "duration_s": max(0, coverage_end - self.previous_boundary),
                "last_frame_time_s": self.last["source_time_s"],
                "entries": sum(e["direction"] == "entry" for e in self.events),
                "exits": sum(e["direction"] == "exit" for e in self.events),
                "last_state": dict(self.last), "excluded_from_regular_csv": True}


# Existing callers keep working; the implementation uses configuration, not its old name.
TenSecondSampler = IntervalSampler


class IntervalCSVWriter:
    """Persist generated records separately from sampling and any future consumers."""
    def __init__(self, folder, config):
        folder = Path(folder)
        self.assumptions = {"available_stalls": config.get("available_stalls"),
                            "average_stall_use_s": config.get("average_stall_use_s")}
        self.usage_file = (folder / "usage_summary.csv").open("w", newline="", encoding="utf-8-sig")
        try:
            self.detail_file = (folder / "interval_details.jsonl").open("w", encoding="utf-8")
        except BaseException:
            self.usage_file.close()
            raise
        self.writer = csv.DictWriter(self.usage_file, USAGE_FIELDS)
        self.writer.writeheader()
        self.usage_file.flush()

    def write(self, row, detail):
        self.writer.writerow(row)
        self.usage_file.flush()
        self.detail_file.write(json.dumps({**detail, **self.assumptions}, ensure_ascii=False) + "\n")
        self.detail_file.flush()

    def close(self):
        self.usage_file.close()
        self.detail_file.close()


class DailyCSVWriter:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.rows = {}

    def add(self, row):
        end = row["촬영종료시각"]
        date = datetime.fromisoformat(end).astimezone(KOREA).date().isoformat() if end else "날짜미설정"
        room = row["화장실ID"]
        if room not in ("north", "south", "east"):
            raise ValueError("공유 CSV 화장실ID는 north/south/east여야 합니다.")
        path = self.folder / f"{room}_{date}.csv"
        rows = self.rows.setdefault(path, [])
        rows.append(dict(row))
        rows.sort(key=lambda r: (datetime.fromisoformat(r["촬영종료시각"]).timestamp()
                                  if r["촬영종료시각"] else float('-inf'), r["화장실_영상ID"]))
        # Persist each boundary, already sorted, without exposing a half-rewritten file.
        temp = path.with_suffix(".csv.tmp")
        with temp.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, USAGE_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        return path

    def manifest(self):
        return [{"path": str(p), "rows": len(rows)} for p, rows in sorted(self.rows.items())]
