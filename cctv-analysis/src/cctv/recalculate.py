"""Rebuild demo summaries from immutable tracker logs; render only changed videos."""
import argparse
import csv
import io
import json
from pathlib import Path
import shutil
import sys
import time
from .config import load, clone, resolve, validate
from .core import Counter, Observation, SecondSampler
from .intervals import IntervalSampler, IntervalCSVWriter, DailyCSVWriter
from .media import unique_dir, write_json, verify_output
from .panel import geometry
from .pipeline import EVENT_FIELDS, TIME_FIELDS
from .profiles import apply_profile, load_profile
from .rerender import canonical, digest, log_frames, replay, source_runs
from .usage import usage_row
from .stream_output import StreamOutput
from .output_config import output_settings

DEPENDENT = {'inside_estimate', 'internal_waiting_estimate', 'current_waiting_estimate',
             'total_queue_estimate', 'available_stalls_estimate', 'expected_wait_s', 'measurement_status'}


def recalculate_run(source, target, daily, profile):
    begun = time.perf_counter()
    old, old_config = load(source / 'summary.json'), load(source / 'config_used.json')
    config = apply_profile(old_config, profile)
    config.update(prediction_mode='disabled', csv_split_interval_s=3600)
    config.update(output_settings(config))
    validate(config)
    if old['processed_frames'] != old['input_video']['frame_count'] or old['actual_start_s'] != 0:
        raise ValueError('A full source run beginning at frame zero is required.')
    target.mkdir(parents=True, exist_ok=False)
    write_json(target / 'config_used.json', config)
    width, height, fps = (old['input_video'][k] for k in ('width', 'height', 'fps'))
    details = [json.loads(line) for line in (source / 'interval_details.jsonl').read_text(encoding='utf-8').splitlines()]
    checkpoints = {d['state']['frame_index']: d['state'] for d in details}
    checkpoints[old['processed_frames'] - 1] = old['final_state']
    counter = Counter(config, width, height)
    writer = IntervalCSVWriter(target, config)
    def persist(row, detail):
        writer.write(row, detail)
        if isinstance(daily, StreamOutput):
            daily.write(row, detail, config, source_csv=target / 'usage_summary.csv')
        else:
            daily.add(row)  # Legacy caller compatibility.
    sampler = IntervalSampler(config, 0, persist)
    seconds = SecondSampler(0)
    generated_events, count, diagnostics_identical = [], 0, True
    try:
        with (target / 'timeseries.csv').open('w', encoding='utf-8-sig', newline='') as time_file, \
             (target / 'diagnostics.jsonl').open('w', encoding='utf-8') as diagnostic_file:
            series = csv.DictWriter(time_file, TIME_FIELDS, extrasaction='ignore')
            series.writeheader()
            for index, records in log_frames(source / 'diagnostics.jsonl'):
                if index != count:
                    raise ValueError('Non-contiguous original tracker log.')
                markers = [r for r in records if r['kind'] == 'detector_boxes']
                if len(markers) != 1 or abs(markers[0]['video_time_s'] - index / fps) > 1e-9:
                    raise ValueError('Source frame marker/time mismatch.')
                observations = [Observation(r['track_id'], tuple(r['box']), r['confidence'])
                                for r in records if r['kind'] in ('observation', 'excluded_observation')]
                state, events, logs = counter.update(index / fps, index, observations)
                expected = [{k: v for k, v in r.items() if k not in ('restroom_id', 'frame_index')}
                            for r in records if r['kind'] != 'detector_boxes']
                # This run changes only initial-inside-dependent values, never tracking/events/waiting.
                independent = lambda values: [r for r in values if r['kind'] != 'negative_inside']
                if canonical(independent(logs)) != canonical(independent(expected)):
                    raise ValueError(f'{config["restroom_id"]} frame {index}: diagnostic/event mismatch.')
                diagnostics_identical &= canonical(logs) == canonical(expected)
                for record in [*markers, *logs]:
                    diagnostic_file.write(json.dumps({'restroom_id': config['restroom_id'],
                                          'frame_index': index, **record}, ensure_ascii=False) + '\n')
                if index in checkpoints:
                    before = {k: v for k, v in checkpoints[index].items() if k not in DEPENDENT}
                    after = {k: v for k, v in state.items() if k not in DEPENDENT}
                    if before != after:
                        raise ValueError('Entry/exit/external waiting/source timing changed.')
                generated_events.extend(events)
                series.writerows(seconds.push(state))
                sampler.push(state, events)
                count += 1
            remainder = sampler.finish(old['analysis_coverage_end_s'])
    finally:
        writer.close()
    independent_anomalies = lambda values: {k: v for k, v in values.items() if k != 'negative_inside_transitions'}
    if count != old['processed_frames'] or independent_anomalies(counter.anomalies) != independent_anomalies(old['anomalies']):
        raise ValueError('Log coverage or anomaly policy changed.')
    event_buffer = io.StringIO(newline='')
    event_writer = csv.DictWriter(event_buffer, EVENT_FIELDS, extrasaction='ignore')
    event_writer.writeheader()
    event_writer.writerows(generated_events)
    with (source / 'events.csv').open(encoding='utf-8-sig', newline='') as f:
        expected_events = list(csv.DictReader(f))
    if list(csv.DictReader(io.StringIO(event_buffer.getvalue()))) != expected_events:
        raise ValueError('Original entry/exit event stream changed.')
    shutil.copy2(source / 'events.csv', target / 'events.csv')
    if diagnostics_identical:
        shutil.copy2(source / 'diagnostics.jsonl', target / 'diagnostics.jsonl')
    write_json(target / 'final_state.json', state)
    write_json(target / 'remainder.json', remainder)
    final = {'last_frame_usage': usage_row(config, state, 0, state['source_time_s']), 'state': state,
             'actual_start_s': 0, 'actual_last_frame_s': state['source_time_s'],
             'available_stalls': config['available_stalls'], 'average_stall_use_s': config['average_stall_use_s']}
    write_json(target / 'final_usage_detail.json', final)
    summary = clone(old)
    for key in ('output_video', 'stream_output', 'timing', 'stream_output_scope', 'delivery_shutdown_elapsed_s',
                'total_elapsed_s', 'runtime_device', 'measure_csv_latency'):
        summary.pop(key, None)
    summary.update(status='csv_completed_video_pending', initial_inside=config['initial_inside'],
                   capture_start_time=config['capture_start_time'], capture_time_kind=config['capture_time_kind'],
                   profile_name=config['profile_name'], periodic_interval_s=1, regular_csv_rows=sampler.rows,
                   final_state=state, final_usage_detail=final, remainder=remainder,
                   execution_method='recalculated_from_original_tracker_log', source_analysis_run=str(source),
                   inference_performed=False, tracker_rerun=False,
                   prediction_mode='disabled', csv_split_interval_s=3600, anomalies=counter.anomalies,
                   model_metadata_scope='source_analysis_only_no_new_inference',
                   source_analysis_elapsed_s=old.get('elapsed_s'))
    summary['elapsed_s'] = time.perf_counter() - begun
    summary['processing_fps'] = count / summary['elapsed_s']
    summary['timing_scope'] = 'tracker_log_replay_and_csv_not_inference_or_video_render'
    summary['wait_time_assumptions'].update(available_stalls=config['available_stalls'],
                                           average_stall_use_s=config['average_stall_use_s'])
    write_json(target / 'summary.json', summary)
    result = {'restroom_id': config['restroom_id'], 'status': 'prepared', 'run_dir': str(target),
              'source_run': str(source), 'processed_frames': count, 'csv_rows': sampler.rows,
              'initial_inside': config['initial_inside'], 'available_stalls': config['available_stalls'],
              'average_stall_use_s': config['average_stall_use_s'], 'events_identical': True,
              'all_frame_diagnostics_identical': diagnostics_identical,
              'non_initial_dependent_diagnostics_identical': True,
              'external_waiting_identical_at_all_checkpoints': True,
              'final_state': state, 'remainder': remainder}
    if config['restroom_id'] == 'north':
        if (source / 'usage_summary.csv').read_bytes() != (target / 'usage_summary.csv').read_bytes():
            raise ValueError('North CSV differs; cannot treat the old north result as reusable.')
        result['north_csv_identical_to_source'] = True
    return result


def prepare(source_batch, output, rooms=None):
    profile = load_profile('demo')
    daily = StreamOutput(output, {**profile['defaults'], 'prediction_mode': 'disabled', 'csv_split_interval_s': 3600})
    write_json(output / 'profile_used.json', profile)
    results, previews = [], []
    for source in source_runs(source_batch):
        config = load(source / 'config_used.json')
        if rooms is not None and config['restroom_id'] not in rooms:
            continue
        target = output / config['restroom_id']
        result = recalculate_run(source, target, daily, profile)
        results.append(result)
        previews.append(replay(target, output, preview_only=True))
        print(f'{config["restroom_id"]}: CSV {result["csv_rows"]} rows, initial {result["initial_inside"]}', flush=True)
    daily.close()
    write_json(output / 'preview_manifest.json', {'status': 'completed', 'items': previews})
    write_json(output / 'batch_summary.json', {'status': 'prepared', 'source_batch': str(source_batch),
               'profile': 'demo', 'scope': 'development_video_only', 'limit_seconds_per_video': None,
               'accuracy_evaluation': 'not_performed_no_manual_truth', 'results': results,
               'shared_csv': daily.manifest(), 'completed_count': 0, 'failed_count': 0})


def finish(output, reuse_render=None):
    batch = load(output / 'batch_summary.json')
    preview = load(output / 'preview_manifest.json')
    if load(output / 'profile_used.json') != load_profile('demo'):
        raise ValueError('Demo profile changed since CSV generation; prepare a new batch.')
    north_render = None
    if any(item['restroom_id'] == 'north' for item in batch['results']):
        if reuse_render is None:
            raise ValueError('A north render source is required only when north is included.')
        north_render = load(reuse_render / 'north' / 'render_summary.json')
    for result in batch['results']:
        render_started = time.perf_counter()
        run = Path(result['run_dir'])
        config, summary = load(run / 'config_used.json'), load(run / 'summary.json')
        if (run / 'annotated.mp4').exists():
            raise FileExistsError('Refusing to overwrite an existing video.')
        prior = next(item for item in preview['items'] if item['restroom_id'] == config['restroom_id'])
        if geometry(prior['width'], prior['height'], config) != prior['panel']:
            raise ValueError('Overlay changed after preview.')
        if config['restroom_id'] == 'north':
            source_config = load(Path(north_render['source_run']) / 'config_used.json')
            keys = ('initial_inside', 'available_stalls', 'average_stall_use_s', 'capture_start_time',
                    'capture_time_kind', 'video_id', 'video_sha256', 'rules', 'boundary', 'entry_direction',
                    'outside_zone', 'inside_zone', 'waiting_zone', 'transit_zone', 'excluded_zones')
            if any(config.get(k) != source_config.get(k) for k in keys):
                raise ValueError('North video assumptions or geometry differ.')
            if summary['final_state'] != north_render['final_state'] or prior['panel'] != north_render['panel']:
                raise ValueError('North video state or panel settings differ.')
            source = Path(north_render['video'])
            info = summary['input_video']
            verified = verify_output(source, info['width'], info['height'], info['fps'], summary['processed_frames'])
            shutil.copy2(source, run / 'annotated.mp4')
            if digest(source) != digest(run / 'annotated.mp4'):
                raise ValueError('North reused video byte comparison failed.')
            verified['path'] = str(run / 'annotated.mp4')
            summary['output_video'] = verified
            result['video_method'] = 'verified_existing_compact_video_copied'
            result['video_source'] = str(source)
        else:
            rendered = replay(run, output, preview_only=False)
            summary['output_video'] = rendered['output_video']
            result['video_method'] = 'original_video_and_tracker_log_rerender'
        summary.update(status='completed', video_method=result['video_method'],
                       render_elapsed_s=time.perf_counter() - render_started)
        result['status'] = 'completed'
        write_json(run / 'summary.json', summary)
        write_json(run / 'result.json', result)
        print(f'{config["restroom_id"]}: {result["video_method"]}', flush=True)
    batch.update(status='completed', completed_count=len(batch['results']))
    write_json(output / 'batch_summary.json', batch)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='기존 추적 로그로 demo 초기 인원 재계산·CSV·결과 영상 생성')
    parser.add_argument('--source-batch')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--reuse-render-batch')
    parser.add_argument('--rooms', nargs='+', choices=['north', 'south', 'east'],
                        help='재계산할 환경만 선택. 기본값은 원본 묶음의 세 환경')
    args = parser.parse_args()
    if args.prepare_only:
        if not args.source_batch or args.output:
            parser.error('--prepare-only requires --source-batch and creates a new output folder.')
        output = unique_dir('outputs', 'batch_demo_recalc')
        print(f'Output: {output}', flush=True)
        prepare(resolve(args.source_batch), output, args.rooms)
    else:
        if not args.output:
            parser.error('Final rendering requires --output; north also requires --reuse-render-batch.')
        finish(resolve(args.output), resolve(args.reuse_render_batch) if args.reuse_render_batch else None)


if __name__ == '__main__':
    main()
