"""Fresh YOLO and ByteTrack instances for every run, including empty frames."""
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
from .config import ROOT, resolve
from .core import Observation


def setup_local_cache(cache_dir=None):
    os.environ['YOLO_OFFLINE'] = 'true'
    folder = Path(cache_dir or os.environ.get('CCTV_CACHE_DIR', str(ROOT / '.cache'))) / 'ultralytics'
    folder.mkdir(parents=True, exist_ok=True)
    if cache_dir is not None:
        os.environ['YOLO_CONFIG_DIR'] = str(folder)
    else:
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
        setup_local_cache(config.get('cache_dir'))
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
        self.runtime_info = None

    def warmup(self, width, height):
        """Prepare the inference backend without advancing ByteTrack or counting."""
        import numpy as np
        import torch
        before = self.tracker.frame_id
        self.model.predict(np.zeros((height, width, 3), dtype=np.uint8), classes=[0],
                           conf=self.c['confidence'], iou=self.c['iou'], imgsz=self.c['imgsz'],
                           device=self.device, verbose=False)
        if self.device.startswith('cuda'):
            torch.cuda.synchronize(self.device)
            torch.cuda.reset_peak_memory_stats(self.device)
        if self.tracker.frame_id != before:
            raise RuntimeError('Warmup advanced the tracking state.')

    def observe(self, frame):
        result = self.model.predict(frame, classes=[0], conf=self.c["confidence"],
                                    iou=self.c["iou"], imgsz=self.c["imgsz"],
                                    device=self.device, verbose=False)[0]
        if self.runtime_info is None:
            import torch
            backend = self.model.predictor.model
            parameter = next(backend.backend.model.parameters())
            self.runtime_info = {'parameter_device': str(parameter.device),
                                 'parameter_dtype': str(parameter.dtype),
                                 'result_device': str(result.boxes.data.device),
                                 'backend_device': str(backend.device), 'fp16': backend.fp16,
                                 'cuda_allocated_bytes': torch.cuda.memory_allocated(self.device) if self.device.startswith('cuda') else 0,
                                 'scope': 'actual inference backend after first prediction, not source checkpoint object'}
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
