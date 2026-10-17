"""Run from a directory outside this repository after wheel installation."""
import argparse
import csv
import json
from pathlib import Path
import sys
import time
import cctv
from cctv import AnalysisService, BusyError, OwnershipError
from cctv.usage import USAGE_FIELDS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--materials', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--end', type=float, default=3.25)
    parser.add_argument('--skip-stop', action='store_true')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    root = args.materials
    result = {'python': sys.executable, 'package': cctv.__file__, 'cwd': str(Path.cwd()),
              'device': args.device, 'requested_end': args.end}
    with AnalysisService() as service:
        options = dict(restroom_id='north', video_path=root / '북쪽_화장실_cctv.mp4',
                       model_path=root / 'models/yolo11n.pt', output_dir=args.output,
                       profile='demo', device=args.device)
        job = service.start(owner='verification', end=args.end, **options)
        try:
            service.start(owner='another', **options)
            raise AssertionError('Duplicate start allowed')
        except BusyError:
            pass
        try:
            service.stop('another')
            raise AssertionError('Non-owner stop allowed')
        except OwnershipError:
            pass
        values = list(job.records())
        status = job.status()
        assert status['status'] == 'completed', status
        assert status['processed_frames'] == round(args.end * 24), status
        assert len(values) == int(args.end)
        assert len({v['record_id'] for v in values}) == len(values)
        for envelope in values:
            assert list(envelope['csv_row']) == USAGE_FIELDS
            with Path(envelope['csv_ref']['path']).open(encoding='utf-8-sig', newline='') as handle:
                rows = list(csv.DictReader(handle))
            actual = rows[envelope['csv_ref']['row_number_at_write'] - 1]
            assert actual == {k: '' if v is None else str(v) for k, v in envelope['csv_row'].items()}
        assert status['runtime_device']['parameter_device'] == args.device
        assert status['runtime_device']['parameter_dtype'] == 'torch.float32'
        result.update(completed=status, record_ids=[v['record_id'] for v in values], csv_matches_records=True)
        if not args.skip_stop:
            stopping = service.start(owner='stop-test', **options)
            for _ in stopping.records():
                stopping.stop(wait=True)
                break
            stopped = stopping.status()
            assert stopped['status'] == 'stopped', stopped
            assert stopped['processed_frames'] < 2524
            result['stopped'] = stopped
        missing = service.start(owner='missing-test', **{**options, 'video_path': args.output / 'not_present.mp4'})
        list(missing.records())
        assert missing.status()['status'] == 'failed'
        assert 'not_present.mp4' in missing.status()['error']
        result['missing_data'] = missing.status()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('completed', 'stopped', 'missing_data')}, ensure_ascii=False))
    print(args.output / 'verification.json')


if __name__ == '__main__':
    main()
