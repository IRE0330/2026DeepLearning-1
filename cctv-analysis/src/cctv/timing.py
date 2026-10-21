"""Monotonic saved-video CSV flush measurements, separate from the 13-column CSV."""
import csv
import json
import math
from pathlib import Path
import statistics
import time
from .media import write_json

FIELDS = ['record_id', 'record_index', 'csv_path', 'csv_row_number_at_write',
          'interval_end_time', 'interval_end_s', 'video_elapsed_s', 'flush_monotonic_ns',
          'run_elapsed_s', 'processing_elapsed_s', 'since_previous_flush_s',
          'run_minus_video_s', 'processing_minus_video_s', 'source_time_s',
          'input_start_monotonic_ns', 'boundary_due_monotonic_ns', 'record_delay_s']


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * q
    lo, hi = math.floor(index), math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def distribution(values):
    return {'count': len(values), 'median_s': statistics.median(values) if values else None,
            'p95_s': percentile(values, .95), 'max_s': max(values) if values else None}


class RunTiming:
    def __init__(self, folder, started_ns, origin):
        self.folder, self.started_ns, self.origin = Path(folder), started_ns, origin
        self.events, self.rows = {}, []
        self.input_start_ns = None
        self.event_file = (self.folder / 'timing_events.jsonl').open('x', encoding='utf-8')
        self.csv_file = (self.folder / 'csv_latency.csv').open('x', encoding='utf-8-sig', newline='')
        self.writer = csv.DictWriter(self.csv_file, FIELDS)
        self.writer.writeheader()
        self.csv_file.flush()
        self.mark('execution_start', started_ns)

    def mark(self, name, at_ns=None):
        if name in self.events:
            raise ValueError(f'Duplicate timing milestone: {name}')
        at_ns = time.perf_counter_ns() if at_ns is None else at_ns
        self.events[name] = {'monotonic_ns': at_ns, 'run_elapsed_s': (at_ns - self.started_ns) / 1e9}
        self.event_file.write(json.dumps({'event': name, **self.events[name]}) + '\n')
        self.event_file.flush()

    def csv_flushed(self, row, detail, service, analysis_start_s):
        at_ns = service.last_csv_flush_ns
        first = self.events['first_frame_start']['monotonic_ns']
        video = detail['interval_end_s'] - analysis_start_s
        run = (at_ns - self.started_ns) / 1e9
        processing = (at_ns - first) / 1e9
        record = {'record_id': service.last_record_id, 'record_index': detail['record_index'],
                  'csv_path': service.last_ref['path'],
                  'csv_row_number_at_write': service.last_ref['row_number_at_write'],
                  'interval_end_time': row['촬영종료시각'], 'interval_end_s': detail['interval_end_s'],
                  'video_elapsed_s': video, 'flush_monotonic_ns': at_ns,
                  'run_elapsed_s': run, 'processing_elapsed_s': processing,
                  'since_previous_flush_s': (at_ns - self.rows[-1]['flush_monotonic_ns']) / 1e9 if self.rows else None,
                  'run_minus_video_s': run - video, 'processing_minus_video_s': processing - video}
        due = self.input_start_ns + round(video * 1e9) if self.input_start_ns is not None else None
        record.update(source_time_s=detail.get('source_time_s'), input_start_monotonic_ns=self.input_start_ns,
                      boundary_due_monotonic_ns=due,
                      record_delay_s=(at_ns - due) / 1e9 if due is not None else None)
        if due is not None and (at_ns < due or detail['source_time_s'] > detail['interval_end_s'] + 1e-9):
            raise ValueError('Early CSV flush or future source state in paced input.')
        if self.rows and at_ns < self.rows[-1]['flush_monotonic_ns']:
            raise ValueError('Monotonic CSV flush time moved backward.')
        self.writer.writerow(record)
        self.csv_file.flush()
        self.rows.append(record)

    def finish(self, frames, status):
        self.mark('analysis_end')
        self.csv_file.close()
        self.event_file.close()
        def difference(key):
            if not self.rows:
                return None
            values = [r[key] for r in self.rows]
            slope = statistics.linear_regression([r['video_elapsed_s'] for r in self.rows], values).slope if len(values) > 1 else None
            return {'first_s': values[0], 'final_s': values[-1], 'max_s': max(values), 'min_s': min(values),
                    'final_minus_first_s': values[-1] - values[0], 'slope_s_per_video_s': slope,
                    'positive_records': sum(v > 0 for v in values),
                    'upward_steps': sum(b > a for a, b in zip(values, values[1:]))}
        first = self.events.get('first_frame_start', {}).get('monotonic_ns')
        loop_end = self.events.get('processing_loop_end', {}).get('monotonic_ns')
        loop_s = (loop_end - first) / 1e9 if first is not None and loop_end is not None else None
        run_s = self.events['analysis_end']['run_elapsed_s']
        result = {'clock': 'time.perf_counter_ns_monotonic', 'origin': self.origin, 'status': status,
                  'events': self.events, 'records': len(self.rows),
                  'first_csv_run_elapsed_s': self.rows[0]['run_elapsed_s'] if self.rows else None,
                  'first_csv_processing_elapsed_s': self.rows[0]['processing_elapsed_s'] if self.rows else None,
                  'processing_loop_elapsed_s': loop_s, 'processing_loop_fps': frames / loop_s if loop_s else None,
                  'run_elapsed_s': run_s, 'run_fps': frames / run_s if run_s else None,
                  'flush_intervals_excluding_first': distribution([r['since_previous_flush_s'] for r in self.rows[1:]]),
                  'run_difference': difference('run_minus_video_s'),
                  'processing_difference': difference('processing_minus_video_s'),
                  'latency_csv': str(self.folder / 'csv_latency.csv'),
                  'flush_definition': 'immediately after shared CSV writer append/flush returns; before index/outbox; not fsync or physical-disk durability',
                  'model_preparation': 'model_ready=constructor/weights metadata; lazy CUDA backend and warmup occur during first observe and are included in loop/first CSV time',
                  'limitations': 'saved-video throughput, not live capture latency; negative signed differences preserved; no concurrent CCTV claim'}
        if self.input_start_ns is not None:
            delays = [r['record_delay_s'] for r in self.rows]
            result.update(input_start_monotonic_ns=self.input_start_ns,
                          record_delay={**distribution(delays),
                                        'first_s': delays[0] if delays else None,
                                        'last_s': delays[-1] if delays else None,
                                        'over_one_second_count': sum(d > 1 for d in delays),
                                        'over_one_second_ratio': sum(d > 1 for d in delays) / len(delays) if delays else None},
                          model_preparation='Inspection, model loading, CUDA backend warmup/synchronize finish before the common input origin; tracker is not advanced.',
                          limitations='Fixed-origin paced saved-file input emulation; no camera/network latency or manual counting accuracy verification.')
        write_json(self.folder / 'timing_summary.json', result)
        return result
