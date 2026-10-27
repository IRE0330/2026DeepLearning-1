# 화장실 CCTV 분석 모듈 — 0.3.3

저장 영상에서 출입·외부 대기와 내부 인원 추정치를 집계하고 CSV/API 레코드를 생성합니다. 0.3.3은 **선택형 북쪽 GPU YOLO11s**를 추가합니다. 기본 n, 사용자 가중치·장치 선택, 남쪽·동쪽, 공개 AnalysisService는 유지됩니다.

## 설치

[시작 안내](deployment/START_HERE.md)의 0.3.3 ZIP·wheel과 공식 가중치를 준비합니다. Python 3.13의 새 환경에서 CPU 또는 GPU용 PyTorch를 먼저 설치한 뒤, ZIP을 푼 폴더에서 실행합니다.

```powershell
& $py -m pip install '.\dist\busan_cctv_analysis-0.3.3-py3-none-any.whl[analysis]'
& $py -m pip check
```

## 기본 실행 · 선택형 GPU 실행

```powershell
# 기본 n CPU. 남쪽·동쪽은 room과 영상을 함께 변경합니다.
& $py .\examples\analyze_video.py --room north --video .\inputs\north.mp4 --model .\models\yolo11n.pt --device cpu --profile demo --output .\runs-n --end 3.25
# CUDA 환경에서 명시적으로 선택한 북쪽 s만 적용합니다.
& $py -m cctv.gpu_profile --runtime-profile north-gpu-s --video .\inputs\north.mp4 --model .\models\yolo11s.pt --profile demo --output-dir .\runs-s --end 3.25
```

`$py`는 선택한 가상환경의 Python 경로입니다. 실제 영상과 가중치를 직접 준비하세요. 기본 API의 `model_path`·`device`·`config_path`와 `CCTV_MODEL_PATH`는 유지됩니다. 선택형 s는 공식 가중치 해시와 CUDA를 검증하며 자동 적용·CPU 폴백을 하지 않습니다. `demo`의 초기 인원·가상 촬영시각은 시연 가정입니다.

개발 영상 41이벤트의 **통과 시각** 합산 F1은 전 환경 n 77.61% → 북쪽 s·남/동 n 81.16%입니다. 가림·ID 유실로 누락될 수 있고 별도 영상 일반화·실제 CCTV·세 입력 동시 실시간은 미검증입니다. 새 구도는 마스킹을 다시 설정해야 합니다.

상세: [설치·다운로드·버전 차이](deployment/START_HERE.md) · [평가·GPU 검증·한계](docs/NORTH_GPU_S_033.md) · [검증 요약](docs/VALIDATION_033.json) · [API 연동](docs/DATA_CONTRACT.md) · [기존 인계](docs/FINAL_HANDOFF.md).
