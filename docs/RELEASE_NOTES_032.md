# 안정 인계 CCTV analysis 0.3.2

시작: https://github.com/IRE0330/2026DeepLearning-1/blob/cctv-analysis-v0.3.2/cctv-analysis/README.md

검증된 0.3.2 wheel은 재빌드하지 않았습니다. 오늘의 구역·정확도 실험과 수동 정답 변경은 제외했습니다. 출입·마스킹·대기 3.5초·CSV 13열·계산식·AnalysisService 공개 인터페이스를 유지합니다.

- `deployment.zip`: 새 설치/진단 안내와 스크립트, 검증된 소스·설정·예제·원본 wheel.
- `handoff.zip`: 최초 검증 인계 ZIP, 바이트/해시 그대로 보존.
- `example-results.zip`: 공유용 최종 예시 CSV 3개. 추론 입력/정답이나 새 분석 대체물이 아닙니다.
- `SHA256SUMS-0.3.2.txt`: wheel 및 ZIP의 SHA-256.

Windows x64 / Python 3.13.9 / CPU 환경에서 새 가상환경 설치·pip check·ultralytics import/메타데이터·짧은 실제 분석·새 CSV/API 일치를 검증합니다. macOS Python 3.13의 설치 절차는 제공하지만 해당 OS 실행은 미검증입니다. Python 3.14는 이 wheel의 지원 범위 밖입니다. 세 CCTV 동시 실시간, 다른 장비/OS/GPU, 장시간 운영은 미검증입니다.

가중치는 직접 첨부하지 않습니다. 실제 사용 파일과 동일한 공식 `yolo11n.pt` 다운로드:
https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt

SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`

Ultralytics AGPL-3.0/Enterprise 조건과 프로젝트 전체 라이선스의 적용 범위를 확인해야 합니다. 이 저장소 전체의 배포 라이선스가 별도로 확정되지 않아 직접 재배포 대신 공식 경로·파일명·검증 해시를 제공합니다. 라이선스 고지: https://www.ultralytics.com/license

원본·결과 영상과 전체 outputs는 공개 권한 근거가 없어 제외했습니다. 인증정보·가상환경·MICC 데이터·임시 로그는 포함하지 않습니다. MICC 목록 점검 보조 코드는 사용자 확인에 따라 안정 0.3.2 그대로 유지합니다.

태그는 게시 소스 커밋을 고정합니다. 모듈 전용 태그에만 실행되는 workflow가 파일 해시와 wheel/소스 일치를 검증한 뒤 게시하며 기존 Release를 덮어쓰지 않습니다.
