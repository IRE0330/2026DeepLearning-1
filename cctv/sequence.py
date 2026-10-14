"""Frame-number-only RGB sequence smoke/review path. No behavior rules."""
import csv
import json
import math
import time
from .config import resolve, template, validate
from .detector import Detector
from .media import unique_dir, write_json, image_write, verify_output
from .micc import numeric_files


def review_sequence(rgb, start_frame=0, count=60, preview_fps=12, device='auto'):
    import cv2
    import numpy as np
    if start_frame < 0 or count <= 0 or not math.isfinite(preview_fps) or preview_fps <= 0:
        raise ValueError('시작 프레임은 0 이상, 프레임 수와 미리보기 FPS는 양수여야 합니다.')
    source = resolve(rgb)
    if not source.is_dir():
        raise ValueError(f'RGB 폴더가 없습니다: {source}')
    files = [p for p in numeric_files(source, '.png') if int(p.stem) >= start_frame][:count]
    if not files or int(files[0].stem) != start_frame:
        raise ValueError('지정한 시작 프레임 PNG가 없습니다.')
    indices = [int(p.stem) for p in files]
    if any(b != a + 1 for a, b in zip(indices, indices[1:])):
        raise ValueError('누락된 프레임이 있어 연속 추적을 진행하지 않았습니다.')
    c = template('micc_' + source.parent.name.lower(), str(source))
    c['device'] = device
    validate(c, require_zones=False)
    out = unique_dir('outputs', c['restroom_id'] + '_sequence')
    report = {'status': 'starting', 'mode': 'rgb_sequence_tracking', 'source': str(source),
              'source_fps': None, 'time_basis': 'source_frame_number',
              'preview_fps': preview_fps, 'preview_use': 'visual_review_only_arbitrary_fps',
              'behavior_rules_applied': False, 'quantitative_metrics': None,
              'visual_review_completed': False, 'requested_frames': count, 'processed_frames': 0}
    write_json(out / 'summary.json', report)
    write_json(out / 'config_used.json', c)
    writer = None
    begun = time.perf_counter()
    failure = None
    try:
        detector = Detector(c, None)
        report['model'] = detector.metadata()
        previous, known = set(), set()
        with (out / 'diagnostics.jsonl').open('w', encoding='utf-8') as log, \
             (out / 'tracks.csv').open('w', encoding='utf-8-sig', newline='') as tracks_file:
            fields = ['source_frame_number', 'source_file', 'track_id', 'x1', 'y1', 'x2', 'y2', 'confidence']
            csv_writer = csv.DictWriter(tracks_file, fields)
            csv_writer.writeheader()
            for i, path in enumerate(files):
                frame = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError(f'이미지를 읽지 못했습니다: {path}')
                h, w = frame.shape[:2]
                if writer is None:
                    if w % 2 or h % 2:
                        raise ValueError('미리보기 출력은 짝수 해상도가 필요합니다.')
                    size = (w, h)
                    writer = cv2.VideoWriter(str(out / 'preview.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), preview_fps, size)
                    if not writer.isOpened():
                        raise RuntimeError('미리보기 영상을 열지 못했습니다.')
                if (w, h) != size:
                    raise ValueError('시퀀스 도중 해상도가 바뀌었습니다.')
                observations = detector.observe(frame)
                current = {o.track_id for o in observations}
                lifecycle = [{'kind': 'first_observed' if tid not in known else 'reobserved_same_tracker_id', 'track_id': tid}
                             for tid in sorted(current - previous)]
                lifecycle += [{'kind': 'tracker_id_not_observed', 'track_id': tid} for tid in sorted(previous - current)]
                number = int(path.stem)
                row = {'source_frame_number': number, 'source_file': path.name,
                       'detections': detector.raw_detections,
                       'tracks': [{'track_id': o.track_id, 'box': o.box, 'confidence': o.confidence} for o in observations],
                       'lifecycle': lifecycle}
                log.write(json.dumps(row) + '\n')
                for o in observations:
                    csv_writer.writerow(dict(zip(fields, [number, path.name, o.track_id, *o.box, o.confidence])))
                    x1, y1, x2, y2 = map(round, o.box)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 2)
                    cv2.putText(frame, f'ID {o.track_id} {o.confidence:.2f}', (x1, max(50, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 180, 0), 1)
                cv2.rectangle(frame, (0, 0), (w, 44), (25, 25, 25), -1)
                cv2.putText(frame, f'Frame {number} | FPS UNKNOWN | VISUAL PREVIEW ONLY', (8, 20), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
                cv2.putText(frame, 'Detection + ByteTrack; no entry/waiting/inside counts', (8, 39), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
                writer.write(frame)
                if i in {0, len(files)//4, len(files)//2, 3*len(files)//4, len(files)-1}:
                    image_write(out / f'frame_{number:06d}.jpg', frame)
                previous, known = current, known | current
                report['processed_frames'] += 1
                report['last_frame_number'] = number
                if i % 60 == 0:
                    print(f'프레임 {number} 처리 중: {out}', flush=True)
        report.update(status='completed', first_frame_number=indices[0], unique_tracker_ids=len(known),
                      requested_range_complete=len(files) == count)
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=f'{type(exc).__name__}: {exc}')
        failure = exc
    finally:
        if writer is not None:
            writer.release()
        report['elapsed_s'] = time.perf_counter() - begun
        if report['processed_frames']:
            try:
                report['output_video'] = verify_output(out / 'preview.mp4', *size, preview_fps, report['processed_frames'])
            except Exception as exc:
                report.update(status='failed_output_verification', output_verification_error=str(exc))
                failure = failure or exc
        write_json(out / 'summary.json', report)
    if failure:
        raise RuntimeError(f'시퀀스 실행 실패. 기록: {out}') from failure
    print(f'결과 폴더: {out}')
    return out
