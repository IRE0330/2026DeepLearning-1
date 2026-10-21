"""Measure the unchanged analysis pipeline; no detector/counting policy overrides."""
import argparse
from collections import Counter as Counts, defaultdict
import json
from pathlib import Path
import platform
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cctv.config import load
from cctv.profiles import apply_profile, load_profile
from cctv import pipeline
from cctv.media import write_json


def benchmark(config_path, device, start, end, output_base):
    import torch
    from cctv.detector import setup_local_cache
    setup_local_cache()
    from ultralytics.nn.autobackend import AutoBackend
    totals, calls = defaultdict(float), defaultdict(int)
    detection_times, yolo_speeds = [], []
    tensor_devices, parameter_devices, result_devices = Counts(), Counts(), Counts()
    tensor_dtypes, parameter_dtypes = Counts(), Counts()
    original_forward = AutoBackend.forward

    def measured_forward(backend, inputs, *args, **kwargs):
        # AutoBackend can copy the original YOLO model. Inspect the model that
        # executes inference, rather than the source checkpoint object.
        tensor_devices.update([str(inputs.device)])
        tensor_dtypes.update([str(inputs.dtype)])
        parameter = next(backend.backend.model.parameters())
        parameter_devices.update([str(parameter.device)])
        parameter_dtypes.update([str(parameter.dtype)])
        return original_forward(backend, inputs, *args, **kwargs)

    def timed(label, fn):
        def invoke(*args, **kwargs):
            begun = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                totals[label] += time.perf_counter() - begun
                calls[label] += 1
        return invoke

    original_detector = pipeline.Detector

    class MeasuredDetector(original_detector):
        def __init__(self, *args, **kwargs):
            begun = time.perf_counter()
            super().__init__(*args, **kwargs)
            totals['detector_init'] += time.perf_counter() - begun
            calls['detector_init'] += 1
            predict = self.model.predict

            def measured_predict(*args, **kwargs):
                results = predict(*args, **kwargs)
                yolo_speeds.extend(dict(r.speed) for r in results)
                for result in results:
                    result_devices.update([str(result.boxes.data.device)])
                return results
            self.model.predict = measured_predict

        def observe(self, frame):
            begun = time.perf_counter()
            try:
                return super().observe(frame)
            finally:
                elapsed = time.perf_counter() - begun
                detection_times.append(elapsed)
                totals['detect_and_track'] += elapsed
                calls['detect_and_track'] += 1

    original_frames = pipeline.frames

    def measured_frames(*args, **kwargs):
        iterator = iter(original_frames(*args, **kwargs))
        while True:
            begun = time.perf_counter()
            try:
                value = next(iterator)
            except StopIteration:
                break
            finally:
                totals['decode_frames'] += time.perf_counter() - begun
            calls['decode_frames'] += 1
            yield value

    import cv2
    original_writer = cv2.VideoWriter

    class MeasuredWriter:
        def __init__(self, *args, **kwargs):
            self.writer = timed('video_writer_init', original_writer)(*args, **kwargs)

        def isOpened(self):
            return self.writer.isOpened()

        def write(self, frame):
            return timed('encode_video', self.writer.write)(frame)

        def release(self):
            return timed('encode_release', self.writer.release)()

    config = apply_profile(load(config_path), load_profile('demo'))
    config.update(device=device, prediction_mode='disabled', csv_split_interval_s=3600)
    if device.startswith('cuda'):
        if not torch.cuda.is_available():
            raise RuntimeError('Requested CUDA is unavailable; CPU fallback is forbidden.')
        torch.cuda.reset_peak_memory_stats()
    begun = time.perf_counter()
    with patch.object(AutoBackend, 'forward', measured_forward), \
         patch.object(pipeline, 'Detector', MeasuredDetector), \
         patch.object(pipeline, 'frames', measured_frames), \
         patch.object(pipeline, 'probe', timed('input_full_pts_probe', pipeline.probe)), \
         patch.object(pipeline, 'video_digest', timed('source_hash', pipeline.video_digest)), \
         patch.object(pipeline, 'annotate', timed('overlay', pipeline.annotate)), \
         patch.object(pipeline, 'verify_output', timed('output_full_decode_verification', pipeline.verify_output)), \
         patch.object(pipeline.Counter, 'update', timed('counting', pipeline.Counter.update)), \
         patch.object(pipeline.IntervalCSVWriter, 'write', timed('video_csv_detail_flush', pipeline.IntervalCSVWriter.write)), \
         patch.object(pipeline.StreamOutput, 'write', timed('shared_csv_index_flush', pipeline.StreamOutput.write)), \
         patch.object(cv2, 'VideoWriter', MeasuredWriter):
        result = pipeline.analyze(config_path, start=start, end=end, device=device,
                                  config_override=config, output_base=output_base)
    wall = time.perf_counter() - begun
    summary = json.loads((result / 'summary.json').read_text(encoding='utf-8'))
    assert len(detection_times) == summary['processed_frames']
    expected = 'cuda:0' if device.startswith('cuda') else 'cpu'
    assert set(parameter_devices) == {expected}, parameter_devices
    assert set(result_devices) == {expected}, result_devices
    assert tensor_devices and set(tensor_devices) == {expected}, tensor_devices
    # Stage totals are exclusive except detector internals reported separately.
    exclusive = ['input_full_pts_probe', 'source_hash', 'detector_init', 'decode_frames',
                 'video_writer_init', 'detect_and_track', 'counting', 'overlay',
                 'encode_video', 'encode_release', 'video_csv_detail_flush',
                 'shared_csv_index_flush', 'output_full_decode_verification']
    profile = {
        'requested_device': device, 'actual_tensor_input_devices': dict(tensor_devices),
        'actual_parameter_devices_after_prediction': dict(parameter_devices),
        'actual_result_devices': dict(result_devices),
        'actual_tensor_dtypes': dict(tensor_dtypes), 'actual_parameter_dtypes': dict(parameter_dtypes),
        'python': platform.python_version(), 'python_executable': sys.executable,
        'torch': torch.__version__, 'torch_cuda_build': torch.version.cuda,
        'cuda_available': torch.cuda.is_available(),
        'cuda_device_name': torch.cuda.get_device_name(0) if device.startswith('cuda') else None,
        'cuda_peak_allocated_mb': torch.cuda.max_memory_allocated() / 1024**2 if device.startswith('cuda') else 0,
        'cuda_peak_reserved_mb': torch.cuda.max_memory_reserved() / 1024**2 if device.startswith('cuda') else 0,
        'end_to_end_wall_s': wall, 'end_to_end_wall_fps': summary['processed_frames'] / wall,
        'summary_elapsed_s': summary['elapsed_s'], 'summary_processing_fps': summary['processing_fps'],
        'stage_seconds': dict(totals), 'stage_calls': dict(calls),
        'unattributed_seconds': wall - sum(totals[k] for k in exclusive),
        'detect_track_first_frame_s': detection_times[0],
        'detect_track_subsequent_median_s': statistics.median(detection_times[1:]),
        'detect_track_subsequent_mean_s': statistics.mean(detection_times[1:]),
        'ultralytics_speed_sum_ms': {key: sum(v.get(key, 0) for v in yolo_speeds)
                                     for key in ('preprocess', 'inference', 'postprocess')},
        'profile_instrumentation': 'timing wrappers and actual AutoBackend forward device checks; no model/count/CSV changes; small timing overhead',
        'prediction_mode': 'disabled', 'run': str(result),
    }
    write_json(result / 'device_profile.json', profile)
    return result, summary, profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=['cpu', 'cuda:0'], required=True)
    parser.add_argument('--config', default='configs/north.json')
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--end', type=float, default=30)
    parser.add_argument('--output-base', required=True)
    args = parser.parse_args()
    result, summary, profile = benchmark(args.config, args.device, args.start, args.end, args.output_base)
    print(json.dumps({'run': str(result), 'device': args.device, 'frames': summary['processed_frames'],
                      'processing_fps': summary['processing_fps'],
                      'end_to_end_wall_fps': profile['end_to_end_wall_fps']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
