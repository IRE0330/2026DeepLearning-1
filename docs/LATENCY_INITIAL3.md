# 북쪽 전체 GPU CSV 저장 시점과 남쪽·동쪽 초기3명 갱신

2026-10-17에 구현·전체 실행·검증했습니다. 북쪽은 **전체 영상을 GPU에서 두 번 실제 분석**했고, 남쪽·동쪽은 충분한 기존 추적 로그를 사용해 **재계산·원본 재렌더링**했습니다. 기존 결과를 덮어쓰지 않았습니다. 실제 영상 실행은 모두 전달 disabled이며 실제 예측모델은 미연동입니다. Git push는 하지 않았습니다.

기계 판독 근거: [latency_initial3_checks.json](latency_initial3_checks.json). 백업·보존 해시·검증 스크립트는 로컬 `inspections/latency_initial3_20261017_211325_2e7fd1ea`입니다.

## 실행 조건과 변경 범위

- 북쪽 원본2,524프레임·24 FPS·1280×720·재생 길이105.166667초 전체를 처리했습니다. 구간 제한, 프레임 생략, 재생속도 맞춤 sleep은 없습니다.
- `.venv-gpu`, RTX4060/cuda:0, YOLO11n 동일 SHA-256, FP32, imgsz640, confidence0.1, IoU0.7, 동일 ByteTrack·마스킹·규칙·계산을 사용했습니다. 두 모드의 설정 사본과 진단 수준도 같습니다.
- A는 기존 오버레이·결과 영상 생성/전체 재디코딩 검증, B는 새 `--no-video` 옵션으로 오버레이·인코딩·출력 영상 재검증만 생략했습니다. CSV·출입·매 프레임 탐지/추적·상세 진단은 유지합니다. 기본값은 기존 영상 저장입니다.
- 각 모드는 별도의 새 프로세스에서 순차 실행했습니다. 사전 검사·가중치/객체 준비·CUDA 백엔드 준비·첫 추론 warmup을 포함하며 별도 사전 warmup 실행은 하지 않았습니다.
- 1초 기록과1시간 파일 분할은 유지합니다. 파일 소속은 구간 시작 한국시간이며 공유13열/BOM/순서를 변경하지 않았습니다. 측정값은 별도 파일입니다.
- demo 초기값만 **north29/south3/east3**, 운영 가능 칸 수27/19/23, 평균105초, 시연 가상 시작2026-10-14T00:00:00+09:00입니다. 운영 초기값/촬영시각null·기록10초, 영상 목록·영상 경로·최종 마스킹은 보존했습니다.

실제 추론 후 수집한 `summary.json.runtime_device`에서 양쪽 모두 backend/parameter/result가cuda:0, 가중치torch.float32, fp16=false, CUDA 메모리 할당을 확인했습니다. 원본 모델 객체와 실제 추론 백엔드를 구분해 검사합니다.

## 측정 기준

`--measure-csv-latency`는 `time.perf_counter_ns()`를 사용합니다. 벽시계/촬영 가상일시의 변경을 경과시간 계산에 쓰지 않습니다.

| 파일 | 내용 |
|---|---|
| `timing_events.jsonl` | 실행 시작, 사전 검사 완료, 모델 객체 준비 완료, 첫 프레임 처리 시작, 첫 추론 백엔드 준비, 프레임 반복/처리 루프 종료, 분석 작업 종료 |
| `csv_latency.csv` | 각105개 공유 CSV 행의 record_id·행 번호·영상 구간 종료·영상 경과·monotonic flush 시각·실행/처리 경과·직전 저장 간격·두 기준 차이 |
| `timing_summary.json` | 단계별 시간, 각 범위 FPS, 저장 간격 중앙값/선형 보간95백분위/최댓값, 차이의 시작/최종/최대/최소/추세 |
| `record_index.jsonl` | 같은 ID와 공유13열 본문·CSV 행 참조를 대응하는 기존 인덱스 |

실행 기준0점은 **CLI main 진입**이며 Python 프로세스 생성과 초기 모듈 import는 제외합니다. 무거운 탐지 라이브러리 import와 모델 로드는 그 이후이므로 포함합니다. 별도 외부 프로세스 monotonic 타이머로 프로세스 시작~종료도 측정했습니다. `model_ready`는 생성자/가중치/메타데이터 준비이며 실제 CUDA 백엔드와 warmup은 첫 `observe()`에서 수행됩니다. 첫 프레임 처리는 첫 프레임 디코딩 후 첫 `observe()` 직전입니다.

CSV 측정점은 **공유 CSV append/flush가 반환된 직후, 인덱스/outbox 기록 전**입니다. 영상별 원장/상세 flush는 그보다 먼저 끝납니다. 이는 flush 완료 시각이지 fsync·물리 디스크 영구 기록 확인이나 다른 프로그램에 도착한 시각은 아닙니다. 첫 기록의 직전 저장 간격은 빈 칸이며 통계는 나머지104개 간격입니다. 실제 A 실행 중 완료 전에73개 CSV 행을 읽을 수 있었던 관측도 인계 자료에 보존했습니다.

처리 루프 범위는 첫 프레임 처리 시작~마지막 프레임 처리/마지막 구간 마감·writer release까지입니다. 분석 작업 종료는 출력 재검증/전달 서비스 종료까지 포함하고 마지막 요약 파일 쓰기와 프로세스 종료는 제외합니다. 기존 `summary.elapsed_s/processing_fps`는 pipeline의 초기 요약 저장 이후~CSV/진단 핸들 종료까지이며 사전 검사·모델 준비는 포함하고 출력 재검증은 제외합니다. 범위가 다른 이 값을 새 루프 FPS와 혼용하지 않습니다.

## 북쪽 A/B 결과

| 항목 | A 영상·오버레이 | B 데이터 중심 |
|---|---:|---:|
| 사전 검사 완료 (실행 기준) | 9.844초 | 9.812초 |
| 모델 객체 준비 완료 (실행 기준) | 14.869초 | 12.046초 |
| 검사 완료~모델 객체 준비 | 5.025초 | 2.234초 |
| 첫 프레임 처리 시작 (실행 기준) | 14.929초 | 12.100초 |
| 첫 observe/백엔드·warmup 포함 | 3.460초 | 2.492초 |
| 첫 CSV 저장 (실행 / 처리 기준) | 19.029 /4.100초 | 15.101 /3.001초 |
| 처리 루프 시간 / FPS | 83.235초 /30.324 | 68.194초 /37.012 |
| 분석 작업 전체 시간 / FPS | 99.709초 /25.314 | 80.296초 /31.434 |
| 프로세스 시작~종료 | 100.947초 | 81.326초 |
| 저장 간격 중앙값 /95백분위 /최대 | 0.764 /0.816 /0.883초 | 0.632 /0.700 /0.753초 |
| 실행 기준 차이: 시작 /최종 /최대 | +18.029 /−6.936 /+18.029초 | +14.101 /−24.794 /+14.101초 |
| 처리 기준 차이: 시작 /최종 /최대 | +3.100 /−21.864 /+3.100초 | +2.001 /−36.893 /+2.001초 |
| 차이가 증가한 인접 기록 쌍 | 0/104 | 0/104 |

공식은 `실행 경과−영상 경과`, `첫 프레임 처리 후 경과−영상 경과`이며 원시 양수·음수를 보존했습니다. 두 실행에서는 차이가 계속 줄었고 지속적으로 누적되는 지연은 관측되지 않았습니다. B의 처리 루프는 약1.221배 빨랐습니다. 준비·첫 warmup 시간도 달라 전체 차이를 전부 영상 인코딩 비용이라고 단정하지 않습니다. 각 모드1회이며 데스크톱 배경 부하는 통제하지 않았습니다.

음수는 이미 저장된 파일을 재생속도보다 앞서 처리했다는 의미입니다. 실제 관측 전에 데이터를 얻었다는 뜻이 아닙니다. 첫 행은 실제로15~19초 후에 저장됐습니다. 이후104개 간격이 이번 실행에서1초 이내였다는 사실이나 평균 FPS가24보다 높다는 사실로 실시간 매초 제공을 보장하지 않습니다. 실제 CCTV 입력 지연·세 CCTV 동시 처리를 검증한 실험이 아닙니다.

추세 그림: `outputs/north_latency_ab_20261017_211718_82b9d4ed/latency_comparison.png`.

## 집계 일치와 이전 CPU 결과의 차이

A/B는 각각105행이며 공유 CSV·출입 이벤트·상세 시계열·프레임 진단·구간 상세·최종 상태·잔여 파일이 **바이트 일치**했습니다. 양쪽 모두 입장5/퇴장9/최종 내부25명/빈칸2/외부·내부·전체대기0, 가정 예상3.888889초입니다. 마지막1초 미만 약0.166667초의 출입0/0과 최종 프레임105.125초는 별도 잔여/최종 파일에 보존합니다.

이전 CPU 전체 결과 `outputs/batch_demo_recalc_20261017_144846_e9dd5976/north`와는 CSV31·33·34·35행의 **측정상태만** 다릅니다. 나머지12개 열과 모든105행의 수치 열은 같습니다. candidate/confirmed 분배·가림 억제 상세 상태는 동일하지 않습니다. 기존 파일이나 새 값을 맞추기 위해 수정하지 않았습니다.

현재 Counter로 이전 CPU 로그와 새 GPU 로그를 각각 재생해 각 원본 구간 상태가 그대로 재현됨을 확인했습니다. 입력 로그에는 탐지 수가 다른8개 프레임과 추적 ID 집합이 다른1,354개 프레임이 있었고, 프레임 상태는127개에서 달랐습니다. 따라서 두 장치의 탐지/추적 입력 차이가 세부 상태 경로 차이로 이어진 것으로 판단합니다. 정확한 CUDA 커널/매칭 임계점 원인은 분리하지 않았습니다. 실제 카운팅 정확도 비교로 해석하지 않습니다. 상세 근거는 합본 JSON과 `north_device_status_review.json`에 있습니다.

## 남쪽·동쪽 초기3명 결과

환경 설정 → 영상 목록 → 선택 프로필 순으로 적용하며 CLI가 장치/출력 옵션을 마지막으로 지정합니다. 운영 영상 목록의 초기값은null이고 demo 프로필이3으로 덮어씁니다. 로그 재계산도 과거 실행 설정 뒤에 현재 demo를 적용합니다. `apply_profile()`은 초기값을 바꾸면 오래된 `initial_inside_assumed_*` 표기를 제거하고 새 표기를 넣으므로 이전18명 가정이 남지 않습니다. 운영 프로필은 초기값을 덮어쓰지 않습니다.

| 환경 | 프레임 /1초 행 | 내부 인원 범위 | 입장 /퇴장 | 최종 내부 /빈칸 | 최종 내부·전체대기 | 가정 예상시간 |
|---|---:|---:|---:|---:|---:|---:|
| south | 2,827 /94 | 2~4명 | 2 /2 | 3명 /16칸 | 0 /0 | 5.526316초 |
| east | 2,700 /90 | 3~8명 | 5 /3 | 5명 /18칸 | 0 /0 | 4.565217초 |

초기3명은 시작시점 가정이며 `3+누적입장−누적퇴장`으로 매 프레임 변합니다. 전체 프레임에서 음수는 없었습니다. 내부·빈칸·대기·가정 시간을 재계산했고, 이번 두 영상에서는 이전18명 가정에서도 내부 초과가 없어 내부대기/Q/예상시간의 수치는 그대로인 구간이 있습니다. 이는 값을 고정한 결과가 아닙니다. 실제 음수 상황은 원시 음수와 상태를 보존하고 의존 계산을 비우는 회귀 테스트로 확인했습니다.

기존 events/diagnostics는 바이트 보존했습니다. 재탐지·ByteTrack 재실행 없이 기록된 모든 프레임의 관측/출입·외부대기 일치를 확인한 뒤 새1초 CSV·상세·최종/잔여를 생성하고 원본 영상에서 공통 한글 수치표를 다시 렌더링했습니다. 남쪽 약0.233333초 잔여/출입0·0, 동쪽 정확한90초 끝 경계 정책도 유지합니다.

새 결과 영상은1920×1080/30 FPS/2,827 및2,700프레임 전체 디코딩을 확인했습니다. 모든 CSV 구간 상태가 영상 렌더링 입력과 일치했고 환경별3개 CSV 체크포인트의 디코딩 영상 패널도 기대 패널과 대조했습니다(압축 후 평균 픽셀 오차2.14~2.66/255). 첫 프레임 한글 수치표의 내부3명·빈칸16/20칸도 시각 확인했습니다. 남쪽 왼쪽 아래/동쪽 오른쪽 아래, 너비35%·높이약22%의 기존 디자인은 유지했습니다.

## 새 파일 위치

북쪽 묶음: `outputs/north_latency_ab_20261017_211718_82b9d4ed`

- A: `A_video/north_20261017_211719_783c2efb/`
- B: `B_data/north_20261017_211900_1bda2e30/`
- 각 모드의 `shared/north_2026-10-14_0000.csv`, `csv_latency.csv`, `timing_events.jsonl`, `timing_summary.json`, `summary.json`을 확인합니다. A에는 `annotated.mp4`가 있습니다.
- 묶음 루트 `comparison.json`, `ab_manifest.json`, `latency_comparison.png`가 비교 결과입니다.

남쪽·동쪽 묶음: `outputs/batch_demo_recalc_20261017_212102_c5dd7a25`

- `shared/south_2026-10-14_0000.csv`, `shared/east_2026-10-14_0000.csv`
- `{south,east}/annotated.mp4`, `usage_summary.csv`, `timeseries.csv`, `interval_details.jsonl`, `final_state.json`, `remainder.json`, `summary.json`, `render_summary.json`
- `batch_summary.json`, `delivery_summary.json`, `validation.json`, `record_index.jsonl`

영상별 원장과 화장실별 시간 CSV의 기존 구조를 유지하며 두 파일은 같은 데이터를 담습니다. 같은 내용의 하루 CSV를 추가 생성하지 않았습니다. IDE에 열려 있을 수 있는 이전 `east_2026-10-14.csv` 등은18명 가정의 보존 결과입니다.

## 실제 실행 명령과 바로 열기

프로젝트 루트 PowerShell에서 실행했습니다. 각 analyze는 새 고유 하위 폴더를 생성합니다. 명령 전체와 프로세스 시간은 `ab_manifest.json`에도 남습니다.

```powershell
& .\.venv-gpu\Scripts\python.exe -B -u -m cctv analyze --config configs/north.json --profile demo --device cuda:0 --prediction disabled --csv-split-seconds 3600 --measure-csv-latency --output-dir outputs/north_latency_ab_20261017_211718_82b9d4ed/A_video
& .\.venv-gpu\Scripts\python.exe -B -u -m cctv analyze --config configs/north.json --profile demo --device cuda:0 --prediction disabled --csv-split-seconds 3600 --measure-csv-latency --output-dir outputs/north_latency_ab_20261017_211718_82b9d4ed/B_data --no-video
& .\.venv-gpu\Scripts\python.exe -B -u -m cctv.recalculate --source-batch outputs/batch_demo_recalc_20261017_144846_e9dd5976 --prepare-only --rooms south east
& .\.venv-gpu\Scripts\python.exe -B -u -m cctv.recalculate --output outputs/batch_demo_recalc_20261017_212102_c5dd7a25
```

재계산 prepare는 매번 새 폴더를 표시합니다. 다음 `--output`에는 그 새 경로를 지정합니다. 위 마지막 명령은 이번 실행 이력이며 이미 생성된 영상의 덮어쓰기는 거부합니다.

```powershell
$northA = 'outputs/north_latency_ab_20261017_211718_82b9d4ed/A_video/north_20261017_211719_783c2efb'
$northB = 'outputs/north_latency_ab_20261017_211718_82b9d4ed/B_data/north_20261017_211900_1bda2e30'
$updated = 'outputs/batch_demo_recalc_20261017_212102_c5dd7a25'
Invoke-Item -LiteralPath (Join-Path $northA 'annotated.mp4')
Invoke-Item -LiteralPath (Join-Path $northA 'shared/north_2026-10-14_0000.csv')
Invoke-Item -LiteralPath (Join-Path $northA 'csv_latency.csv')
Invoke-Item -LiteralPath (Join-Path $northB 'csv_latency.csv')
foreach ($room in 'south','east') {
    Invoke-Item -LiteralPath (Join-Path $updated "shared/${room}_2026-10-14_0000.csv")
    Invoke-Item -LiteralPath (Join-Path $updated "$room/annotated.mp4")
}
```

## 검증과 다음 작업

관련32개 테스트 통과(2.787초): 영상 출력 생략 시 동일 프레임/CSV/진단, flush와 ID/행 대응·부호·monotonic, 초기3명/오래된 태그·우선순위, 재계산 음수 처리, 기존13열/1초/정각 정책과 회귀 검사를 포함합니다. 기존471개 스냅샷 중 허용 변경11개를 제외한 **460개 파일 해시가 일치**했고 CPU/GPU 패키지 목록도 유지됐습니다. 운영 설정·마스킹·기존 결과는 보존했습니다.

변경 파일은 `cctv/timing.py`, `pipeline.py`, `stream_output.py`, `detector.py`, `__main__.py`, `profiles.py`, `recalculate.py`, `configs/profiles/demo.json`, 관련3개 테스트와 README/HANDOFF/이번 문서·검증 JSON입니다.

첫 행의15~19초 준비 지연과 과거 CPU 대비 세부 상태 차이는 남아 있습니다. 다음은 사전 검사 캐시/모델 준비 단계 개선과 북쪽31~35초 후보·가림 억제 차이, 남쪽 최종 미확정 출입 후보를 수동 검토하고 정답을 작성하는 작업을 권장합니다. 실제 인원 집계 정확도·실제 CCTV 지연·동시 처리·실제 예측모델은 아직 검증/연동하지 않았습니다.
