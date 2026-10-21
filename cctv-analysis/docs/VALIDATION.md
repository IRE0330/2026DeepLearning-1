# 설치·호출 검증 — 2026-10-18

**2026-10-21 / 0.3.2 최신 인계 검증:** [FINAL_HANDOFF.md](FINAL_HANDOFF.md)와 `handoff_verification_032.json`을 기준으로 합니다. 아래 내용은 2026-10-18 실행 이력입니다. 이번에는 동일 PC의 저장소 내 별도 수신 폴더·새 가상환경에서 ZIP의 wheel을 설치해 검증하며 다른 PC 검증으로 해석하지 않습니다.

최종 결과 정리의 추가 검증은 [FINAL_HANDOFF.md](FINAL_HANDOFF.md)와 [final_output_checks.json](final_output_checks.json)에 있습니다. 사용자 전체 수동 입장/퇴장 north10/11·south4/3·east7/6과 자동5/9·2/2·5/3을 확인했습니다. 시각별 정답이 없어 Precision·Recall·F1은 만들지 않았습니다. 수동 총합과 내부 검산값으로 이벤트·CSV를 수정하지 않았고 추가 튜닝/학습은 없습니다. 원본·최신 마스킹·초기29/3/3·칸27/19/23·105초 가정·전체 프레임·기록1초/13열/1시간·최종 영상/CSV 일치를 검사했습니다. 남쪽/동쪽의 표시 전용 재렌더링은 재추론이 아닙니다. 기존 설치/83개 기능 검증은 재사용하며 이번 경로 정리에 관련된 검사만 추가합니다.

패키징 전 성능 시험과 이번 기능 검증을 구분합니다. 단일 재생속도 모사의 북쪽/남쪽/동쪽 최대43/44/59ms, 세 입력 적체 자동 중단은 기존 로그를 확인한 이력입니다. 이번 작업에서 전체 영상을 다시 탐지·분석하거나 동시 처리 구조를 개선하지 않았습니다. 사전 PTS 검사는 기존 정책대로 전체 시각 메타데이터를 검사합니다.

## 이번 실제 실행

Windows·Python3.13.9에서 기존 CPU/GPU 가상환경을 보존하고 별도 임시 CPU 가상환경을 만들었습니다. 공식 CPU torch2.14.1+cpu/torchvision0.29.1+cpu, 기존 잠금 의존성, Streamlit1.66.0을 설치했습니다. pip check 통과입니다. base wheel은 영상·가중치·torch·Streamlit 없는 별도 가벼운 환경에서도 import/CLI·콘솔 entry point 도움말을 확인했습니다. 설정/정답 양식 내보내기와 기존 폴더 덮어쓰기 거부도 확인했습니다.

CPU wheel은 프로젝트 **밖 임시 작업 폴더**에서 설치된 site-packages의 cctv를 import해 사용했습니다. src를 PYTHONPATH로 연결해 설치 성공이라고 주장하지 않습니다. GPU만 기존 .venv-gpu의 소스 API로 짧게 실행했고 기존 GPU 패키지는 설치/교체하지 않았습니다.

| 경로/방식 | 실제 범위 | 확인 |
|---|---|---|
|새 CPU 환경·설치된 wheel·공개 API|북쪽0~3.25초,78프레임,1초3행|레코드/CSV 동일·13열·ID·정상 완료·실제 CPU FP32|
|최종 wheel·프로젝트 밖 CLI|북쪽0~1.25초,30프레임,1행|프리셋/영상/모델/결과 경로 지정·정상 완료·잔여0.25초|
|같은 CPU 환경·공개 API 중지|북쪽28프레임,1행까지|첫 수신 후 정상 중지·stopped 구분·CSV 닫힘·잔여/최종 보존|
|기존 .venv-gpu·소스 공개 API|북쪽0~2.25초,54프레임,2행|backend/가중치/결과 cuda:0·FP32, 레코드/CSV 동일|
|Streamlit AppTest+실제 CPU 탐지|북쪽37프레임,1행 후 UI로 중지|UI 재실행129회에도 같은 작업·최신값 표시·다른 세션 시작/중지 제한·정상 중지|
|CPU/GPU API·AppTest 실제 자료 없음|존재하지 않는 파일|failed 상태와 구체적인 경로를 제공·0행을 정상 성공으로 표현하지 않음|

AppTest는 브라우저 없이 Streamlit 스크립트/위젯을 실행하는 공식 프레임워크입니다. 실제 분석 중 수동 조회 rerun의 최고 경과시간은 약0.024초였지만 브라우저 렌더링·자동1초 타이머·네트워크 왕복의 성능 보장이 아닙니다. **실제 브라우저/웹소켓 세션 연결 종료/서버 강제 종료를 직접 검증한 것은 아닙니다.** UI 연결 lease/중지 timeout/프로세스 강제 종료는 별도의 모의 프로세스 테스트로 검사했습니다. 실제 수동 카운팅 정답 정확도도 평가하지 않았습니다.

83개 unittest가 통과했습니다. 기존75개 규칙/CSV/시간/전달/오버레이 테스트와 새8개 공개 API/Windows spawn/Streamlit 테스트입니다. 느린 소비자·cursor·record_id·null·최신 사본 변경 격리·중복 시작·소유권·lease·재시작·정상 중지·강제 종료·자식 비정상 종료·자료 경로·UI 상태를 검사합니다. 합성/가짜 작업자 시험을 실제 사람 탐지 정확도 검사로 해석하지 않습니다.

wheel은 약99KB이며 소스/마스킹 사본의 바이트 일치, 빈 정답 양식/예제 포함과 영상/가중치/캐시/인증정보 미포함을 확인했습니다. 기존805개 검사 대상은 소스25개 이동을 반영해 대조했습니다. 의도한 소스/문서10개 외795개가 SHA-256 동일했고, 기존 결과693개·설정12개·정답20개와 규칙/계산/구간 집계/기하 코드를 보존했습니다. 이동한 파일은 누락되지 않았으며 Git 표시의 루트 소스 삭제는 새 src/cctv로 옮긴 결과입니다.

설치 검증에서 사용자 홈 캐시 접근과 Windows JSON 상태 교체 충돌을 발견해, API 캐시는 지정 출력 아래에 두고 활성 상태를 SQLite WAL로 조회하도록 수정했습니다. 초기 실패 로그도 삭제하지 않았습니다. 성공/중지/자료 없음 결과는 아래 verification.json이 가리키는 실행을 기준으로 확인하세요.

## 근거 위치

개발 PC 프로젝트 상대 경로입니다. 대용량 원본/영상/결과는 wheel/Git에 포함하지 않습니다.

- outputs/package_handoff_3271ac24/cpu/verification.json
- outputs/package_handoff_3271ac24/gpu/verification.json
- outputs/package_handoff_3271ac24/ui/ui_verification.json
- inspections/package_handoff_20261017_235317_3271ac24/tests.txt
- inspections/package_handoff_20261017_235317_3271ac24/before.json
- cctv-analysis/docs/validation_checks.json — 패키지/보존/검증 요약

CPU 정상 CSV: `outputs/package_handoff_3271ac24/cpu/job_e39314bed73e41f2b5849dce9a2ed9f3/analysis/north_20261018_001104_7adba922/shared/north_2026-10-14_0000.csv`.

기존 단일 재생속도 시험 근거는 outputs/paced_single_20261017_221517_1fc29ead(north), paced_single_20261017_223347_7040a3cd(south), paced_single_20261017_224801_b1147deb(east)의 timing_summary/summary입니다. 기존 동시 시험은 outputs/paced_concurrent_20261017_221734_8a201c7d입니다. 이번 설치 검증 수치로 다시 이름 붙이지 않았습니다.

## 재현 명령

인계 폴더에서 의존성을 설치한 Python으로 다음을 실행합니다.

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'tests')
python -B -m unittest discover -s tests -v
python -m build --wheel
```

프로젝트 밖 폴더에서 wheel을 설치한 Python으로 실제 짧은 호출을 재현할 수 있습니다. 아래 materials 경로에는 원본 영상/동일 가중치가 있어야 하고 output은 쓰기 가능한 새 경로로 지정합니다.

```powershell
python 'D:\handoff\cctv-analysis\scripts\verify_install.py' --materials 'D:\materials' --output 'D:\results\installation-check' --device cpu --end 3.25
python 'D:\handoff\cctv-analysis\scripts\verify_streamlit_actual.py' --materials 'D:\materials' --output 'D:\results\ui-check'
```

verify_install의 materials는 기존 개발 자료 배치(북쪽_화장실_cctv.mp4와 models/yolo11n.pt)를 사용한 검증 스크립트입니다. 일반 새 영상 호출은 examples/analyze_video.py 또는 Service.start에 실제 영상/모델 경로를 직접 지정합니다.

실제 CCTV/네트워크·장시간 운영·브라우저 렌더링/연결·수동 정답 정확도·다른 Python/OS·다른 GPU·예측모델·세 환경 동시 처리 개선은 미검증/후속 범위입니다. 이 검증 단계에서는 Git push/main 병합/외부 배포를 하지 않았습니다. 후속 작업 브랜치 공유는 이 검증 기록의 재수행과 구분합니다.
