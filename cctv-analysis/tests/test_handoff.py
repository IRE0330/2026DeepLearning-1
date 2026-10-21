import json
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from cctv.api import AnalysisService, BusyError, OwnershipError, _save_state
from cctv.config import load, save
from cctv.pipeline import analyze
from test_stream_output import config, record
from test_pipeline import FakeDetector, cv2, np
from cctv.stream_output import StreamOutput


def fake_worker(options, folder, stop_event, notifications):
    """Real spawned process/journal transport, synthetic aggregates only."""
    folder = Path(folder)
    run = folder / 'fake_run'
    c = config(initial_inside=None)
    state = {'status': 'running', 'phase': 'running', 'run_dir': str(run), 'latest_record': None}
    with StreamOutputContext(run, c) as output:
        for i in range(1, int(options.get('end') or 30) + 1):
            if stop_event.is_set():
                break
            row, detail = record(c, i)
            detail['state']['inside_estimate'] = None
            from cctv.usage import queue_estimates, usage_row
            detail['state'].update(queue_estimates(c, None, detail['state']['waiting_total']))
            row = usage_row(c, detail['state'], i - 1, i)
            output.write(row, detail, c)
            state['latest_record'] = json.loads(output.last_envelope)
            _save_state(folder, state)
            stop_event.wait(.01)
    state['status'] = 'stopped' if stop_event.is_set() else 'completed'
    _save_state(folder, state)


class StreamOutputContext(StreamOutput):
    def __enter__(self): return self
    def __exit__(self, *_): self.close()


class PublicAPI(unittest.TestCase):
    def test_spawn_single_owner_rerun_slow_reader_and_record_identity(self):
        with tempfile.TemporaryDirectory() as folder, patch('cctv.api._worker', fake_worker), AnalysisService() as service:
            job = service.start(owner='one', restroom_id='north', output_dir=folder)
            with self.assertRaises(BusyError):
                service.start(owner='one', restroom_id='north', output_dir=folder)
            with self.assertRaises(OwnershipError):
                service.stop('two')
            for _ in range(100):
                if job.latest() is not None:
                    break
                time.sleep(.01)
            self.assertIsNotNone(job.latest())
            latest = job.latest()
            latest['csv_row']['화장실ID'] = 'mutated'
            self.assertEqual(job.latest()['csv_row']['화장실ID'], 'north')
            time.sleep(.4)  # Slow UI: worker may complete without a consumer.
            values = list(job.records(poll_interval=.01))
            self.assertEqual(len(values), 30)
            self.assertEqual([v['record_index'] for v in values], list(range(1, 31)))
            self.assertEqual(len({v['record_id'] for v in values}), 30)
            first = job.read_records(limit=5)
            second = job.read_records(first.next_cursor, limit=5)
            self.assertEqual(second.records[0]['record_index'], 6)
            self.assertEqual(job.status()['status'], 'completed')
            self.assertFalse(service.status('two')['owned_by_session'])
            self.assertIsNone(values[-1]['detail']['state']['inside_estimate'])
            with (Path(job.status()['run_dir']) / 'record_index.jsonl').open('ab') as handle:
                handle.write(b'{"partial":')
            self.assertTrue(job.read_records().incomplete_tail)

    def test_lease_expiry_requests_stop_and_owner_can_restart(self):
        with tempfile.TemporaryDirectory() as folder, patch('cctv.api._worker', fake_worker), AnalysisService(lease_seconds=.05) as service:
            # Hold the fake source until the real watchdog notices a missed heartbeat.
            job = service.start(owner='one', restroom_id='north', output_dir=folder, end=1000)
            deadline = time.monotonic() + 5
            while job.alive and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertEqual(job.status()['status'], 'stopped')
            again = service.start(owner='two', restroom_id='south', output_dir=folder)
            self.assertNotEqual(again.folder, job.folder)
            again.stop()
            self.assertEqual(again.status()['status'], 'stopped')

    def test_config_paths_relative_to_config_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'settings.json'
            p.write_text(json.dumps({'model': 'weights/a.pt', 'video': 'clips/a.mp4', 'output_dir': 'runs'}), encoding='utf-8')
            c = load(p)
            self.assertEqual(Path(c['video']), p.parent / 'clips/a.mp4')
            self.assertEqual(Path(c['model']), p.parent / 'weights/a.pt')

    @unittest.skipIf(cv2 is None, 'Requires analysis optional dependencies')
    def test_cooperative_pipeline_stop_closes_csv_and_keeps_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            video = folder / 'synthetic.mp4'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 10, (200, 200))
            for _ in range(35): writer.write(np.zeros((200, 200, 3), dtype=np.uint8))
            writer.release()
            c = config(video=str(video), reference_size=[200, 200], initial_inside=29)
            from cctv.usage import bind_video
            bind_video(c)
            path = folder / 'config.json'
            save(c, path)
            stop = threading.Event()
            received = []
            def sink(serialized):
                received.append(json.loads(serialized))
                stop.set()
            with patch('cctv.pipeline.Detector', FakeDetector):
                out = analyze(path, output_base=folder / 'runs', save_video=False,
                              record_sink=sink, stop_event=stop)
            summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['status'], 'stopped')
            self.assertEqual(summary['processed_frames'], 11)
            self.assertEqual(summary['regular_csv_rows'], 1)
            self.assertTrue(summary['stream_output']['closed'])
            self.assertEqual(received[0]['record_id'], json.loads((out / 'record_index.jsonl').read_text(encoding='utf-8'))['record_id'])
            self.assertAlmostEqual(summary['remainder']['duration_s'], .1)


if __name__ == '__main__':
    unittest.main()
