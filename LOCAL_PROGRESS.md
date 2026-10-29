# 로컬 개발 마무리 기록

기준일: 2026-10-25 (Asia/Seoul). 추가 개발은 중단하고 현재 상태를 저장·백업했습니다.

공개 공유본: 개인 PC 절대경로를 제거하고 실행 스크립트를 환경 선택 방식으로 정리했습니다. 아래 백업·Push 미실행 기록은 로컬 개발 종료 당시의 이력입니다. 사용자 설정, 저장된 기준선, SQLite 및 진단·백업 자료는 로컬에 보존하며 이번 소스 공유에는 포함하지 않습니다. 원격에 이미 추적된 파일은 이번 작업에서 삭제하지 않습니다.

## 실행

프로젝트 최상위 PowerShell에서:

```powershell
.\run-dashboard.ps1
```

- 주소: http://localhost:8501
- 사용 Python: `-Python` 인수 또는 `DASHBOARD_PYTHON` 환경변수로 지정한 Python
- 스크립트가 프로젝트 폴더로 이동하고 UTF-8·로컬 8501 포트로 실행합니다.
- 기존 `rr313` 환경은 유지합니다. 공개 실행 스크립트는 각 PC의 Python 환경을 선택합니다.

## 저장한 주요 변경 파일

- `run-dashboard.ps1`: Windows 로컬 실행.
- `busan_restroom_dashboard/app.py`, `core.py`, `views.py`: 거리 기반 대표 대기시간·혼잡도 통일, 인원 기반 시간 표시 제거.
- `busan_restroom_dashboard/worker.py`: 긴 Windows 경로를 피하도록 `analysis_runs/<실행ID>`에 분석 출력.
- `busan_restroom_dashboard/distance_demo.py`, `distance_ui.py`, `distance_editor.js`, `distance_display.py`: CCTV별 마우스 기준선 지정·판정·표시.
- `busan_restroom_dashboard/distance_stability.py`: 영상 시각 기준 최대 3초 유지, 최근 판정 유지 표시, 연속 관측 확인.
- `busan_restroom_dashboard/history.py`, `history_ui.py`: 과거 인원 기반 시간 환산 제거, 거리 기반 그래프.
- `cctv-analysis/src/cctv/core.py`, `distance_candidates.py`: 거리 분석에만 쓰는 조건부 후보자 근거 추가. 기존 출입·잔류 카운팅은 유지.
- 관련 안내: `busan_restroom_dashboard/README.md`, `DISTANCE_DEMO.md`.
- 테스트: `tests/test_distance*.py`, `test_distance_frontend.cjs`, `test_distance_stability_frontend.cjs`, `test_worker_output_path.py`, `build_distance_fixtures.py`.

## 보존할 설정과 데이터

- `busan_restroom_dashboard/data/settings.json`: 북쪽·동쪽·남쪽 각각의 5m·10m·15m 기준선, 시작점, 영상 식별값과 기타 사용자 설정. 총 9개 기준선이 저장되어 있습니다.
- `busan_restroom_dashboard/data/dashboard.sqlite`: 기존 실행·작업·분석 레코드.
- `busan_restroom_dashboard/data/`: 영상, 미리보기, 기존 실행 자료.
- `analysis_runs/`: 원본 분석 결과, CSV, 상세 JSON 및 추적 로그.
- `configs/`, 모델 파일, 원본 CSV·Excel 및 `.local-run/`의 기존 진단·백업 자료.

거리·시간 기준은 고정입니다. 5m 미만은 여유/1분 미만, 5m 이상은 보통/1분 이상, 10m 이상은 혼잡/2분 이상, 15m 이상은 매우 혼잡/3분 이상입니다. 모두 **임의 거리 기준 시연값**입니다. 거리 판정 실패 시 인원 기반 수식으로 대체하지 않습니다. 기존 외부 분석 CSV 형식과 모듈 원본 값은 호환성을 위해 보존합니다.

## 미해결 문제

1. 북쪽의 **2분 이상 ↔ 측정 불가 표시 불안정**: 최대 3초 유지·연속 관측 로직으로 일부 완화했지만 미해결로 남깁니다. 기준선 폭 필터, 가림/추적 중복 억제, 체류 근거 부족 등이 원인입니다. 3초를 넘는 판정 공백은 측정 불가로 표시합니다.
2. **실제 거리 정확도 미검증**: 기준선은 관리자 임의 지정값이며 실측 거리·실제 대기시간 정확도를 입증하지 않았습니다. 전체 영상 정답 라벨 기반 오탐률도 미검증입니다.
3. **MySQL 열차 DB 인증 오류**: 앞선 진단에서 `auth_gssapi_client` 인증 방식의 드라이버 미지원이 확인됐습니다. DB 인증 설정은 변경하지 않았습니다.

자동 테스트 통과와 실제 영상 정확도 검증은 구분합니다. 상세 기록은 `.local-run/candidate-audit/REPORT.md`, `.local-run/stability-audit/REPORT.md`를 참고하세요.

## 백업

현재 프로젝트 전체(숨김 파일, 기존 분석 결과·영상·CSV·설정·진단 자료 포함)를 프로젝트 밖의 프로젝트 밖의 로컬 백업 경로 하위 시간별 폴더에 보관합니다. 해당 폴더에는 프로젝트 ZIP, SHA-256 파일 목록, 검증 결과 및 SQLite 일관성 스냅샷이 있습니다. 정확한 경로는 프로젝트의 `.local-run/final-backup-location.txt`에 기록합니다.

기존 파일·분석 결과 삭제, GitHub 커밋·Push·브랜치 작업, 추가 기능·알고리즘 변경은 하지 않았습니다.
