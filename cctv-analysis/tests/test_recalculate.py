"""Real codec source/log roundtrip: initial assumption changes, events do not."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cctv.config import save
from cctv.intervals import DailyCSVWriter
from cctv.pipeline import analyze
from cctv.profiles import load_profile
from cctv.recalculate import recalculate_run
from cctv.usage import bind_video
from test_batch import settings
from test_pipeline import FakeDetector, cv2, np


@unittest.skipIf(cv2 is None, 'OpenCV/PyAV unavailable')
class RecalculateInitial(unittest.TestCase):
    def test_recalculation_preserves_negative_raw_inside_and_updates_only_its_diagnostics(self):
        class ExitingDetector(FakeDetector):
            def observe(self, frame):
                observations = super().observe(frame)
                from cctv.core import Observation
                return [Observation(o.track_id, (200-o.box[2], o.box[1], 200-o.box[0], o.box[3]), o.confidence)
                        for o in observations]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root / 'source.mp4'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 10, (200, 200))
            for _ in range(25):
                writer.write(np.zeros((200, 200, 3), dtype=np.uint8))
            writer.release()
            c = settings('south', 18)
            c.update(video=str(video), reference_size=[200,200], record_interval_s=1, output_dir=str(root/'old'))
            bind_video(c)
            save(c, root/'config.json')
            with patch('cctv.pipeline.Detector', ExitingDetector):
                source = analyze(root/'config.json')
            profile = load_profile('demo')
            profile['environments']['south'] = {'initial_inside': 0, 'measurement_status_tags': ['initial_inside_assumed_0']}
            result = recalculate_run(source, root/'new/south', DailyCSVWriter(root/'new/shared'), profile)
            state = result['final_state']
            self.assertEqual((state['entries'], state['exits'], state['inside_estimate']), (0,1,-1))
            self.assertIsNone(state['total_queue_estimate'])
            self.assertIn('negative_inside', state['measurement_status'])
            self.assertFalse(result['all_frame_diagnostics_identical'])
            self.assertTrue(result['non_initial_dependent_diagnostics_identical'])
            self.assertEqual((source/'events.csv').read_bytes(), (root/'new/south/events.csv').read_bytes())

    def test_null_to_3_from_recorded_observations_preserves_events_and_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root / 'source.mp4'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 10, (200, 200))
            self.assertTrue(writer.isOpened())
            for _ in range(25):
                writer.write(np.zeros((200, 200, 3), dtype=np.uint8))
            writer.release()
            c = settings('south', None)
            c.update(video=str(video), reference_size=[200, 200], available_stalls=19,
                     record_interval_s=1, output_dir=str(root / 'source_runs'))
            bind_video(c)
            cfg = root / 'source.json'
            save(c, cfg)
            with patch('cctv.pipeline.Detector', FakeDetector):
                source = analyze(cfg)
            protected = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
            target = root / 'new' / 'south'
            daily = DailyCSVWriter(root / 'new' / 'shared')
            # Any fresh detector use would fail this test.
            with patch('cctv.pipeline.Detector', side_effect=AssertionError('Inference must not run')):
                result = recalculate_run(source, target, daily, load_profile('demo'))
            before = json.loads((source / 'final_state.json').read_text(encoding='utf-8'))
            final = json.loads((target / 'final_state.json').read_text(encoding='utf-8'))
            self.assertEqual((final['entries'], final['exits'], final['waiting_total']),
                             (before['entries'], before['exits'], before['waiting_total']))
            self.assertEqual(final['inside_estimate'], 3 + before['entries'] - before['exits'])
            self.assertEqual(final['internal_waiting_estimate'], max(final['inside_estimate'] - 19, 0))
            self.assertEqual(final['available_stalls_estimate'], max(19 - final['inside_estimate'], 0))
            self.assertAlmostEqual(final['expected_wait_s'], (final['total_queue_estimate'] + 1) * 105 / 19)
            self.assertEqual(result['csv_rows'], 2)
            self.assertEqual(result['remainder']['duration_s'], .5)
            self.assertEqual((target / 'events.csv').read_bytes(), (source / 'events.csv').read_bytes())
            self.assertEqual((target / 'usage_summary.csv').read_bytes(),
                             (root / 'new/shared/south_2026-10-14.csv').read_bytes())
            with (target / 'usage_summary.csv').open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(all('initial_inside_unset' not in row['측정상태'] for row in rows))
            self.assertTrue(all('initial_inside_assumed_3' in row['측정상태'] for row in rows))
            self.assertTrue(all((source / name).read_bytes() == data for name, data in protected.items()))


if __name__ == '__main__':
    unittest.main()
