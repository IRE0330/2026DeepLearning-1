# 프론트 담당자 인계

가져갈 폴더는 cctv-analysis/ 전체입니다. src/cctv가 유일한 분석 구현이고, examples는 호출 예제, tests는 규칙/수명주기/최소 화면 검사, ground_truth는 빈 수동 정답 양식입니다. dist의 wheel과 README/docs를 함께 전달할 수 있습니다. 빌드 부산물 build·egg-info와 원래 가상환경은 가져갈 필요가 없습니다.

## 설치

wheel과 dist는 Git 제외입니다. 저장소에서 받은 소스만 있는 경우 이 폴더에서 다음 명령으로 먼저 wheel을 생성하세요. 영상·가중치 없이 빌드할 수 있습니다.

```powershell
python -m pip install build
python -m build --wheel
```

또는 README의 CPU/CUDA PyTorch 준비 후 `python -m pip install '.[analysis,streamlit]'`로 소스에서 설치할 수 있습니다. 오늘까지의 소스·설정·문서는 기존 작업 브랜치 mvp/busan-cctv-20261014의 새 커밋으로 공유하며, 아래 설치/검증 수치는 기존 실행 근거를 재사용합니다.

README의 CPU 명령은 일반 CPU PyTorch를 먼저 설치한 다음 wheel의 analysis/streamlit extra를 설치합니다. base wheel만 설치해도 영상/가중치 없이 import와 `python -m cctv --help`가 됩니다. 전체 의존성의 검증 기준은 requirements-lock.txt(CPU)와 requirements-gpu-lock.txt(CUDA)이며, Streamlit은 선택 의존성1.66.0입니다. 잠금 파일은 기존 환경의 이력을 보존한 것입니다. 현재 설치 검증의 freeze는 별도 검증 자료입니다.

CUDA가 필요하면 **별도** 가상환경에서 장치/드라이버를 확인하고 맞는 공식 PyTorch 빌드를 먼저 설치합니다. 기존 검증 PC는 RTX4060·드라이버610.88·Python3.13.9·cu132입니다. [PyTorch 공식 설치 안내](https://pytorch.org/get-started/locally/)를 기준으로 다른 PC의 호환성을 확인하세요. 아래는 이 프로젝트에서 사용한 조합이며 모든 장비에 맞는 명령이라는 뜻은 아닙니다.

```powershell
py -3.13 -m venv .venv-cctv-gpu
& .\.venv-cctv-gpu\Scripts\python.exe -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu132
& .\.venv-cctv-gpu\Scripts\python.exe -m pip install '.\dist\busan_cctv_analysis-0.1.0-py3-none-any.whl[analysis,streamlit]'
& .\.venv-cctv-gpu\Scripts\python.exe -m pip check
& .\.venv-cctv-gpu\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
```

CPU/CUDA PyTorch를 기존 환경에 덮어쓰지 않습니다. GPU를 요청했는데 사용할 수 없으면 CPU로 조용히 전환하지 않고 오류를 표시합니다.

## 별도 자료와 경로

원본 north/south/east 영상, [MODEL.md](MODEL.md)의 동일 해시 yolo11n.pt를 별도로 준비합니다. 원래 개발 PC의 영상명은 북쪽_화장실_cctv.mp4 / 남쪽 화장실_CCTV.mov / 동쪽_화장실_cctv.mov이며, 새 PC에서는 CLI/API의 영상 경로로 지정할 수 있습니다. 마스킹은 원래 카메라 구도에 대한 것이므로 다른 구도의 영상에 그대로 맞는다고 보장하지 않습니다.

설치된 패키지의 기본 설정 위치는 `python -m cctv preset north`로 조회합니다. 번들 설정/빈 정답 양식은 다음처럼 **새 폴더**로 내보냅니다.

```powershell
& .\.venv-cctv\Scripts\python.exe -m cctv export-assets --destination '.\my-assets'
```

외부 사용자 설정 파일의 video/model/output_dir 상대 경로는 **해당 JSON 파일이 있는 디렉터리** 기준입니다. path_base가 있으면 그 디렉터리에서 한 번 더 적용합니다. CLI/API에서 명시한 경로는 호출 위치 기준으로 절대화한 뒤 작업자에 전달합니다. 입력 영상/가중치/결과 경로를 절대 경로로 주면 어느 작업 폴더에서도 같은 파일을 사용합니다. 쓰기 가능한 output_dir는 호출자가 반드시 지정합니다. API 캐시는 해당 작업 출력의 .cache에 두며 site-packages에 쓰지 않습니다.

기존 루트 configs는 기존 문서의 저장소 루트 기준 해석을 보존합니다. 이 호환 규칙은 소스 체크아웃에만 있으며 인계받은 사용자 JSON에는 적용하지 않습니다. 번들 JSON은 읽기 전용 프리셋이고 직접 수정하지 말고 내보낸 사본을 사용하세요. 운영 초기값/시각 null·10초, demo29/3/3명·1초는 프로필로 구분합니다.

## CLI 실제 파일 분석

다음 예의 D: 경로를 실제 자료/결과 경로로 바꾸세요. 해당 모델·최종 마스킹과 모든 프레임 분석을 사용합니다. `--end`는 짧은 확인용이고 생략하면 전체 길이입니다.

```powershell
$cfg = & .\.venv-cctv\Scripts\python.exe -m cctv preset north
& .\.venv-cctv\Scripts\python.exe -m cctv analyze --config $cfg --profile demo --video 'D:\materials\north.mp4' --model 'D:\materials\yolo11n.pt' --output-dir 'D:\results' --device cpu --prediction disabled --csv-split-seconds 3600 --no-video --end 3.25
```

콘솔 entry point는 같은 명령의 `cctv-analysis`입니다. API 예제는 `python examples/analyze_video.py --room north --video ... --model ... --output ... --device cpu --profile demo --end 3.25`이며 실제 분석을 호출합니다. 시작은 빠르게 반환하고 모델 준비는 자식에서 진행합니다. Python 호출/상태/순차 수신/cursor/예외는 [DATA_CONTRACT.md](DATA_CONTRACT.md)에 있습니다.

## Streamlit 최소 예제

```powershell
$app = & .\.venv-cctv\Scripts\python.exe -m cctv example-path
& .\.venv-cctv\Scripts\python.exe -m streamlit run $app
```

소스 폴더를 함께 받았으면 `python -m streamlit run examples/streamlit_app.py`도 같습니다. 새 HTTP API 서버나 완성된 프론트는 제공하지 않습니다. 실제 영상 파일을 선택해 분석 프로그램을 호출하며 기존 CSV를 재생하는 화면이 아닙니다. 원하면 자신의 Streamlit 코드에서 `AnalysisService`만 호출하면 됩니다.

공식 사용법은 설치된 Streamlit1.66.0의 번들 reference와 `python -m streamlit docs st.fragment`로 확인했습니다. [공식 fragment 문서](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)의 run_every=1로 활성 세션에서 약1초마다 조회하며, [cache_resource](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource)로 Service 하나를 공유합니다. 모델/분석 작업은 캐시 함수 안에서 로딩하지 않고 시작 버튼을 눌렀을 때 별도 spawn 프로세스로 만듭니다. 작업자는 st.*를 호출하지 않습니다. Windows spawn 재수입에서는 UI 진입점이 실행되지 않도록 __main__ 가드가 있습니다.

## 소유권·재실행·종료

같은 Streamlit 서버 프로세스의 전체 세션에서 동시에 작업1개만 허용합니다. 화면 rerun/중복 시작은 기존 작업을 다시 만들지 않습니다. 다른 세션에는 사용 중 상태를 표시하고 소유 세션만 중지할 수 있습니다. 로컬 세션 조정이며 인증/보안 경계가 아니고 여러 서버/호스트를 조율하는 스케줄러도 아닙니다.

소유 세션은 status 조회 시 heartbeat를 보냅니다. 정상적인 화면 rerun은 같은 소유자를 유지합니다. 브라우저 새로고침으로 세션 ID가 바뀌거나 연결이 끝나도 작업을 즉시 감지/종료하지 않습니다. 마지막 소유자 조회부터90초가 지나면 중지를 요청하고 최대10초 후 필요하면 강제 종료합니다. 그 전에는 새 세션도 기존 작업을 기다립니다. 웹 페이지가 백그라운드에서 조회하지 않거나 매우 느려도 이 정책이 적용될 수 있습니다.

정상 서버 종료는 atexit/Service.close로 같은 중지 절차를 적용합니다. 자식은 부모 종료를 주기적으로 확인하고 협조적 중지를 요청합니다. OS 강제 종료·전원 장애·멈춘 GPU 호출의 모든 정리를 보장하지는 않습니다. 상태/CSV/저널 꼬리와 작업 프로세스를 확인해야 합니다. 중지·강제 종료·실패·정상 완료는 서로 다른 상태입니다. 완료/중지 후 새 작업은 새 고유 폴더와 새 Tracker 상태로 시작합니다.

## 전달할 것

- cctv-analysis/의 소스·pyproject·의존성 파일·tests·examples·ground_truth·README/docs, 또는 dist wheel과 예제/문서
- 별도 원본 영상·동일 해시 가중치
- 필요 시 검토할 실행 결과(기본 wheel/Git에는 미포함)

원본/결과 영상·모델·MICC·가상환경·캐시·대용량 출력·인증정보는 Git 제외입니다. CSV/JSON 전체를 제외하지 않아 설정과 빈 양식은 포함합니다. 기존 로컬 자료/키/환경을 이동·삭제하거나 값을 출력하지 않았습니다. 소스 공유는 기존 작업 브랜치 mvp/busan-cctv-20261014에서 기존 이력을 보존하는 새 커밋으로 진행합니다. main 병합·force push·외부 배포는 하지 않습니다.

현재 지원 범위·과거 단일/동시 시험·향후9개 항목은 README, 실제 설치/짧은 실행과 모의/화면 검증 구분은 [VALIDATION.md](VALIDATION.md)을 확인하세요. 세 환경 동시 처리 개선은 후속 과제입니다.
