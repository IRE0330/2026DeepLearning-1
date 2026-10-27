"""Package the current wheel and reviewable source; never delete old releases."""
import hashlib
import json
from pathlib import Path
import tomllib
import zipfile

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parent


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    version = tomllib.loads((PKG / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    wheel = PKG / f'dist/busan_cctv_analysis-{version}-py3-none-any.whl'
    with zipfile.ZipFile(wheel) as archive:
        for p in (PKG / 'src/cctv').rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                assert archive.read(p.relative_to(PKG / 'src').as_posix()) == p.read_bytes(), p
    files = {}
    for folder in ('src', 'docs', 'examples', 'scripts', 'tests', 'ground_truth'):
        for p in (PKG / folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and not any(x.endswith('.egg-info') for x in p.parts) and p.suffix not in ('.pyc', '.log'):
                files[p.relative_to(PKG).as_posix()] = p
    for p in PKG.iterdir():
        if p.is_file() and (p.name in ('pyproject.toml', 'README.md') or p.name.startswith('requirements')):
            files[p.name] = p
    for p in (ROOT / 'configs').rglob('*.json'):
        key = p.relative_to(ROOT).as_posix()
        if len(p.relative_to(ROOT / 'configs').parts) == 1:
            bundled = PKG / 'src/cctv/data' / key
            assert p.read_bytes() == bundled.read_bytes(), p
        files[key] = p
    files['dist/' + wheel.name] = wheel
    manifest = {'version': version, 'source_wheel_equal': True,
                'files': {k: {'bytes': p.stat().st_size, 'sha256': digest(p)} for k, p in sorted(files.items())}}
    target = PKG / f'dist/busan_cctv_analysis-{version}-handoff.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for key, p in sorted(files.items()):
            archive.write(p, key)
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    with zipfile.ZipFile(target) as archive:
        for key, entry in manifest['files'].items():
            assert hashlib.sha256(archive.read(key)).hexdigest() == entry['sha256'], key
    print(json.dumps({'version': version, 'files': len(files), 'wheel_sha256': digest(wheel),
                      'zip_sha256': digest(target), 'source_wheel_zip_equal': True}))


if __name__ == '__main__':
    main()
