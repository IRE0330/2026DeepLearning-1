> 이 문서는 이전 실행·검증 이력을 보존한 기록입니다. 현재 설치·실행은 [시작 안내](https://github.com/IRE0330/2026DeepLearning-1/blob/mvp/busan-cctv-20261014/cctv-analysis/deployment/START_HERE.md)를 사용하세요. 과거 버전·경로·게시 상태는 현재 안내와 구분합니다.

**최종 인계 0.3.2 (2026-10-21):** 세 환경 최신 결과는 `outputs/final/{north|south|east}/`에 통합했습니다. 북쪽·남쪽은 3.5초 확정 결과, 동쪽은 소화기 제외 결과입니다. 대기 규칙·기록 정책은 유지하며 재분석·수치 보정하지 않았습니다. [최종 인계](../../cctv-analysis/docs/FINAL_HANDOFF.md)를 따릅니다. 아래 중간 실행·검증 설명은 이력이며 과거 경로는 보존 근거로 이동했습니다. 이번 인계에서는 추가 삭제·commit·push를 하지 않습니다. 최신0.3.2 ZIP과 wheel을 별도 전달하며 모델 경로는 실행자가 지정합니다.

# 딥러닝 기초 1조

> **최종 인계 (2026-10-18):** 팀원은 [최종 설치·Streamlit 연동 안내](../../cctv-analysis/docs/FINAL_HANDOFF.md)부터 확인하세요. 담당 패키지는 `cctv-analysis/`, 로컬 최종 영상/CSV는 `outputs/final/{north,south,east}/`, Git 공개용 동일 시연 CSV3개는 `cctv-analysis/examples/data/`입니다. 단독 전체 입력 모사의 기록 지연 목표는 충족했지만 시작 준비시간이 있으며 동시3개 처리는 미충족입니다. 자동 입장/퇴장은 북쪽5/9·남쪽2/2·동쪽5/3, 사용자 수동 총합10/11·4/3·7/6이며 시각별 정확도 평가는 미완료입니다. 초기29/3/3명·27/19/23칸·평균105초·가상시각·1초/13열/1시간 정책을 유지합니다. 실제 CCTV/네트워크/장시간 운영과 예측모델은 미검증/미구현입니다. 아래의 기존 outputs 경로와 push 관련 표현은 당시의 작업 이력이며, 현행 경로·별도 전달 자료·정리 내역은 최종 인계 문서를 기준으로 합니다.
AI 기반 화장실 혼잡도 분석 및 분산 안내 시스템


> 위 문구는 기존 팀 저장소 소개를 보존한 것입니다. 아래는 현재 구현된 CCTV 카운팅 MVP의 실행 안내이며, 미래 혼잡도 예측·분산 안내·웹 배포는 미구현입니다.

# 부산역 CCTV 입장·퇴장·대기 카운팅 MVP

**현재 공유 기준 (2026-10-18):** 기존 작업 브랜치 [mvp/busan-cctv-20261014](https://github.com/IRE0330/2026DeepLearning-1/tree/mvp/busan-cctv-20261014)에 오늘까지의 분석 패키지·Streamlit 연동 예시·관련 설정/문서를 새 커밋으로 반영합니다. demo는 영상 시각 기준1초 기록·한국시간 정시1시간 CSV 분할이며, 초기 내부/운영 가능 칸 수는 북쪽29명/27칸·남쪽3명/19칸·동쪽3명/23칸, 평균 칸 이용시간은 모두105초입니다. 초기값은 영상 시작 가정이며 누적 출입으로 변합니다. 운영 기본10초 기록은 보존합니다. 세 환경 각각의 단일 재생속도 입력 모사는 준비 완료 후 기록 지연 시험 목표를 충족했고, 세 환경 동시 처리 개선은 후속 과제입니다. 수동 카운팅 정확도·실제 CCTV·장시간 운영은 미검증이며 실제 예측모델은 미구현·미연동입니다. 기존83개 테스트·실제 짧은 설치/호출 검증을 재사용하고 이번 Git 공유를 위해 영상 재분석을 반복하지 않습니다.

영상·가중치·MICC·가상환경·outputs/inspections·캐시·인증정보와 wheel 빌드 산출물은 Git 제외입니다. 저장소를 받은 담당자는 `cctv-analysis`에서 `python -m pip install build` 후 `python -m build --wheel`로 wheel을 생성하거나, CPU/CUDA PyTorch를 준비한 뒤 `python -m pip install '.[analysis,streamlit]'`로 소스 설치합니다. 자세한 명령은 [인계 문서](../../cctv-analysis/docs/HANDOFF.md)에 있습니다. 아래는 공유 전까지의 구현·검증 이력이며 과거의 미커밋/push 미실행 표기는 당시 상태입니다.

**Python 모듈 인계 (2026-10-18):** 분석 담당 폴더는 [cctv-analysis/](../../cctv-analysis/README.md)입니다. 실제 소스는 `cctv-analysis/src/cctv`로 모았고 루트 `cctv`는 기존 `python -m cctv` 명령의 호환 경로입니다. 설치 가능한 wheel·공개 시작/상태/레코드/중지 인터페이스·단일 작업 Streamlit 호출 예제를 추가했습니다. 별도 CPU 환경의 외부 작업 폴더에서 wheel 실제 분석과 기존 GPU의 짧은 호출을 검증했으며, Streamlit은 실제 분석을 연결한 AppTest로 확인했습니다(실제 브라우저 미검증). 설치·사용·제한·향후 작업은 [분석 모듈 인계](../../cctv-analysis/docs/HANDOFF.md), [검증](../../cctv-analysis/docs/VALIDATION.md), [데이터 규격](../../cctv-analysis/docs/DATA_CONTRACT.md)에 있습니다. 기존 자료·마스킹·판정·CSV 정책을 보존하고 동시 처리 개선/예측 연동/외부 배포/push는 수행하지 않았습니다. 아래 실행 결과는 이전 검증 이력입니다.

**최신 입력 지연 시험 (2026-10-17):** `simulate-input`으로 준비/워밍업 후 고정 monotonic 일정의 저장 영상 공급과1초 CSV flush 지연을 측정했습니다. 북쪽 단일 전체는2524프레임/105행·기록 지연 중앙값29ms/p95 36ms/최대43ms, 조기 저장·누락·중복0입니다. 세 환경은 별도 프로세스/공통 입력 시작으로 동시 공급했지만 지연이 증가해 입력24.023초 후 사전 보호 기준으로 자동 중단했습니다. 부분 결과는 북쪽467프레임/19행, 남쪽467/15, 동쪽468/15이며 마지막 지연4.506/8.192/8.175초입니다. 모든 비교 구간은 같은 GPU 비제한 속도 결과와 CSV13열/출입/진단이 일치합니다. 실제 CCTV 입력/장시간 운영/수동 정답 정확도는 미검증입니다. 모델·마스킹·계산·운영 설정과 기존 결과를 보존했으며 전달 disabled·영상 출력 없음입니다. 실제 명령·새 경로·전체 통계·제한·수동 검토 후보는 [PACED_INPUT.md](../../docs/PACED_INPUT.md)를 확인하세요.

**직전 최대 처리속도·초기값 갱신 이력 (2026-10-17):** 북쪽 전체 GPU A/B CSV 저장 시점을 monotonic으로 측정하고 남쪽·동쪽 demo 초기값을3명으로 갱신했습니다. 북쪽은 각2,524프레임/1초105행이며 A 영상 모드와 B 데이터 모드의 CSV·출입·대기·상세 진단이 바이트 일치합니다. 첫 행 저장은 실행 후19.029/15.101초, 처리 루프는83.235/68.194초, 저장 간격 중앙값은0.764/0.632초였습니다. 남쪽·동쪽은 기존 전체 로그로94/90행을 재계산하고 원본을 재렌더링해 최종 내부3/5명·빈칸16/18칸을 확인했습니다. 초기3명으로 고정하지 않으며 실제 범위는2~4/3~8명입니다. 영상 출력 생략은 `--no-video`, 측정은 `--measure-csv-latency`입니다. 모든 실제 실행의 전달은 disabled, 실제 예측모델은 미연동입니다. 기존460개 보호 파일과 운영/마스킹/패키지를 보존했고 관련32개 테스트를 통과했습니다. [LATENCY_INITIAL3.md](../../docs/LATENCY_INITIAL3.md)에 실행 범위·A/B 표·새 CSV/영상·명령·한계가 있으며 [검증 JSON](../../docs/latency_initial3_checks.json)도 있습니다. 저장 파일 최대 처리속도 실험 이력입니다.

**이전 GPU 구성·0~30초 비교 이력 (2026-10-17):** 기존 CPU `.venv`를 보존하고 RTX4060용 `.venv-gpu`를 구성했습니다. Python3.13.9·드라이버610.88·PyTorch2.14.1+cu132에서 실제 CUDA 입력/가중치/출력을 확인했습니다. 북쪽0~30초의 동일 FP32/demo/전달 disabled 비교는 CPU18.73 FPS → GPU25.19 FPS(분석 요약 기준 약1.34배),720프레임·30행이었습니다. CSV는 바이트 일치, 출입2/1·최종 내부30명도 같았습니다. 기존395개 파일과 CPU 패키지 보존·GPU 환경 관련28개 테스트를 확인했습니다. 병목과 정확한 명령·결과 경로는 [GPU_SETUP.md](../../docs/GPU_SETUP.md), 기계 판독 근거는 [gpu_benchmark_checks.json](../../docs/gpu_benchmark_checks.json)에 있습니다. 이번에는 GPU 구성/비교까지만 수행했고 예측모델 개발·실제 연동·Git push는 하지 않았습니다.

고정 CCTV 영상에서 사람을 탐지하고 ByteTrack ID의 이동 순서로 출입을 집계합니다. 외부 대기 행동을 보이는 인원을 추정하고, 초기 내부 인원을 입력하면 내부 체류 인원을 계산합니다. 성별이나 외형으로 이용 목적을 판단하지 않습니다.

**집계/전달 구현 상태 (2026-10-17):** 매 프레임 분석 → 영상 시각별 레코드 → CSV append/flush → 선택적 비동기 전달 → 한국시간 정시 파일 전환을 구현했습니다. demo 기록1초·운영 기록10초와 파일 분할1시간을 별도 설정하며 전달 기본값은 disabled입니다. 앞선 북쪽0~10초 demo+mock에서240프레임·CSV10행·모의 수신10건·미전달0건을 확인했습니다. 실제 예측모델은 연결하지 않았습니다. 전달 구조와 앞선 검증 경로는 [HOURLY_DELIVERY.md](../../docs/HOURLY_DELIVERY.md), 계약은 [PREDICTION_INTEGRATION.md](../../docs/PREDICTION_INTEGRATION.md)에 있습니다.

기존 전체 결과는 `outputs/batch_demo_recalc_20261017_144846_e9dd5976`에 그대로 보존합니다. demo 초기 내부29/18/18명·운영 가능27/19/23칸·평균105초·가상 시작2026-10-14T00:00:00+09:00와 최종 내부25/18/20명은 이전 전체 검증 결과입니다. 공유1초 CSV105/94/90행, 북쪽 영상 재사용·남쪽/동쪽 재렌더링 이력과 여는 명령은 [DEMO_INITIAL18.md](../../docs/DEMO_INITIAL18.md)를 확인하세요. 현재 상태는 [HANDOFF.md](../../docs/HANDOFF.md), 이전 이력은 [FULL_MVP_1S.md](../../docs/FULL_MVP_1S.md)와 [COMPACT_OVERLAY.md](../../docs/COMPACT_OVERLAY.md)에 있습니다. 운영 설정·마스킹·판정 정책과 기존 결과를 보존하며 Git push는 하지 않았습니다.

**GitHub 인계:** 작업 브랜치는 `mvp/busan-cctv-20261014`입니다. 2026-10-14 공유 준비의51개 테스트·의존성 검사와 최초 전체1초 실행의12개 테스트, 초기18명 갱신의13개 테스트는 이전 이력입니다. 현재 인계 기준은 위의2026-10-18 공유 안내와 분석 모듈의83개 테스트/설치 검증입니다. 기존 이력을 보존하는 작업 브랜치의 새 커밋을 사용하며 main을 병합하거나 직접 반영하지 않습니다. 원본영상·모델·출력 자료는 별도 전달이 필요합니다.

**결과 영상 표시:** 작은 한글 수치표는 왼쪽 아래를 기본으로 사용하며 동쪽은 대기열을 피한 오른쪽 아래입니다. 제목·수치4줄·짧은 추정/미설정 상태만 표시하고 기존 사람 ID·대기 상태는 유지합니다. 원본 영상과 위 전체 실행의 확정 추적 로그로 재렌더링하며 CSV·카운팅·계산·마스킹을 변경하지 않습니다. 디자인·위치 설정과 새 영상/미리보기 경로는 [COMPACT_OVERLAY.md](../../docs/COMPACT_OVERLAY.md)를 확인하세요.

## 1. 환경 설치 — Windows PowerShell

지원·검증 기준은 **Windows 11, Python3.13.9**, 기존 CPU `.venv`와 별도 RTX4060 CUDA `.venv-gpu`입니다. GPU 검증 범위는 북쪽0~30초 비교이며 다른 Python 버전·Linux/macOS는 이번 환경에서 검증하지 않았습니다. 아래 기본 설치는 기존 CPU 환경이고 별도 GPU 설치/명령은 [GPU_SETUP.md](../../docs/GPU_SETUP.md)를 사용하세요. PowerShell 명령 앞의 `&`도 포함하며 가상환경 활성화/실행 정책 변경 없이 실행할 수 있습니다.

저장소의 기존 `main`은 보존하며 MVP 코드는 아래 별도 브랜치에 있습니다. 팀원은 프로젝트 폴더가 없는 위치에서 내려받습니다.

```powershell
git clone --branch mvp/busan-cctv-20261014 git@github.com:IRE0330/2026DeepLearning-1.git
Set-Location -LiteralPath '2026DeepLearning-1'
python --version
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m cctv doctor
& .\.venv\Scripts\python.exe -m cctv download-model
```

`python --version`이3.13이 아니거나 명령을 찾지 못하면 Python3.13을 설치/선택하고 터미널을 다시 여세요. `python` 대신 해당 Python 실행 파일 경로를 사용하는 경우에도 같은 `-m venv .venv` 명령입니다. 가상환경에는 실행 폴더 이름이 포함될 수 있으므로 다른 사람의 `.venv`를 복사하지 않습니다.

개발 PC의 기존 `.venv`는 보존·재사용했습니다. 초기에는 설치된 Blender의 Python3.13.9로 표준 `venv`를 만든 이력이 있으며 Blender 패키지는 변경하지 않았습니다. **팀원 설치에 Blender는 필요하지 않습니다.** 위 설치는 같은 Python의 표준 venv/pip 방식입니다. GitHub 준비에서는 새 가상환경을 만들거나 모델/패키지를 다시 다운로드하지 않고 기존 환경의 테스트와 `pip check`를 실행했습니다. 새 팀원 PC에서의 다운로드/설치 성공까지 확인했다는 뜻은 아닙니다.

`requirements-lock.txt`는 기존 CPU 개발 환경의 정확한 패키지 버전, `requirements-gpu-lock.txt`는 새 GPU 환경의 버전이며 `requirements.txt`는 허용 범위입니다. 기존 CPU 잠금 파일은 보존했습니다. `.venv`는 torch2.14.1+cpu/자동 CPU, `.venv-gpu`는 torch2.14.1+cu132/자동 CUDA이며 검증·비교에는 `--device cpu`/`--device cuda:0`을 명시합니다. 다른 패키지 버전이나 장치에서는 짧은 실행을 다시 검증하세요.

**Git에 포함되지 않는 자료:** 원본영상, MICC/압축파일, 가중치, `.venv`, `outputs/`, `inspections/`, 설정 미리보기 이미지. 이 자료들은 별도로 준비해야 합니다. `download-model`은 실제 구현·실행 확인된 가중치 준비 명령이며 `models/yolo11n.pt`로 저장합니다. 이미 별도 전달받은 같은 가중치가 있으면 그 경로에 배치해도 됩니다. 분석은 가중치를 자동 다운로드하지 않습니다.

GPU 사용은 별도 `.venv-gpu`를 선택합니다. 기존 `.venv`에 CUDA 패키지를 덮어쓰지 않습니다. 공식 설치 방법, 실제 CUDA 텐서/NMS 검사, 같은 북쪽 구간의 CPU/GPU 수치와 남은 병목은 [GPU_SETUP.md](../../docs/GPU_SETUP.md)를 확인하세요. `--device cuda:0`을 지정했는데 지원되지 않으면 CPU로 조용히 바꾸지 않고 오류를 냅니다.

## 2. 영상 준비와 확인

과거 CPU 전체 처리 실측의 북쪽87.61초/남쪽134.71초는 당시 실행 이력입니다. 최신 장치 비교는 동일한 현재 코드·북쪽0~30초로 다시 측정한 CPU18.73 FPS/GPU25.19 FPS입니다. 전체 원본 PTS 검사와 CPU 디코딩/오버레이/영상 인코딩도 시간을 사용합니다. GPU 장치 전환 자체가 정확도 개선이나 세 CCTV 동시 실시간 처리를 뜻하지 않습니다.

개발 PC에서 확인한 영상은 다음과 같습니다. GitHub에 영상은 없으므로 별도로 전달받아 프로젝트 최상위에 배치하면 기존 설정을 사용할 수 있습니다. 다른 위치라면 환경 JSON의 `video`와 영상 목록 JSON의 `video`를 같은 프로젝트 상대 경로로 지정하세요. 경로는 터미널 위치가 아니라 프로젝트 폴더 기준입니다. 다른 원본으로 교체했다면 새 영상ID/해시와 구도를 확인해야 합니다.

| 환경 | 설정 | 영상 | 해상도 / FPS / 프레임 / 재생시간 |
|---|---|---|---|
| north 북쪽 여자 화장실 | `configs/north.json` | `북쪽_화장실_cctv.mp4` | 1280×720 / 24 / 2524 / 약 105.167초 |
| south 남쪽 여자 화장실 | `configs/south.json` | `남쪽 화장실_CCTV.mov` | 1920×1080 / 30 / 2827 / 약 94.233초 |
| east 동쪽 여자 화장실 | `configs/east.json` | `동쪽_화장실_cctv.mov` | 1920×1080 / 30 / 2700 / 90초 |

북쪽은 사용자가 새 영상을 선택했으며 실제 파일명을 설정에 반영했습니다. 새 영상의 전체 PTS 검사 보고서는 `inspections/north_new_video_20261014_165129_0765e720/video_info.json`입니다. 이전 `북쪽_최종.mp4`의 2257프레임/94.042초 기록과 ID 6 사례는 이전 영상의 이력이며 현재 영상의 결과로 해석하지 않습니다. 영상 ID는 원본 SHA-256에 연결해 설정에 저장합니다.

`configs/environment_c.json`과 `ground_truth/environment_c`는 기존 미사용 자료로 보존했습니다. 좌표와 정답 행이 없고 영상 경로도 존재하지 않아 동쪽 데이터라는 근거가 없습니다. 운영 환경 이름과 새 양식은 north·south·east를 사용합니다. 사용자 제공 동쪽 실제 파일을 전체 PTS 검사하고 0·45·89.967초 대표 이미지를 확인했습니다. 기록은 `inspections/east_20261014_113926_c1ff1011/video_info.json`입니다. 대표 이미지에서 통행인은 보이지만 출입·퇴장·대기 행동이 확인됐다고 단정하지 않습니다.

전체 프레임의 PTS 간격을 검사한 결과 세 영상은 고정 FPS입니다. **행동을 전체 프레임에서 수동 확인했다는 뜻은 아닙니다.** 시작·중간·끝 이미지를 확인했으며 북쪽에서 줄과 출입구가 함께 보여 개발 대상으로 선정했습니다. 출입 순서, 퇴장, 가림, 카메라 움직임이나 인물의 비정상 생성·소멸은 전체 영상을 추가로 검토해야 합니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv inspect --video '북쪽_화장실_cctv.mp4' --label north
& .\.venv\Scripts\python.exe -m cctv inspect --video '남쪽 화장실_CCTV.mov' --label south
& .\.venv\Scripts\python.exe -m cctv inspect --video '동쪽_화장실_cctv.mov' --label east
```

터미널에 표시된 `inspections\north_날짜_고유번호` 같은 폴더에 `start_*.jpg`, `middle_*.jpg`, `end_*.jpg`, `video_info.json`이 생성됩니다. 영상 교체 시 구도가 같은지 확인하세요. 종횡비가 바뀌면 분석을 거부합니다. 같은 종횡비라도 카메라 위치가 달라지면 구역을 다시 지정해야 합니다.

FPS가 없거나 PTS가 불규칙한 VFR 영상은 분석을 거부합니다. FFmpeg가 설치된 컴퓨터에서 새 파일 이름으로 변환한 뒤 설정의 `video`를 바꾸고 구역을 확인하세요. 이 컴퓨터에서는 FFmpeg 명령이 발견되지 않았습니다.

```powershell
ffmpeg -i '원본.mov' -vf 'fps=30' -an -c:v libx264 -crf 18 'data\변환_CFR.mp4'
```

## 3. 마우스 구역 설정

이전 영상·confirmed만 집계하던 정책의 마스크 점검은 [NORTH_MASK_RETEST.md](../../docs/NORTH_MASK_RETEST.md)에 보존했습니다. 당시 표지 그림 오탐 하단점이 제외 마스크 아래에 남는 문제를 확인했습니다. 이후 사용자가 구역을 다시 저장했으므로 현재 마스크는 현재 영상에서 별도로 확인해야 합니다. 마스크는 영상 픽셀을 지우지 않고 박스 하단 중앙점으로 규칙에서 제외합니다.

이전 영상의 ID 6 미집계에서는 박스 하단 변화와 ID 대상 변경을 확인했습니다. [ID 6 원인 점검](../../docs/NORTH_ID6_REVIEW.md)의 0.167초 상한은 **당시 영상과 당시 경계**의 기록으로 현재 새 영상/구역에 그대로 적용하지 않습니다. 구역 검토 없이 `side_confirm_s`를 먼저 낮추지 마세요. 남쪽·동쪽으로 확대하기 전에 북쪽의 실제 발 기준점과 경계·양쪽 확인 구역을 검토합니다.

먼저 북쪽 영상에 맞게 지정합니다. 검증 전 예시 좌표를 자동으로 채우지 않았으며 모든 환경 설정은 독립적입니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv configure --config configs/north.json --time 0 --max-width 1100 --max-height 620
```

창의 그림 부분을 왼쪽 마우스로 클릭합니다. 다각형은 둘레를 따라 시계 또는 반시계 방향으로 점을 찍고, 첫 점을 마지막에 다시 찍지 마세요. 창에는 전체 프레임이 축소 표시되고, 좌표는 표시 크기에서 원본 크기로 변환된 후 0~1 값으로 저장됩니다. 기준 원본 해상도와 선택 프레임 시각도 저장됩니다.

| 순서 | 항목 | 지정 방법 |
|---|---|---|
| 1 | `boundary` | 실제 출입 통로를 가로지르는 유한한 선분: 두 점 |
| 2 | `entry_direction` | 외부에서 내부로 향하는 화살표: 시작·끝 두 점; 경계를 가로질러야 함 |
| 3 | `outside_zone` | 사람이 바깥에 있음을 확인할 수 있는 바닥 영역: 세 점 이상 |
| 4 | `inside_zone` | 경계를 지난 안쪽 방향을 확인할 수 있는 영역: 세 점 이상 |
| 5 | `waiting_zone` | 줄의 사람 발 위치가 들어오는 외부 대기 영역: 세 점 이상 |
| 6 | `transit_zone` | 선택 사항. 일반 통행 구역은 대기 판정에서 제외; 필요 없으면 점 없이 N |
| 7 | `excluded_zones` | 표지 그림·광고 등 제외 영역: 세 점 이상; N으로 여러 다각형 추가 가능 |

확인 구역은 경계 양쪽 완충 간격 바깥에 있어야 합니다. 경계 좌표 흔들림을 걸러낼 간격의 초기값은 정규화 거리 0.005입니다. 박스의 **하단 중앙점** 기준으로 지정하세요. 북쪽 첫 프레임에서 표지의 사람 그림도 탐지되었습니다. 표지 그림의 박스 하단 중앙점이 들어오는 작은 제외 영역을 지정하고, 실제 사람의 발까지 함께 제외하지 않도록 미리보기를 확인하세요. 광고 화면도 사람 이미지가 나타날 수 있습니다.

| 키 | 기능 |
|---|---|
| N | 입력 점을 현재 항목에 적용하고 다음으로 이동; 제외 다각형은 추가 후 같은 항목 유지 |
| Tab / B | 다음 / 이전 항목으로 이동; 적용하지 않은 점은 버림 |
| U / 오른쪽 클릭 | 방금 입력한 점 하나 취소 |
| R | 현재 항목의 저장된 좌표와 입력 점 초기화; 제외 항목이면 모든 제외 다각형 초기화 |
| P | 입력 검사 및 전체 오버레이 미리보기 확인 단계 |
| S | P 후 화면을 검토한 사용자의 확인으로 저장; `configured: true` 설정 |
| Q / Esc | 저장하지 않고 종료 |

**P로 검사한 화면을 직접 검토한 다음 S를 눌러야 분석에 사용할 수 있습니다.** P 단계의 오류는 터미널에도 출력됩니다. GUI 안내는 영어이며 위 표를 참고하세요. 저장하면 설정 옆에 `.preview.jpg` 이미지가 생성됩니다. 재설정 중 종료하면 기존 파일은 유지됩니다. 창 크기를 조절하려면 `--max-width`, `--max-height`로 다시 실행하세요.

```powershell
& .\.venv\Scripts\python.exe -m cctv validate --config configs/north.json
& .\.venv\Scripts\python.exe -m cctv preview --config configs/north.json --time 5
```

`preview`는 창 없이 새 `inspections` 폴더에 이미지를 저장합니다. GUI 없는 환경에서도 사용자 확인이 끝난 JSON 설정을 읽어 분석할 수 있습니다. `configured`만 바꿔 좌표 검토를 건너뛰지 마세요. 내부 방향 확인 구역이 보이지 않는 구도는 출입을 충분히 확인할 수 없다는 한계가 남습니다.

초기 내부 인원을 모르면 `initial_inside`를 `null`로 둡니다. CSV의 내부 인원 칸이 비고 순유입만 계산됩니다. 정확히 0명임을 아는 경우만 `0`을 입력하세요. 부분 분석이면 **그 구간의 실제 시작 프레임 시점** 인원입니다.

## 4. 짧은 구간 분석

구역을 저장한 다음 실행합니다. `--start`는 포함, `--end`는 제외입니다. 영상 시각은 0초부터 시작하며 영상 PTS의 시작 오프셋을 제외한 프레임 번호/FPS를 사용합니다. 프레임 번호는 0부터 시작합니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --start 0 --end 10
```

매 실행마다 `outputs\north_날짜_고유번호` 폴더를 만듭니다. 이전 결과를 덮어쓰지 않습니다. 터미널의 **결과 폴더** 경로를 확인하세요.

| 파일 | 내용 / 확인 방법 |
|---|---|
| `annotated.mp4` | 원본 해상도·FPS 유지. 더블클릭해 박스, ID, 빨간 하단점, 구역, 집계를 확인. 오디오는 포함하지 않음 |
| `events.csv` | 입장 `entry` / 퇴장 `exit`, ID, 프레임, 위치, 판정 확정 영상 시각 |
| `timeseries.csv` | 기존 열 유지. 관측 대기는 후보+확정이며 후보/확정 관측 수·내부 대기·통합 Q·가정 예상시간을 뒤에 추가 |
| `usage_summary.csv` | 한국어13열·UTF-8 BOM·설정 간격마다1행 추가/flush. MVP1초·운영10초. 간격 미만이면 헤더만 저장 |
| `interval_details.jsonl` | 기록 번호/간격, 구간 원본 경계/소스 시각, 누적 출입, 외부/내부 대기, Q, 빈 칸 추정, 예상 대기시간과 계산 가정 |
| `final_usage_detail.json`, `remainder.json` | 마지막 처리 프레임 상태와 정기 CSV에 포함하지 않은 잔여 구간 |
| `final_state.json` | 마지막 처리 프레임의 최종 상태; 초 단위 CSV 마지막 행과 다를 수 있음 |
| `diagnostics.jsonl` | 탐지 박스, 신뢰도, 추적 ID, 관측·유실·재관측, 상태 변화와 출입 근거. 한 줄이 JSON 한 개 |
| `summary.json` | 완료/실패, 처리 범위·속도, 실제 장치, 버전, 모델 SHA-256, 이상 건수, 출력 전체 디코딩 검증 |
| `config_used.json` | 실행 당시 설정 사본 |

CSV는 UTF-8 BOM이며 Excel에서 열 수 있습니다. `inside_estimate`가 빈 값이면 미설정입니다. 음수이면 원시 계산값을 유지하고 `negative_inside` 상태를 기록합니다. `inside_estimate = initial_inside + entries - exits`, `net_inflow = entries - exits`입니다. 내부 인원은 변기 칸 점유 수가 아니며 평균 이용시간으로 차감하지 않습니다.

영어 영상 오버레이의 `Entry/Exit`는 누적 입장/퇴장, `Waiting observed`와 `External waiting total/grace`는 외부 관측·합계·가림 유예, `Net/Inside`는 순유입·내부 인원입니다. `Q`는 외부+내부 추정 대기, `Free stalls`는 빈 칸 추정, `Assumed wait`는 사용자 공식의 예상 대기시간입니다. 계산할 수 없으면 unknown/None입니다. `uncertain_grace_suppressed`는 아래 중복 가능성 때문에 가림 유예 집계를 억제한 상태입니다.

구역을 아직 지정하지 않고 탐지·추적부터 확인하려면 다음을 실행할 수 있습니다. 이 모드는 실제 영상에서 동작하지만 **출입·대기 인원은 계산하지 않습니다.** `events.csv`, `timeseries.csv`는 헤더만 있고 영상에도 집계하지 않는 상태가 표시됩니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv baseline --config configs/north.json --start 0 --end 10
```

## 5. 전체 분석과 판정 기준

짧은 구간에서 경계 통과·되돌아감·대기·통행인 오인과 제외 구역을 확인한 다음 전체 분석하세요.

```powershell
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json
```

기본은 모든 프레임을 순서대로 처리합니다. 실행이 느려도 대기·가림 판정 시간은 영상 시간입니다. 정수 초 CSV에는 그 시각 이하의 가장 최근 상태만 기록하며 미래 프레임을 앞선 초에 사용하지 않습니다. 예를 들어 10.03초 프레임이 도착해도 10초 표본은 10초 이하 프레임에서 가져옵니다. `sample_time_s`와 `source_time_s`를 구분하세요. 최종 상태는 따로 저장합니다.

출입은 확인 구역에서 일정 시간 관측한 뒤 유한 선분을 통과하고 반대쪽 확인 구역에서 다시 관측해야 확정됩니다. 최초부터 내부에 있거나 화면에서 사라지는 것만으로 입장을 추측하지 않습니다. 확인되지 않은 가림 공백은 미확정으로 남깁니다. ID가 실제 퇴장 후 재입장하면 새 이벤트를 기록합니다. `events.csv.video_time_s`는 **판정 확정 시각**이며 평가도 이 시각을 사용합니다. `crossing_time_estimate_s`는 두 관측점 사이에서 선분을 지난 시각의 선형 추정값이며 별도 의미입니다.

대기 상태는 `nonwaiting → candidate → confirmed`입니다. 0.2.0부터 candidate는 영상에 표시하되 대기 합계에서 제외합니다. 영상 시각으로 연속 관측된 3.5초의 정지·느린 이동 증거와 구간 평균 속도 조건을 만족해야 confirmed가 됩니다. 가려진 시간은 증거에 포함하지 않으며 confirmed에만 기존 1.5초 가림 유예를 적용합니다. 짧은 전진을 유지하고 지속 이탈 0.8초 또는 입장 확정으로 종료합니다. 3.5초는 현재 MVP 설정값으로 잠깐 멈춘 통행인도 대기로 오인할 수 있습니다. [수정과 전체 검증](../../cctv-analysis/docs/WAITING_35S.md)을 확인하세요.

관측 외부 대기 = `waiting_confirmed_observed` = `waiting_observed`입니다. 전체 외부 대기 = 관측 confirmed + 중복 억제 후 `waiting_grace` = `waiting_total`입니다. 후보 수 필드는 별도로 유지합니다. 표지 그림 오탐이나 박스 하단 흔들림은 구역/탐지 검토가 필요합니다.

| 설정 항목 (`rules`) | 초기값 | 의미 |
|---|---|---|
| `side_confirm_s` | 0.2초 | 확인 구역의 연속 관측시간 |
| `boundary_margin` | 0.005 | 정규화 화면 좌표에서 경계와의 완충 거리 |
| `max_observation_gap_s` | 0.25초 | 이보다 긴 시간 간격 또는 한 프레임이라도 ID 관측 유실이 있으면 출입 경로를 초기화 |
| `waiting_confirm_s` | 3초 | 관측된 느린 이동 증거 확정시간; 속도 계산 초기 구간 때문에 실제 확정은 더 늦을 수 있음 |
| `occlusion_grace_s` | 1.5초 | 확정 대기자의 가림 유예; 초과 시 해제 |
| `zone_exit_s` | 0.8초 | 관측된 구역 이탈을 유지해야 확정 대기 종료 |
| `motion_window_s` / `motion_min_span_s` | 1초 / 0.3초 | 이동량 평가 창 / 최소 관측 길이 |
| `slow_speed_body_heights_s` | 0.35 | 관측 경로 길이를 박스 높이로 보정한 초당 이동량; 물리적 m/s가 아님 |
| `duplicate_radius_body_heights` | 0.7 | 유실 대기자 주변 관측 ID가 있을 때 유예 집계 억제 반경 |
| `forget_track_s` | 60초 | 오래 관측되지 않은 규칙 상태 삭제 |

모두 개발 영상 검증용 초기값이며 과학적으로 확정된 이용 목적 기준이 아닙니다. 저 FPS 영상에서 `max_observation_gap_s`가 프레임 간격보다 짧으면 경로가 매번 초기화되므로 조정이 필요합니다. 정규화 화면 거리에는 원근·실거리 보정이 없습니다.

서로 다른 ID는 병합하지 않습니다. 유실된 확정 대기자의 마지막 위치 근처에 **어떤 관측 ID라도** 있으면 이전 ID의 유예 인원을 그 프레임에서 집계하지 않고 불확실 상태를 표시합니다. 새 관측 ID가 candidate라면 그 후보는 관측 인원에 포함하되 이전 ID 유예를 더하지 않습니다. 주변 동행인이나 통행인 때문에 억제가 생길 수 있고, 실제 다른 사람이 멀리 분리되거나 동시에 중복 탐지되면 과대 집계도 남습니다. 이 정책은 재식별 성공을 의미하지 않습니다.

기본 모델은 CPU에서도 실행 가능한 소형 사전학습 YOLO11n이며 추가 학습은 하지 않습니다. `model`을 다른 로컬 가중치 경로로 바꿀 수 있습니다. person 클래스(0)만 탐지합니다. 탐지 신뢰도 0.1, ByteTrack 상위 0.25 / 하위 0.1 / 새 ID 0.25로 낮은 신뢰도 검출을 추적의 두 번째 매칭에 전달합니다. [공식 추적 문서](https://docs.ultralytics.com/modes/track/)와 [기본 ByteTrack 설정](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/trackers/bytetrack.yaml)을 확인했고, 실제 설치된 API를 실행 검증했습니다. `track_buffer: 30`은 처리 프레임 수로, 북쪽에서는 1.25초·남쪽에서는 1초입니다. 규칙의 가림 유예와 서로 다른 설정입니다. 실행마다 모델·ByteTrack·규칙 상태를 새로 만듭니다.

오류 개선은 탐지(해상도·신뢰도), 추적(ID 유실 의심·버퍼), 규칙(구역·방향·체류) 순서로 진단하세요. 로그만으로 실제 사람이 누락됐거나 두 ID가 같은 사람이라고 확정하지 않습니다. 설정 오류와 모델 오류를 구분하기 전에 학습부터 시작하지 않습니다.

## 6. 수동 정답 작성

실제 양식은 `ground_truth\north`, `south`, `east`에 있습니다. 기존 `environment_c` 양식도 보존했습니다. `example_only`는 설명용 가상 값이며 평가 명령에서 거부합니다. 실제 폴더의 빈 파일에 예시 행을 복사해 정답으로 사용하지 마세요.

```powershell
& .\.venv\Scripts\python.exe scripts/make_truth_templates.py
```

이 명령은 누락된 양식만 만들고 기존 정답을 보존합니다. 영상 플레이어에서 원본 또는 결과 영상을 확인하여 CSV를 작성하세요. 영상 시각은 원본 기준 초 단위입니다. 부분 결과 영상의 플레이어가 0초부터 보이면 원본 분석 시작 시각을 더해야 합니다.

| 파일 | 입력 열 | 작성 원칙 |
|---|---|---|
| `events.csv` | `restroom_id,video_time_s,direction` | `north` 등 환경 ID; direction은 entry/exit. 지정한 반대 확인 구역에 도달·확정한 영상 시각 기준으로 일관되게 작성 |
| `waiting.csv` | `restroom_id,video_time_s,waiting_count` | 후보 포함 정책: 확인 가능한 정수 초에서 대기 구역에 관측된 후보/확정 대상 사람과 근거 있는 확정 가림 유예를 포함. 모르는 시각은 행을 만들지 않음 |
| `inside.csv` | `restroom_id,video_time_s,inside_count` | 내부 인원을 실제로 아는 시점에만 작성. 입구 영상만으로 모르면 비워 둠 |

출입 정답의 `video_time_s`는 경계를 넘는 순간이 아니라 **반대 확인 구역에서 연속 관측이 `side_confirm_s`(기본 0.2초)를 충족한 첫 프레임 시각**입니다. 외부→경계→내부는 entry, 내부→경계→외부는 exit로 작성합니다. 가림 때문에 순서를 확인할 수 없으면 완전한 출입 정답 구간으로 지정하지 마세요. `crossing_time_estimate_s`는 경계 통과의 추정값이므로 정답 CSV 시각으로 복사하지 않습니다. 출입이 없었던 구간도 CSV를 비워 두며 현재 평가는 빈 정답에 수치를 생성하지 않습니다.

`metadata.json`도 직접 편집합니다. 실제 양식의 `is_example`은 false입니다. `events_complete`는 지정 구간의 출입 정답을 **빠짐없이** 작성한 경우에만 true로 바꾸고 `annotated_start_s`, `annotated_end_s`를 입력하세요. 일부 사례만 적으면 Recall이나 False Positive를 제대로 평가할 수 없어 출입 지표를 생략합니다. `initial_time_s`와 `initial_inside`에는 내부 인원 평가의 기준 시점과 아는 초기 인원을 입력하세요. 기준 시점은 실행의 `summary.json.actual_start_s`와 같아야 합니다.

Excel에서 저장할 때 CSV UTF-8 형식을 선택하고 헤더 철자와 소수점을 유지하세요. 대기·내부 인원은 0 이상의 정수입니다. 빈 셀 대신 모르는 정답의 행을 삭제하세요. 정답은 환경별로 따로 작성합니다.

새 대기 정답은 3.5초 이상 실제 관측된 정지·느린 이동 후 확정된 외부 대기 기준으로 작성하며 candidate를 포함하지 않습니다. 짧은 전진·이탈 유지와 확정자 가림 유예를 적용하되 동일 인물을 중복 세지 않습니다. 가림 동일인을 확인할 수 없으면 해당 정답 행은 비워 두세요. 알고리즘 출력은 정답으로 복사하지 않습니다. `metadata.json.waiting_count_policy`는 `confirmed_observed_plus_confirmed_grace_3p5s_v4`입니다. 기존 정책으로 작성한 정답은 보존하고 별도 재검토해야 하며 정책이 다른 정답의 MAE 계산은 거부합니다.

## 7. 평가

`--run`에 **집계 분석** 결과 폴더를 입력합니다. baseline은 평가할 수 없습니다. 아래 `실제_결과폴더명`을 본인 폴더로 바꾸세요.

```powershell
& .\.venv\Scripts\python.exe -m cctv evaluate --run 'outputs\실제_결과폴더명' --truth ground_truth/north --tolerance 1
```

평가 결과는 해당 실행 폴더의 `evaluations\evaluation_날짜_고유번호\metrics.json`에 저장됩니다. 이 영상들은 모두 **개발 영상**이며 결과도 `development_video_only`로 표시합니다. 별도의 새 영상 검증 전에는 일반화 정확도로 해석하지 마세요.

출입은 같은 방향에서 ±1초 허용으로 시간순 일대일 대응하여 최대 매칭 수를 확보합니다. 정답/예측 하나를 여러 번 사용하지 않습니다. Precision=TP/(TP+FP), Recall=TP/(TP+FN), F1=2TP/(2TP+FP+FN)이며 각 분모 0은 JSON의 `null`입니다. 전체 출입 정답이 없거나 비어 있으면 출입 성능 수치를 만들지 않습니다.

대기 MAE는 정답과 예측의 **동일 시각** 표본만 사용합니다. 없는 정답을 0명으로 간주하지 않습니다. 매칭 표본 수, 정답은 있지만 예측이 없는 표본 수, 정답이 없는 예측 표본 수를 함께 보고합니다. 내부 인원 MAE는 같은 초기 인원·기준 시각이 확인되어야 계산합니다. 수동 내부 정답이 없으면 그 구간 전체 출입 정답과 초기값이 확인된 경우만 내부 정답을 계산합니다. 실제 마지막 프레임 시각의 내부 정답이 있을 때만 종료 오차를 계산하며 마지막 정수 초 오차와 구분합니다.

## 8. MICC 보조 점검

```powershell
& .\.venv\Scripts\python.exe -m cctv micc-inspect --path data/micc
& .\.venv\Scripts\python.exe -m cctv micc-track --rgb data/micc/micc_crowd_counting/Flow/RGB --start-frame 80 --frames 60
```

다운로드·압축 해제는 완료되었습니다. 다시 다운로드할 필요가 없습니다. 폴더 입력은 기존에도 지원했으며 이번에 설명·평가 코드·정답 샘플·RGB/깊이 이미지 형식 검사를 보완했습니다. 실제 루트는 `data/micc/micc_crowd_counting`입니다. 검사 결과는 `inspections/micc_20261014_112925_a7b18a08/micc_inventory.json`입니다.

Flow·Queue·Groups마다 `RGB/*.png`, `depth/*.png`, `GT_dat/*.dat`가 있습니다. RGB 샘플은 640×480 uint8 3채널, 깊이는 640×480 uint16입니다. 동봉 설명과 실제 정답에서 **머리 박스 `x y w h`**를 확인했습니다. 정답 행 수는 평가 코드의 인원수 근거이고, 추적 ID 열은 없습니다. 전신 person 박스와 직접 비교하거나 화장실 출입·대기 정답으로 변환하지 않습니다. 깊이 단위와 RGB 정합은 미확인입니다. Flow는 RGB 1266장, 정답 1260개로 마지막 6장의 정답이 없으며 자동으로 채우지 않습니다.

원본 FPS·타임스탬프는 포함된 설명과 평가 코드에서 확인하지 못했습니다. `micc-track`는 파일명 숫자 순서로 연속 프레임을 처리하고, 누락 번호가 있으면 거부합니다. `.DS_Store`와 `._*`는 데이터에서 제외합니다. 출입·대기·내부 판정을 호출하지 않습니다. `tracks.csv`와 `diagnostics.jsonl`의 시각 기준은 `source_frame_number`이며 초를 생성하지 않습니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv micc-track --rgb data/micc/micc_crowd_counting/Queue/RGB --start-frame 140 --frames 180
& .\.venv\Scripts\python.exe -m cctv micc-track --rgb data/micc/micc_crowd_counting/Groups/RGB --start-frame 360 --frames 180
```

각 실행은 새 `outputs/micc_*_sequence_날짜_고유번호`에 저장합니다. `preview.mp4`는 기본 **임의 12 FPS의 시각 점검용**이며 원본 시간·속도·대기시간을 나타내지 않습니다. `frame_*.jpg`에서 박스·ID를, `summary.json`에서 실제 장치·처리 프레임·출력 전체 재디코딩을 확인하세요. 짧은 실행과 세 시퀀스의 각 180프레임 실행은 완료됐습니다. 대표 이미지와 각 12프레임 연속 구간을 직접 확인했지만 전체 실행 구간의 시각 검토는 미완료입니다. 의자 오탐·가림으로 발 기준점이 어긋나는 사례를 `docs/VALIDATION.md`에 기록했습니다. 정량 평가·추가 학습·자동 정답 변환은 하지 않았습니다.

## 9. 다른 화장실에 적용

남쪽은 여자 화장실 동선만 따로 설정하고 남자 화장실·일반 통로는 출입 구역에 포함하지 마세요. 북쪽 좌표를 복사하지 않습니다. 환경별 상태와 결과는 독립적입니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv configure --config configs/south.json --time 47
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/south.json --start 40 --end 50
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/south.json
& .\.venv\Scripts\python.exe -m cctv evaluate --run 'outputs\남쪽_실제_결과폴더명' --truth ground_truth/south
```

동쪽 실제 경로는 `configs/east.json`에 반영했습니다. 동쪽 여자 출입구와 일반 통행·남자 출입구를 구분하여 별도로 지정하세요. 벽의 사람 그림도 박스 하단 기준으로 제외해야 합니다. 사용자 좌표 없이 `configured`만 true로 바꾸지 마세요.

동쪽 40~50초 baseline은 `outputs/east_baseline_20261014_113957_370b4f63`에 있습니다. 원본 45초에 해당하는 `review_original_45s.jpg`를 직접 확인해 여자 출입구 옆 **소화기가 person으로 탐지되는 오탐**을 발견했습니다. 제외 구역은 오탐 박스의 하단 중앙점 위치를 포함하되 실제 출입자의 발 위치를 가리지 않도록 작게 지정·검토하세요. 사람 그림은 원본에서 보이는 설정 주의점이며 이 표본에서 오탐됐다고 단정하지 않습니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv inspect --video '동쪽_화장실_cctv.mov' --label east
& .\.venv\Scripts\python.exe -m cctv configure --config configs/east.json --time 0 --max-width 1100 --max-height 620
& .\.venv\Scripts\python.exe -m cctv validate --config configs/east.json
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/east.json --start 0 --end 10
```

북쪽 실제 카운팅을 먼저 검증한 뒤 남쪽·동쪽으로 확장합니다. 각 환경에서 구역을 저장하고 `validate`와 `preview`를 실행한 다음, 실제 입장·퇴장·대기가 있는 구간을 골라 짧은 분석을 하세요. 0~10초는 첫 실행 확인용일 뿐이며 그 구간에 없는 행동은 검증 완료로 보고하지 않습니다. 오류를 수정하고 가능하면 전체 분석, 별도 수동 정답, 평가로 진행합니다. 카메라 구도가 다른 설정은 반드시 각각 지정합니다.

핵심 테스트 실행 명령:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`cctv/core.py`는 OpenCV와 모델 없이 동작하며, `pipeline.analyze()`는 향후 다른 UI에서 호출할 수 있습니다. 이번 추가 요구로 사용자 가정에 따른 초기 예상 대기시간 공식만 구현했습니다. 서버·웹 UI·미래 혼잡도 예측·혼잡도 등급·추가 학습은 구현 범위에 포함하지 않습니다. `.gitignore`는 영상, 모델, MICC, 가상환경, 캐시와 결과를 제외합니다.

## 10. 등록 영상 일괄 실행과 MVP1초·운영10초 CSV

북쪽1초 기록의 짧은 점검이 필요하면 아래 명령을 사용합니다. 0~10초만 분석하며 기록10개를 새 결과 폴더의 `usage_summary.csv`에 저장합니다. 전체 길이 결과는 아래 batch 명령을 사용하세요. PowerShell에서 프로젝트 폴더를 연 상태로 실행합니다. 기본 프로필은 `operating`(10초)이며 `--profile demo`를 지정해야 MVP1초가 적용됩니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 10
```

화장실별·시간별 CSV를 생성하는 전체 일괄 시연/운영 명령은 아래와 같습니다. 등록된 세 영상을 순서대로 첫 프레임부터 마지막 프레임까지 처리합니다. 세 CCTV 동시 실시간 처리는 구현하지 않았습니다. 전체 실행에는 `--limit-seconds`나 등록 항목의 `end_s`를 지정하지 않습니다. 전달 기본값은 disabled입니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv batch --registry configs/video_registry.json --profile demo
& .\.venv\Scripts\python.exe -m cctv batch --registry configs/video_registry.json --profile operating
```

매 실행은 새 `outputs/batch_프로필_날짜_고유번호` 폴더를 만듭니다. **목록에 등록한 영상만** 순서대로 처리하며 다른 폴더의 영상을 자동 검색하지 않습니다. `batch_summary.json`의 `completed_count`, `failed_count`, 각 `results[].error`를 확인하세요. 한 항목이 실패해도 다음 항목을 실행하고, 실패가 포함되면 CLI는 종료코드 2를 반환합니다. 목록/프로필 구조 오류 등 실행 전 오류는 종료코드 1입니다. 완료한 영상마다 `videos/entry_번호/환경_날짜_고유번호` 아래에 결과 영상·이벤트·시계열·진단·설정·최종 상태를 저장합니다. 미설정 항목에는 `videos/entry_번호/result.json`에 이유를 남깁니다. 추적 ID·누적 출입·내부 인원은 독립 영상마다 초기화하며 이전 영상의 값을 자동으로 이어받지 않습니다.

### 영상 목록에 등록하기

VS Code에서 `configs/video_registry.json`을 열고 `videos` 배열을 편집하세요. 현재는 north/south/east의 기존 영상 3개만 명시적으로 등록돼 있습니다. 항목의 필수 정보는 아래와 같습니다. 설명용 값이며 실제 촬영시각이나 정답으로 복사하지 마세요.

```json
{
  "restroom_id": "north",
  "video": "사용자가_준비한_새_영상.mp4",
  "config": "configs/north.json",
  "video_id": "north_새로운_영상_식별자",
  "capture_start_time": null,
  "capture_time_kind": null,
  "initial_inside": null,
  "start_s": 0,
  "end_s": null
}
```

같은 화장실 영상도 항목을 여러 개 등록할 수 있습니다. 배열 안의 항목 사이에는 쉼표가 필요하고 마지막 항목 뒤에는 쉼표를 붙이지 않습니다. Windows 전체 경로는 `/`를 사용하거나 역슬래시를 `\\`로 입력하세요. 상대 경로는 프로젝트 기준입니다. 환경 설정에는 해당 영상 구도의 사용자 마스킹과 판정 기준이 있어야 합니다. 구도가 다르면 기존 설정을 보존한 별도 환경 설정 파일을 만들고, 그 파일을 `config`로 지정해 직접 마우스로 설정하세요. 화장실ID는 해당 설정의 ID와 같아야 합니다.

동일 원본 영상의 반복 실행에는 **같은 video_id**를 사용합니다. 영상 교체 시 새 ID를 사용하세요. 같은 ID·같은 경로·동일 내용 해시의 중복 등록은 오류로 남기고 재실행/중복 기록을 막습니다. 기존 3개 항목에는 SHA-256도 저장해 파일 교체를 검사합니다. 새 영상 항목의 `video_sha256`은 선택사항이며, 없으면 실행 시 실제 해시를 계산해 `config_used.json`에 저장합니다. 같은 기존 ID를 재사용하면서 환경 설정의 원본 내용과 달라지면 거부합니다.

일괄 분석은 환경 설정 → 영상 목록 → 선택 프로필 순으로 적용합니다. operating에서는 **초기 내부 인원·촬영시각에 영상별 목록 값**을 사용하고, demo는 나중에29/3/3명과 가상 시작시각을 덮어씁니다. 로그 재계산도 과거 설정 뒤에 현재 demo를 적용합니다. `initial_inside`는 해당 영상의 실제 분석 시작 시점에 아는 인원으로 입력하고, 모르면 null입니다. 정확히 0명임을 확인했을 때만 0을 씁니다. `start_s`/`end_s`는 선택사항으로 원본 영상 기준 초이며, `--limit-seconds`는 각 시작 시점부터 최대 분석 길이를 제한합니다. 날짜를 알면 `capture_start_time`을 시간대가 포함된 ISO 시각으로 입력하고 실제 촬영은 `capture_time_kind: "real"`, 가상 시나리오는 `"virtual"`로 지정합니다. 시각을 모르면 두 항목을 null로 둡니다. 파일/실행 시각으로 대신하지 않습니다.

환경별 **총칸 수**는 `configs/north.json`, `south.json`, `east.json`의 `total_stalls`, **운영 가능 칸 수**는 기존 `available_stalls`, 평균 이용시간은 `average_stall_use_s`입니다. 현재 총칸 수/운영 가능 칸 수는 북쪽27/27, 남쪽19/19, 동쪽23/23이며 폐쇄·고장 칸이 없다는 사용자 가정입니다. 향후 폐쇄 칸이 생기면 총칸 수를 보존하고 `available_stalls`만 변경할 수 있습니다. 계산은 총칸 수나 현재 빈 칸 추정치가 아니라 `available_stalls`를 사용합니다. 평균105초는 모든 환경의 사용자 지정 계산 가정이며 실측 검증값이 아닙니다. 특정 영상의 당시 값이 다르면 목록 항목에 기존 `available_stalls`/`average_stall_use_s` 키를 추가해 그 영상만 지정할 수 있습니다. 단일 `analyze`는 환경 설정의 메타데이터를 사용하므로 목록의 초기값·촬영시각과 독립적입니다. 설정 수정은 다음 실행부터 적용하며 실행 중인 설정 사본에는 소급하지 않습니다.

### 운영과 시연 프로필

`configs/profiles/operating.json.defaults.record_interval_s`는10, `demo.json.defaults.record_interval_s`는1입니다. 간격은 이 JSON에서 관리하며 공통 기록 코드에1/10초를 하드코딩하지 않았습니다. 기록 키가 없는 기존 환경 설정은 operating 프로필의 기본값10초를 사용합니다. 프로필을 생략한 단일 `analyze`도 운영10초입니다. 사용자 프로필 경로를 `--profile`로 지정할 수 있으며 간격은 양의 유한한 초여야 합니다.

operating 프로필은 기록 간격10초만 지정하고 촬영시각/초기값/칸 수를 덮어쓰지 않습니다. demo 프로필은 기록 간격1초와 **가상 촬영 기준시각 2026-10-14 00:00:00+09:00**, **북쪽 초기29명·남쪽3명·동쪽3명**을 적용합니다. 칸 수와 평균시간은 각 환경 설정에서 읽습니다. 저장된 마스킹·영상 경로·판정 기준은 변경하지 않습니다. 프로필은 촬영시각·초기값·칸 수·평균시간·기록 간격·상태 표시와 CSV 분할/전달 모드만 바꿀 수 있으며 구역/행동 규칙은 환경 설정에서 읽습니다.

시연 CSV의 상태에는 `demo_assumptions`, `synthetic_material`, `virtual_scenario_time`, `mean_use_user_assumption`, `all_stalls_operating_assumed`가 들어가며 북쪽은 `initial_inside_assumed_29`, 남쪽·동쪽은 `initial_inside_assumed_3`도 표시합니다. 초기 인원과 시연 일시는 실제 관측값/정답이 아닙니다. 운영 설정의 초기 내부 인원·촬영시각은 세 환경 모두 null을 유지합니다. 실제 적용한 칸 수/평균시간은 공유13열에 추가하지 않고 설정 사본·상세 레코드·실행 요약에 보존합니다. 프로필 우선순위는 환경 설정 → 영상 목록 → 선택 프로필입니다. 초기값을 덮어쓰면 오래된 `initial_inside_assumed_*` 태그도 제거하고 새 표기를 적용합니다.

### 기록 간격과 정시 파일 분할

`configs/streaming.json`은 기록 간격과 별도로 `csv_split_interval_s=3600`, `prediction_mode=disabled`를 관리합니다. 단일/일괄 분석 모두 `shared/north_YYYY-MM-DD_HH00.csv`처럼 화장실별·한국시간 정시별로 나눕니다. **구간 시작일시**가 속한 시간대를 사용하므로14:59:59~15:00:00은1400,15:00:00~15:00:01은1500 파일입니다. 자정에 끝나는 구간도 시작한 전날2300 파일에 속합니다. 실행 시작부터60분 기준이 아닙니다. 관측하지 않은 시간대의 빈 CSV는 만들지 않으며 종료 때 현재 파일을 닫습니다. 파일마다 UTF-8 BOM·13열 헤더는 한 번입니다.

촬영시각이 없으면 `shared/time_unset/north_relative.csv` 등 별도 경로에 저장하고 전달 레코드에 상대시각·시각 미설정 상태를 유지합니다. PC 실행/수정 시각으로 촬영일시를 만들지 않습니다. `--csv-split-seconds 86400`은 기존 종료일시 기준 날짜 분리/정렬/파일 교체 방식의 호환 옵션입니다. 과거 하루 단위 출력은 보존합니다. 영상별 `usage_summary.csv`도 같은13열 원장으로 계속 저장합니다.

실제 첫 처리 프레임이 a초이고 간격이 d초이면 기록은 **a+d, a+2d, …**입니다. MVP는1,2,3…초이며 컴퓨터 실행시간이 아닌 영상 시각입니다. 출입은 판정 확정 시각으로 첫 구간 `[a,a+d]`, 이후 `(이전 경계,현재 경계]`에 일회만 집계합니다. 내부 인원에는 분석 시작부터의 누적 출입을 사용합니다. 현재 상태는 기록 경계 이하의 가장 최근 프레임이며 미래 프레임을 쓰지 않습니다. 24FPS의0~10초 실행은 마지막 처리 프레임9.958초의 재생 범위까지 포함해10초 행도 기록합니다. 소스 시각은 상세 파일에 구분하고 `--end`의 미처리 프레임 출입을 추정하지 않습니다.

설정 간격 미만의 마지막 잔여는 정기 CSV에서 제외합니다. MVP는1초 미만, 운영은10초 미만입니다. `remainder.json`/`summary.json`에 원본 범위·길이·잔여 출입·마지막 상태를 남기고 `final_state.json`/`final_usage_detail.json`도 유지합니다. 단일/영상별 `usage_summary.csv`는 같은13열의 완성된 설정 구간 파일입니다. 과거10초/구간당1행14열 결과는 그대로 보존하며 새 결과와 구분하세요.

시간별 CSV는 파일 핸들을 유지해 매 기록 append/flush하고 시간대가 바뀔 때 교체합니다. 기록 중에도 완성된 행을 읽기 전용으로 사용할 수 있으며 마지막 불완전 행은 다음 읽기까지 보류합니다. 탐지·추적·출입·대기 판정은 기존대로 모든 처리 프레임에서 실행합니다. 기록은 영상 시각 기준이며 실제 처리속도가 느리면 현실의 매초 데이터가 도착하지 않을 수 있습니다. 저장 영상은 처리 속도로 실행하고 실시간처럼 보이게 sleep을 넣지 않습니다. 잔여가 있으면 마지막 CSV 행과 최종 프레임 상태가 다를 수 있습니다. 과거 결과를 덮어쓰지 않으며 실행 상태/처리 FPS/전달 요약도 확인합니다.

### 공유 CSV의 정확한13열

| 순서 | 열 이름 | 의미 |
|---|---|---|
| 1 | 촬영시작시각 | 입력 촬영 기준시각 + 해당 기록 구간의 원본 시작 오프셋 |
| 2 | 촬영종료시각 | 같은 기준시각 + 해당 기록 구간의 원본 종료 오프셋 |
| 3 | 화장실ID | north/south/east |
| 4 | 화장실_영상ID | 동일 원본을 반복 실행해도 유지되는 ID |
| 5 | 구간_입장인원 | 해당 기록 구간에서 확정한 entry 수, 누적값과 구분 |
| 6 | 구간_퇴장인원 | 해당 기록 구간에서 확정한 exit 수 |
| 7 | 내부잔류인원_추정 | 분석 시작 초기값 + 분석 시작 이후 누적 입장 − 누적 퇴장, 음수 원시 값 보존 |
| 8 | 현재대기인원_추정 | 외부대기인원_추정 + 추정내부대기인원 |
| 9 | 측정상태 | 초기값/시각/칸 수 미설정, 가림 유예/억제, 출입 미확정, 시연 가정, accuracy_not_validated 등. '정상'으로 정확도를 주장하지 않음 |
| 10 | 추정내부대기인원 | MAX(내부잔류인원_추정 − 운영 가능 칸 수, 0) |
| 11 | 전체대기인원_추정 | 현재대기인원_추정과 **같은 값**, 공식의 Q. 내부 대기를 다시 더하지 않음 |
| 12 | 현재이용가능칸수_추정 | MAX(운영 가능 칸 수 − 내부잔류인원_추정, 0), 운영 총칸 수와 구분 |
| 13 | 외부대기인원_추정 | 관측candidate + 관측confirmed + 중복 억제 후 confirmed 가림 유예 |

내부 대기·빈 칸은 단순 인원 비교에 따른 가정이며 실제 칸 점유를 관측한 값이 아닙니다. 내부 인원을 칸 수로 제한하거나 평균 시간으로 차감하지 않습니다. 초기값이 null이면 내부/내부대기/현재대기/Q/빈칸/예상시간은 빈 칸이고 외부 대기는 유지합니다. 음수 내부 원시 값과 상태는 남기되 관련 계산은 비웁니다. 운영 칸 수가 null이면 의존 계산을 비우고, 0이면 빈 칸0/내부대기 비교는 가능하지만 예상시간은 계산 불가입니다. 음수 칸 수·잘못된 초기값·시각 역전은 오류입니다.

예상 대기시간 `(Q+1) × average_stall_use_s ÷ available_stalls`는 **공유13열에 넣지 않고** `timeseries.csv.expected_wait_s`, `interval_details.jsonl`의 `state.expected_wait_s`, `final_state.json`에 저장하며 결과 영상에도 표시합니다. 분모는 운영 가능 칸 수이고 현재 빈 칸 추정치가 아닙니다. N=0/null이면 나누지 않고, Q=0일 때도 사용자 공식대로105/27초 같은 양수입니다. 실제 대기시간을 검증한 예측값은 아닙니다.

수동 `ground_truth/*/waiting.csv`의 정답은 **외부 대기**입니다. confirmed-only 기준은6절을 따르며, 내부 추정 대기를 더한 새 공유 `현재대기인원_추정`을 외부 대기 정답으로 복사하지 마세요. 평가는 기존 상세 `timeseries.waiting_total`(외부)과 비교합니다. 초기값29 등 시연 가정과 참조 CSV는 실제 정답이 아닙니다.

세 환경의 사용자 구역은 저장돼 있으며 전체1초 결과에도 기존 좌표를 그대로 사용합니다. 현재 demo 초기 내부 인원은29/3/3, 운영 가능 칸 수는27/19/23입니다. 운영 설정의 초기 인원null은 보존합니다. 구도가 바뀌어 재설정할 때만 다음 명령과3절 방법을 사용합니다. 사용자 좌표를 임의로 대체하지 않습니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv configure --config configs/south.json --time 47
& .\.venv\Scripts\python.exe -m cctv configure --config configs/east.json --time 0 --max-width 1100 --max-height 620
```

**이전 2026-10-14 북쪽 짧은1초 검증 이력:** `outputs/batch_demo_20261014_232207_857644d5/shared/north_2026-10-14.csv`입니다. 0~1초부터9~10초까지 정확히10행이며 같은 영상별 `usage_summary.csv`에도10행을 저장했습니다. 북쪽240프레임을 CPU로 약20.10초에 처리했고 출력1280×720/24FPS/240프레임 전체 재디코딩을 확인했습니다. 마지막10초 행은9.958초 프레임을 사용합니다. 프로그램의 이 짧은 구간 판정은 입장/퇴장0/0이며 실제 정확도를 평가한 수치는 아닙니다.

화장실별 날짜 파일을 포함한 **이전 로컬 북쪽 전용 검증 명령 이력**은 아래와 같습니다. 이 inspection 목록은 GitHub에 포함되지 않으므로 새로 내려받은 팀원은 위의 단일 `analyze --profile demo --start 0 --end 10`이나 정식 영상 목록 batch 명령을 사용하세요. 개발 PC의 사본은 기존 등록에서 북쪽 항목만 복사했으며 원본 등록/환경 설정은 그대로입니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv batch --registry inspections/mvp_1s_north_check_20261014_232206_9ce06691/north_registry.json --profile demo --limit-seconds 10 --device cpu
```

기존10초 기록의20초 CSV `outputs/batch_demo_20261014_184050_53150edc/shared/north_2026-10-14.csv`(2행)와 전체 CSV `outputs/batch_demo_20261014_184158_d218fec0/shared/north_2026-10-14.csv`(10행)는 보존했습니다. 기존 전체 판정 입장5/퇴장9, 마지막10초 미만 잔여의 퇴장2와 후반 구도 검토 한계는 당시10초 실행의 이력입니다. 이전 짧은1초 검증은 `docs/mvp_interval_checks.json`과 `docs/VALIDATION.md`에 있으며 최신 전체 실행은 인수인계 문서에서 확인하세요. 빈 정답에는 정확도 수치를 생성하지 않습니다.

## 11. 비동기 전달 연결부와 실제 예측모델 연결 위치

`StreamOutput`은 공통 생성 레코드를 공유 CSV에 추가·flush한 다음 직렬화해 전달합니다. 기본 `disabled`는 보내지 않습니다. `mock`은 제한된 메모리 큐·SQLite outbox·별도 전달 작업자를 사용해 로컬 모의 수신을 확인합니다. 같은 record_id의 제한 재시도·미전달 보존·재시작 복구와 큐 적체/지연 요약을 구현했습니다. 수신 확인은 예측 성공과 구분하며 실제 예측값은 생성하지 않습니다.

전달용 envelope는 schema_version/run_id/record_id/영상·화장실ID/절대·상대 구간시각/자료 유형·시연 여부와 같은13열 본문·상세를 담습니다. CSV에 메타데이터 열을 추가하지 않습니다. `record_index.jsonl`은 ID와 CSV 행 대응, `delivery_summary.json`은 생성/저장/시도/확인/실패/대기와 파일 목록, `delivery/outbox.sqlite3`는 미전달 원장입니다. 미래 어댑터는 `cctv/delivery.py`의 `Receiver.send(envelope)`에 연결합니다. 확인 응답 유실로 중복 전송될 수 있으므로 수신 측 record_id 중복 방지가 필요합니다. 실제 모델/클라이언트·결과 검증은 남은 작업입니다. 계약·한계·복구 명령은 [PREDICTION_INTEGRATION.md](../../docs/PREDICTION_INTEGRATION.md)에 있습니다.

```powershell
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 10 --csv-split-seconds 3600 --prediction disabled
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 10 --device cpu --csv-split-seconds 3600 --prediction mock
```

이번 북쪽240프레임의10행은 기존 전체 결과 첫10행과 계산값을 대조했습니다. 정각/자정·화장실별 분리·BOM/헤더·실패 후 CSV 보존·재시도/강제 중단 복구·느린 수신/큐 적체·미설정/이상 상태·13열을 포함한 관련28개 테스트를 통과했습니다. 실제 검증 출력은 [HOURLY_DELIVERY.md](../../docs/HOURLY_DELIVERY.md)를 확인하세요.

## 12. 전체 영상 CSV 저장 시점과 데이터 중심 모드

현재 demo 초기값은 north29/south3/east3명입니다. 다음은 북쪽 전체 영상을 같은 GPU 설정으로 처리하는 명령이며 매 실행은 새 결과 폴더를 만듭니다. 첫 명령은 기존 결과 영상/오버레이를 저장하고 두 번째는 해당 출력만 생략합니다. 프레임 분석·CSV·전체 진단 수준은 같습니다.

```powershell
& .\.venv-gpu\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --device cuda:0 --prediction disabled --csv-split-seconds 3600 --measure-csv-latency
& .\.venv-gpu\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --device cuda:0 --prediction disabled --csv-split-seconds 3600 --measure-csv-latency --no-video
```

측정 결과는 `csv_latency.csv`, `timing_events.jsonl`, `timing_summary.json`에 저장하며 공유13열은 유지합니다. 모델 객체 준비와 첫 CUDA 백엔드/warmup을 구분하고 첫 처리시간에 warmup을 포함합니다. 음수 차이는 저장 영상을 재생속도보다 앞서 처리한 뜻이며 관측 이전 데이터를 얻었다는 의미가 아닙니다.

A/B의 이번105행은 모든 값이 일치합니다. 이전 CPU 전체 결과 대비31/33/34/35행의 측정상태만 다르고 수치 열은 같습니다. 세부 후보/확정·가림 유예 경로는 달라 기존 결과를 보존했습니다. 실제 영상·지연 측정·재계산·PowerShell로 여는 명령은 [LATENCY_INITIAL3.md](../../docs/LATENCY_INITIAL3.md)를 확인하세요.
