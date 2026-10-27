"""Read-only verification of published 0.3.3 archives against runtime source."""
import hashlib
import io
import json
from pathlib import Path
import zipfile


def normalize(value):
    return value.decode('utf-8-sig').replace('\r\n', '\n')


def main():
    module = Path(__file__).resolve().parents[1]
    deployment = module / 'deployment'
    wheel_name = 'busan_cctv_analysis-0.3.3-py3-none-any.whl'
    zip_name = 'busan_cctv_analysis-0.3.3-handoff.zip'
    hashes = dict(line.split(None, 1)[::-1] for line in
                  (deployment / 'SHA256SUMS.txt').read_text().splitlines() if line.strip())
    for name in (wheel_name, zip_name):
        assert hashlib.sha256((deployment / name).read_bytes()).hexdigest() == hashes[name]
    count = 0
    with zipfile.ZipFile(deployment / wheel_name) as wheel, zipfile.ZipFile(deployment / zip_name) as archive:
        assert archive.read('dist/' + wheel_name) == (deployment / wheel_name).read_bytes()
        for name in wheel.namelist():
            if name.startswith('cctv/') and not name.endswith('/'):
                content = wheel.read(name)
                assert normalize(content) == normalize((module / 'src' / name).read_bytes()), name
                assert normalize(content) == normalize(archive.read('src/' + name)), name
                count += 1
        profile = json.loads(wheel.read('cctv/data/configs/runtime_profiles/north_gpu_s.json'))
        assert profile['explicit_selection_only'] and profile['restroom_id'] == 'north'
        assert profile['device'] == 'cuda:0'
        assert 'crossing_continuity' not in normalize(wheel.read('cctv/core.py'))
        for room in ('north', 'south', 'east'):
            config = json.loads(wheel.read(f'cctv/data/configs/{room}.json'))
            assert config['imgsz'] == 640 and config['iou'] == .7
            assert config['model'] == '${CCTV_MODEL_PATH}'
    print(json.dumps({'version': '0.3.3', 'runtime_files_source_wheel_zip_equal_after_newline_normalization': count,
                      'hashes_match': True, 'embedded_wheel_identical': True,
                      'default_configs_preserved': True, 'inference_or_build': False}, indent=2))


if __name__ == '__main__':
    main()
