"""Apply updated application files while preserving recordings and local run data."""
import argparse, shutil, sqlite3, os, sys
from pathlib import Path
from datetime import datetime

def install(source,target):
    target=Path(target).expanduser().resolve()
    if not (target/'app.py').is_file():raise SystemExit(f'기존 앱을 찾지 못했습니다: {target}\n--target 옵션으로 app.py가 있는 폴더를 지정하세요.')
    db=target/'data/dashboard.sqlite'
    if db.is_file():
        with sqlite3.connect(db) as c:
            row=c.execute('SELECT status,pid FROM runs ORDER BY created DESC LIMIT 1').fetchone()
        if row and row[0] not in {'completed','failed','stopped','interrupted','force_terminated'} and row[1]:
            try:os.kill(row[1],0)
            except ProcessLookupError:pass
            else:raise SystemExit('현재 CCTV 분석이 진행 중입니다. 메인에서 분석 중지 후 업데이트를 다시 실행하세요.')
    source=Path(source)
    files=[p for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'data' not in p.relative_to(source).parts]
    backup=target/'.updates'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    for p in files:
        rel=p.relative_to(source);dest=target/rel
        if dest.is_file():
            old=backup/rel;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,old)
        dest.parent.mkdir(parents=True,exist_ok=True)
        tmp=dest.with_name(dest.name+'.update-tmp');shutil.copy2(p,tmp);tmp.replace(dest)
    print('업데이트 완료:',target)
    print('기존 영상, data/ 설정, 분석 기록을 유지했습니다.')
    print('기존 코드 백업:',backup)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',default=str(Path.home()/'Downloads/cctv032/busan_restroom_dashboard'))
    args=parser.parse_args()
    install(Path(__file__).resolve().parent/'files',args.target)
