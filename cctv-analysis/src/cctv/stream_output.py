"""The same persisted interval snapshot goes to CSV and an optional local outbox."""
from datetime import datetime, timezone
import hashlib
import json
import time
from pathlib import Path
import uuid
from .delivery import DeliveryWorker
from .intervals import HourlyCSVWriter, DailyCSVWriter
from .media import write_json
from .output_config import output_settings
from .usage import USAGE_FIELDS


def make_envelope(run_id, row, detail, config, csv_ref):
    if list(row) != USAGE_FIELDS:
        raise ValueError('Envelope CSV body must retain the exact existing 13 columns.')
    identity = [run_id, config['restroom_id'], config.get('video_id'), detail['record_index'],
                detail['interval_start_s'], detail['interval_end_s']]
    record_id = uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(identity, separators=(',', ':'))).hex
    demo = config.get('profile_name') == 'demo'
    envelope = {'schema_version': 1, 'run_id': run_id, 'record_id': record_id,
                'restroom_id': config['restroom_id'], 'video_id': config.get('video_id'),
                'interval_start_time': row['촬영시작시각'] or None,
                'interval_end_time': row['촬영종료시각'] or None,
                'interval_start_s': detail['interval_start_s'], 'interval_end_s': detail['interval_end_s'],
                'source_time_s': detail['source_time_s'], 'record_index': detail['record_index'],
                'record_interval_s': detail['record_interval_s'],
                'data_type': 'demo_assumptions' if demo else 'observed_aggregate', 'is_demo': demo,
                'capture_time_kind': config.get('capture_time_kind'),
                'capture_time_unset': not bool(row['촬영시작시각']),
                'csv_ref': csv_ref, 'csv_row': row, 'detail': detail,
                'assumptions': {k: config.get(k) for k in ('initial_inside', 'available_stalls', 'average_stall_use_s')},
                'persisted_at': datetime.now(timezone.utc).isoformat()}
    # Serialization is the ownership boundary. No live frame-state object survives.
    return json.dumps(envelope, ensure_ascii=False, allow_nan=False)


class StreamOutput:
    def __init__(self, folder, config=None, receiver=None):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.run_id = self.folder.name
        self.options = output_settings(config)
        self.partition = (HourlyCSVWriter if self.options['csv_split_interval_s'] == 3600 else DailyCSVWriter)(self.folder / 'shared')
        self.index_path = self.folder / 'record_index.jsonl'
        self.index = self.index_path.open('x', encoding='utf-8', newline='')
        self.worker = None
        try:
            if self.options['prediction_mode'] != 'disabled':
                self.worker = DeliveryWorker(self.folder / 'delivery/outbox.sqlite3', self.options['delivery'], receiver)
        except BaseException:
            self.index.close()
            raise
        self.generated = self.stored = self.queued = self.enqueue_errors = 0
        self.closed = False
        self.last_ref = None
        self.last_delivery = None
        self.last_csv_flush_ns = self.last_record_id = None
        self.last_envelope = None

    def write(self, row, detail, config, source_csv=None):
        if self.closed:
            raise RuntimeError('Output is closed.')
        if output_settings(config) != self.options:
            raise ValueError('A batch must use consistent CSV partition and prediction settings.')
        self.generated += 1
        path = self.partition.add(row)  # append + flush completes BEFORE enqueue/send
        self.last_csv_flush_ns = time.perf_counter_ns()
        self.stored += 1
        if isinstance(self.partition, HourlyCSVWriter):
            reference = dict(self.partition.last_ref)
        else:
            rows = self.partition.rows[path]
            reference = {'path': str(path), 'row_number_at_write': max(i + 1 for i, value in enumerate(rows) if value == row),
                         'assignment': 'legacy_capture_end_date_sorted', 'row_number_may_move_after_sort': True}
        reference.update(source_csv=str(source_csv) if source_csv is not None else None,
                         row_sha256=hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest())
        serialized = make_envelope(self.run_id, row, detail, config, reference)
        self.last_record_id = json.loads(serialized)['record_id']
        self.index.write(serialized + '\n')
        self.index.flush()
        self.last_envelope = serialized
        self.last_ref = reference
        if self.worker:
            try:
                if self.worker.enqueue(serialized):
                    self.queued += 1
            except Exception:
                self.enqueue_errors += 1
                raise
        return path

    def manifest(self):
        return self.partition.manifest()

    def stats(self):
        delivery = self.last_delivery if self.closed else self.worker.stats() if self.worker else None
        status = ('disabled' if delivery is None else 'worker_error' if delivery['worker_error']
                  else 'shutdown_timeout' if self.closed and delivery['worker_alive']
                  else 'unacknowledged' if delivery['unacknowledged'] else 'confirmed')
        return {'run_id': self.run_id, 'settings': self.options,
                'generated': self.generated, 'stored': self.stored, 'queued': self.queued,
                'delivery_disabled_records': self.stored if self.worker is None else 0,
                'enqueue_errors': self.enqueue_errors,
                'stored_without_outbox': max(0, self.stored - self.queued) if self.worker else 0,
                'csv_files': self.manifest(), 'record_index': str(self.index_path),
                'delivery': delivery, 'delivery_status': status, 'closed': self.closed,
                'time_basis': 'video_time_not_process_wall_clock',
                'wall_clock_arrivals_not_guaranteed_every_second': True,
                'prediction_performed': False}

    def close(self):
        if not self.closed:
            if isinstance(self.partition, HourlyCSVWriter):
                self.partition.close()
            self.index.close()
            if self.worker:
                self.last_delivery = self.worker.close()
            self.closed = True
            write_json(self.folder / 'delivery_summary.json', self.stats())
        return self.stats()


def retry_outbox(path, retry_failed=False, shutdown_timeout_s=None):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    options = output_settings()['delivery']
    if shutdown_timeout_s is not None:
        options = output_settings({'delivery': {'shutdown_timeout_s': shutdown_timeout_s}})['delivery']
    worker = DeliveryWorker(path, options, retry_failed=retry_failed)
    index = path.parent.parent / 'record_index.jsonl'
    restored, incomplete_tail = 0, False
    try:
        if index.is_file():
            # Repair the CSV/journal-flushed -> SQLite-commit crash window from the
            # saved envelope, never by recalculating values from a CSV.
            with index.open(encoding='utf-8') as f:
                while line := f.readline():
                    try:
                        json.loads(line)
                    except json.JSONDecodeError:
                        if f.read().strip():
                            raise ValueError('Corrupt record index before its final line.')
                        incomplete_tail = True
                        break
                    restored += worker.enqueue(line.rstrip('\r\n'))
    finally:
        result = worker.close()
    result.update(index_records_restored=restored, incomplete_index_tail=incomplete_tail,
                  record_index=str(index) if index.is_file() else None)
    target = path.parent / f'retry_summary_{uuid.uuid4().hex[:8]}.json'
    write_json(target, result)
    return result, target
