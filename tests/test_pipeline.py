"""Real codec/export smoke test with synthetic frames and an injected tracker."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
try:
    import cv2
    import numpy as np
    import av
except ImportError:
    cv2 = None
from cctv.config import save
from cctv.core import Observation
from cctv.pipeline import analyze
from cctv.evaluate import evaluate
from test_core import config


class FakeDetector:
    def __init__(self, c, fps):
        self.i = -1
        self.raw_detections = []
        self.tracker = type("Tracker", (), {"max_frames_lost": 30})()

    def metadata(self):
        return {"name": "synthetic_injected_tracker", "device": "cpu"}

    def observe(self, frame):
        self.i += 1
        x = 80 if self.i < 10 else 120
        return [Observation(1, (x - 8, 60, x + 8, 100))]


@unittest.skipIf(cv2 is None, "OpenCV/PyAV 없는 환경에서는 모델 없는 core 테스트만 실행")
class ExportSmoke(unittest.TestCase):
    def test_video_csv_final_state_and_empty_truth(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root / "synthetic.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (200, 200))
            self.assertTrue(writer.isOpened())
            for _ in range(35):
                writer.write(np.zeros((200, 200, 3), dtype=np.uint8))
            writer.release()
            c = config(0)
            c.update(video=str(video), reference_size=[200, 200], output_dir=str(root / "outputs"),
                     available_stalls=27, average_stall_use_s=105,
                     capture_start_time='2026-01-02T09:00:00+09:00', capture_time_kind='virtual')
            from cctv.usage import bind_video, USAGE_FIELDS
            bind_video(c, 'synthetic_source_001')
            cfg = root / "config.json"
            save(c, cfg)
            with patch("cctv.pipeline.Detector", FakeDetector):
                out = analyze(cfg, start=0.2, end=3.0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["processed_frames"], 28)
            self.assertEqual(summary["actual_start_s"], 0.2)
            self.assertEqual(summary["actual_last_frame_s"], 2.9)
            self.assertTrue(summary["output_video"]["all_frames_decoded"])
            self.assertEqual(summary["final_state"]["entries"], 1)
            self.assertEqual(summary["final_state"]["inside_estimate"], 1)
            self.assertTrue((out / "timeseries.csv").read_bytes().startswith(b"\xef\xbb\xbf"))
            with (out / "timeseries.csv").open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([int(r["sample_time_s"]) for r in rows], [1, 2])
            self.assertTrue(all(float(r["source_time_s"]) <= float(r["sample_time_s"]) for r in rows))
            self.assertTrue((out / 'usage_summary.csv').read_bytes().startswith(b'\xef\xbb\xbf'))
            with (out / 'usage_summary.csv').open(encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, USAGE_FIELDS)
                usage = list(reader)
            self.assertEqual(len(usage), 0)  # <10s is detail only.
            detail = summary['final_usage_detail']['last_frame_usage']
            self.assertEqual(detail['구간_입장인원'], 1)
            # Earlier candidate=1 and cumulative entry=1, but final external waiting=0.
            self.assertEqual(detail['외부대기인원_추정'], 0)
            self.assertEqual(detail['현재대기인원_추정'], 0)
            self.assertEqual(detail['내부잔류인원_추정'], 1)
            self.assertEqual(detail['촬영시작시각'], '2026-01-02T09:00:00.200000+09:00')
            self.assertEqual(detail['촬영종료시각'], '2026-01-02T09:00:02.900000+09:00')
            self.assertIn('virtual_scenario_time', detail['측정상태'])
            self.assertAlmostEqual(summary['remainder']['duration_s'], 2.8)
            self.assertEqual(summary['video_id'], 'synthetic_source_001')
            self.assertTrue(summary['video_identity_bound'])
            with patch("cctv.pipeline.Detector", FakeDetector):
                repeated = analyze(cfg, start=0.2, end=3.0)
            repeated_summary = json.loads((repeated / 'summary.json').read_text(encoding='utf-8'))
            self.assertNotEqual(out, repeated)
            self.assertEqual(summary['video_id'], repeated_summary['video_id'])
            self.assertEqual(summary['final_state'], repeated_summary['final_state'])
            truths = root / "truth"
            truths.mkdir()
            from scripts.make_truth_templates import create
            create(truths, "test")
            metadata = json.loads((truths / 'metadata.json').read_text(encoding='utf-8'))
            self.assertEqual(metadata['waiting_count_policy'], summary['waiting_count_policy'])
            # Old confirmed-only labels must not be evaluated against v2 counts.
            with (truths / 'waiting.csv').open('w',encoding='utf-8-sig',newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['restroom_id','video_time_s','waiting_count'])
                writer.writerow(['test',1,1])
            metadata['waiting_count_policy'] = 'confirmed_only_v1'
            (truths / 'metadata.json').write_text(json.dumps(metadata),encoding='utf-8')
            with self.assertRaises(ValueError):
                evaluate(out, truths)
            with (truths / 'waiting.csv').open('w',encoding='utf-8-sig',newline='') as f:
                csv.writer(f).writerow(['restroom_id','video_time_s','waiting_count'])
            result = evaluate(out, truths)
            metrics = json.loads((result / "metrics.json").read_text(encoding="utf-8"))
            self.assertIsNone(metrics["event_metrics"])
            self.assertIsNone(metrics["waiting"])
            self.assertIsNone(metrics["inside"])

    def test_real_export_ten_seconds_remainder_and_live_sink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root / 'synthetic.mp4'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 10, (200, 200))
            for _ in range(253):
                writer.write(np.zeros((200, 200, 3), dtype=np.uint8))
            writer.release()
            c = config(29)
            c.update(restroom_id='north', video=str(video), reference_size=[200, 200],
                     output_dir=str(root / 'outputs'), available_stalls=27, average_stall_use_s=105)
            from cctv.usage import bind_video
            bind_video(c)
            cfg = root / 'c.json'
            save(c, cfg)
            recorded = []
            def sink(row, detail):
                # File is present and flushed while the pipeline is still running.
                path = next((root / 'outputs').glob('*/usage_summary.csv'))
                with path.open(encoding='utf-8-sig', newline='') as f:
                    on_disk = list(csv.DictReader(f))
                self.assertEqual(len(on_disk), len(recorded) + 1)
                self.assertLessEqual(detail['source_time_s'], detail['interval_end_s'])
                recorded.append((row, detail))
            with patch('cctv.pipeline.Detector', FakeDetector):
                out = analyze(cfg, interval_sink=sink)
            summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual([d['interval_end_s'] for _, d in recorded], [10, 20])
            self.assertEqual([r['구간_입장인원'] for r, _ in recorded], [1, 0])
            self.assertEqual([r['내부잔류인원_추정'] for r, _ in recorded], [30, 30])
            self.assertEqual([r['현재대기인원_추정'] for r, _ in recorded], [3, 3])
            self.assertEqual([r['전체대기인원_추정'] for r, _ in recorded], [3, 3])
            self.assertAlmostEqual(summary['remainder']['duration_s'], 5.3)
            self.assertEqual(summary['final_state']['source_time_s'], 25.2)
            self.assertAlmostEqual(summary['final_state']['expected_wait_s'], 4 * 105 / 27)
            self.assertEqual(summary['processed_frames'], 253)


if __name__ == "__main__":
    unittest.main()
