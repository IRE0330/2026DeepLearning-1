"""Run from outside the checkout with the installed wheel on PYTHONPATH."""
import argparse
import csv
import importlib.metadata
import json
from pathlib import Path
import sys
from cctv import AnalysisService
from cctv.core import Counter, Observation
from cctv.config import load, preset_path
from cctv.rerender import log_frames
from cctv.usage import USAGE_FIELDS, WAITING_POLICY
import cctv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--materials', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--rooms', nargs='+', choices=['north', 'south', 'east'], default=['north', 'south', 'east'])
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--end', type=float, default=6)
    args = parser.parse_args()
    assert Path(cctv.__file__).is_relative_to(args.installed.resolve()), cctv.__file__
    assert importlib.metadata.version('busan-cctv-analysis') == '0.3.2'
    videos = {'north': '북쪽_화장실_cctv.mp4', 'south': '남쪽 화장실_CCTV.mov', 'east': '동쪽_화장실_cctv.mov'}
    report = {'version': '0.3.2', 'package': cctv.__file__, 'policy': WAITING_POLICY, 'rooms': {}}
    with AnalysisService() as service:
        for room, filename in videos.items():
            if room not in args.rooms:
                continue
            assert load(preset_path(room))['rules']['waiting_confirm_s'] == 3.5
            job = service.start(owner='installed-waiting-check', restroom_id=room,
                                video_path=args.materials / filename,
                                model_path=args.materials / 'models/yolo11n.pt',
                                output_dir=args.output, device='cpu', profile='demo', start=args.start, end=args.end)
            records = list(job.records())
            status = job.status()
            assert status['status'] == 'completed', status
            assert len(records) == int(args.end - args.start)
            run = Path(status['run_dir'])
            c = load(run / 'config_used.json')
            summary = load(run / 'summary.json')
            assert summary['waiting_count_policy'] == WAITING_POLICY
            checkpoints = {r['detail']['state']['frame_index']: r for r in records}
            counter = Counter(c, *c['reference_size'])
            excluded_extinguisher = 0
            for index, logs in log_frames(run / 'diagnostics.jsonl'):
                marker, = [r for r in logs if r['kind'] == 'detector_boxes']
                obs = [Observation(r['track_id'], tuple(r['box']), r['confidence']) for r in logs
                       if r['kind'] in ('observation', 'excluded_observation')]
                state, _, _ = counter.update(marker['video_time_s'], index, obs)
                if room == 'east':
                    from cctv.geometry import in_polygon
                    for o in obs:
                        if in_polygon(counter.normalized(o.point), c['excluded_zones'][-1]):
                            assert counter.tracks[o.track_id].wait == 'nonwaiting'
                            excluded_extinguisher += 1
                assert state['waiting_total'] == state['waiting_confirmed_observed'] + state['waiting_grace']
                if index in checkpoints:
                    assert state == checkpoints[index]['detail']['state']
            for record in records:
                assert list(record['csv_row']) == USAGE_FIELDS
                with Path(record['csv_ref']['path']).open(encoding='utf-8-sig') as f:
                    rows = list(csv.DictReader(f))
                assert rows[record['csv_ref']['row_number_at_write'] - 1] == {
                    k: '' if v is None else str(v) for k, v in record['csv_row'].items()}
                assert record['csv_row']['외부대기인원_추정'] == record['detail']['state']['waiting_total']
            report['rooms'][room] = {'records': len(records), 'status': status['status'],
                'csv_detail_counter_equal': True, 'run_dir': str(run),
                'extinguisher_mask_observations_excluded': excluded_extinguisher,
                'waiting_received': [r['detail']['state']['waiting_total'] for r in records],
                'candidate_received': [r['detail']['state']['waiting_candidate_observed'] for r in records]}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'installed_api_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
