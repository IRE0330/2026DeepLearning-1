"""Focused recording tests; injected observations do not measure detection accuracy."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cctv.config import clone, record_interval_s, save
from cctv.intervals import IntervalSampler
from cctv.pipeline import analyze
from cctv.profiles import apply_profile, load_profile
from cctv.usage import bind_video, USAGE_FIELDS
from test_batch import settings, state, event
from test_pipeline import FakeDetector, cv2, np


class RecordingIntervals(unittest.TestCase):
    def test_profiles_and_legacy_default_only_change_recording_interval(self):
        original = settings()
        before = clone(original)
        demo = apply_profile(original, load_profile('demo'))
        operating = apply_profile(original, load_profile('operating'))
        self.assertEqual(record_interval_s(demo), 1)
        self.assertEqual(record_interval_s(operating), 10)
        legacy = clone(original)
        legacy.pop('record_interval_s', None)
        self.assertEqual(record_interval_s(legacy), 10)
        self.assertEqual(original, before)
        for name in ('boundary', 'entry_direction', 'outside_zone', 'inside_zone',
                     'waiting_zone', 'excluded_zones', 'rules', 'video', 'initial_inside', 'available_stalls'):
            self.assertEqual(demo[name], original[name])

    def test_invalid_recording_intervals_rejected(self):
        for value in (0, -1, True, None, '1', float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                IntervalSampler(dict(settings(), record_interval_s=value), 0, lambda r, d: None)

    def test_one_second_edge_events_once_cumulative_inside_and_remainder(self):
        records = []
        sampler = IntervalSampler(dict(settings(), record_interval_s=1), 0,
                                  lambda r, d: records.append((r, d)))
        sampler.push(state(0, 1), [event(0, 'entry')])
        sampler.push(state(.958333, 1, external=3), [])
        sampler.push(state(1, 2, external=2), [event(1, 'entry')])
        sampler.push(state(1.041667, 2, 1, 9), [event(1.041667, 'exit')])
        sampler.push(state(2, 3, 1, 4), [event(2, 'entry')])
        sampler.push(state(2.4, 3, 2, 0), [event(2.4, 'exit')])
        remainder = sampler.finish(2.5)
        self.assertEqual([(r['구간_입장인원'], r['구간_퇴장인원']) for r, _ in records], [(2, 0), (1, 1)])
        self.assertEqual([r['내부잔류인원_추정'] for r, _ in records], [31, 31])
        self.assertEqual([r['현재대기인원_추정'] for r, _ in records], [6, 8])
        self.assertEqual([r['전체대기인원_추정'] for r, _ in records], [6, 8])
        self.assertEqual([r['현재이용가능칸수_추정'] for r, _ in records], [0, 0])
        self.assertEqual([d['record_index'] for _, d in records], [1, 2])
        self.assertEqual(records[0][0]['촬영종료시각'], '2026-10-14T00:00:01+09:00')
        self.assertEqual(records[1][0]['촬영시작시각'], '2026-10-14T00:00:01+09:00')
        self.assertEqual(remainder['duration_s'], .5)
        self.assertEqual(remainder['exits'], 1)
        self.assertEqual(remainder['last_state']['inside_estimate'], 30)

    def test_fractional_origin_never_uses_future_and_finishes_cfr_boundary(self):
        records = []
        sampler = IntervalSampler(dict(settings(), record_interval_s=1), .125,
                                  lambda r, d: records.append((r, d)))
        sampler.push(state(.125), [])
        sampler.push(state(1.083333, external=5), [])
        sampler.push(state(1.166667, 1, external=99), [event(1.166667, 'entry')])
        sampler.push(state(2.083333, 1, external=3), [])
        remainder = sampler.finish(2.125)
        self.assertEqual([d['interval_end_s'] for _, d in records], [1.125, 2.125])
        self.assertEqual([r['외부대기인원_추정'] for r, _ in records], [5, 3])
        self.assertEqual([r['구간_입장인원'] for r, _ in records], [0, 1])
        self.assertTrue(all(d['source_time_s'] <= d['interval_end_s'] for _, d in records))
        self.assertEqual(remainder['duration_s'], 0)

    @unittest.skipIf(cv2 is None, 'OpenCV/PyAV unavailable')
    def test_pipeline_appends_and_flushes_each_record_with_detail_only_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root / 'synthetic.mp4'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 10, (200, 200))
            self.assertTrue(writer.isOpened())
            for _ in range(25):
                writer.write(np.zeros((200, 200, 3), dtype=np.uint8))
            writer.release()
            c = settings()
            c.update(video=str(video), reference_size=[200, 200], output_dir=str(root / 'outputs'))
            c = apply_profile(c, load_profile('demo'))
            bind_video(c)
            cfg = root / 'config.json'
            save(c, cfg)
            records = []
            def after_save(row, detail):
                path = next((root / 'outputs').glob('*/usage_summary.csv'))
                self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
                with path.open(encoding='utf-8-sig', newline='') as f:
                    reader = csv.DictReader(f)
                    self.assertEqual(reader.fieldnames, USAGE_FIELDS)
                    self.assertEqual(len(list(reader)), len(records) + 1)
                records.append((row, detail))
            with patch('cctv.pipeline.Detector', FakeDetector):
                out = analyze(cfg, interval_sink=after_save)
            summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['periodic_interval_s'], 1)
            self.assertEqual(summary['regular_csv_rows'], 2)
            self.assertEqual([d['interval_end_s'] for _, d in records], [1, 2])
            self.assertEqual([r['구간_입장인원'] for r, _ in records], [0, 1])
            self.assertEqual([r['내부잔류인원_추정'] for r, _ in records], [29, 30])
            self.assertEqual(summary['processed_frames'], 25)  # No detection-frame skipping.
            self.assertEqual(summary['actual_last_frame_s'], 2.4)
            self.assertEqual(summary['remainder']['duration_s'], .5)
            details = [json.loads(line) for line in (out / 'interval_details.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([d['record_interval_s'] for d in details], [1, 1])


if __name__ == '__main__':
    unittest.main()
