"""Persistence/rotation/async-failure tests. No prediction or accuracy claims."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from cctv.config import save
from cctv.delivery import DeliveryWorker
from cctv.intervals import HourlyCSVWriter
from cctv.output_config import output_settings
from cctv.pipeline import analyze
from cctv.profiles import apply_profile, load_profile
from cctv.stream_output import StreamOutput, make_envelope, retry_outbox
from cctv.usage import USAGE_FIELDS, bind_video, queue_estimates, usage_row
from test_batch import settings, state
from test_pipeline import cv2, np, FakeDetector


def config(room='north', prediction='disabled', **options):
    c = settings(room)
    c.update(record_interval_s=1, prediction_mode=prediction, profile_name='demo')
    c.update(options)
    return c


def record(c, index=1, snapshot=None):
    s = snapshot if snapshot is not None else state(index, external=2)
    s.update(queue_estimates(c, s['inside_estimate'], s['waiting_total']))
    detail = {'record_index': index, 'record_interval_s': 1, 'interval_start_s': index - 1,
              'interval_end_s': index, 'source_time_s': s['source_time_s'], 'state': s,
              'interval_entries': 0, 'interval_exits': 0}
    return usage_row(c, s, index - 1, index), detail


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


class HourlyFiles(unittest.TestCase):
    def test_hour_midnight_room_timezone_start_assignment_handles_bom_header(self):
        with tempfile.TemporaryDirectory() as folder:
            writer = HourlyCSVWriter(folder)
            c = config(capture_start_time='2026-10-14T05:59:59+00:00')  # 14:59:59 KST
            first = writer.add(record(c, 1)[0])
            old_handle = writer.active['north'][1]
            second = writer.add(record(c, 2)[0])
            self.assertTrue(old_handle.closed)
            current = writer.active['north'][1]
            writer.add(record(c, 3)[0])
            self.assertIs(writer.active['north'][1], current)
            self.assertEqual(first.name, 'north_2026-10-14_1400.csv')
            self.assertEqual(second.name, 'north_2026-10-14_1500.csv')
            # Revisit the old bucket: append once, never another header/BOM.
            writer.add(record(c, 1)[0])
            c['capture_start_time'] = '2026-10-14T23:59:59+09:00'
            self.assertEqual(writer.add(record(c, 1)[0]).name, 'north_2026-10-14_2300.csv')
            self.assertEqual(writer.add(record(c, 2)[0]).name, 'north_2026-10-15_0000.csv')
            for room in ('south', 'east'):
                rc = config(room)
                self.assertEqual(writer.add(record(rc)[0]).name, f'{room}_2026-10-14_0000.csv')
            writer.close()
            self.assertTrue(all(item['closed'] for item in writer.manifest()))
            self.assertEqual(len(list(Path(folder).glob('*.csv'))), 6)
            for file in Path(folder).glob('*.csv'):
                self.assertEqual(file.read_bytes().count(b'\xef\xbb\xbf'), 1)
                fields, rows = read(file)
                self.assertEqual(fields, USAGE_FIELDS)
                self.assertTrue(all(set(row) == set(USAGE_FIELDS) for row in rows))
                self.assertEqual(file.read_text(encoding='utf-8-sig').count('촬영시작시각'), 1)
            self.assertEqual(len(read(first)[1]), 2)
            self.assertEqual(len(read(second)[1]), 2)

    def test_default_disabled_intervals_independent_and_legacy_daily_preserved(self):
        self.assertEqual(output_settings()['prediction_mode'], 'disabled')
        self.assertEqual(output_settings()['csv_split_interval_s'], 3600)
        self.assertEqual(load_profile('demo')['defaults']['record_interval_s'], 1)
        self.assertEqual(load_profile('operating')['defaults']['record_interval_s'], 10)
        with tempfile.TemporaryDirectory() as folder:
            c = config(csv_split_interval_s=86400)
            output = StreamOutput(folder, c)
            row, detail = record(c)
            output.write(row, detail, c)
            stats = output.close()
            self.assertTrue((Path(folder) / 'shared/north_2026-10-14.csv').is_file())
            self.assertEqual(stats['delivery_disabled_records'], 1)
            self.assertIsNone(stats['delivery'])
            self.assertFalse((Path(folder) / 'delivery/outbox.sqlite3').exists())


class DeliveryCases(unittest.TestCase):
    def test_restart_restores_csv_flushed_envelope_missing_from_outbox_and_flags_partial_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            c = config(prediction='mock')
            output = StreamOutput(folder, c)
            output.close()  # Empty initialized database: simulate commit not reached.
            row, detail = record(c)
            csv_writer = HourlyCSVWriter(Path(folder) / 'shared')
            csv_path = csv_writer.add(row)
            reference = dict(csv_writer.last_ref)
            csv_writer.close()
            payload = make_envelope(Path(folder).name, row, detail, c, reference)
            index = Path(folder) / 'record_index.jsonl'
            index.write_text(payload + '\n', encoding='utf-8')
            original_csv = csv_path.read_bytes()
            resumed, _ = retry_outbox(Path(folder) / 'delivery/outbox.sqlite3')
            self.assertEqual((resumed['index_records_restored'], resumed['acknowledged']), (1, 1))
            self.assertEqual(csv_path.read_bytes(), original_csv)
            with index.open('a', encoding='utf-8') as f:
                f.write('{"record_id":')  # Report an incomplete final write, never silently ignore it.
            again, _ = retry_outbox(Path(folder) / 'delivery/outbox.sqlite3')
            self.assertTrue(again['incomplete_index_tail'])
            self.assertEqual((again['index_records_restored'], again['acknowledged']), (0, 1))

    def test_failed_receipts_retry_same_id_csv_preserved_then_restart_failed(self):
        class Reject:
            def __init__(self):
                self.ids = []
            def send(self, envelope):
                self.ids.append(envelope['record_id'])
                raise OSError('simulated acceptance/receipt loss')
        with tempfile.TemporaryDirectory() as folder:
            receiver = Reject()
            c = config(prediction='mock', delivery={'max_attempts': 2, 'retry_delay_s': .001})
            output = StreamOutput(folder, c, receiver)
            row, detail = record(c)
            csv_path = output.write(row, detail, c)
            serialized = output.index_path.read_text(encoding='utf-8').strip()
            self.assertFalse(output.worker.enqueue(serialized))
            before = csv_path.read_bytes()
            stats = output.close()['delivery']
            self.assertEqual((stats['attempts'], stats['failed'], stats['unacknowledged']), (2, 1, 1))
            self.assertEqual(len(set(receiver.ids)), 1)
            resumed, _ = retry_outbox(Path(folder) / 'delivery/outbox.sqlite3', retry_failed=True)
            self.assertEqual((resumed['attempts'], resumed['acknowledged'], resumed['unacknowledged']), (3, 1, 0))
            accepted = json.loads((Path(folder) / 'delivery/mock_received.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(accepted['record_id'], receiver.ids[0])
            self.assertFalse(accepted['prediction_performed'])
            self.assertEqual(csv_path.read_bytes(), before)
            self.assertEqual(len(read(csv_path)[1]), 1)

    def test_transient_failure_and_receiver_mutation_cannot_change_saved_payload(self):
        class Flaky:
            def __init__(self):
                self.calls = []
            def send(self, envelope):
                self.calls.append(copy.deepcopy(envelope))
                envelope['csv_row']['전체대기인원_추정'] = 999
                if len(self.calls) == 1:
                    raise TimeoutError('one lost acknowledgement')
                return {'record_id': envelope['record_id'], 'acknowledged': True}
        with tempfile.TemporaryDirectory() as folder:
            c = config(prediction='mock', delivery={'retry_delay_s': .001})
            receiver = Flaky()
            output = StreamOutput(folder, c, receiver)
            row, detail = record(c)
            expected = copy.deepcopy(row)
            output.write(row, detail, c)
            row['전체대기인원_추정'] = 77
            detail['state']['inside_estimate'] = 300
            delivery = output.close()['delivery']
            self.assertEqual((delivery['attempts'], delivery['acknowledged']), (2, 1))
            self.assertEqual(receiver.calls[0]['csv_row'], expected)
            self.assertEqual(receiver.calls[1]['csv_row'], expected)
            self.assertEqual(receiver.calls[0]['record_id'], receiver.calls[1]['record_id'])
            index = json.loads(output.index_path.read_text(encoding='utf-8'))
            self.assertEqual(index['csv_row'], expected)
            self.assertEqual(index['schema_version'], 1)
            self.assertTrue(index['is_demo'])

    def test_unknown_capture_initial_and_negative_status_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            c = config(prediction='mock', initial_inside=None, capture_start_time=None, capture_time_kind=None)
            output = StreamOutput(folder, c)
            unknown = state(1)
            unknown.update(inside_estimate=None, measurement_status='initial_inside_unset')
            row, detail = record(c, snapshot=unknown)
            output.write(row, detail, c)
            negative_c = dict(c, initial_inside=0, video_id='negative_source')
            negative = state(2, exits=3, initial=0)
            negative['measurement_status'] = 'negative_inside'
            output.write(*record(negative_c, 2, negative), negative_c)
            stats = output.close()
            self.assertEqual(stats['delivery']['acknowledged'], 2)
            self.assertEqual([p.name for p in (Path(folder) / 'shared').glob('*.csv')], [])
            unknown_file = Path(folder) / 'shared/time_unset/north_relative.csv'
            fields, rows = read(unknown_file)
            self.assertEqual(fields, USAGE_FIELDS)
            self.assertEqual(rows[0]['내부잔류인원_추정'], '')
            self.assertEqual(rows[1]['내부잔류인원_추정'], '-3')
            receipts = [json.loads(line)['envelope'] for line in (Path(folder) / 'delivery/mock_received.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertTrue(all(e['capture_time_unset'] and e['interval_start_time'] is None for e in receipts))
            self.assertIsNone(receipts[0]['csv_row']['내부잔류인원_추정'])
            self.assertIsNone(receipts[1]['csv_row']['전체대기인원_추정'])
            self.assertIn('negative_inside', receipts[1]['csv_row']['측정상태'])
            self.assertEqual(receipts[1]['interval_start_s'], 1)

    def test_slow_receiver_bounded_memory_disk_backlog_and_shutdown(self):
        started, release = threading.Event(), threading.Event()
        class Slow:
            def send(self, envelope):
                started.set()
                release.wait(2)
                return {'record_id': envelope['record_id'], 'acknowledged': True}
        with tempfile.TemporaryDirectory() as folder:
            c = config(prediction='mock', delivery={'queue_capacity': 2, 'shutdown_timeout_s': .02})
            output = StreamOutput(folder, c, Slow())
            try:
                output.write(*record(c), c)
                self.assertTrue(started.wait(1))
                for i in range(2, 13):
                    output.write(*record(c, i), c)
                before_close = time.monotonic()
                stats = output.close()['delivery']
                self.assertLess(time.monotonic() - before_close, .5)
                self.assertEqual(stats['records'], 12)
                self.assertGreater(stats['unacknowledged'], 0)
                self.assertGreater(stats['queue_full_events'], 0)
                self.assertLessEqual(stats['max_memory_queue_depth'], 2)
                self.assertGreater(stats['max_pending_records'], 2)
                self.assertEqual(len(read(Path(folder) / 'shared/north_2026-10-14_0000.csv')[1]), 12)
            finally:
                release.set()
                output.worker.thread.join(2)
                output.close()

    def test_actual_process_crash_inflight_recovery_same_record_id(self):
        child = '''
import json,os,sys,threading
from cctv.delivery import DeliveryWorker
from cctv.output_config import output_settings
ready=threading.Event()
class Hung:
 def send(self,envelope):
  ready.set()
  threading.Event().wait(60)
w=DeliveryWorker(sys.argv[1],output_settings()['delivery'],Hung())
w.enqueue(sys.argv[2])
if not ready.wait(3): raise RuntimeError('worker did not claim record')
os._exit(0)
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'outbox.sqlite3'
            c = config(prediction='mock')
            row, detail = record(c)
            payload = make_envelope('crash_run', row, detail, c, {'path': 'saved.csv', 'row_number_at_write': 1})
            result = subprocess.run([sys.executable, '-B', '-c', child, str(path), payload],
                                    capture_output=True, timeout=10,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(result.returncode, 0, result.stderr)
            resumed, _ = retry_outbox(path)
            self.assertEqual((resumed['records'], resumed['attempts'], resumed['acknowledged'], resumed['unacknowledged']), (1, 2, 1, 0))
            receipt = json.loads((Path(folder) / 'mock_received.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(receipt['record_id'], json.loads(payload)['record_id'])

    def test_duplicate_record_id_cannot_replace_content(self):
        with tempfile.TemporaryDirectory() as folder:
            c = config(prediction='mock')
            output = StreamOutput(folder, c)
            row, detail = record(c)
            output.write(row, detail, c)
            payload = output.index_path.read_text(encoding='utf-8').strip()
            altered = json.loads(payload)
            altered['csv_row']['구간_입장인원'] = 99
            try:
                with self.assertRaises(ValueError):
                    output.worker.enqueue(json.dumps(altered, ensure_ascii=False))
            finally:
                output.close()


@unittest.skipIf(cv2 is None, 'OpenCV/PyAV unavailable')
class PipelineDelivery(unittest.TestCase):
    def test_per_frame_pipeline_csv_flush_before_mock_same_snapshot_and_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root / 'synthetic.mp4'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 10, (200, 200))
            self.assertTrue(writer.isOpened())
            for _ in range(25):
                writer.write(np.zeros((200, 200, 3), dtype=np.uint8))
            writer.release()
            c = apply_profile(settings(), load_profile('demo'))
            c.update(video=str(video), reference_size=[200, 200], prediction_mode='mock', output_dir=str(root / 'videos'))
            bind_video(c)
            cfg = root / 'config.json'
            save(c, cfg)
            receipts = []
            class CheckReceipt:
                def send(inner, envelope):
                    # Sender can only see rows after BOTH CSVs have been flushed.
                    reference = envelope['csv_ref']
                    fields, rows = read(reference['path'])
                    csv_row = rows[reference['row_number_at_write'] - 1]
                    expected = {k: '' if value is None else str(value) for k, value in envelope['csv_row'].items()}
                    if fields != USAGE_FIELDS or csv_row != expected or expected not in read(reference['source_csv'])[1]:
                        raise AssertionError('CSV and recipient differ or unflushed.')
                    receipts.append(envelope)
                    return {'record_id': envelope['record_id'], 'acknowledged': True}
            output = StreamOutput(root / 'bundle', c, CheckReceipt())
            with patch('cctv.pipeline.Detector', FakeDetector):
                run = analyze(cfg, record_output=output)
            stats = output.close()
            summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual((stats['generated'], stats['stored'], stats['delivery']['acknowledged']), (2, 2, 2))
            self.assertEqual(summary['processed_frames'], 25)
            self.assertEqual(summary['remainder']['duration_s'], .5)
            self.assertEqual([e['interval_end_s'] for e in receipts], [1, 2])
            self.assertTrue(all(e['source_time_s'] <= e['interval_end_s'] for e in receipts))
            self.assertEqual(len({e['record_id'] for e in receipts}), 2)


if __name__ == '__main__':
    unittest.main()
