"""Saved-video A/B and monotonic CSV completion tests, with no real detector."""
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from cctv.config import save
from cctv.pipeline import analyze
from cctv.profiles import apply_profile, load_profile
from cctv.timing import RunTiming
from cctv.usage import bind_video, USAGE_FIELDS
from test_batch import settings
from test_pipeline import FakeDetector, cv2, np


class TimingCases(unittest.TestCase):
    def test_signed_differences_and_monotonic_only(self):
        with tempfile.TemporaryDirectory() as folder, patch('time.time', side_effect=AssertionError('Wall clock forbidden')):
            timing = RunTiming(folder, 0, 'test')
            timing.mark('first_frame_start', 1_000_000_000)
            for i, at in [(1, 1_500_000_000), (2, 2_000_000_000)]:
                service = SimpleNamespace(last_csv_flush_ns=at, last_record_id=f'id{i}',
                                          last_ref={'path': 'north.csv', 'row_number_at_write': i})
                timing.csv_flushed({'촬영종료시각': str(i)}, {'record_index': i, 'interval_end_s': i}, service, 0)
            timing.mark('processing_loop_end', 2_050_000_000)
            with patch('cctv.timing.time.perf_counter_ns', return_value=2_100_000_000):
                result = timing.finish(20, 'completed')
            self.assertEqual(result['processing_difference']['first_s'], -.5)
            self.assertEqual(result['processing_difference']['final_s'], -1)
            self.assertEqual(result['run_difference']['final_s'], 0)
            self.assertEqual(result['flush_intervals_excluding_first']['p95_s'], .5)
            self.assertAlmostEqual(result['processing_loop_elapsed_s'], 1.05)

    def test_profile_overrides_registry_18_and_stale_assumption_tag(self):
        for room, stalls in [('south', 19), ('east', 23)]:
            c = settings(room, 18)
            c.update(available_stalls=stalls, measurement_status_tags=['demo_assumptions', 'initial_inside_assumed_18'])
            demo = apply_profile(c, load_profile('demo'))
            self.assertEqual((demo['initial_inside'], demo['available_stalls']), (3, stalls))
            self.assertNotIn('initial_inside_assumed_18', demo['measurement_status_tags'])
            self.assertIn('initial_inside_assumed_3', demo['measurement_status_tags'])
            self.assertEqual(apply_profile(c, load_profile('operating'))['initial_inside'], 18)
            self.assertEqual(c['initial_inside'], 18)

    @unittest.skipIf(cv2 is None, 'OpenCV/PyAV unavailable')
    def test_no_video_same_records_full_frames_and_flush_row_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source.mp4'
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 10, (200, 200))
            self.assertTrue(writer.isOpened())
            for _ in range(35):
                writer.write(np.zeros((200, 200, 3), dtype=np.uint8))
            writer.release()
            c = settings('north', 29)
            c.update(video=str(source), reference_size=[200, 200], output_dir=str(root / 'outputs'),
                     record_interval_s=1, prediction_mode='disabled')
            bind_video(c)
            config = root / 'config.json'
            save(c, config)
            with patch('cctv.pipeline.Detector', FakeDetector):
                full = analyze(config, measure_csv_latency=True)
                with patch('cctv.pipeline.annotate', side_effect=AssertionError('No overlay')), \
                     patch('cv2.VideoWriter', side_effect=AssertionError('No encoder')), \
                     patch('cctv.pipeline.verify_output', side_effect=AssertionError('No video verification')):
                    data = analyze(config, save_video=False, measure_csv_latency=True)
            self.assertEqual((full / 'usage_summary.csv').read_bytes(), (data / 'usage_summary.csv').read_bytes())
            self.assertEqual((full / 'events.csv').read_bytes(), (data / 'events.csv').read_bytes())
            self.assertEqual((full / 'diagnostics.jsonl').read_bytes(), (data / 'diagnostics.jsonl').read_bytes())
            self.assertFalse((data / 'annotated.mp4').exists())
            summary = json.loads((data / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['processed_frames'], 35)
            self.assertFalse(summary['output_video']['enabled'])
            with (data / 'csv_latency.csv').open(encoding='utf-8-sig', newline='') as f:
                latencies = list(csv.DictReader(f))
            index = [json.loads(s) for s in (data / 'record_index.jsonl').read_text(encoding='utf-8').splitlines()]
            with (data / 'usage_summary.csv').open(encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, USAGE_FIELDS)
                self.assertEqual(len(list(reader)), 3)
            self.assertEqual([float(r['interval_end_s']) for r in latencies], [1, 2, 3])
            self.assertEqual([r['record_id'] for r in latencies], [r['record_id'] for r in index])
            for n, row in enumerate(latencies, 1):
                self.assertEqual(int(row['csv_row_number_at_write']), n)
                self.assertTrue(Path(row['csv_path']).exists())
                self.assertAlmostEqual(float(row['run_minus_video_s']), float(row['run_elapsed_s']) - n)
            self.assertEqual(latencies[0]['since_previous_flush_s'], '')
            self.assertEqual(summary['timing']['records'], 3)
            self.assertGreaterEqual(summary['timing']['events']['processing_loop_end']['monotonic_ns'],
                                    int(latencies[-1]['flush_monotonic_ns']))


if __name__ == '__main__':
    unittest.main()
