import csv
import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cctv.paced import due_ns, wait_until, LagGuard, InputAborted, InputController, STRIDE
from cctv.timing import RunTiming
from cctv.intervals import IntervalSampler
from test_batch import settings


class FakeClock:
    def __init__(self):
        self.ns = 0
        self.waits = []
    def clock(self):
        return self.ns
    def wait(self, seconds):
        self.waits.append(seconds)
        self.ns += max(1, round(seconds * 1e9))
        return False


class PacedCases(unittest.TestCase):
    def test_cli_reports_partial_group_as_nonzero(self):
        from cctv.__main__ import main
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for status, code in [('partial_or_failed', 2), ('completed', 0)]:
                (root / 'experiment_summary.json').write_text(json.dumps({'status': status}), encoding='utf-8')
                with patch('cctv.paced.run_simulation', return_value=root):
                    self.assertEqual(main(['simulate-input', '--rooms', 'north', 'south', 'east']), code)

    def test_fixed_origin_deadlines_do_not_rebase_when_late(self):
        clock = FakeClock()
        origin = 100_000_000
        wait_until(due_ns(origin, 1), clock, clock.clock)
        self.assertEqual(clock.ns, 1_100_000_000)
        clock.ns = 2_500_000_000
        previous = len(clock.waits)
        wait_until(due_ns(origin, 2), clock, clock.clock)
        self.assertEqual(len(clock.waits), previous)
        self.assertEqual(due_ns(origin, 3), 3_100_000_000)

    def test_stop_and_sustained_guard_preserve_original_thresholds(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(InputAborted):
            wait_until(10, stop, lambda: 0)
        guard = LagGuard(5, 10, 15)
        self.assertIsNone(guard.check(6, 100))
        self.assertIsNone(guard.check(6, 109.9))
        self.assertEqual(guard.check(6, 110), 'sustained_frame_start_lag')
        self.assertIsNone(guard.check(4, 111))
        self.assertIsNone(guard.check(6, 112))
        self.assertEqual(guard.check(16, 113), 'hard_frame_start_lag')

    def test_integer_eof_uses_past_state_and_waits_for_boundary(self):
        clock = FakeClock()
        rows = []
        config = settings('east', 3)
        config.update(record_interval_s=1, available_stalls=23)
        def sink(row, detail):
            wait_until(due_ns(0, detail['interval_end_s']), clock, clock.clock)
            self.assertLessEqual(detail['source_time_s'], detail['interval_end_s'])
            rows.append((detail['interval_end_s'], detail['source_time_s'], clock.ns))
        sampler = IntervalSampler(config, 0, sink)
        for index in range(2700):
            t = index / 30
            clock.ns = max(clock.ns, due_ns(0, t))
            sampler.push(dict(source_time_s=t, frame_index=index, entries=0, exits=0,
                              inside_estimate=3, waiting_total=0, measurement_status='ok'), [])
        self.assertEqual(len(rows), 89)
        sampler.finish(90)
        self.assertEqual(rows[-1], (90, 2699 / 30, 90_000_000_000))
        self.assertEqual(len(rows), 90)

    def test_timing_records_boundary_source_and_rejects_early_flush(self):
        with tempfile.TemporaryDirectory() as folder:
            timing = RunTiming(folder, 0, 'test')
            timing.input_start_ns = 1_000_000_000
            timing.mark('first_frame_start', 1_000_000_000)
            detail = dict(record_index=1, interval_end_s=1, source_time_s=1)
            service = SimpleNamespace(last_csv_flush_ns=1_999_999_999, last_record_id='stable',
                                      last_ref={'path': 'north.csv', 'row_number_at_write': 1})
            with self.assertRaises(ValueError):
                timing.csv_flushed({'촬영종료시각': 'end'}, detail, service, 0)
            service.last_csv_flush_ns = 2_200_000_000
            timing.csv_flushed({'촬영종료시각': 'end'}, detail, service, 0)
            timing.mark('processing_loop_end', 2_300_000_000)
            with patch('cctv.timing.time.perf_counter_ns', return_value=2_400_000_000):
                summary = timing.finish(30, 'completed')
            self.assertAlmostEqual(summary['record_delay']['first_s'], .2)
            self.assertEqual(timing.rows[0]['record_id'], 'stable')

    def test_bounded_source_is_contiguous_and_does_not_load_entire_video(self):
        ctx = mp.get_context('spawn')
        group = dict(stop=ctx.Event(), metrics=ctx.Array('q', STRIDE), reason=ctx.Array('c', 2048))
        controller = InputController(group, 0, dict(input_mode='unpaced', queue_capacity=2,
                                    soft_lag_s=5, sustained_lag_s=10, hard_lag_s=15, room='north'))
        controller.origin = 0
        controller.info = {'frame_count': 100}
        decoded = []
        def source(_):
            for i in range(100):
                decoded.append(i)
                yield i, i
        with patch('cctv.media.frames', source):
            iterator = controller.frames('unused', 10, None)
            first = next(iterator)
            # Producer can hold only capacity+one pending decoded frame.
            threading.Event().wait(.03)
            self.assertLessEqual(len(decoded), 4)
            self.assertEqual([first[0]] + [i for i, _ in iterator], list(range(100)))
        stats = controller.close()
        self.assertLessEqual(stats['max_queue_depth'], 2)
        self.assertEqual(stats['missing_or_duplicate_frames'], 0)


if __name__ == '__main__':
    unittest.main()
