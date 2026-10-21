# RTX 4060 구성과 CPU/GPU 비교 (2026-10-17)

기존 CPU 가상환경 `.venv`를 보존하고 별도 `.venv-gpu`에 CUDA용 PyTorch를 설치했습니다. 북쪽0~30초를 동일한 demo 설정·FP32·매 프레임 분석·전달 disabled로 순차 비교했습니다. 실제 CUDA 사용, CSV/출입 집계 일치, 속도와 남은 병목을 확인했습니다. 이번 범위는 환경 구성과 비교 검증이며 분석 규칙·모델·마스킹·계산·CSV 구조는 변경하지 않았습니다. 실제 예측 연동·Git push는 하지 않았습니다.

## 확인한 호환성

| 항목 | 확인값 |
|---|---|
| OS / Python | Windows 11,64비트 / Python3.13.9 |
| GPU | NVIDIA GeForce RTX 4060,8188 MiB, 연산 능력8.9 |
| 드라이버 | 610.88, `nvidia-smi` CUDA UMD13.3 |
| 기존 CPU 환경 | `.venv`, torch2.14.1+cpu / torchvision0.29.1 |
| 새 GPU 환경 | `.venv-gpu`, torch2.14.1+cu132 / torchvision0.29.1+cu132 |
| CUDA / cuDNN | PyTorch CUDA13.2 / cuDNN92400 |
| 격리 | `include-system-site-packages=false`, 기존과 같은 Python3.13.9 사용 |

PyTorch의 [공식 Windows/Pip 설치 안내](https://pytorch.org/get-started/locally/), [버전별 CUDA 설치 명령](https://pytorch.org/get-started/previous-versions/), 공식 [torch CUDA13.2 wheel 목록](https://download.pytorch.org/whl/cu132/torch/)과 [torchvision wheel 목록](https://download.pytorch.org/whl/cu132/torchvision/)에서 cp313/win_amd64 패키지를 확인했습니다. [NVIDIA 드라이버 호환성 표](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html)는 CUDA13.x의 최소 드라이버580 및 새 드라이버의 이전 CUDA 지원을 설명합니다. 설치된610.88에서 CUDA13.2 실연산을 확인했으며 드라이버·전역 CUDA Toolkit·Blender 설치는 변경하지 않았습니다. `nvidia-smi`의 UMD 표기와 PyTorch 빌드에 포함된 CUDA 버전은 구분합니다.

`torch.cuda.is_available()`가 true일 뿐 아니라 CUDA 행렬 곱의 오차0, CUDA `torchvision.ops.nms`의 예상 결과[0,2]와 출력 장치cuda:0을 확인했습니다. 실제 영상 분석에서도 추론 백엔드의 입력과 가중치는 FP32/cuda:0,720개 탐지 결과의 장치는cuda:0이었습니다. CUDA forward721회 중1회는 프레임 분석 전 warmup이며 실제 분석은720프레임입니다. PyTorch 최대 텐서 할당59.75 MiB·예약68 MiB는 다른 앱/드라이버를 포함한 전체 VRAM 사용량이 아닙니다.

두 환경의 `pip check`를 통과했습니다. 기존 CPU의 pip freeze는 전후 동일하며 새 환경은 torch/torchvision의 CUDA 빌드를 제외한42개 잠금 목록의 나머지 패키지 버전이 같습니다. 설정·핵심 코드·모델·기존 결과395개 파일의 SHA-256도 모두 유지됐습니다. 증거는 [gpu_benchmark_checks.json](gpu_benchmark_checks.json)과 로컬 `inspections/gpu_setup_20261017_190026_dab9c42a`에 있습니다.

## 비교 조건과 결과

`configs/north.json` + demo 프로필, 원본0~30초,24 FPS/1280×720,720프레임, YOLO11n 동일 SHA-256, 동일 imgsz/신뢰도/ByteTrack/구역·계산을 사용했습니다. 설정 사본은 device만 다릅니다. demo 초기29명·운영 가능27칸·평균105초·가상 촬영시작2026-10-14T00:00:00+09:00입니다. 전달은 양쪽 모두 disabled, 기록1초/정시 분할3600초입니다. FP16·TensorRT·배치 추론·모델 교체는 적용하지 않았습니다.

| 측정 | CPU `.venv` | GPU `.venv-gpu` |
|---|---:|---:|
| 분석 요약 elapsed_s | 38.44초 | 28.59초 |
| 분석 요약 processing_fps | 18.73 | 25.19 |
| 출력 전체 재디코딩 검증 포함 API 시간 / FPS | 38.95초 /18.49 | 29.12초 /24.73 |
| Python 프로세스 시작·종료까지 포함 | 41.65초 | 32.39초 |
| 탐지+추적 누계 | 21.19초 | 11.92초 |
| 첫 프레임 탐지+추적 | 1.56초 | 2.27초 |
| 이후 프레임 탐지+추적 중앙값 | 26.45ms | 12.12ms |
| 공유 CSV | 30행·13열·BOM | 30행·13열·BOM |
| 입장 / 퇴장 / 최종 내부 | 2 /1 /30명 | 2 /1 /30명 |

분석 요약 기준1.345배, 출력 검증 포함 API 기준1.338배, 프로세스 전체 기준1.286배 빨랐습니다. 분석 요약의 elapsed_s는 출력 재검증/프로세스 시작을 제외합니다. 프로파일 스크립트의 사전 import와 시각/장치 검사에 작은 계측 비용이 있으며 CLI 전체 소요는 별도로 측정했습니다. 최종 유효 비교는 장치별1회로, 데스크톱의 다른 앱 부하는 통제하지 않았습니다. 다른 영상/전체 길이에서도 같은 배율이나 동시 실시간 처리를 보장하지 않습니다.

CPU/GPU 공유 CSV는 **30행 전체 바이트 일치**,30개 상세 구간 상태도 일치했습니다. 출입 방향·확정 프레임은 입장368/693,퇴장510으로 같았습니다. 최종 외부대기4·내부대기3·전체Q7·빈칸0·가정 예상31.111초도 같습니다. 이벤트 파일의 좌표는 최대약0.0072픽셀, 교차 추정시각은 최대약0.000836초 차이가 있어 원시 부동소수점 결과까지 동일하다고 주장하지 않습니다. 집계에 맞춰 이벤트를 수정하지 않았으며 수동 정답 정확도 평가는 별도입니다.

GPU 환경에서 관련 회귀 테스트28개도 통과했습니다(2.452초). 합성 테스트 안의 mock 검사는 저장/전달 회귀 검사이고, 실제 두 영상 비교는 disabled로 실행해 각각 생성/저장30·전달0, outbox 미생성을 확인했습니다.

## 남은 병목

GPU 실행의 탐지+추적11.92초(약41%) 중 Ultralytics가 보고한 신경망 inference 누계는6.42초입니다. CPU inference17.10초보다 약2.66배 빠르지만 전체 프로그램은 다른 작업도 수행합니다.

- 원본 전체2,524프레임 PTS 검사:8.28초, 전체 API 시간의 약28%. 30초 구간 분석이어도 현행 검증은 원본 전체를 스캔합니다.
- 선택 구간 디코딩2.78초·오버레이1.76초·영상 인코딩2.64초:합계7.18초, 약25%. 이 경로는 이번에 GPU로 옮기지 않았습니다.
- 전/후처리·GPU/CPU 데이터 이동·ByteTrack과 초기 warmup도 남습니다. CSV/인덱스 flush 누계는약0.0185초로 이 실행의 주요 병목이 아닙니다.

다음 성능 작업은 검증 정책을 유지하는 PTS 검사 캐시와 디코딩/오버레이/인코딩 경로의 검토가 우선입니다. 이번에는 해당 최적화를 구현하지 않았습니다. 영상 시각1초 기록과 실제 처리시간은 다르며 이번 속도로 세 CCTV 동시 실시간 처리가 검증됐다는 뜻도 아닙니다.

## 최종 결과 경로

최종 비교 묶음: `outputs/device_benchmark_20261017_191234_711f6f90`

| 구분 | 하위 경로 |
|---|---|
| CPU 결과 | `cpu/north_20261017_191236_689be39c/` |
| GPU 결과 | `gpu/north_20261017_191318_866024e8/` |
| 각 결과의 영상 | `annotated.mp4` |
| 각 결과의 공유 CSV | `shared/north_2026-10-14_0000.csv` |
| 장치 증거·단계별 시간 | `device_profile.json` |
| 실행·집계·출력 검증 | `summary.json`, `delivery_summary.json` |
| 비교표 원본 | 묶음 루트 `comparison.json`, `benchmark_manifest.json` |

초기 계측이 원본 모델 객체를 검사한 시도와 import 시 캐시 경로 오류가 난 시도도 새 폴더로 보존했습니다. 최종 계측은 **실제 AutoBackend.forward의 입력/가중치/결과**를 검사하도록 수정했고, 위 묶음의 CPU/GPU 실행만 최종 수치에 사용합니다. 프로그램의 탐지/계산 코드 수정은 없습니다.

## 바로 실행할 PowerShell 명령

프로젝트 루트에서 기존 CPU와 GPU 환경을 명시적으로 선택합니다. 새로운 결과는 매번 고유 폴더에 저장됩니다.

```powershell
# 장치 확인
& .\.venv-gpu\Scripts\python.exe -m cctv doctor
# 같은 북쪽0~30초 GPU 실행, 전달 중지
& .\.venv-gpu\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 30 --device cuda:0 --prediction disabled --csv-split-seconds 3600
# 같은 조건의 CPU 실행
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 30 --device cpu --prediction disabled --csv-split-seconds 3600
# 북쪽 전체 길이 GPU 실행 명령 (이번 검증에서는 전체 길이를 실행하지 않음)
& .\.venv-gpu\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --device cuda:0 --prediction disabled --csv-split-seconds 3600
```

단계별 계측을 다시 하려면 두 명령을 순차 실행합니다. `scripts/benchmark_device.py`는 기존 분석을 감싼 계측 도구로, 분석 설정은 device만 바꿉니다.

```powershell
& .\.venv\Scripts\python.exe -B -u scripts/benchmark_device.py --device cpu --start 0 --end 30 --output-base outputs/device_check/cpu
& .\.venv-gpu\Scripts\python.exe -B -u scripts/benchmark_device.py --device cuda:0 --start 0 --end 30 --output-base outputs/device_check/gpu
```

GPU 결과 바로 열기:

```powershell
$gpuResultPath = Join-Path (Get-Location) 'outputs/device_benchmark_20261017_191234_711f6f90/gpu/north_20261017_191318_866024e8'
Invoke-Item -LiteralPath (Join-Path $gpuResultPath 'annotated.mp4')
Invoke-Item -LiteralPath (Join-Path $gpuResultPath 'shared/north_2026-10-14_0000.csv')
Invoke-Item -LiteralPath (Join-Path $gpuResultPath 'device_profile.json')
```

## 설치 재현

아래는 **아직 `.venv-gpu`가 없는 새 작업 폴더에서만** 실행할 설치 명령입니다. 현재 설치된 환경에는 재생성하지 않습니다. 기존 CPU 가상환경/시스템 Python에 CUDA 패키지를 설치하지 않습니다.

```powershell
& .\.venv\Scripts\python.exe -m venv .venv-gpu
& .\.venv-gpu\Scripts\python.exe -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu132
& .\.venv-gpu\Scripts\python.exe -m pip install -r requirements-lock.txt --index-url https://pypi.org/simple
& .\.venv-gpu\Scripts\python.exe -m pip check
```

첫 설치의 CUDA local version은 `requirements-lock.txt`의 같은 공개 버전 제약을 만족하므로 두 번째 설치에서 CPU 빌드로 바뀌지 않았음을 확인했습니다. 최종 GPU 환경은 `requirements-gpu-lock.txt`에 저장했으며 직접 재현할 경우 `--extra-index-url https://download.pytorch.org/whl/cu132 -r requirements-gpu-lock.txt`를 사용합니다. `.venv-gpu/`는 Git 제외 대상으로 추가했습니다. 기존 `requirements-lock.txt`는 바꾸지 않았습니다.
