"""Run from an extracted handoff in a fresh venv using separately supplied media."""
import argparse
import csv
import importlib.metadata as metadata
import json
import math
import os
from pathlib import Path
import sys

import cctv
from cctv import AnalysisService
from cctv.config import LEGACY_ROOT, load, preset_path
from cctv.usage import USAGE_FIELDS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--materials', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    root, output = args.materials.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ['YOLO_OFFLINE'] = 'true'
    os.environ['YOLO_CONFIG_DIR'] = str(output / '.cache/ultralytics')
    os.environ['MPLCONFIGDIR'] = str(output / '.cache/matplotlib')
    Path(os.environ['YOLO_CONFIG_DIR']).mkdir(parents=True, exist_ok=True)
    Path(os.environ['MPLCONFIGDIR']).mkdir(parents=True, exist_ok=True)
    assert LEGACY_ROOT is None, 'Must use installed wheel, not repository imports'
    assert Path(cctv.__file__).is_relative_to(Path(sys.prefix))
    assert sys.prefix != sys.base_prefix
    assert 'include-system-site-packages = false' in (Path(sys.prefix) / 'pyvenv.cfg').read_text(encoding='utf-8')
    assert metadata.version('busan-cctv-analysis') == '0.3.2'
    report = {'version': '0.3.2', 'python': sys.version, 'package': cctv.__file__,
              'system_site_packages': False, 'same_pc': True, 'different_pc_verified': False,
              'device': 'cpu', 'rooms': {}}
    from importlib import import_module
    for name in ('torch', 'torchvision', 'ultralytics', 'cv2', 'av', 'lap', 'streamlit'):
        import_module(name)
    videos = {'north': '북쪽_화장실_cctv.mp4', 'south': '남쪽 화장실_cctv.mov', 'east': '동쪽_화장실_cctv.mov'}
    weights = root / 'models/yolo11n.pt'
    with AnalysisService() as service:
        for room, video in videos.items():
            # Verify both explicit API selection and the environment default.
            os.environ['CCTV_MODEL_PATH'] = str(weights)
            assert load(preset_path(room))['model'] == str(weights)
            options = {'model_path': weights} if room != 'east' else {}
            job = service.start(owner='handoff-verification', restroom_id=room,
                                video_path=root / video, output_dir=output,
                                profile='demo', device='cpu', end=3.25, **options)
            records = list(job.records())
            status = job.status()
            assert status['status'] == 'completed', status
            assert len(records) == 3
            assert [v['record_index'] for v in records] == [1, 2, 3]
            assert len({v['record_id'] for v in records}) == 3
            rows = []
            for record in records:
                assert list(record['csv_row']) == USAGE_FIELDS
                p = Path(record['csv_ref']['path'])
                assert p.read_bytes().startswith(b'\xef\xbb\xbf')
                with p.open(encoding='utf-8-sig', newline='') as handle:
                    reader = csv.DictReader(handle)
                    assert reader.fieldnames == USAGE_FIELDS
                    actual = list(reader)[record['csv_ref']['row_number_at_write'] - 1]
                assert actual == {k: '' if v is None else str(v) for k, v in record['csv_row'].items()}
                rows.append(actual)
            run = Path(status['run_dir'])
            summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
            used = json.loads((run / 'config_used.json').read_text(encoding='utf-8'))
            expected = math.ceil(3.25 * summary['input_video']['fps'] - 1e-8)
            assert status['processed_frames'] == expected
            preset = json.loads(preset_path(room).read_text(encoding='utf-8'))
            for key in ('boundary', 'entry_direction', 'outside_zone', 'inside_zone', 'waiting_zone', 'transit_zone', 'excluded_zones', 'rules'):
                assert used[key] == preset[key], key
            assert status['runtime_device']['parameter_device'] == 'cpu'
            assert status['runtime_device']['parameter_dtype'] == 'torch.float32'
            report['rooms'][room] = {'status': status['status'], 'processed_frames': expected,
                                     'csv_rows': rows, 'api_records': records,
                                     'csv_matches_api': True, 'mask_matches_preset': True,
                                     'model_selection': 'environment' if room == 'east' else 'explicit model_path',
                                     'csv_files': status['csv_files'], 'run_dir': str(run)}
            print(json.dumps({'room': room, 'frames': expected, 'records': len(records), 'csv_matches_api': True}))
        os.environ.pop('CCTV_MODEL_PATH', None)
        bad = service.start(owner='missing-model', restroom_id='north', video_path=root / videos['north'],
                            output_dir=output, profile='demo', end=1)
        assert list(bad.records()) == []
        assert bad.status()['status'] == 'failed'
        assert 'model_path' in bad.status()['error']
        report['unset_model_error'] = bad.status()['error']
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
