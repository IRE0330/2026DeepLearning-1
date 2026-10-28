"""Dashboard-only runtime checks and explicit per-room model selection."""
from importlib import metadata
from pathlib import Path
import json
import sys
from urllib.parse import urlsplit
from urllib.request import url2pathname

SOURCE = Path(__file__).resolve().parents[1] / 'cctv-analysis' / 'src' / 'cctv'
SUPPORTED_VERSIONS = {'0.3.3'}
INSTALL_HINT = '대시보드와 같은 Python으로 -m pip install -e "./cctv-analysis[analysis,streamlit]"를 실행하세요.'


def runtime_info():
    """Reject stale distributions and the legacy duplicate source tree."""
    try:
        installed = metadata.version('busan-cctv-analysis')
    except metadata.PackageNotFoundError as error:
        raise ValueError('분석 모듈이 설치되지 않았습니다. ' + INSTALL_HINT) from error
    if installed not in SUPPORTED_VERSIONS:
        raise ValueError(f'지원 분석 버전은 0.3.3입니다 (현재 {installed}). ' + INSTALL_HINT)
    # A root compatibility bridge can otherwise hide a different installed copy
    # that the worker (whose cwd is the dashboard folder) would import.
    origin = json.loads(metadata.distribution('busan-cctv-analysis').read_text('direct_url.json') or '{}')
    url = urlsplit(origin.get('url', ''))
    if (not origin.get('dir_info', {}).get('editable') or url.scheme != 'file'
            or Path(url2pathname(url.path)).resolve() != SOURCE.parent.parent.resolve()):
        raise ValueError('현재 브랜치의 editable 소스 설치가 아닙니다. ' + INSTALL_HINT)
    import cctv.api
    actual = Path(cctv.api.__file__).resolve()
    if actual != (SOURCE / 'api.py').resolve():
        raise ValueError(f'다른 분석 소스를 불러왔습니다: {actual}. ' + INSTALL_HINT)
    for package in ['ultralytics', 'torch', 'torchvision', 'opencv-python', 'av', 'lap', 'streamlit']:
        try:
            metadata.version(package)
        except metadata.PackageNotFoundError as error:
            raise ValueError(f'분석 의존성 {package}가 없습니다. ' + INSTALL_HINT) from error
    return {'version': installed, 'python': sys.executable, 'source': str(actual)}


def validate_selection(request):
    profile = request.get('runtime_profile', 'default-n')
    if profile not in ('default-n', 'north-gpu-s'):
        raise ValueError('지원하지 않는 실행 프로필입니다.')
    if profile == 'north-gpu-s':
        # The official helper only supports bundled north geometry. Never drop a
        # user's config_path and silently substitute those masks.
        if request['configs'].get('north'):
            raise ValueError('north-gpu-s는 번들 북쪽 구역만 지원합니다. 사용자 북쪽 JSON은 기본 n으로 실행하세요.')
        if request['device'] != 'cuda:0':
            raise ValueError('north-gpu-s는 cuda:0을 명시적으로 선택해야 합니다. CPU/MPS 대체 실행은 하지 않습니다.')
        if not request.get('north_s_model'):
            raise ValueError('북쪽 s 가중치 yolo11s.pt 경로를 지정하세요.')
        from cctv.gpu_profile import selection
        selected = selection(model_path=request['north_s_model'], device=request['device'])
        request['north_s_model'] = str(selected['model_path'])


def start_room(service, request, room, **options):
    """Keep n and user config/device unchanged except for explicit north opt-in."""
    if request.get('runtime_profile', 'default-n') == 'north-gpu-s' and room == 'north':
        # Validate again in the worker in case a weight file changed after start.
        validate_selection(request)
        from cctv.gpu_profile import start_north_gpu_s
        return start_north_gpu_s(service, model_path=request['north_s_model'], **options)
    return service.start(restroom_id=room, model_path=request['model'],
                         config_path=request['configs'][room] or None,
                         device=request['device'], **options)
