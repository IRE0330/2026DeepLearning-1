"""Actual short AnalysisService run; compare every received field with new CSV."""
import argparse
import csv
import importlib.metadata as metadata
import json
import math
import os
from pathlib import Path
import sys

# Windows venv launchers may expose the base executable to OS process tools.
# This runs in the actual AnalysisService spawn worker while its main module is
# initialized; verify sys.executable/sys.prefix/import path there, without
# modifying the installed worker, counter, or public API.
if __name__=='__mp_main__' and os.environ.get('CCTV_RELEASE_PROBE_DIR'):
    import cctv
    probe=dict(pid=os.getpid(),python=sys.executable,prefix=sys.prefix,package=cctv.__file__,
               ultralytics_metadata=metadata.version('ultralytics'))
    probe_file=Path(os.environ['CCTV_RELEASE_PROBE_DIR'])/f'worker_identity_{os.getpid()}.json'
    probe_file.write_text(json.dumps(probe,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    from cctv import AnalysisService
    import cctv
    import psutil
    from cctv.config import LEGACY_ROOT,preset_path
    from cctv.usage import USAGE_FIELDS
    parser=argparse.ArgumentParser()
    parser.add_argument('--room',required=True,choices=['north','south','east'])
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--end',type=float,default=3.25)
    args=parser.parse_args()
    if not args.video.is_file() or not args.model.is_file():
        raise RuntimeError('원본 영상 또는 가중치 파일이 없습니다. --video/--model의 실제 파일을 확인하세요.')
    assert LEGACY_ROOT is None,'저장소 밖 별도 폴더에서 설치 wheel을 검증하세요.'
    assert Path(cctv.__file__).is_relative_to(Path(sys.prefix)),'현재 Python의 설치 패키지가 아닙니다.'
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    os.environ['YOLO_OFFLINE']='true';os.environ['YOLO_CONFIG_DIR']=str(out/'.cache/ultralytics')
    os.environ['MPLCONFIGDIR']=str(out/'.cache/matplotlib')
    os.environ['CCTV_CACHE_DIR']=str(out/'.cache')
    for key in ['YOLO_CONFIG_DIR','MPLCONFIGDIR']:Path(os.environ[key]).mkdir(parents=True,exist_ok=True)
    os.environ['CCTV_RELEASE_PROBE_DIR']=str(out)
    with AnalysisService() as service:
        job=service.start(owner='release-verification',restroom_id=args.room,
            video_path=args.video.resolve(),model_path=args.model.resolve(),output_dir=out,
            profile='demo',device='cpu',end=args.end)
        initial=job.status();worker=psutil.Process(initial['worker_pid'])
        worker_executable=worker.exe();worker_command=worker.cmdline()
        records=list(job.records());state=job.status()
        if state['status']!='completed':
            raise RuntimeError(f"실제 분석 실패: {state.get('error')}. 현재 Python의 analysis 의존성·가중치 경로를 확인하세요. 기존 CSV로 대체하지 않습니다.")
        worker_identity=json.loads((out/f"worker_identity_{initial['worker_pid']}.json").read_text(encoding='utf-8'))
        assert worker_identity['pid']==initial['worker_pid']
        assert Path(worker_identity['python']).resolve()==Path(sys.executable).resolve(), '분석 자식의 sys.executable이 앱과 다릅니다.'
        assert Path(worker_identity['prefix']).resolve()==Path(sys.prefix).resolve()
        assert Path(worker_identity['package']).resolve()==Path(cctv.__file__).resolve()
        run=Path(state['run_dir']);summary=json.loads((run/'summary.json').read_text(encoding='utf-8'))
        expected=math.ceil(args.end*summary['input_video']['fps']-1e-8)
        assert state['processed_frames']==expected
        assert records and len(records)==math.floor(args.end)
        assert job.latest()==records[-1]
        assert state['runtime_device']['parameter_device']=='cpu'
        assert state['runtime_device']['parameter_dtype']=='torch.float32'
        for record in records:
            file=Path(record['csv_ref']['path']);assert file.is_relative_to(out)
            assert file.read_bytes().startswith(b'\xef\xbb\xbf')
            with file.open(encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f);assert reader.fieldnames==USAGE_FIELDS
                actual=list(reader)[record['csv_ref']['row_number_at_write']-1]
            assert actual=={k:'' if v is None else str(v) for k,v in record['csv_row'].items()}
        used=json.loads((run/'config_used.json').read_text(encoding='utf-8'))
        preset=json.loads(preset_path(args.room).read_text(encoding='utf-8'))
        for key in ['boundary','entry_direction','outside_zone','inside_zone','waiting_zone','transit_zone','excluded_zones','rules']:
            assert used[key]==preset[key],key
        report=dict(room=args.room,version=metadata.version('busan-cctv-analysis'),python=sys.executable,
            package=cctv.__file__,worker_executable=worker_executable,worker_command=worker_command,
            worker_identity=worker_identity,
            processed_frames=expected,api_records=len(records),csv_matches_api_all_13_fields=True,
            mask_matches_stable_bundle=True,runtime_device=state['runtime_device'],run_dir=str(run),
            generated_csv_files=state['csv_files'],records=records)
        (out/f'verification_{args.room}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:report[k] for k in ['room','version','processed_frames','api_records','csv_matches_api_all_13_fields','mask_matches_stable_bundle']},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(f'설치/실행 검증 실패: {exc}',file=sys.stderr);raise SystemExit(2)
