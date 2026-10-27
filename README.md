# 딥러닝 기초 1조

AI 기반 화장실 혼잡도 분석 및 분산 안내 시스템

## CCTV 화장실 분석 모듈

저장 영상에서 출입·외부 대기를 집계하고 내부 인원 추정치와 CSV를 생성합니다. 팀 앱은 AnalysisService로 분석 결과를 받을 수 있습니다.

- **[다운로드·설치·짧은 실행](cctv-analysis/deployment/START_HERE.md)** · [모듈 개요](cctv-analysis/README.md)
- [API·데이터 계약](cctv-analysis/docs/DATA_CONTRACT.md) · [최종 인계](cctv-analysis/docs/FINAL_HANDOFF.md)
- [이전 상세 실행·검증 기록](cctv-analysis/docs/ROOT_README_HISTORY.md)

기존 안정 배포 0.3.2와 선택형 북쪽 GPU 기능을 추가한 0.3.3을 함께 제공합니다. 기본 n·남쪽·동쪽 실행과 AnalysisService API는 유지됩니다. 검증 환경은 Windows x64·Python 3.13.9이며 북쪽 s는 RTX 4060 CUDA FP32에서 확인했습니다. 실제 CCTV 수신·예측모델 연동은 제공하지 않습니다. [개발 영상 평가·검증과 한계](cctv-analysis/docs/NORTH_GPU_S_033.md)를 확인하세요.
