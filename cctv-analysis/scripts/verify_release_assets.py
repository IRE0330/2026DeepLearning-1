"""Verify immutable 0.3.2 artifacts against this checkout before publication."""
import hashlib
import json
from pathlib import Path
import zipfile

PKG=Path(__file__).resolve().parents[1]
FILES=PKG/'release-files'


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    manifest=json.loads((PKG/'docs/RELEASE_FILES_032.json').read_text(encoding='utf-8'))
    for name,expected in manifest['assets'].items():
        assert digest((FILES/name).read_bytes())==expected['sha256'],name
    wheel=FILES/'busan_cctv_analysis-0.3.2-py3-none-any.whl'
    with zipfile.ZipFile(wheel) as archive:
        count=0
        for name in archive.namelist():
            if not name.startswith('cctv/'):continue
            source=PKG/'src'/name
            assert source.is_file(),name
            assert source.read_bytes().replace(b'\r\n',b'\n')==archive.read(name).replace(b'\r\n',b'\n'),name
            count+=1
    with zipfile.ZipFile(FILES/'busan_cctv_analysis-0.3.2-deployment.zip') as archive:
        embedded=json.loads(archive.read('manifest.json'))
        for name,entry in embedded['files'].items():
            assert digest(archive.read(name))==entry['sha256'],name
        assert archive.read('dist/'+wheel.name)==wheel.read_bytes()
    for room in ['north','south','east']:
        name=f'{room}_2026-10-14_0000.csv'
        expected=manifest['example_csv_sha256'][name]
        assert digest((PKG/'examples/data'/name).read_bytes())==expected
    for name in manifest['assets']:
        if not name.endswith('.zip'):continue
        with zipfile.ZipFile(FILES/name) as archive:
            for entry in archive.namelist():
                path=Path(entry)
                assert not path.is_absolute() and '..' not in path.parts
                assert not any(part.lower() in {'.git','.ssh','.aws','.codex','.venv','models','outputs','reviews'} for part in path.parts),entry
                assert path.suffix.lower() not in {'.pt','.mp4','.mov','.avi','.pem','.key','.log'},entry
                assert not path.name.lower().startswith('.env'),entry
    print(json.dumps(dict(version='0.3.2',wheel_source_files_matched=count,assets_matched=len(manifest['assets']),
                         source_comparison='CRLF/LF normalized only',credentials_media_and_datasets_included=False)))


if __name__=='__main__':main()
