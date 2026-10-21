"""Add deployment documentation around frozen artifacts; never rebuild/replace 0.3.2."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

PKG=Path(__file__).resolve().parents[1];ROOT=PKG.parent
VERSION='0.3.2';TAG='cctv-analysis-v0.3.2'
BASE=f'https://github.com/IRE0330/2026DeepLearning-1/releases/download/{TAG}/'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(data):return hashlib.sha256(data).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verification-dir',type=Path,required=True);args=parser.parse_args()
    verification=args.verification_dir.resolve();target=PKG/'release-files';target.mkdir(exist_ok=True)
    if any(target.iterdir()):raise RuntimeError('Release files already exist; refusing to overwrite.')
    diagnosis=read(verification/'diagnostics.json')
    python=verification/'clean-venv/Scripts/python.exe'
    pip=subprocess.run([str(python),'-m','pip','check'],capture_output=True,text=True,check=True)
    assert 'No broken requirements found' in pip.stdout
    assert 'include-system-site-packages = false' in (verification/'clean-venv/pyvenv.cfg').read_text(encoding='utf-8')
    runs={room:read(verification/f'actual-runs/verification_{room}.json') for room in ['north','south','east']}
    summary=dict(version=VERSION,date='2026-10-21',host='Windows x64, same PC; new isolated directory and venv',
        python=diagnosis['version'].split()[0],device='cpu',venv_system_site_packages=False,
        dependency_versions={name:r['version'] for name,r in diagnosis['dependencies'].items()},
        pip_check='passed',ultralytics_import_and_metadata='passed',generic_spawn_same_python=True,
        missing_dependency_error_test='passed: base-only environment fails clearly, no CSV substitute',
        rooms={room:{k:r[k] for k in ['processed_frames','api_records','csv_matches_api_all_13_fields','mask_matches_stable_bundle','runtime_device']} for room,r in runs.items()},
        actual_analysis_worker_python_matches_app={room:r['worker_identity']['python']==r['python'] for room,r in runs.items()},
        source_base_commit='570c91a30a17eef438545cae4434d5ce4fced3a1',
        unverified=['macOS','Python 3.14 (excluded by Requires-Python)','other PCs','new GPU validation','three-camera simultaneous real time'])
    write(PKG/'docs/RELEASE_VERIFICATION_032.json',summary)
    expected={'busan_cctv_analysis-0.3.2-py3-none-any.whl':'d1684fe3ca58b469728f2650e81aae07ad5cadc9141471557080cbaa09778c84',
              'busan_cctv_analysis-0.3.2-handoff.zip':'198af19b58c4b9b4e5b11829a73bc67e8e02b127a727123843f75fcb55451ad2'}
    for name,h in expected.items():
        source=PKG/'dist'/name;assert digest(source.read_bytes())==h
        shutil.copyfile(source,target/name)
    examples={}
    results=target/'busan_cctv_analysis-0.3.2-example-results.zip'
    with zipfile.ZipFile(results,'w',zipfile.ZIP_DEFLATED) as z:
        for room in ['north','south','east']:
            name=f'{room}_2026-10-14_0000.csv';data=(PKG/'examples/data'/name).read_bytes()
            assert data==(ROOT/f'outputs/final/{room}/shared'/name).read_bytes()
            examples[name]=digest(data);z.writestr(name,data)
        z.writestr('README.md',(PKG/'examples/data/README.md').read_bytes())
        z.writestr('SHA256SUMS.txt',''.join(f'{h}  {name}\n' for name,h in examples.items()))
    with zipfile.ZipFile(target/'busan_cctv_analysis-0.3.2-handoff.zip') as z:
        payload={name:z.read(name) for name in z.namelist() if name!='manifest.json'}
    payload['docs/ORIGINAL_README_032.md']=payload['README.md']
    for name in ['README.md','docs/RELEASE_NOTICES.md','docs/RELEASE_NOTES_032.md','docs/RELEASE_VERIFICATION_032.json',
                 'scripts/diagnose_install.py','scripts/verify_release_install.py']:
        payload[name]=(PKG/name).read_bytes()
    manifest=dict(version=VERSION,source_base_commit=summary['source_base_commit'],frozen_wheel_unchanged=True,
                  packaging='documentation wrapper; original handoff and wheel remain immutable',
                  files={name:dict(bytes=len(data),sha256=digest(data)) for name,data in sorted(payload.items())})
    deployment=target/'busan_cctv_analysis-0.3.2-deployment.zip'
    with zipfile.ZipFile(deployment,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(payload.items()):z.writestr(name,data)
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    files={p.name:dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes()),download_url=BASE+p.name) for p in sorted(target.iterdir())}
    sums=target/'SHA256SUMS-0.3.2.txt';sums.write_text(''.join(f"{v['sha256']}  {k}\n" for k,v in files.items()),encoding='utf-8')
    files[sums.name]=dict(bytes=sums.stat().st_size,sha256=digest(sums.read_bytes()),download_url=BASE+sums.name)
    write(PKG/'docs/RELEASE_FILES_032.json',dict(version=VERSION,tag=TAG,
        release_url=f'https://github.com/IRE0330/2026DeepLearning-1/releases/tag/{TAG}',
        publication_status='Release API/page existence is authoritative; this manifest describes verified assets, not proof of publication',
        assets=files,example_csv_sha256=examples,weight=dict(filename='yolo11n.pt',directly_attached=False,
            official_url='https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt',
            sha256='0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1',
            official_download_equals_used_file=True,reason='AGPL-3.0/Enterprise obligations; whole-project redistribution license not established'),
        videos_published=False,full_outputs_published=False,experimental_accuracy_changes_included=False))
    print(json.dumps(dict(assets=len(files),bytes=sum(v['bytes'] for v in files.values()),frozen_artifacts_preserved=True)))

if __name__=='__main__':main()
