"""Durable delivery-only outbox. No prediction model or external client is built in."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import sqlite3
import threading
import time
from typing import Protocol


class Receiver(Protocol):
    def send(self, envelope: dict) -> dict:
        """Return {record_id, acknowledged: True}; this is NOT a prediction result.

        Future clients must set their own bounded I/O timeout and deduplicate by
        record_id. Receipt may be lost after acceptance; retries can be duplicates.
        """


class MockReceiver:
    def __init__(self, path, delay_s=0):
        self.path = Path(path)
        self.delay_s = delay_s

    def send(self, envelope):
        if self.delay_s:
            # Only the delivery worker waits. Analysis never sleeps for video time.
            threading.Event().wait(self.delay_s)
        received = {'record_id': envelope['record_id'],
                    'received_at': datetime.now(timezone.utc).isoformat(),
                    'delivery_acknowledged': True, 'prediction_performed': False,
                    'envelope': envelope}
        with self.path.open('a', encoding='utf-8', newline='') as f:
            f.write(json.dumps(received, ensure_ascii=False) + '\n')
            f.flush()
            os.fsync(f.fileno())
        return {'record_id': envelope['record_id'], 'acknowledged': True}


class _WorkerLock:
    """OS lock is automatically released on process exit, including crashes."""
    def __init__(self, path):
        self.file = Path(path).open('a+b')
        self.file.seek(0)
        if not self.file.read(1):
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('An outbox worker already owns this database; retry after it exits.')

    def close(self):
        self.file.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()


def _connect(path):
    connection = sqlite3.connect(str(path), timeout=2, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('PRAGMA synchronous=FULL')
    connection.execute('PRAGMA busy_timeout=2000')
    return connection


class DeliveryWorker:
    """SQLite is the durable queue; RAM contains at most N wake-up record IDs.

    SQLite claims/commits are short. Receiver calls always run outside transactions
    in one daemon worker. A blocking receiver cannot hold analysis at shutdown
    beyond shutdown_timeout_s; unfinished payloads remain in the outbox.
    """
    def __init__(self, path, options, receiver=None, retry_failed=False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.options = dict(options)
        self.lock = _WorkerLock(self.path.with_suffix('.worker.lock'))
        try:
            self.db = _connect(self.path)
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS records (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL UNIQUE, envelope TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                    cycle_attempts INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL, next_attempt_at REAL NOT NULL,
                    acknowledged_at REAL, last_error TEXT);
                CREATE INDEX IF NOT EXISTS ready_records ON records(status, next_attempt_at, seq);
                CREATE TABLE IF NOT EXISTS attempts (
                    record_id TEXT NOT NULL, number INTEGER NOT NULL,
                    started_at REAL NOT NULL, finished_at REAL,
                    acknowledged INTEGER NOT NULL DEFAULT 0, error TEXT,
                    PRIMARY KEY(record_id, number));
            ''')
            now = time.time()
            self.db.execute("UPDATE attempts SET finished_at=?, error='interrupted_before_local_ack' WHERE finished_at IS NULL", (now,))
            self.db.execute("UPDATE records SET status='pending', next_attempt_at=? WHERE status='inflight'", (now,))
            self.db.execute("UPDATE records SET status='failed' WHERE status='pending' AND cycle_attempts>=?", (options['max_attempts'],))
            if retry_failed:
                self.db.execute("UPDATE records SET status='pending', cycle_attempts=0, next_attempt_at=? WHERE status='failed'", (now,))
        except BaseException:
            self.lock.close()
            raise
        self.receiver = receiver if receiver is not None else MockReceiver(
            self.path.parent / 'mock_received.jsonl', options['mock_delay_s'])
        self.signals = queue.Queue(maxsize=options['queue_capacity'])
        self.closing = threading.Event()
        self.deadline = None
        self.session_started = time.time()
        self.max_memory_queue_depth = 0
        self.queue_full_events = 0
        self.max_pending_records = self._pending(self.db)
        self.error = None
        self.closed = False
        self.final_stats = None
        self.thread = threading.Thread(target=self._loop, name='cctv-outbox', daemon=True)
        self.thread.start()

    @staticmethod
    def _pending(db):
        return db.execute("SELECT count(*) FROM records WHERE status IN ('pending','inflight')").fetchone()[0]

    def enqueue(self, serialized_envelope):
        if self.closed:
            raise RuntimeError('Outbox is already closed.')
        envelope = json.loads(serialized_envelope)
        rid = envelope['record_id']
        existing = self.db.execute('SELECT envelope FROM records WHERE record_id=?', (rid,)).fetchone()
        if existing:
            if existing['envelope'] != serialized_envelope:
                raise ValueError('Same record_id was reused with different content.')
            return False
        now = time.time()
        self.db.execute('INSERT INTO records(record_id,envelope,created_at,next_attempt_at) VALUES(?,?,?,?)',
                        (rid, serialized_envelope, now, now))
        self.max_pending_records = max(self.max_pending_records, self._pending(self.db))
        try:
            self.signals.put_nowait(rid)
            self.max_memory_queue_depth = max(self.max_memory_queue_depth, self.signals.qsize())
        except queue.Full:
            # The record is committed in SQLite. Only a redundant wake-up is omitted.
            self.queue_full_events += 1
        return True

    def _claim(self, db):
        db.execute('BEGIN IMMEDIATE')
        try:
            row = db.execute("SELECT * FROM records WHERE status='pending' AND cycle_attempts<? AND next_attempt_at<=? ORDER BY seq LIMIT 1",
                             (self.options['max_attempts'], time.time())).fetchone()
            if row:
                db.execute("UPDATE records SET status='inflight', attempts=attempts+1, cycle_attempts=cycle_attempts+1 WHERE record_id=?", (row['record_id'],))
                db.execute('INSERT INTO attempts(record_id,number,started_at) VALUES(?,?,?)',
                           (row['record_id'], row['attempts'] + 1, time.time()))
            db.execute('COMMIT')
            return row
        except BaseException:
            db.execute('ROLLBACK')
            raise

    def _send(self, db, row):
        rid, error = row['record_id'], None
        try:
            # Fresh JSON objects prevent receivers from mutating saved/retried data.
            receipt = self.receiver.send(json.loads(row['envelope']))
            if not isinstance(receipt, dict) or receipt.get('acknowledged') is not True or receipt.get('record_id') != rid:
                raise ValueError('Receiver did not confirm this record_id.')
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        now = time.time()
        db.execute('BEGIN IMMEDIATE')
        try:
            db.execute('UPDATE attempts SET finished_at=?,acknowledged=?,error=? WHERE record_id=? AND number=?',
                       (now, int(error is None), error, rid, row['attempts'] + 1))
            if error is None:
                db.execute("UPDATE records SET status='acknowledged', acknowledged_at=?,last_error=NULL WHERE record_id=?", (now, rid))
            else:
                status = 'failed' if row['cycle_attempts'] + 1 >= self.options['max_attempts'] else 'pending'
                db.execute('UPDATE records SET status=?, next_attempt_at=?, last_error=? WHERE record_id=?',
                           (status, now + self.options['retry_delay_s'], error, rid))
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            raise

    def _loop(self):
        db = None
        try:
            db = _connect(self.path)
            while True:
                if self.closing.is_set() and (time.monotonic() >= self.deadline or self._pending(db) == 0):
                    break
                try:
                    self.signals.get_nowait()
                except queue.Empty:
                    pass
                row = self._claim(db)
                if row:
                    self._send(db, row)
                else:
                    try:
                        self.signals.get(timeout=.02)
                    except queue.Empty:
                        pass
        except BaseException as exc:
            self.error = f'{type(exc).__name__}: {exc}'
        finally:
            if db is not None:
                db.close()
            self.lock.close()

    def stats(self):
        if self.final_stats is not None:
            return dict(self.final_stats)
        counts = {r['status']: r['n'] for r in self.db.execute('SELECT status,count(*) n FROM records GROUP BY status')}
        attempts = self.db.execute('SELECT count(*) n, sum(acknowledged) ack, sum(CASE WHEN finished_at IS NOT NULL AND acknowledged=0 THEN 1 ELSE 0 END) failures FROM attempts').fetchone()
        delays = self.db.execute('SELECT max(acknowledged_at-created_at) maximum, avg(acknowledged_at-created_at) average FROM records WHERE acknowledged_at IS NOT NULL').fetchone()
        oldest = self.db.execute("SELECT min(created_at) FROM records WHERE status IN ('pending','inflight','failed')").fetchone()[0]
        attempted_records = self.db.execute('SELECT count(*) FROM records WHERE attempts>0').fetchone()[0]
        return {'outbox': str(self.path), 'attempts': attempts['n'], 'confirmed_attempts': attempts['ack'] or 0,
                'attempted_records': attempted_records,
                'failed_attempts': attempts['failures'] or 0, 'acknowledged': counts.get('acknowledged', 0),
                'pending': counts.get('pending', 0), 'inflight': counts.get('inflight', 0), 'failed': counts.get('failed', 0),
                'unacknowledged': sum(counts.get(k, 0) for k in ('pending', 'inflight', 'failed')),
                'records': sum(counts.values()), 'max_pending_records': self.max_pending_records,
                'max_memory_queue_depth': self.max_memory_queue_depth, 'queue_capacity': self.options['queue_capacity'],
                'queue_full_events': self.queue_full_events,
                'max_delivery_delay_s': max(0, delays['maximum']) if delays['maximum'] is not None else None,
                'mean_delivery_delay_s': max(0, delays['average']) if delays['average'] is not None else None,
                'oldest_unacknowledged_age_s': max(0, time.time() - oldest) if oldest is not None else 0,
                'worker_alive': self.thread.is_alive(), 'worker_error': self.error,
                'prediction_performed': False}

    def close(self):
        if not self.closed:
            self.closed = True
            self.deadline = time.monotonic() + self.options['shutdown_timeout_s']
            self.closing.set()
            self.thread.join(timeout=self.options['shutdown_timeout_s'])
            self.final_stats = self.stats()
            self.db.close()
        return self.stats()
