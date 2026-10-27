"""Timestamp inspection, full-frame previews and output decoding checks."""
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import uuid
from .config import resolve


def unique_dir(base, label):
    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in label)
    path = resolve(base) / f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def image_write(path, frame):
    import cv2
    ok, encoded = cv2.imencode(Path(path).suffix, frame)
    if not ok:
        raise RuntimeError("이미지를 저장하지 못했습니다.")
    encoded.tofile(str(path))


def probe(video, preview_dir=None, stop_event=None):
    from .lifecycle import check_stop
    import av
    path = resolve(video)
    if not path.is_file():
        raise FileNotFoundError(f"입력 영상이 없습니다: {path}")
    timestamps, selected = [], {}
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or 0)
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("영상 FPS가 유효하지 않습니다. 고정 FPS 영상으로 변환하세요.")
        width, height = stream.width, stream.height
        duration_hint = float(stream.duration * stream.time_base) if stream.duration else 0
        middle_target = duration_hint / 2
        first_pts = None
        for i, frame in enumerate(container.decode(stream)):
            check_stop(stop_event)
            if frame.pts is None or frame.time_base is None:
                raise ValueError("유효한 프레임 타임스탬프가 없습니다. 고정 FPS로 변환하세요.")
            pts = float(frame.pts * frame.time_base)
            if first_pts is None:
                first_pts = pts
            t = pts - first_pts
            timestamps.append(t)
            if preview_dir:
                if i == 0:
                    selected["start"] = (i, t, frame.to_ndarray(format="bgr24"))
                if "middle" not in selected and t >= middle_target:
                    selected["middle"] = (i, t, frame.to_ndarray(format="bgr24"))
                last_frame = frame
        if not timestamps:
            raise ValueError("읽을 수 있는 영상 프레임이 없습니다.")
        if preview_dir:
            selected["end"] = (len(timestamps) - 1, timestamps[-1], last_frame.to_ndarray(format="bgr24"))
    deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
    tolerance = max(0.0001, 1 / fps * 0.005)
    cfr = all(d > 0 and abs(d - 1 / fps) <= tolerance for d in deltas)
    duration = len(timestamps) / fps if cfr else timestamps[-1] + (statistics.median(deltas) if deltas else 1 / fps)
    info = {"path": str(path), "width": width, "height": height, "fps": fps,
            "frame_count": len(timestamps), "duration_s": duration,
            "last_frame_time_s": timestamps[-1], "first_pts_s": first_pts,
            "cfr_verified": cfr, "timestamp_scan": "all_decoded_frames",
            "timestamp_tolerance_s": tolerance,
            "min_frame_delta_s": min(deltas) if deltas else None,
            "max_frame_delta_s": max(deltas) if deltas else None,
            "median_frame_delta_s": statistics.median(deltas) if deltas else None,
            "representative_frames": {}}
    if preview_dir:
        out = Path(preview_dir)
        out.mkdir(parents=True, exist_ok=True)
        for label, (i, t, frame) in selected.items():
            name = f"{label}_{i:06d}.jpg"
            image_write(out / name, frame)
            info["representative_frames"][label] = {"frame_index": i, "video_time_s": t, "file": name}
        write_json(out / "video_info.json", info)
    return info


def frames(video):
    import av
    with av.open(str(resolve(video))) as container:
        stream = container.streams.video[0]
        for i, frame in enumerate(container.decode(stream)):
            yield i, frame.to_ndarray(format="bgr24")


def frame_at(video, time_s):
    import cv2
    cap = cv2.VideoCapture(str(resolve(video)))
    try:
        if not cap.isOpened():
            raise ValueError("영상 파일을 열지 못했습니다.")
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("영상 FPS가 유효하지 않습니다.")
        index = max(0, math.floor(time_s * fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok:
            raise ValueError("선택 시각의 프레임을 읽지 못했습니다.")
        return frame, index / fps
    finally:
        cap.release()


def verify_output(path, width, height, fps, expected_frames):
    info = probe(path)
    valid = (info["width"] == width and info["height"] == height and
             abs(info["fps"] - fps) < 0.001 and info["frame_count"] == expected_frames)
    if not valid:
        raise RuntimeError(f"출력 영상 해상도/FPS/프레임 검증 실패: {info}")
    return {"decodable": True, "all_frames_decoded": True, **info}
