"""Local single-job API. Workers never import/call Streamlit; no HTTP server."""
import atexit
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import multiprocessing as mp
from pathlib import Path
import queue
import sqlite3
import threading
import time
import uuid

TERMINAL = {'completed', 'stopped', 'failed', 'force_terminated'}
_gate = threading.RLock()
_live_job = None


class BusyError(RuntimeError):
    pass


class OwnershipError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _atomic(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    for attempt in range(6):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 5:
                temporary.unlink(missing_ok=True)
                raise
            time.sleep(.005)  # Bounded Windows reader/replace contention, not input pacing.


def _save_state(folder, state):
    """WAL avoids Windows JSON replace/read-handle contention during UI polling."""
    connection = sqlite3.connect(Path(folder) / 'job_state.sqlite3', timeout=2)
    try:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE IF NOT EXISTS current_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        connection.execute('INSERT OR REPLACE INTO current_state VALUES (1, ?)',
                           (json.dumps(state, ensure_ascii=False, allow_nan=False),))
        connection.commit()
    finally:
        connection.close()


def _read_state(folder):
    connection = sqlite3.connect(Path(folder) / 'job_state.sqlite3', timeout=2)
    try:
        return json.loads(connection.execute('SELECT payload FROM current_state WHERE id=1').fetchone()[0])
    finally:
        connection.close()


@dataclass(frozen=True)
class RecordBatch:
    records: tuple
    next_cursor: int
    done: bool
    incomplete_tail: bool = False


def _worker(options, folder, stop_event, notifications):
    import contextlib
    import traceback
    from .config import load, preset_path, validate
    from .profiles import apply_profile, load_profile
    from .pipeline import analyze
    from .lifecycle import check_stop, AnalysisStopped
    folder = Path(folder)
    state = {'job_id': folder.name, 'status': 'preparing', 'phase': 'configuration',
             'requested_device': options['device'], 'runtime_device': None, 'run_dir': None,
             'processed_frames': 0, 'progress': None, 'latest_record': None,
             'error': None, 'notification_coalesced': 0, 'updated_at': _now()}
    last_publish = 0
    lock = threading.RLock()

    def publish(force=False):
        nonlocal last_publish
        now = time.perf_counter()
        if not force and now - last_publish < .5:
            return
        with lock:
            state['updated_at'] = _now()
            _save_state(folder, state)
            try:
                notifications.put_nowait(1)  # Signals only. All records remain in StreamOutput's journal.
            except queue.Full:
                state['notification_coalesced'] += 1
            last_publish = now

    finished = threading.Event()
    def monitor_parent():
        parent = mp.parent_process()
        while not finished.wait(1):
            if parent is not None and not parent.is_alive():
                stop_event.set()
                return  # Cooperative checks; hard parent death cannot guarantee final file cleanup.
    threading.Thread(target=monitor_parent, daemon=True).start()
    with (folder / 'worker.log').open('x', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            publish(True)
            check_stop(stop_event)
            config_path = options['config_path'] or str(preset_path(options['restroom_id']))
            config = apply_profile(load(config_path), load_profile(options['profile']))
            if config['restroom_id'] != options['restroom_id']:
                raise ValueError('Selected restroom and configuration restroom_id differ.')
            for key, override in [('video', options['video_path']), ('model', options['model_path'])]:
                if override is not None:
                    config[key] = override
                if not Path(config[key]).is_file():
                    raise FileNotFoundError(f'Missing {key}: {config[key]}. Specify {key}_path or the corresponding CLI option.')
            config.update(output_dir=str(folder / 'analysis'), prediction_mode='disabled', device=options['device'])
            config['cache_dir'] = str(folder / '.cache')
            if options['video_path'] is not None:
                from .usage import bind_video
                bind_video(config)  # New video identity in the run copy; never overwrite source masks/config.
            validate(config)
            check_stop(stop_event)

            def progress(update):
                phase_changed = state['phase'] != update['phase']
                state.update(update)
                state['status'] = 'running' if update['phase'] == 'running' else 'preparing'
                info = update.get('input_video')
                if info:
                    import math
                    begin = math.ceil(options['start'] * info['fps'] - 1e-8)
                    end = math.ceil(min(options['end'] or info['duration_s'], info['duration_s']) * info['fps'] - 1e-8)
                    expected = max(0, end - begin)
                    state['expected_frames'] = expected
                    state['progress'] = min(1., update['processed_frames'] / expected) if expected else None
                publish(phase_changed)

            def record(serialized):
                state['latest_record'] = json.loads(serialized)
                state['run_id'] = state['latest_record']['run_id']
                publish(True)

            out = analyze(config_path, start=options['start'], end=options['end'], device=options['device'],
                          config_override=config, output_base=folder / 'analysis', save_video=options['save_video'],
                          stop_event=stop_event, progress_sink=progress, record_sink=record)
            summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            state.update(status=summary['status'], phase=summary['status'], run_dir=str(out),
                         processed_frames=summary['processed_frames'], runtime_device=summary.get('runtime_device'),
                         csv_files=summary.get('stream_output', {}).get('csv_files', []),
                         final_state=summary.get('final_state'), remainder=summary.get('remainder'))
            if state['status'] == 'completed':
                state['progress'] = 1.
        except AnalysisStopped:
            state.update(status='stopped', phase='stopped')
        except BaseException as exc:
            state.update(status='failed', phase='failed', error=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
        finally:
            finished.set()
            publish(True)
            _atomic(folder / 'job.json', state)  # Human-readable final snapshot; live reads use SQLite.
            notifications.cancel_join_thread()


class AnalysisJob:
    """A process handle; latest is replaceable, record batches are journal cursors."""
    def __init__(self, folder, options):
        self.folder = Path(folder)
        self.options = options
        ctx = mp.get_context('spawn')
        self._stop = ctx.Event()
        self._notifications = ctx.Queue(maxsize=8)
        self._process = ctx.Process(target=_worker, args=(options, str(folder), self._stop, self._notifications))
        self._stop_lock = threading.Lock()
        self._stop_thread = None
        _save_state(self.folder, {'job_id': self.folder.name, 'status': 'preparing',
                'phase': 'spawning', 'run_dir': None, 'processed_frames': 0, 'latest_record': None,
                'progress': None, 'runtime_device': None, 'error': None, 'updated_at': _now()})
        self._process.start()

    @property
    def alive(self):
        return self._process.is_alive()

    def status(self):
        while True:
            try:
                self._notifications.get_nowait()
            except queue.Empty:
                break
        state = _read_state(self.folder)
        if not self.alive and state['status'] not in TERMINAL:
            state.update(status='failed', error=f'Worker exited without final status (exitcode={self._process.exitcode}); inspect CSV/journal tail.')
        elif self._stop.is_set() and state['status'] not in TERMINAL:
            state['status'] = 'stopping'
        state.update(job_dir=str(self.folder), worker_pid=self._process.pid, worker_alive=self.alive)
        return state

    def latest(self):
        return self.status().get('latest_record')

    def read_records(self, cursor=0, limit=100):
        if type(cursor) is not int or cursor < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Use a nonnegative byte cursor and limit between 1 and 1000.')
        status = self.status()
        run = status.get('run_dir')
        journal = Path(run) / 'record_index.jsonl' if run else None
        values, position, partial, eof = [], cursor, False, True
        if journal is not None and journal.exists():
            with journal.open('rb') as handle:
                handle.seek(cursor)
                for _ in range(limit):
                    line = handle.readline()
                    if not line:
                        break
                    if not line.endswith(b'\n'):
                        partial = True
                        break
                    values.append(json.loads(line))
                    position = handle.tell()
                eof = handle.read(1) == b''
        return RecordBatch(tuple(values), position, not self.alive and (eof or partial), partial)

    def records(self, cursor=0, poll_interval=.1):
        if poll_interval <= 0:
            raise ValueError('poll_interval must be positive.')
        while True:
            batch = self.read_records(cursor)
            yield from batch.records
            cursor = batch.next_cursor
            if batch.done:
                return
            time.sleep(poll_interval)  # Consumer polling only; never paces or blocks analysis.

    def stop(self, timeout=10., wait=True):
        if timeout < 0:
            raise ValueError('timeout must be nonnegative.')
        self._stop.set()
        def finish():
            with self._stop_lock:
                self._process.join(timeout)
                if self.alive:
                    self._process.terminate()
                    self._process.join(3)
                    state = _read_state(self.folder)
                    state.update(status='force_terminated', phase='force_terminated', updated_at=_now(),
                                 error='Stop timeout; process terminated. CSV/journal/video tail may be incomplete.')
                    _save_state(self.folder, state)
                    _atomic(self.folder / 'job.json', state)
        if wait:
            finish()
        elif self._stop_thread is None or not self._stop_thread.is_alive():
            self._stop_thread = threading.Thread(target=finish, daemon=True)
            self._stop_thread.start()
        return self.status()


class AnalysisService:
    """Share ONE instance across Streamlit sessions with st.cache_resource.

    Scope: one Python server process. This is local ownership coordination,
    not authentication, a multi-host scheduler or a CCTV streaming service.
    """
    def __init__(self, lease_seconds=None, stop_timeout=10.):
        if lease_seconds is not None and lease_seconds <= 0:
            raise ValueError('lease_seconds must be positive or None.')
        self.lease_seconds, self.stop_timeout = lease_seconds, stop_timeout
        self._job, self._owner, self._heartbeat = None, None, 0
        self._closed = threading.Event()
        self._watcher = threading.Thread(target=self._watch, daemon=True)
        self._watcher.start()
        atexit.register(self.close)

    def start(self, *, owner, restroom_id, output_dir, config_path=None, video_path=None,
              model_path=None, profile='operating', device='cpu', start=0., end=None, save_video=False):
        global _live_job
        if not isinstance(owner, str) or not owner:
            raise ValueError('An owner identifier is required.')
        if restroom_id not in ('north', 'south', 'east'):
            raise ValueError('Select north, south or east.')
        def absolute(path):
            return str(Path(path).expanduser().resolve()) if path is not None else None
        options = dict(restroom_id=restroom_id, config_path=absolute(config_path), video_path=absolute(video_path),
                       model_path=absolute(model_path), profile=profile if profile in ('demo', 'operating') else absolute(profile),
                       device=device, start=start, end=end, save_video=save_video)
        with _gate:
            if self._closed.is_set():
                raise RuntimeError('Service is closed.')
            if _live_job is not None and _live_job.alive:
                raise BusyError('An analysis is already running; wait for completion or owner stop.')
            folder = Path(output_dir).expanduser().resolve() / ('job_' + uuid.uuid4().hex)
            folder.mkdir(parents=True, exist_ok=False)
            _atomic(folder / 'request.json', options)
            self._job = AnalysisJob(folder, options)
            self._owner, self._heartbeat = owner, time.monotonic()
            _live_job = self._job
            return self._job

    def status(self, owner=None):
        with _gate:
            if owner == self._owner:
                self._heartbeat = time.monotonic()
            if self._job is None:
                return {'status': 'idle', 'owned_by_session': False}
            return {**self._job.status(), 'owned_by_session': owner == self._owner}

    def job(self, owner):
        if self._job is None or owner != self._owner:
            raise OwnershipError('Only the session that started this job may control it.')
        return self._job

    def stop(self, owner, wait=False):
        return self.job(owner).stop(self.stop_timeout, wait)

    def _watch(self):
        while not self._closed.wait(1):
            with _gate:
                expired = (self.lease_seconds is not None and self._job is not None and self._job.alive
                           and time.monotonic() - self._heartbeat > self.lease_seconds)
                job = self._job
            if expired:
                job.stop(self.stop_timeout, wait=False)

    def close(self):
        self._closed.set()
        if self._job is not None and self._job.alive:
            self._job.stop(self.stop_timeout)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
