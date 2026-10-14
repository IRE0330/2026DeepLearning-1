"""Fresh YOLO and ByteTrack instances for every run, including empty frames."""
import hashlib
import os
from types import SimpleNamespace
from .config import ROOT, resolve
from .core import Observation


def setup_local_cache():
    folder = ROOT / ".cache" / "ultralytics"
    folder.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(folder))


def select_device(requested):
    import torch
    if requested == "auto":
        return "cuda:0" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    if requested == "cpu":
        return requested
    if requested == "mps" and torch.backends.mps.is_available():
        return requested
    if requested.isdigit():
        requested = "cuda:" + requested
    if requested == "cuda":
        requested = "cuda:0"
    if requested.startswith("cuda:") and torch.cuda.is_available():
        try:
            index = int(requested.split(":")[1])
            if 0 <= index < torch.cuda.device_count():
                return requested
        except ValueError:
            pass
    raise ValueError(f"요청 장치 '{requested}'를 사용할 수 없습니다. device=auto 또는 cpu로 바꾸거나 CUDA용 PyTorch 설치를 확인하세요.")


def download_default():
    """Explicit download command; inference never silently downloads weights."""
    import urllib.request
    path = resolve("models/yolo11n.pt")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"기존 가중치 사용: {path}")
        return path
    url = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"
    temporary = path.with_suffix(".pt.partial")
    urllib.request.urlretrieve(url, temporary)
    temporary.replace(path)
    print(f"다운로드 완료: {path}")
    return path


class Detector:
    def __init__(self, config, fps):
        setup_local_cache()
        from ultralytics import YOLO
        from ultralytics.trackers.byte_tracker import BYTETracker
        self.c = config
        self.device = select_device(config["device"])
        self.path = resolve(config["model"])
        if not self.path.is_file():
            raise FileNotFoundError(f"가중치가 없습니다: {self.path}. 먼저 python -m cctv download-model을 실행하세요.")
        self.model = YOLO(str(self.path))
        if self.model.names.get(0) != "person":
            raise ValueError("이 모델의 클래스 0은 person이 아닙니다. COCO person 사전학습 탐지 모델을 지정하세요.")
        # track_buffer is explicitly a number of processed source frames.
        # Current API takes only args; older API's default frame_rate=30 leaves it unscaled.
        self.tracker = BYTETracker(SimpleNamespace(**config["tracker"]))
        self.raw_detections = []

    def observe(self, frame):
        result = self.model.predict(frame, classes=[0], conf=self.c["confidence"],
                                    iou=self.c["iou"], imgsz=self.c["imgsz"],
                                    device=self.device, verbose=False)[0]
        boxes = result.boxes.cpu().numpy()
        self.raw_detections = [{"box": list(map(float, box)), "confidence": float(conf), "class_id": 0}
                               for box, conf in zip(boxes.xyxy, boxes.conf)]
        tracks = self.tracker.update(boxes, frame)
        return [Observation(int(row[4]), tuple(map(float, row[:4])), float(row[5])) for row in tracks]

    def metadata(self):
        import torch
        with self.path.open("rb") as weights:
            digest = hashlib.file_digest(weights, "sha256").hexdigest()
        return {"name": self.path.name, "weights_path": str(self.path),
                "sha256": digest,
                "device": self.device, "cuda_available": torch.cuda.is_available(),
                "device_name": torch.cuda.get_device_name(self.device) if self.device.startswith("cuda") else self.device,
                "selection_reason": "YOLO11 nano: small pretrained person detector; no additional training",
                "confidence": self.c["confidence"], "tracker": self.c["tracker"]}
