"""Fixed-origin saved-file input experiment. No camera or prediction client.

Each stream owns a process (including ByteTrack's process-global ID counter),
a bounded decode queue and its own output writer. One GPU semaphore serializes
inference; input clocks and queue accounting remain independent and concurrent.
"""
import csv
import json
import math
import multiprocessing as mp
from pathlib import Path
import queue
import threading
import time
import traceback

from .media import unique_dir, write_json


class InputAborted(RuntimeError):
    input_abort = True


def due_ns(origin, source_s):
    return origin + round(source_s * 1e9)


def wait_until(target_ns, stop, clock=time.perf_counter_ns):
    """Wait against a fixed deadline; late calls never move that deadline."""
    while True:
        remaining = (target_ns - clock()) / 1e9
        if remaining <= 0:
            return
        if stop.wait(min(remaining, .05)):
            raise InputAborted('Input group stopped before scheduled arrival.')


class LagGuard:
    def __init__(self, soft, sustained, hard):
        self.soft, self.sustained, self.hard = soft, sustained, hard
        self.since = None

    def check(self, lag, now_s):
        if lag > self.hard:
            return 'hard_frame_start_lag'
        if lag > self.soft:
            self.since = now_s if self.since is None else self.since
            if now_s - self.since >= self.sustained:
                return 'sustained_frame_start_lag'
        else:
            self.since = None
        return None


# Shared metrics: produced, completed, queue depth, max depth, GPU waiter,
# frame-start lag ns, virtual due backlog, allocated, reserved, peak allocated.
STRIDE = 10


class InputController:
    def __init__(self, group, slot, options):
        self.g, self.slot, self.options = group, slot, options
        self.paced = options['input_mode'] == 'paced'
        self.description = ('Fixed common-origin, original-FPS saved-file input emulation; ordered/no skipping; '
                            'bounded queue; one serialized GPU inference slot; not a camera/network test.'
                            if self.paced else 'Unpaced saved-file reference with identical pre-input warmup and analysis settings.')
        self.stop = group['stop']
        self.local_stop = threading.Event()
        self.q = queue.Queue(maxsize=options['queue_capacity'])
        self.guard = LagGuard(options['soft_lag_s'], options['sustained_lag_s'], options['hard_lag_s'])
        self.producer = None
        self.handle = None
        self.stats = {'produced_frames': 0, 'processed_frames': 0, 'max_queue_depth': 0,
                      'max_virtual_due_backlog': 0, 'max_frame_start_lag_s': 0,
                      'gpu_wait_total_s': 0, 'gpu_wait_max_s': 0, 'producer_backpressure_s': 0,
                      'early_analysis_frames': 0, 'missing_or_duplicate_frames': 0,
                      'input_mode': options['input_mode'], 'scope': 'saved_file_input_emulation',
                      'queue_capacity': options['queue_capacity'], 'gpu_inference_slots': 1,
                      'memory_bound_frames_per_stream': options['queue_capacity'] + 2,
                      'frame_bound_scope': 'source queue + pending decode + consumer; excludes model-retained arrays/tensors'}

    def metric(self, key, value):
        with self.g['metrics'].get_lock():
            self.g['metrics'][self.slot * STRIDE + key] = value

    def abort(self, reason):
        message = json.dumps({'room': self.options['room'], 'reason': reason,
                              'monotonic_ns': time.perf_counter_ns(),
                              'processed_frames': self.stats['processed_frames']}).encode()
        with self.g['reason'].get_lock():
            if not self.g['reason'].value:
                self.g['reason'].value = message[:2047]
        self.stop.set()

    def prepare(self, detector, width, height, info, out, timing):
        self.out, self.info = Path(out), info
        # Loading/warmup across processes is also bounded to one GPU operation.
        with self.g['gpu']:
            detector.warmup(width, height)
        if timing:
            timing.mark('gpu_warmup_complete')
        self.stats['local_ready_monotonic_ns'] = time.perf_counter_ns()
        self.g['barrier'].wait(timeout=180)
        if self.slot == 0:
            self.g['ready_ns'].value = time.perf_counter_ns()
            self.g['start_ns'].value = self.g['ready_ns'].value + (100_000_000 if self.paced else 0)
        self.g['barrier'].wait(timeout=30)
        self.origin = self.g['start_ns'].value
        self.stats.update(common_ready_monotonic_ns=self.g['ready_ns'].value,
                          input_start_monotonic_ns=self.origin,
                          pre_input_ready_wait_s=(self.origin - self.stats['local_ready_monotonic_ns']) / 1e9)
        if timing:
            timing.mark('local_input_ready', self.stats['local_ready_monotonic_ns'])
            timing.mark('common_input_ready', self.g['ready_ns'].value)
            timing.mark('scheduled_input_start', self.origin)
            if self.paced:
                timing.input_start_ns = self.origin
        self.handle = (self.out / 'frame_arrivals.csv').open('x', encoding='utf-8-sig', newline='')
        self.writer = csv.DictWriter(self.handle, ['frame_index', 'source_time_s', 'due_monotonic_ns',
                                    'released_monotonic_ns', 'enqueued_monotonic_ns', 'dequeued_monotonic_ns',
                                    'gpu_start_monotonic_ns', 'gpu_end_monotonic_ns', 'frame_start_lag_s',
                                    'gpu_wait_s', 'queue_depth', 'virtual_due_backlog'])
        self.writer.writeheader()
        write_json(self.out / 'input_options.json', {**self.options, **self.stats})

    def frames(self, video, fps, end):
        from .media import frames
        self.fps = fps
        self.frame_limit = min(self.info['frame_count'], math.ceil(end * fps - 1e-8) if end is not None else self.info['frame_count'])

        def put(item):
            blocked = None
            while not self.stop.is_set() and not self.local_stop.is_set():
                try:
                    if item is not None and not isinstance(item, BaseException):
                        item['enqueued'] = time.perf_counter_ns()
                    self.q.put_nowait(item)
                    if blocked is not None:
                        self.stats['producer_backpressure_s'] += (time.perf_counter_ns() - blocked) / 1e9
                    depth = self.q.qsize()
                    self.stats['max_queue_depth'] = max(self.stats['max_queue_depth'], depth)
                    self.metric(2, depth)
                    self.metric(3, self.stats['max_queue_depth'])
                    return
                except queue.Full:
                    blocked = time.perf_counter_ns() if blocked is None else blocked
                    self.local_stop.wait(.005)

        def produce():
            try:
                for index, frame in frames(video):
                    if index >= self.frame_limit or self.stop.is_set() or self.local_stop.is_set():
                        break
                    due = due_ns(self.origin, index / fps)
                    if self.paced:
                        wait_until(due, self.stop)
                    packet = {'index': index, 'frame': frame, 'due': due,
                              'released': time.perf_counter_ns()}
                    put(packet)
                    if self.stop.is_set() or self.local_stop.is_set():
                        return
                    self.stats['produced_frames'] += 1
                    self.metric(0, self.stats['produced_frames'])
                # A final CFR frame covers its duration. Gate EOF to that boundary too.
                if self.paced:
                    wait_until(due_ns(self.origin, self.frame_limit / fps), self.stop)
                put(None)
            except BaseException as exc:
                if not self.stop.is_set():
                    put(exc)
        self.producer = threading.Thread(target=produce, name='bounded-source', daemon=True)
        self.producer.start()
        expected = 0
        while True:
            if self.stop.is_set():
                raise InputAborted('Shared input stop: ' + self.g['reason'].value.decode())
            try:
                packet = self.q.get(timeout=.05)
            except queue.Empty:
                continue
            if packet is None:
                return
            if isinstance(packet, BaseException):
                raise packet
            if packet['index'] != expected:
                self.stats['missing_or_duplicate_frames'] += 1
                raise ValueError('Source sequence is not a contiguous ordered prefix.')
            expected += 1
            self.current = packet
            packet['dequeued'] = time.perf_counter_ns()
            self.metric(2, self.q.qsize())
            yield packet['index'], packet['frame']

    def observe(self, detector, frame, index, t):
        waiting = time.perf_counter_ns()
        self.metric(4, 1)
        while not self.g['gpu'].acquire(timeout=.05):
            if self.stop.is_set():
                self.metric(4, 0)
                raise InputAborted('Stopped waiting for GPU.')
        begin = time.perf_counter_ns()
        self.metric(4, 0)
        try:
            if self.stop.is_set():
                raise InputAborted('Group stopped before inference.')
            lag = (begin - self.current['due']) / 1e9
            if self.paced:
                if lag < 0:
                    self.stats['early_analysis_frames'] += 1
                    raise ValueError('Analysis began before source frame arrival.')
                reason = self.guard.check(lag, begin / 1e9)
                if reason:
                    self.abort(reason)
                    raise InputAborted(reason)
            result = detector.observe(frame)
            finish = time.perf_counter_ns()
        finally:
            self.g['gpu'].release()
        completed = self.stats['processed_frames'] + 1
        backlog = max(0, min(self.frame_limit, math.floor((finish - self.origin) / 1e9 * self.fps) + 1) - completed)
        wait = (begin - waiting) / 1e9
        self.stats.update(processed_frames=completed,
                          max_frame_start_lag_s=max(self.stats['max_frame_start_lag_s'], lag),
                          max_virtual_due_backlog=max(self.stats['max_virtual_due_backlog'], backlog),
                          gpu_wait_total_s=self.stats['gpu_wait_total_s'] + wait,
                          gpu_wait_max_s=max(self.stats['gpu_wait_max_s'], wait))
        self.writer.writerow(dict(frame_index=index, source_time_s=t, due_monotonic_ns=self.current['due'],
                                  released_monotonic_ns=self.current['released'], enqueued_monotonic_ns=self.current['enqueued'],
                                  dequeued_monotonic_ns=self.current['dequeued'], gpu_start_monotonic_ns=begin,
                                  gpu_end_monotonic_ns=finish, frame_start_lag_s=lag, gpu_wait_s=wait,
                                  queue_depth=self.q.qsize(), virtual_due_backlog=backlog))
        self.handle.flush()
        import torch
        for key, value in ((1, completed), (2, self.q.qsize()), (5, max(0, round(lag * 1e9))), (6, backlog),
                           (7, torch.cuda.memory_allocated(detector.device)),
                           (8, torch.cuda.memory_reserved(detector.device)),
                           (9, torch.cuda.max_memory_allocated(detector.device))):
            self.metric(key, value)
        return result

    def wait_boundary(self, boundary, analysis_start):
        if self.paced:
            wait_until(due_ns(self.origin, boundary - analysis_start), self.stop)

    def close(self):
        self.local_stop.set()
        if self.producer:
            self.producer.join(timeout=2)
        if self.handle:
            self.handle.close()
        self.stats.update(producer_joined=self.producer is None or not self.producer.is_alive(),
                          queued_unprocessed_frames=self.q.qsize(),
                          remaining_source_frames=max(0, getattr(self, 'frame_limit', 0) - self.stats['processed_frames']),
                          abort_reason=self.g['reason'].value.decode() or None)
        processed = self.stats['processed_frames']
        self.stats['unprocessed_source_index_range'] = [processed, self.frame_limit - 1] if hasattr(self, 'frame_limit') and processed < self.frame_limit else None
        self.stats['dequeued_but_not_completed_index'] = self.current['index'] if hasattr(self, 'current') and self.current['index'] >= processed else None
        with self.g['metrics'].get_lock():
            memory = list(self.g['metrics'])[self.slot * STRIDE + 7:self.slot * STRIDE + 10]
        self.stats['cuda_memory_bytes'] = dict(zip(('allocated', 'reserved', 'peak_allocated'), memory))
        if hasattr(self, 'out'):
            write_json(self.out / 'input_summary.json', self.stats)
        return self.stats


def _worker(entry, config, folder, group, slot, options):
    import contextlib
    from .pipeline import analyze
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'worker.log').open('x', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        result = {'room': config['restroom_id'], 'pid': mp.current_process().pid}
        try:
            out = analyze(entry['config'], end=options.get('end'), device='cuda:0', config_override=config,
                          output_base=folder, save_video=False, measure_csv_latency=True,
                          input_controller=InputController(group, slot, options))
            result.update(status='completed', run_dir=str(out))
        except BaseException as exc:
            result.update(status='failed', error=str(exc), traceback=traceback.format_exc())
            summaries = list(folder.glob('*/summary.json'))
            if summaries:
                result['run_dir'] = str(summaries[0].parent)
                result['status'] = json.loads(summaries[0].read_text(encoding='utf-8'))['status']
            if not group['stop'].is_set():
                with group['reason'].get_lock():
                    group['reason'].value = json.dumps({'room': config['restroom_id'], 'reason': str(exc)}).encode()[:2047]
                group['stop'].set()
            group['barrier'].abort()
        write_json(folder / 'result.json', result)


def run_simulation(rooms, input_mode='paced', output_dir='outputs', end=None, queue_capacity=8,
                   soft_lag_s=5., sustained_lag_s=10., hard_lag_s=15.):
    from .config import load, clone, validate
    from .profiles import load_profile, apply_profile
    if not rooms or len(set(rooms)) != len(rooms) or any(r not in ('north', 'south', 'east') for r in rooms):
        raise ValueError('Select distinct north/south/east streams.')
    if input_mode not in ('paced', 'unpaced') or queue_capacity < 1:
        raise ValueError('Invalid input mode or queue capacity.')
    if not (0 < soft_lag_s < hard_lag_s and sustained_lag_s > 0) or (end is not None and (not math.isfinite(end) or end <= 0)):
        raise ValueError('Invalid lag limits or end.')
    out = unique_dir(output_dir, ('paced_single' if len(rooms) == 1 else 'paced_concurrent') if input_mode == 'paced' else 'unpaced_reference')
    registry, profile = load('configs/video_registry.json'), load_profile('demo')
    selected = []
    for room in rooms:
        entry = next(e for e in registry['videos'] if e['restroom_id'] == room)
        c = clone(load(entry['config']))
        c.update({k: v for k, v in entry.items() if k != 'config'})
        c = apply_profile(c, profile)
        c.update(device='cuda:0', prediction_mode='disabled', csv_split_interval_s=3600)
        validate(c)
        if c['record_interval_s'] != 1:
            raise ValueError('This experiment requires demo 1-second records.')
        selected.append((entry, c))
    options = dict(input_mode=input_mode, queue_capacity=queue_capacity, soft_lag_s=soft_lag_s,
                   sustained_lag_s=sustained_lag_s, hard_lag_s=hard_lag_s, end=end)
    write_json(out / 'experiment.json', {'options': options, 'rooms': rooms, 'profile': profile,
                                       'effective_configs': [c for _, c in selected],
                                       'gpu_scheduling': 'one inference semaphore; independent processes, bounded producer queues',
                                       'scope': 'saved_file_input_emulation_not_camera_or_network',
                                       'auto_stop': 'whole group stops on sustained soft or immediate hard frame-start lag; contiguous processed prefixes preserved'})
    print(f'입력 시험 폴더: {out}', flush=True)
    ctx = mp.get_context('spawn')
    group = dict(stop=ctx.Event(), barrier=ctx.Barrier(len(rooms)), gpu=ctx.Semaphore(1),
                 ready_ns=ctx.Value('q', 0), start_ns=ctx.Value('q', 0),
                 reason=ctx.Array('c', 2048), metrics=ctx.Array('q', STRIDE * len(rooms)))
    processes = []
    for slot, (entry, c) in enumerate(selected):
        process = ctx.Process(target=_worker, args=(entry, c, str(out / c['restroom_id']), group, slot,
                                                    {**options, 'room': c['restroom_id']}))
        process.start()
        processes.append(process)
    # NVML reads device-wide counters without creating another CUDA context.
    import pynvml
    pynvml.nvmlInit()
    gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
    resource_max = {'device_used_bytes': 0, 'gpu_utilization_percent': 0}
    monitor_stop = threading.Event()

    def monitor():
        with (out / 'resource_samples.jsonl').open('x', encoding='utf-8') as handle:
            while not monitor_stop.is_set():
                memory = pynvml.nvmlDeviceGetMemoryInfo(gpu)
                utilization = pynvml.nvmlDeviceGetUtilizationRates(gpu)
                with group['metrics'].get_lock():
                    values = list(group['metrics'])
                item = {'monotonic_ns': time.perf_counter_ns(), 'common_input_start_ns': group['start_ns'].value,
                        'device_used_bytes': memory.used, 'device_total_bytes': memory.total,
                        'gpu_utilization_percent': utilization.gpu,
                        'streams': {r: values[i * STRIDE:(i + 1) * STRIDE] for i, r in enumerate(rooms)}}
                resource_max['device_used_bytes'] = max(resource_max['device_used_bytes'], memory.used)
                resource_max['gpu_utilization_percent'] = max(resource_max['gpu_utilization_percent'], utilization.gpu)
                handle.write(json.dumps(item) + '\n')
                handle.flush()
                monitor_stop.wait(.5)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        group['stop'].set()
        group['barrier'].abort()
        for process in processes:
            process.join(timeout=10)
        raise
    finally:
        monitor_stop.set()
        monitor_thread.join(timeout=3)
        pynvml.nvmlShutdown()
    results = [json.loads((out / r / 'result.json').read_text(encoding='utf-8')) if (out / r / 'result.json').exists()
               else {'room': r, 'status': 'worker_crashed', 'exitcode': p.exitcode}
               for r, p in zip(rooms, processes)]
    summary = {'status': 'completed' if all(r['status'] == 'completed' for r in results) else 'partial_or_failed',
               'results': results, 'common_ready_monotonic_ns': group['ready_ns'].value,
               'common_input_start_ns': group['start_ns'].value,
               'abort_reason': group['reason'].value.decode() or None, 'resource_max': resource_max,
               'metric_columns': ['produced', 'completed', 'queue_depth', 'max_queue_depth', 'gpu_waiter',
                                  'frame_start_lag_ns', 'virtual_due_backlog', 'cuda_allocated', 'cuda_reserved', 'cuda_peak_allocated'],
               'resource_scope': 'NVML total includes other applications; per-stream torch allocation excludes CUDA context/decoder/host memory',
               'options': options}
    write_json(out / 'experiment_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return out
