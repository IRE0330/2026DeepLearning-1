"""Explicit opt-in north CUDA profile; existing AnalysisService API is unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
from .config import DATA

def selection(*, restroom_id='north', device='cuda:0', model_path):
    """Validate before launching a worker; never choose s from device auto-detection."""
    spec=json.loads((DATA/'configs/runtime_profiles/north_gpu_s.json').read_text(encoding='utf-8'))
    if restroom_id!=spec['restroom_id'] or device!=spec['device']:
        raise ValueError('north-gpu-s는 북쪽·명시적 cuda:0 전용입니다. CPU/MPS/auto 및 남·동쪽에는 기본 n을 사용하세요.')
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU를 사용할 수 없습니다. GPU용 새 가상환경을 확인하거나 기본 n CPU 실행을 선택하세요.')
    path=Path(model_path).expanduser().resolve()
    if not path.is_file():raise FileNotFoundError(f'yolo11s.pt가 없습니다: {path}. 공식 URL: {spec["url"]}')
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=spec['sha256']:raise ValueError('yolo11s.pt SHA-256 불일치. 공식 파일과 해시를 확인하세요.')
    return dict(restroom_id='north',device='cuda:0',model_path=path)

def start_north_gpu_s(service, *, owner, video_path, model_path, output_dir,
                      profile='operating', end=None, save_video=False):
    """Use bundled stable north geometry and the existing public service."""
    selected=selection(model_path=model_path)
    return service.start(owner=owner,video_path=video_path,output_dir=output_dir,
                         profile=profile,end=end,save_video=save_video,**selected)

def main():
    p=argparse.ArgumentParser(description='명시적 북쪽 north-gpu-s 프로필 (기본 n과 독립)')
    p.add_argument('--runtime-profile',required=True,choices=['north-gpu-s'])
    p.add_argument('--video',required=True);p.add_argument('--model',required=True)
    p.add_argument('--output-dir',required=True);p.add_argument('--profile',choices=['operating','demo'],default='operating')
    p.add_argument('--end',type=float);p.add_argument('--save-video',action='store_true')
    a=p.parse_args()
    from . import AnalysisService
    with AnalysisService() as service:
        job=start_north_gpu_s(service,owner='north-gpu-s',video_path=a.video,model_path=a.model,
            output_dir=a.output_dir,profile=a.profile,end=a.end,save_video=a.save_video)
        for record in job.records():print(json.dumps(record,ensure_ascii=False),flush=True)
        state=job.status();print(json.dumps(state,ensure_ascii=False),flush=True)
        if state['status']!='completed':raise RuntimeError(state.get('error') or state['status'])

if __name__=='__main__':main()
