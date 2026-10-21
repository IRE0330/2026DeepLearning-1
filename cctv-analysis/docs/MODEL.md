# 모델·가중치·출처

0.3.2 실행 설정의 `model` 기본값은 `${CCTV_MODEL_PATH}`입니다. `--model <자신의 파일>`, `AnalysisService.start(model_path=...)` 또는 환경변수 `CCTV_MODEL_PATH`로 지정하세요. 환경변수의 상대 경로는 실행 폴더 기준이며 직접 CLI/API 지정이 우선합니다. 미설정 상태로 실행하면 파일 누락 오류를 반환하며 자동 다운로드하지 않습니다.

기존 **Ultralytics YOLO11n COCO 사전학습 탐지 모델**의 person 클래스0을 사용합니다. 이번 패키징에서 모델/가중치·추가 학습·입력 해상도·FP32 설정을 바꾸지 않았습니다. 실행 설정은 imgsz640/conf0.1/iou0.7, 환경별 기존 ByteTrack/판정 정책입니다.

사용한 로컬 파일명: yolo11n.pt

SHA-256:

```text
0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1
```

모델 설명은 [Ultralytics 공식 YOLO11 문서](https://docs.ultralytics.com/models/yolo11/), 기존 다운로드 출처는 [Ultralytics 공식 assets v8.3.0](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt)입니다. 가중치는 wheel/Git에 넣지 않습니다. 팀이 보존한 동일 해시 파일을 별도 전달하거나, 기존 명령 `python -m cctv download-model`을 자료 폴더에서 실행해 models/yolo11n.pt를 준비하고 해시를 확인하세요. 다운로드는 명시적 준비 명령이며 분석 중에는 자동 다운로드하지 않습니다. 분석 시 Ultralytics offline 모드를 사용합니다.

```powershell
Get-FileHash -LiteralPath '.\models\yolo11n.pt' -Algorithm SHA256
```

공식 문서는 YOLO11 모델의 **AGPL-3.0 또는 Enterprise** 라이선스를 안내합니다. [공식 라이선스 안내](https://www.ultralytics.com/license)와 사용 중인 의존성의 라이선스를 함께 확인해야 합니다. 이 저장소 자체의 별도 배포 라이선스는 지정돼 있지 않아 이 문서가 새로운 사용권을 부여하지는 않습니다. 외부 배포는 이번 작업에 포함하지 않았습니다.
