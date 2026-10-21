"""Inspect measurements and compare saved GPU results, never alter counts."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from cctv.media import write_json
from cctv.timing import distribution
from cctv.usage import USAGE_FIELDS


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def read_lines(path):
    with Path(path).open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle]


def compare(run, reference):
    reference = Path(reference)
    rows, prior = read_csv(run / 'usage_summary.csv'), read_csv(reference / 'usage_summary.csv')
    changes = []
    for index, (a, b) in enumerate(zip(rows, prior), 1):
        fields = {k: [a[k], b[k]] for k in a if a[k] != b[k]}
        if fields:
            changes.append({'row': index, 'fields': fields})
    count = read_json(run / 'summary.json')['processed_frames']
    current_logs = read_lines(run / 'diagnostics.jsonl')
    prior_logs = [r for r in read_lines(reference / 'diagnostics.jsonl') if r['frame_index'] < count]
    # A full unpaced reference may be reused for a paced prefix.
    by_frame_a, by_frame_b = {}, {}
    for logs, grouped in ((current_logs, by_frame_a), (prior_logs, by_frame_b)):
        for row in logs:
            grouped.setdefault(row['frame_index'], []).append(row)
    differing = [i for i in range(count) if by_frame_a.get(i) != by_frame_b.get(i)]
    kinds = {}
    for kind in sorted({r['kind'] for r in current_logs}):
        kinds[kind] = sum([r for r in by_frame_a.get(i, []) if r['kind'] == kind] !=
                          [r for r in by_frame_b.get(i, []) if r['kind'] == kind] for i in range(count))
    events = read_csv(run / 'events.csv')
    prior_events = [r for r in read_csv(reference / 'events.csv') if int(r['frame_index']) < count]
    details_a, details_b = read_lines(run / 'interval_details.jsonl'), read_lines(reference / 'interval_details.jsonl')
    detail_changes = [i + 1 for i, (a, b) in enumerate(zip(details_a, details_b)) if a != b]
    final = read_json(run / 'final_state.json')
    config_a, config_b = read_json(run / 'config_used.json'), read_json(reference / 'config_used.json')
    settings_diff = {k: [config_a.get(k), config_b.get(k)] for k in set(config_a) | set(config_b)
                     if config_a.get(k) != config_b.get(k)}
    return {'reference': str(reference), 'compared_csv_rows': min(len(rows), len(prior)),
            'effective_config_differences': settings_diff,
            'reference_covers_all_rows': len(prior) >= len(rows), 'csv_differences': changes,
            'events_identical': events == prior_events, 'diagnostic_different_frames': len(differing),
            'diagnostic_different_frame_examples': differing[:20], 'differences_by_kind': kinds,
            'interval_detail_different_rows': detail_changes,
            'final_state_identical_if_same_coverage': final == read_json(reference / 'final_state.json')
             if count == read_json(reference / 'summary.json')['processed_frames'] else None}


def inspect(run):
    run = Path(run)
    summary, timing = read_json(run / 'summary.json'), read_json(run / 'timing_summary.json')
    latency = read_csv(run / 'csv_latency.csv')
    frames = read_csv(run / 'frame_arrivals.csv')
    rows = read_csv(run / 'usage_summary.csv')
    config = read_json(run / 'config_used.json')
    details, index = read_lines(run / 'interval_details.jsonl'), read_lines(run / 'record_index.jsonl')
    n = summary['processed_frames']
    assert len(frames) == n
    assert [int(f['frame_index']) for f in frames] == list(range(n))
    assert all(int(f['gpu_start_monotonic_ns']) >= int(f['due_monotonic_ns']) for f in frames)
    assert all(int(f['released_monotonic_ns']) >= int(f['due_monotonic_ns']) for f in frames)
    assert len(rows) == len(details) == len(index) == len(latency) == summary['regular_csv_rows']
    assert [float(r['interval_end_s']) for r in latency] == list(range(1, len(rows) + 1))
    assert len(rows) == math.floor(summary['analysis_coverage_end_s'] + 1e-9)
    assert all(int(r['flush_monotonic_ns']) >= int(r['boundary_due_monotonic_ns']) for r in latency)
    assert all(float(r['source_time_s']) <= float(r['interval_end_s']) for r in latency)
    assert [r['record_id'] for r in latency] == [r['record_id'] for r in index]
    assert len({r['record_id'] for r in index}) == len(rows)
    for i, (row, detail, measure) in enumerate(zip(rows, details, latency), 1):
        assert list(row) == USAGE_FIELDS
        assert row == read_csv(measure['csv_path'])[i - 1]
        state = detail['state']
        assert int(row['내부잔류인원_추정']) == state['inside_estimate']
        assert state['inside_estimate'] == summary['initial_inside'] + state['entries'] - state['exits']
        assert int(row['구간_입장인원']) == detail['interval_entries']
        assert int(row['구간_퇴장인원']) == detail['interval_exits']
        external = state['waiting_candidate_observed'] + state['waiting_confirmed_observed'] + state['waiting_grace']
        inside, stalls = state['inside_estimate'], config['available_stalls']
        assert external == state['waiting_total'] == int(row['외부대기인원_추정'])
        assert max(inside - stalls, 0) == state['internal_waiting_estimate'] == int(row['추정내부대기인원'])
        assert external + max(inside - stalls, 0) == state['total_queue_estimate'] == int(row['전체대기인원_추정']) == int(row['현재대기인원_추정'])
        assert max(stalls - inside, 0) == state['available_stalls_estimate'] == int(row['현재이용가능칸수_추정'])
        assert abs(state['expected_wait_s'] - (state['total_queue_estimate'] + 1) * 105 / stalls) < 1e-9
        assert float(measure['record_delay_s']) == (int(measure['flush_monotonic_ns']) - int(measure['boundary_due_monotonic_ns'])) / 1e9
        assert int(measure['csv_row_number_at_write']) == i
    shared = list((run / 'shared').glob('*.csv'))
    assert len(shared) == 1
    assert shared[0].read_bytes().count(b'\xef\xbb\xbf') == 1
    assert read_csv(shared[0]) == rows
    assert not (run / 'annotated.mp4').exists()
    assert summary['prediction_mode'] == 'disabled'
    assert summary['runtime_device']['parameter_device'] == 'cuda:0'
    assert summary['runtime_device']['parameter_dtype'] == 'torch.float32'
    events = timing['events']
    common_start = summary['input_simulation']['input_start_monotonic_ns']
    milestones = {k: v['run_elapsed_s'] for k, v in events.items()}
    backlog = [int(r['virtual_due_backlog']) for r in frames]
    lag = [float(r['frame_start_lag_s']) for r in frames]
    def slope(values):
        return statistics.linear_regression([float(r['source_time_s']) for r in frames], values).slope if len(values) > 1 else None
    return {'run_dir': str(run), 'status': summary['status'], 'frames': n, 'csv_rows': len(rows),
            'source_frames_total': summary['input_video']['frame_count'], 'source_fps': summary['input_video']['fps'],
            'coverage_end_s': summary['analysis_coverage_end_s'],
            'preparation_from_worker_analysis_entry_s': events['local_input_ready']['run_elapsed_s'],
            'common_input_origin_from_worker_entry_s': (common_start - events['execution_start']['monotonic_ns']) / 1e9,
            'milestones_run_elapsed_s': milestones, 'delay': timing['record_delay'],
            'flush_intervals': timing['flush_intervals_excluding_first'],
            'frame_start_lag': distribution(lag), 'frame_start_lag_slope_per_video_s': slope(lag),
            'virtual_due_backlog': {'first': backlog[0], 'last': backlog[-1], 'max': max(backlog),
                                    'slope_per_video_s': slope(backlog)},
            'input_summary': summary['input_simulation'], 'runtime_device': summary['runtime_device'],
            'final_state': summary['final_state'], 'all_frame_and_csv_checks_passed': True,
            'csv_path': str(shared[0]), 'latency_path': str(run / 'csv_latency.csv')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment', required=True)
    parser.add_argument('--references', help='JSON room -> reference run directory')
    args = parser.parse_args()
    root = Path(args.experiment)
    experiment = read_json(root / 'experiment_summary.json')
    references = read_json(args.references) if args.references else {}
    result = {'experiment': str(root), 'streams': {}, 'resource_max': experiment['resource_max']}
    samples = read_lines(root / 'resource_samples.jsonl')
    origins, pids = [], []
    for item in experiment['results']:
        run = Path(item['run_dir'])
        inspected = inspect(run)
        measurements = [s['streams'][item['room']] for s in samples]
        inspected['resource_samples_max'] = {
            'cuda_allocated_bytes': max(s[7] for s in measurements),
            'cuda_reserved_bytes': max(s[8] for s in measurements),
            'cuda_peak_allocated_bytes': max(s[9] for s in measurements)}
        if item['room'] in references:
            inspected['comparison'] = compare(run, references[item['room']])
        result['streams'][item['room']] = inspected
        origins.append(inspected['input_summary']['input_start_monotonic_ns'])
        pids.append(item['pid'])
    assert len(set(origins)) == 1
    assert len(set(pids)) == len(pids)
    result['common_origin_and_independent_processes_verified'] = True
    write_json(root / 'verification.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
