**팀원 다운로드·설치·연동:** [여기서 시작하세요](deployment/START_HERE.md)

# 팀원 설치·연동 시작 — 안정 인계 0.3.2

오늘의 구역/정확도 실험·수동 정답 변경을 포함하지 않는 **검증된 0.3.2 분석 모듈**입니다. 이 문서 순서대로 다운로드 → 새 가상환경 → 의존성 포함 설치 → 가중치 → 원본/환경 선택 → 짧은 실제 분석 → 집계 수신을 진행합니다. 기존 output은 필요하지 않습니다. 현재 공개 Release 여부와 검증 해시는 [배포 파일 목록](https://github.com/IRE0330/2026DeepLearning-1/blob/cctv-analysis-v0.3.2/cctv-analysis/docs/RELEASE_FILES_032.json)을 확인하세요.

## 1. 다운로드

- [모듈 전용 Release](https://github.com/IRE0330/2026DeepLearning-1/releases/tag/cctv-analysis-v0.3.2)
- [설치·소스·설정·문서·예제·wheel 묶음 ZIP](https://github.com/IRE0330/2026DeepLearning-1/releases/download/cctv-analysis-v0.3.2/busan_cctv_analysis-0.3.2-deployment.zip)
- [검증된 원본 wheel](https://github.com/IRE0330/2026DeepLearning-1/releases/download/cctv-analysis-v0.3.2/busan_cctv_analysis-0.3.2-py3-none-any.whl)
- [공유 최종 예시 CSV 3개](https://github.com/IRE0330/2026DeepLearning-1/releases/download/cctv-analysis-v0.3.2/busan_cctv_analysis-0.3.2-example-results.zip)
- [SHA256SUMS](https://github.com/IRE0330/2026DeepLearning-1/releases/download/cctv-analysis-v0.3.2/SHA256SUMS-0.3.2.txt)

**Release가 아직 표시되지 않으면 게시 미완료입니다. 로컬 파일이나 이 링크 자체를 원격 게시 증거로 보지 마세요.** 게시/원격 검증 상태는 위 배포 파일 목록에 구분합니다. 최초 검증 인계 ZIP/기존 wheel은 덮어쓰지 않고, 새 안내를 포함한 ZIP에 `deployment` 이름을 사용합니다. 분석 코드·번들 좌표·패키지 버전은 그대로입니다.

ZIP을 새 작업 폴더 `cctv032/`에 풀고 그 안에서 진행하세요. 원격 다운로드 예:

```bash
curl -fL 'https://github.com/IRE0330/2026DeepLearning-1/releases/download/cctv-analysis-v0.3.2/busan_cctv_analysis-0.3.2-deployment.zip' -o cctv032.zip
unzip cctv032.zip -d cctv032
cd cctv032
```

Windows에서는 Release의 ZIP을 다운로드한 뒤 `Expand-Archive -LiteralPath .\cctv032.zip -DestinationPath .\cctv032`로 풀고 이동합니다. macOS는 `shasum -a 256`, Windows는 `Get-FileHash -Algorithm SHA256`으로 다운로드 파일과 SHA256SUMS를 비교하세요. 원격 파일을 확인하기 전 분석을 시작하지 마세요.

## 2. 새 Python 3.13 환경 — CPU 기본

실제 설치 검증 대상은 **Windows x64 / Python 3.13.9 / CPU**입니다. macOS Python 3.13은 아래 절차를 제공하지만 해당 OS에서 실행 검증하지 않았습니다. Python 3.14는 이 wheel의 `Requires-Python >=3.13,<3.14` 범위 밖입니다. 기존 앱 환경을 강제로 바꾸거나 `--ignore-requires-python`, `--system-site-packages`로 우회하지 마세요.

Windows PowerShell:

```powershell
py -3.13 -m venv .venv-cctv
$py = (Resolve-Path .\.venv-cctv\Scripts\python.exe).Path
& $py -c "import sys; print(sys.executable); print(sys.version)"
& $py -m pip --version
& $py -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
& $py -m pip install '.\dist\busan_cctv_analysis-0.3.2-py3-none-any.whl[analysis,streamlit]' -c .\requirements-handoff-032.txt
& $py -m pip check
```

`py` 런처가 없으면 설치된 Python 3.13 실행 파일의 실제 경로로 첫 명령의 `py -3.13`을 대체하세요.

macOS 터미널(미검증 경로):

```bash
python3.13 -m venv .venv-cctv
PY="$PWD/.venv-cctv/bin/python"
"$PY" -c 'import sys; print(sys.executable); print(sys.version)'
"$PY" -m pip --version
"$PY" -m pip install torch==2.14.1 torchvision==0.29.1
"$PY" -m pip install './dist/busan_cctv_analysis-0.3.2-py3-none-any.whl[analysis,streamlit]'
"$PY" -m pip check
```

Windows 전용 잠금 파일을 macOS에 강제 적용하지 않습니다. 해당 Python/아키텍처의 의존성 wheel이 없으면 지원 미확인 환경이며 설치 성공을 보장하지 않습니다. `ultralytics` 메타데이터 오류가 나면 현재 Python에서 `importlib.metadata.version('ultralytics')`와 import를 함께 확인하세요. 앱과 pip의 Python 불일치·analysis extra 미설치·손상된 배포 메타데이터 등을 구분해야 하며 Python 3.14 때문이라고 단정하지 않습니다.

## 3. 동일 가중치 준비·설치 진단

사용 모델은 Ultralytics YOLO11n COCO 사전학습 `yolo11n.pt`입니다. 공식 다운로드와 로컬 사용 파일이 같은 해시임을 확인했습니다.

- [공식 고정 다운로드](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt)
- SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`
- [모델/라이선스 고지와 게시 제외 자료](docs/RELEASE_NOTICES.md)

Windows:

```powershell
& $py -m cctv download-model
$weights = (Resolve-Path .\models\yolo11n.pt).Path
& $py .\scripts\diagnose_install.py --model $weights
$env:CCTV_MODEL_PATH = $weights
```

macOS:

```bash
"$PY" -m cctv download-model
WEIGHTS="$PWD/models/yolo11n.pt"
"$PY" scripts/diagnose_install.py --model "$WEIGHTS"
export CCTV_MODEL_PATH="$WEIGHTS"
```

진단은 선택된 Python·pip·ultralytics import/메타데이터·분석 의존성·spawn 자식 Python·가중치 해시를 확인합니다. 오류가 있으면 중단하고 실제 오류를 표시합니다. 저장 CSV로 추론을 대체하거나 분석 중 가중치를 몰래 내려받지 않습니다. 직접 `model_path` 지정은 환경변수보다 우선합니다.

## 4. 원본과 환경 선택 → 짧은 실제 분석

공개 ZIP에는 원본 영상이 없습니다. 사용 권한이 있는 원본을 팀 내 별도 경로로 준비하세요. 파일 경로를 인수로 넘기므로 개인 PC 절대 경로에 의존하지 않습니다.

|보유 원본|room|기본 선택|
|---|---|---|
|북쪽_화장실_cctv.mp4|north|기존 북쪽 번들 구역·제외 마스킹|
|남쪽 화장실_cctv.mov|south|기존 남쪽 번들 구역·제외 마스킹|
|동쪽_화장실_cctv.mov|east|기존 동쪽 번들 구역·소화기 제외 포함|

같은 전달 원본·카메라 구도에서만 기존 좌표를 사용합니다. 다른 카메라/구도는 `python -m cctv export-assets --destination ./my-assets`로 설정 사본을 만들고, 해당 JSON의 video를 지정한 뒤 `python -m cctv configure --config <JSON>`으로 경계·확인/대기/제외 구역을 다시 설정해야 합니다. 원래 번들 설정을 덮어쓰지 마세요. 사용자 설정은 예제의 `--config <JSON>` 또는 API의 `config_path`로 선택합니다.

Windows(원본 파일을 자신의 위치로 지정):

```powershell
$video = (Resolve-Path '.\media\북쪽_화장실_cctv.mp4').Path
& $py .\examples\analyze_video.py --room north --video $video --model $weights --output .\runs --profile demo --device cpu --end 3.25
& $py .\scripts\verify_release_install.py --room north --video $video --model $weights --output .\verify-runs --end 3.25
```

macOS(실행 미검증):

```bash
VIDEO="$PWD/media/북쪽_화장실_cctv.mp4"
"$PY" examples/analyze_video.py --room north --video "$VIDEO" --model "$WEIGHTS" --output ./runs --profile demo --device cpu --end 3.25
"$PY" scripts/verify_release_install.py --room north --video "$VIDEO" --model "$WEIGHTS" --output ./verify-runs --end 3.25
```

`--end 3.25`는 시작부터 약 3.25초만 실제 프레임을 처리합니다. 남/동쪽은 room과 원본 경로를 함께 바꿉니다. 검증 스크립트는 새 CSV 생성·처리 프레임 수·API 수신의 13열 전부 일치·안정 번들 마스킹·분석 자식 Python을 검사합니다. 실행마다 별도 작업 폴더를 만들며 기존 output이 없어도 됩니다.

## 5. 실제 AnalysisService 연동

[전체 최소 예제](examples/analyze_video.py)는 실제 공개 인터페이스를 사용합니다. Windows spawn을 위해 파일로 저장하고 `if __name__ == '__main__'` 아래에서 시작하세요.

```python
import os
from cctv import AnalysisService

def main():
    with AnalysisService() as service:
        job = service.start(owner='team-app', restroom_id='north',
            video_path=os.environ['CCTV_VIDEO_PATH'],
            model_path=os.environ['CCTV_MODEL_PATH'], output_dir='./new-runs',
            profile='demo', device='cpu', end=3.25)
        for record in job.records():
            print(record['csv_row'])  # 새 실제 분석의 정기 집계
        status = job.status()
        if status['status'] != 'completed':
            raise RuntimeError(status.get('error'))
        print(status['csv_files'])

if __name__ == '__main__':
    main()
```

`job.latest()`는 최신 레코드, `job.records()`는 순차 수신, `job.status()`는 진행/오류/CSV 위치, `job.stop()`은 중지입니다. [데이터 계약](docs/DATA_CONTRACT.md)을 함께 사용하세요. Streamlit도 같은 선택 Python으로 실행해야 합니다: `python -m cctv example-path`가 알려주는 파일을 **선택한 Python의 `-m streamlit run`**으로 실행합니다. `pip`·앱·spawn 자식에 서로 다른 Python을 섞지 마세요.

`examples/data/`의 CSV 3개는 과거 안정 인계의 시연·비교 출력입니다. 추론 입력이나 새 분석의 정답/대체 결과가 아닙니다. 북5/9·남2/2·동5/3의 안정 결과이며 오늘 정확도 실험 결과로 바꾸지 않았습니다.

## GPU·지원 범위

CPU 설치 경로가 기본 검증 경로입니다. GPU는 기존 CPU 환경을 바꾸지 말고 별도 Python 3.13 가상환경을 만드세요. [PyTorch 공식 설치 선택기](https://pytorch.org/get-started/locally/)에서 OS·드라이버에 맞고 **torch 2.14.1 / torchvision 0.29.1**과 호환되는 빌드를 선택한 뒤 선택한 Python의 `-m pip`로 설치합니다. Windows CPU 잠금 파일의 `+cpu` 버전을 GPU 환경에 적용하지 않습니다. 분석은 `--device cuda:0`, 설치 진단은 같은 GPU 환경 Python으로 실행합니다. 이번 게시 검증은 CPU이며 CUDA/Apple MPS를 새로 검증하지 않았습니다.

다른 OS/장비, Python 3.14, 장시간 운영, 실제 CCTV 수신, 세 영상 동시 실시간 처리는 미검증입니다. 대기는 연속 저속 3.5초, CSV 13열과 계산식·공개 API는 유지했습니다. demo 초기 인원·가상 촬영시각·칸 수·평균 이용시간은 시연 가정입니다. 정확도 개선 실험이나 일반화 검증을 이 배포의 성능으로 주장하지 않습니다.

<details>
<summary>0.3.2 최초 인계 당시 설명과 이전 검증 이력</summary>

**최초 인계 0.3.2 (2026-10-21):** 아래는 당시 이력입니다. 현재 설치·다운로드 안내는 위 문서를 사용하고, 과거 경로와 당시 push 미수행 설명은 현재 게시 상태와 구분하세요.

# 부산역 CCTV 분석 모듈

**최종 인계:** [FINAL_HANDOFF.md](docs/FINAL_HANDOFF.md)에 팀원 설치 명령, AnalysisService 시작/상태/최신값/순차수신/중지, Streamlit 실행, 별도 영상·가중치·wheel, 최종 output 경로와 한계를 모았습니다. 공개 시연 CSV3개는 [examples/data](examples/data/)이며 로컬 최신 `outputs/final/{north|south|east}/shared/`의 CSV와 바이트 일치합니다. 최신 자동 출입 north5/9·south2/2·east5/3과 사용자 수동 총합10/11·4/3·7/6은 분리 기록했고 시각별 정확도는 미평가입니다. 아래 설치/API와 기존 검증은 계속 유효하며 과거 출력 경로는 당시 기록입니다.

단일 저장 영상에서 매 프레임 사람 탐지·추적·출입/외부 대기를 판정하고 정기 집계·CSV를 생성하는 인계용 Python 패키지입니다. 기존 분석을 복사해서 프론트에 붙이지 않고 `from cctv import AnalysisService`로 시작·조회·레코드 수신·중지할 수 있습니다. 최소 Streamlit 예시는 실제 파일 분석을 별도 Windows spawn 작업자로 호출합니다. 예측모델·HTTP 서버·실제 CCTV 수신 기능은 없습니다.

담당 폴더는 **cctv-analysis/** 전체입니다. 모델/영상/실행 결과/가상환경은 별도이며 wheel에 넣지 않습니다. 루트 cctv는 기존 저장소 명령을 위한 작은 호환 경로이고, 실제 분석 소스는 여기의 src/cctv 한 곳에 있습니다. 다른 구성원의 프론트/예측 폴더는 만들거나 옮기지 않았습니다.

## 설치와 실행

실행용·번들 설정의 `model` 기본값은 `${CCTV_MODEL_PATH}`입니다. 자신의 가중치를 `--model` 또는 `AnalysisService.start(model_path=...)`로 지정하거나 환경변수 `CCTV_MODEL_PATH`를 설정하세요. 개인 PC 절대 경로를 기본값으로 사용하지 않습니다. 과거 `config_used.json`은 수정하지 않습니다.

실제 검증은 Windows·Python3.13.9·CPU torch2.14.1+cpu, 기존 RTX4060의 torch2.14.1+cu132, Streamlit1.66.0입니다. 패키지는 Python3.13으로 범위를 제한합니다. 다른 Python/운영체제/드라이버 조합은 검증하지 않았습니다. base 설치는 import/CLI 도움말용이며 분석과 Streamlit은 선택 extra입니다.

아래 명령은 인계 폴더에서 실행합니다. CPU PyTorch를 먼저 명시적으로 설치해 일반 설치에서 CUDA 빌드를 강제하지 않습니다.

```powershell
py -3.13 -m venv .venv-cctv
& .\.venv-cctv\Scripts\python.exe -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
& .\.venv-cctv\Scripts\python.exe -m pip install '.\dist\busan_cctv_analysis-0.3.2-py3-none-any.whl[analysis,streamlit]'
& .\.venv-cctv\Scripts\python.exe -m pip check
& .\.venv-cctv\Scripts\python.exe -m cctv --help
$app = & .\.venv-cctv\Scripts\python.exe -m cctv example-path
& .\.venv-cctv\Scripts\python.exe -m streamlit run $app
```

화면에서 화장실 하나, 로컬 영상, yolo11n.pt, 쓰기 가능한 결과 폴더와 CPU/GPU를 지정합니다. demo가 적용되며 저장 파일을 가능한 속도로 처리합니다. 예제 전체 세션을 통틀어 작업1개만 허용하고 소유 세션만 중지할 수 있습니다. 완성된 대시보드가 아닌 호출 예시입니다.

wheel 없이 소스에서 설치할 때는 같은 PyTorch 준비 후 `python -m pip install '.[analysis,streamlit]'`입니다. wheel 빌드는 `python -m pip install build` 후 `python -m build --wheel`입니다. CUDA 별도 환경 설치·프로젝트 밖 호출·정확한 CLI/Python 예시는 [인계 문서](docs/HANDOFF.md), 필드/상태/null/수신 보장은 [데이터 규격](docs/DATA_CONTRACT.md)을 사용하세요.

## 보존한 설정과 정책

운영 초기 인원/촬영시각 null·기본10초 기록은 유지합니다. demo는1초 기록·정시1시간 파일 분할, 초기 north29/south3/east3명, 운영 가능27/19/23칸, 평균105초, 가상 시작2026-10-14T00:00:00+09:00입니다. 초기값은 시작 가정이며 이후 누적 출입을 반영합니다. 예제의 prediction은 disabled입니다. 기존 CLI의 로컬 mock 기능은 남아 있고 실제 예측모델과 구분합니다.

0.2.0부터 candidate는 영상에 별도 표시하지만 대기 합계에서 제외합니다. 영상 시각으로 연속 관측된 3.5초의 정지·느린 이동 증거와 구간 속도 조건을 만족해야 confirmed가 됩니다. 외부 대기는 관측 confirmed + 중복 억제 후 유효 confirmed 가림 유예입니다. 최종 마스킹·모델·FP32·출입 판정·내부 초과 대기 합산·빈칸/가정식 시간·영상 수치표 디자인·공유 CSV13열은 유지합니다. API는 기본 영상 출력을 끄며 `save_video=True`로 영상을 생성합니다. 자세한 규칙·검증·최신 결과는 [대기 판정 갱신](docs/WAITING_35S.md)을 따릅니다.

## 현재 검증 상태와 한계

아래는 **패키징 전 기존 로그**를 확인한 단일 GPU 재생속도 입력 모사 이력입니다. 이번 설치 검증으로 재측정한 수치가 아닙니다. 준비 완료 후 각 정기 기록 경계 대비 CSV flush 지연이며 모두 프로젝트 시험 목표1초를 충족했습니다. 공식 기준이나 보장이 아닙니다.

| 환경 | 전체 프레임 /1초 행 | 지연 중앙값 / p95 / 최대(초) |
|---|---:|---:|
| north |2524 /105|0.029 /0.036 /0.043|
| south |2827 /94|0.028 /0.039 /0.044|
| east |2700 /90|0.028 /0.040 /0.059|

영상 검사·모델 로딩·GPU 준비의 시작 지연은 위 지연에서 제외됐습니다. 세 환경 동시 입력은 지연이 누적돼 입력24.023초 후 자동 중단했습니다(부분 프레임467/467/468, 마지막 기록 지연4.506/8.192/8.175초). 현재 버전은 세 CCTV 동시 실시간 분석을 보장하지 않습니다. 저장 영상 순차 처리와 동시 실시간 분석은 다릅니다. 이번 작업은 동시 처리 구조를 개선하지 않았습니다.

공개 API/Streamlit 예시는 재생속도 대기 없는 파일 분석입니다. 영상 시각 기준1초 기록과 실제 데이터 도착 간격은 다르며 준비 중에는 값이 없습니다. 최신값만 조회해도 모든 정기 행은 CSV/저널에 보존합니다. 실제 CCTV·네트워크·장시간 운영은 미검증입니다. 수동 카운팅 정확도도 미검증이며 가림/ID 유실로 출입을 놓칠 수 있습니다. 내부 인원·빈칸·대기시간은 초기값과 계산 가정에 따른 추정입니다. 실제 예측모델은 미구현·미연동입니다.

이번 wheel/새 CPU 환경/실제 짧은 분석/API/최소 화면 검증 범위와 근거는 [VALIDATION.md](docs/VALIDATION.md)에 구분합니다. [모델/라이선스 정보](docs/MODEL.md)도 함께 전달하세요.

## 향후 진행 사항

1. GPU 공유 잠금과 전처리·추론·추적·저장 병목 분석
2. 환경별 추적 상태를 보존하는 다중 영상 처리 구조 개선
3. 여러 영상 프레임의 묶음 추론 등 GPU 활용 방식 검토
4. 세 환경 동시 입력의 기록 지연·대기열·집계 결과 재검증
5. 필요 시 장비 분산 검토
6. 시작 준비 지연 개선
7. 수동 정답 기반 출입·대기 정확도 평가와 가림 대응 개선
8. 실제 CCTV·네트워크·장시간 운영 검증
9. 향후 예측모델 및 전체 Streamlit 화면과의 통합 검증

위 항목은 후속 과제입니다. 분석 패키지 구성 범위에 새 모델 학습·가림 대응 수정·동시 처리 개선·예측 연결·통합 재생·외부 배포는 포함하지 않았습니다. 작업 브랜치는 mvp/busan-cctv-20261014이며 당시 인계 수정은 로컬 파일과 배포물에만 반영했습니다.

</details>
