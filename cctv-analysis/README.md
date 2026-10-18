# 부산역 CCTV 분석 모듈

**최종 인계:** [FINAL_HANDOFF.md](docs/FINAL_HANDOFF.md)에 팀원 설치 명령, AnalysisService 시작/상태/최신값/순차수신/중지, Streamlit 실행, 별도 영상·가중치·wheel, 최종 output 경로와 한계를 모았습니다. 공개 시연 CSV3개는 [examples/data](examples/data/)이며 로컬 `outputs/final/`의 대표 CSV와 바이트 일치합니다. 최신 자동 출입 north5/9·south2/2·east5/3과 사용자 수동 총합10/11·4/3·7/6은 분리 기록했고 시각별 정확도는 미평가입니다. 아래 설치/API와 기존 검증은 계속 유효하며 과거 출력 경로는 당시 기록입니다.

단일 저장 영상에서 매 프레임 사람 탐지·추적·출입/외부 대기를 판정하고 정기 집계·CSV를 생성하는 인계용 Python 패키지입니다. 기존 분석을 복사해서 프론트에 붙이지 않고 `from cctv import AnalysisService`로 시작·조회·레코드 수신·중지할 수 있습니다. 최소 Streamlit 예시는 실제 파일 분석을 별도 Windows spawn 작업자로 호출합니다. 예측모델·HTTP 서버·실제 CCTV 수신 기능은 없습니다.

담당 폴더는 **cctv-analysis/** 전체입니다. 모델/영상/실행 결과/가상환경은 별도이며 wheel에 넣지 않습니다. 루트 cctv는 기존 저장소 명령을 위한 작은 호환 경로이고, 실제 분석 소스는 여기의 src/cctv 한 곳에 있습니다. 다른 구성원의 프론트/예측 폴더는 만들거나 옮기지 않았습니다.

## 설치와 실행

실제 검증은 Windows·Python3.13.9·CPU torch2.14.1+cpu, 기존 RTX4060의 torch2.14.1+cu132, Streamlit1.66.0입니다. 패키지는 Python3.13으로 범위를 제한합니다. 다른 Python/운영체제/드라이버 조합은 검증하지 않았습니다. base 설치는 import/CLI 도움말용이며 분석과 Streamlit은 선택 extra입니다.

아래 명령은 인계 폴더에서 실행합니다. CPU PyTorch를 먼저 명시적으로 설치해 일반 설치에서 CUDA 빌드를 강제하지 않습니다.

```powershell
py -3.13 -m venv .venv-cctv
& .\.venv-cctv\Scripts\python.exe -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
& .\.venv-cctv\Scripts\python.exe -m pip install '.\dist\busan_cctv_analysis-0.1.0-py3-none-any.whl[analysis,streamlit]'
& .\.venv-cctv\Scripts\python.exe -m pip check
& .\.venv-cctv\Scripts\python.exe -m cctv --help
$app = & .\.venv-cctv\Scripts\python.exe -m cctv example-path
& .\.venv-cctv\Scripts\python.exe -m streamlit run $app
```

화면에서 화장실 하나, 로컬 영상, yolo11n.pt, 쓰기 가능한 결과 폴더와 CPU/GPU를 지정합니다. demo가 적용되며 저장 파일을 가능한 속도로 처리합니다. 예제 전체 세션을 통틀어 작업1개만 허용하고 소유 세션만 중지할 수 있습니다. 완성된 대시보드가 아닌 호출 예시입니다.

wheel 없이 소스에서 설치할 때는 같은 PyTorch 준비 후 `python -m pip install '.[analysis,streamlit]'`입니다. wheel 빌드는 `python -m pip install build` 후 `python -m build --wheel`입니다. CUDA 별도 환경 설치·프로젝트 밖 호출·정확한 CLI/Python 예시는 [인계 문서](docs/HANDOFF.md), 필드/상태/null/수신 보장은 [데이터 규격](docs/DATA_CONTRACT.md)을 사용하세요.

## 보존한 설정과 정책

운영 초기 인원/촬영시각 null·기본10초 기록은 유지합니다. demo는1초 기록·정시1시간 파일 분할, 초기 north29/south3/east3명, 운영 가능27/19/23칸, 평균105초, 가상 시작2026-10-14T00:00:00+09:00입니다. 초기값은 시작 가정이며 이후 누적 출입을 반영합니다. 예제의 prediction은 disabled입니다. 기존 CLI의 로컬 mock 기능은 남아 있고 실제 예측모델과 구분합니다.

최종 마스킹·모델·FP32·모든 프레임 분석·candidate/confirmed/유효 가림 유예 외부 대기·내부 초과 대기 합산·빈칸/가정식 시간·간결한 결과 영상 수치표·공유 CSV13열을 유지합니다. API는 기본 영상 출력을 끄며 `save_video=True` 또는 기존 CLI로 원래 오버레이 영상을 생성할 수 있습니다. 원본/결과를 덮어쓰지 않습니다.

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

위 항목은 후속 과제입니다. 분석 패키지 구성 범위에 새 모델 학습·가림 대응 수정·동시 처리 개선·예측 연결·통합 재생·외부 배포는 포함하지 않았습니다. 소스 공유는 기존 작업 브랜치 mvp/busan-cctv-20261014의 새 커밋으로 진행하며 main 병합이나 이력 재작성은 하지 않습니다.
