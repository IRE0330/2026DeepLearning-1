# 딥러닝 기초 1조

AI 기반 화장실 혼잡도 분석 및 분산 안내 시스템

## CCTV 화장실 분석 모듈

저장 영상에서 출입·외부 대기를 집계하고 내부 인원 추정치와 CSV를 생성합니다. 팀 앱은 AnalysisService로 분석 결과를 받을 수 있습니다.

- **[다운로드·설치·짧은 실행](cctv-analysis/README.md)** · [모듈 개요](cctv-analysis/README.md)
- [API·데이터 계약](cctv-analysis/docs/DATA_CONTRACT.md) · [최종 인계](cctv-analysis/docs/FINAL_HANDOFF.md)
- [이전 상세 실행·검증 기록](cctv-analysis/docs/ROOT_README_HISTORY.md)

안정 배포는 0.3.2, 검증 환경은 Windows x64·Python 3.13.9·CPU입니다. 실제 CCTV 수신·예측모델 연동은 제공하지 않으며, 정확도·동시 실시간 처리·다른 환경의 지원 범위는 시작 안내를 확인하세요.
