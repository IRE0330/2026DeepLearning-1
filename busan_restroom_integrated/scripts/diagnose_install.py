"""Check the selected interpreter, metadata and spawn environment before analysis."""
import argparse
import hashlib
import importlib
import importlib.metadata as metadata
import json
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys

MODEL_SHA256 = '0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1'


def child_probe(queue):
    import cctv
    queue.put(dict(python=sys.executable, version=sys.version, package=cctv.__file__,
                   ultralytics_metadata=metadata.version('ultralytics')))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',type=Path)
    args=parser.parse_args()
    if sys.version_info[:2] != (3,13):
        raise RuntimeError('배포 검증 대상은 Python 3.13입니다. 기존 환경을 바꾸지 말고 Python 3.13으로 새 가상환경을 만드세요.')
    report=dict(python=sys.executable,version=sys.version,venv=sys.prefix!=sys.base_prefix,
                pip=subprocess.check_output([sys.executable,'-m','pip','--version'],text=True).strip())
    os.environ['YOLO_OFFLINE']='true'
    os.environ.setdefault('YOLO_CONFIG_DIR',str(Path.cwd()/'.cache/ultralytics'))
    os.environ.setdefault('MPLCONFIGDIR',str(Path.cwd()/'.cache/matplotlib'))
    for key in ['YOLO_CONFIG_DIR','MPLCONFIGDIR']:Path(os.environ[key]).mkdir(parents=True,exist_ok=True)
    report['dependencies']={}
    for distribution,module in [('busan-cctv-analysis','cctv'),('ultralytics','ultralytics'),
        ('torch','torch'),('torchvision','torchvision'),('opencv-python','cv2'),('av','av'),('lap','lap')]:
        try:
            version=metadata.version(distribution);loaded=importlib.import_module(module)
        except Exception as exc:
            raise RuntimeError(f'{distribution} 설치/메타데이터/import 확인 실패: {exc}. '
                f'현재 Python({sys.executable})의 -m pip로 wheel[analysis]를 새 환경에 설치하세요. 오류를 CSV로 대체하지 않습니다.') from exc
        report['dependencies'][distribution]=dict(version=version,module=loaded.__file__)
    ctx=mp.get_context('spawn');queue=ctx.Queue();child=ctx.Process(target=child_probe,args=(queue,))
    child.start();child.join(60)
    if child.is_alive() or child.exitcode!=0:
        raise RuntimeError('분석과 같은 spawn 자식 환경의 import 확인에 실패했습니다.')
    report['spawn_child']=queue.get(timeout=5)
    if Path(report['spawn_child']['python']).resolve()!=Path(sys.executable).resolve():
        raise RuntimeError('앱과 spawn 자식의 Python 경로가 다릅니다.')
    if args.model:
        if not args.model.is_file():
            raise RuntimeError('가중치가 없습니다. python -m cctv download-model로 준비하거나 --model에 실제 yolo11n.pt 경로를 지정하세요.')
        with args.model.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        if digest!=MODEL_SHA256:
            raise RuntimeError(f'검증된 yolo11n.pt와 해시가 다릅니다: {digest}. README의 공식 파일을 사용하세요.')
        report['model']=dict(path=str(args.model.resolve()),sha256=digest)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(f'설치 진단 실패: {exc}',file=sys.stderr);raise SystemExit(2)
