# 화장실 CCTV 분석 모듈 — 0.3.2

저장 영상의 사람 탐지·추적으로 출입과 외부 대기를 집계하고, 초기값에 따른 내부 인원 추정치와 CSV를 생성합니다. 공개 AnalysisService로 시작·상태 조회·레코드 수신·중지를 연동합니다.

**[다운로드 → 준비 → 설치 → 짧은 실행](https://github.com/IRE0330/2026DeepLearning-1/blob/mvp/busan-cctv-20261014/cctv-analysis/deployment/START_HERE.md)**에서 진행하세요. 설치 명령은 이 시작 안내 한 곳에 모았습니다. main을 보고 있어도 같은 안정 Release를 사용하며, ZIP 안의 기존 README는 배포 당시 기록입니다.

- 준비: 공식 yolo11n.pt와 사용 권한이 있는 영상. 새 CCTV 구도는 마스킹을 다시 설정합니다. [모델·라이선스](docs/MODEL.md) · [배포 고지](https://github.com/IRE0330/2026DeepLearning-1/blob/cctv-analysis-v0.3.2/cctv-analysis/docs/RELEASE_NOTICES.md)
- 결과: 지정한 출력 폴더 아래 새 작업에 생성되며, 정확한 경로는 상태의 `run_dir`·`csv_files`로 확인합니다. 기존 CSV·outputs는 입력으로 필요하지 않습니다. [예시 CSV 3개](examples/data/README.md)
- 검증: Windows x64·Python 3.13.9·CPU. wheel은 Python >=3.13,<3.14입니다. 다른 OS·PC·GPU/드라이버·장시간·세 CCTV 동시 실시간은 이번 안정 배포에서 미검증입니다.
- 한계: 가림·ID 유실로 출입을 놓칠 수 있고 내부 인원·빈칸·대기시간은 가정에 따른 추정입니다. 수동 정답 기반 정확도는 미평가이며 실제 CCTV 수신·예측모델 연동은 제공하지 않습니다.

상세: [AnalysisService·데이터 계약](docs/DATA_CONTRACT.md) · [실행 예제](examples/analyze_video.py) · [최종 인계](docs/FINAL_HANDOFF.md) · [검증 근거](docs/handoff_verification_032.json) · [이전 인계·검증 이력](docs/README_HISTORY.md).
