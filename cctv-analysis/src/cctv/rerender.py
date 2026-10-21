"""Render original source frames with recorded tracker observations, without inference.

Every replayed diagnostic, exported event and saved snapshot must match the source
run before this can be reported as a successful presentation-only rendering.
"""
import argparse
import csv
import hashlib
import io
from itertools import groupby
import json
from pathlib import Path
import sys
from .config import load, resolve, clone
from .core import Counter, Observation
from .media import unique_dir, write_json, frames, frame_at, image_write, verify_output
from .overlay import annotate
from .panel import settings, geometry, font_paths


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def log_frames(path):
    with path.open(encoding='utf-8') as f:
        records = (json.loads(line) for line in f)
        for index, entries in groupby(records, lambda row: row['frame_index']):
            yield index, list(entries)


def source_runs(batch):
    data = load(batch / 'batch_summary.json')
    if data['failed_count'] or len(data['results']) != 3:
        raise ValueError('A completed three-environment source batch is required.')
    return [Path(row['run_dir']) for row in data['results']]


def replay(run, output, preview_only):
    import cv2
    config, original = load(run / 'config_used.json'), load(run / 'summary.json')
    overlay = settings(config)
    config = clone(config)
    config['overlay'] = overlay
    video = resolve(config['video'])
    if video.resolve() == (run / 'annotated.mp4').resolve():
        raise ValueError('Use original video, never an annotated video.')
    if digest(video) != original['source_video_sha256']:
        raise ValueError('Source video identity differs from recorded analysis.')
    width, height, fps = (original['input_video'][key] for key in ('width', 'height', 'fps'))
    count = original['processed_frames']
    if count != original['input_video']['frame_count'] or original['actual_start_s'] != 0:
        raise ValueError('Only complete source videos starting at frame zero are supported.')
    room = config['restroom_id']
    folder = output / room
    folder.mkdir(parents=True, exist_ok=True)
    details = [json.loads(line) for line in (run / 'interval_details.jsonl').read_text(encoding='utf-8').splitlines()]
    checkpoints = {d['state']['frame_index']: d['state'] for d in details}
    checkpoints[count - 1] = original['final_state']
    peak = max(details, key=lambda d: d['state']['waiting_total'])['state']['frame_index']
    selected = sorted({0, count // 2, peak, count - 1})
    previews = []
    with (run / 'events.csv').open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        event_fields, expected_events = reader.fieldnames, list(reader)
    generated_events = []
    counter = Counter(config, width, height)
    writer = None
    target = folder / 'annotated.mp4'
    if not preview_only:
        if target.exists():
            raise FileExistsError(f'Refusing to overwrite {target}')
        writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError('Video writer unavailable.')
        decoded = iter(frames(video))
    seen = 0
    waiting_foot_overlap_frames = 0
    all_foot_overlap_frames = 0
    box = geometry(width, height, config)
    try:
        for index, records in log_frames(run / 'diagnostics.jsonl'):
            if index != seen:
                raise ValueError(f'Non-contiguous tracker log: {index}, expected {seen}')
            markers = [r for r in records if r['kind'] == 'detector_boxes']
            if len(markers) != 1 or abs(markers[0]['video_time_s'] - index / fps) > 1e-9:
                raise ValueError('Frame marker/timestamp mismatch.')
            observations = [Observation(r['track_id'], tuple(r['box']), r['confidence'])
                            for r in records if r['kind'] in ('observation', 'excluded_observation')]
            snapshot, events, logs = counter.update(index / fps, index, observations)
            expected_logs = [{k: v for k, v in r.items() if k not in ('restroom_id', 'frame_index')}
                             for r in records if r['kind'] != 'detector_boxes']
            if canonical(logs) != canonical(expected_logs):
                raise ValueError(f'{room} frame {index}: replay diagnostics differ from source.')
            if index in checkpoints and snapshot != checkpoints[index]:
                raise ValueError(f'{room} frame {index}: replay snapshot differs from source.')
            generated_events.extend(events)
            covered = [o for o in observations if box['x'] <= o.point[0] < box['x'] + box['width']
                       and box['y'] <= o.point[1] < box['y'] + box['height']]
            all_foot_overlap_frames += bool(covered)
            waiting_foot_overlap_frames += any(counter.tracks[o.track_id].wait in ('candidate', 'confirmed') for o in covered)
            if preview_only and index in selected:
                raw, source_time = frame_at(video, index / fps + 1e-7)
                if abs(source_time - index / fps) > 1e-6:
                    raise ValueError('Preview source frame mismatch.')
                image = annotate(raw, config, observations, counter, snapshot)
                name = f'preview_{index:06d}.png'
                image_write(folder / name, image)
                previews.append({'path': str((folder / name).relative_to(output)),
                                 'frame_index': index, 'time_s': index / fps, 'state': snapshot})
            if writer:
                source_index, raw = next(decoded)
                if source_index != index:
                    raise ValueError('Original frame/log alignment mismatch.')
                writer.write(annotate(raw, config, observations, counter, snapshot))
            seen += 1
            if seen % round(fps * 15) == 0:
                print(f'{room}: {seen}/{count} frames', flush=True)
        if writer and next(decoded, None) is not None:
            raise ValueError('Source video has additional unlogged frames.')
    finally:
        if writer:
            writer.release()
    if seen != count or snapshot != original['final_state'] or counter.anomalies != original['anomalies']:
        raise ValueError('Replay coverage/final state/anomaly mismatch.')
    buffer = io.StringIO(newline='')
    csv_writer = csv.DictWriter(buffer, event_fields, extrasaction='ignore')
    csv_writer.writeheader()
    csv_writer.writerows(generated_events)
    regenerated = list(csv.DictReader(io.StringIO(buffer.getvalue())))
    if regenerated != expected_events:
        raise ValueError('Replayed event stream differs from original CSV.')
    result = {'restroom_id': room, 'status': 'completed', 'mode': 'log_replay_rerender',
              'source_run': str(run), 'original_video': str(video), 'processed_frames': seen,
              'width': width, 'height': height, 'fps': fps, 'panel': box,
              'font': font_paths(), 'previews': previews,
              'all_frame_diagnostics_identical': True, 'events_identical': True,
              'recorded_snapshots_identical': True, 'final_state': snapshot,
              'source_csv': str(run / 'usage_summary.csv'), 'csv_rewritten': False,
              'detection_or_tracking_rerun': False, 'synthetic_capture_time': original['capture_time_kind'] == 'virtual',
              'accuracy_evaluation': 'not_performed_no_manual_truth',
              'waiting_foot_overlap_frames': waiting_foot_overlap_frames,
              'any_foot_overlap_frames': all_foot_overlap_frames}
    if not preview_only:
        result['output_video'] = verify_output(target, width, height, fps, seen)
        result['video'] = str(target)
    write_json(folder / ('preview_summary.json' if preview_only else 'render_summary.json'), result)
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='원본 영상·확정 추적 로그 기반 표시 전용 재렌더링')
    parser.add_argument('--source-batch', required=True)
    parser.add_argument('--preview-only', action='store_true')
    parser.add_argument('--output', help='미리보기에서 생성한 새 출력 폴더; 기존 영상 덮어쓰기 금지')
    args = parser.parse_args()
    batch = resolve(args.source_batch)
    output = resolve(args.output) if args.output else unique_dir('outputs', 'compact_overlay')
    if not args.preview_only:
        if not (output / 'preview_manifest.json').is_file():
            raise ValueError('Generate and review previews before rendering complete videos.')
        preview = load(output / 'preview_manifest.json')
        if Path(preview['source_batch']).resolve() != batch.resolve():
            raise ValueError('Preview source batch differs from render source.')
        for item in preview['items']:
            cfg = load(Path(item['source_run']) / 'config_used.json')
            if geometry(item['width'], item['height'], cfg) != item['panel']:
                raise ValueError('Overlay settings changed: regenerate and review previews.')
    print(f'Output: {output}', flush=True)
    results = []
    for run in source_runs(batch):
        results.append(replay(run, output, args.preview_only))
    write_json(output / ('preview_manifest.json' if args.preview_only else 'render_manifest.json'),
               {'status': 'completed', 'source_batch': str(batch), 'items': results})
    print('Completed: 3 environments; original counting data unchanged.', flush=True)


if __name__ == '__main__':
    main()
