# 최종 인계 — 2026-10-18

담당 폴더는 `cctv-analysis/`입니다. 이 폴더의 설치 가능한 패키지를 팀원의 프로그램에서 호출합니다. 결과 CSV만 재생하는 패키지가 아닙니다. 실제 원본 영상·가중치는 별도로 준비해야 합니다. 분석 소스·API·마스킹·집계 임계값·Streamlit 예제 정책은 이번 정리에서 변경하지 않았습니다.

## 팀원 시작 명령

저장소의 작업 브랜치를 clone한 뒤 `cctv-analysis`에서 실행합니다. Python 3.13을 사용합니다. 기존 개발 가상환경이나 임시 검증 폴더를 복사하지 않습니다.

```powershell
py -3.13 -m venv .venv-cctv
& .\.venv-cctv\Scripts\python.exe -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
& .\.venv-cctv\Scripts\python.exe -m pip install '.[analysis,streamlit]'
& .\.venv-cctv\Scripts\python.exe -m pip check
& .\.venv-cctv\Scripts\python.exe -m cctv --help
```

이 버전 조합은 기존 Windows/Python 3.13.9에서 검증한 조합입니다. CUDA 설치는 [HANDOFF](HANDOFF.md)의 별도 GPU 환경 안내를 따릅니다. GPU가 필요한데 사용할 수 없으면 자동 CPU 대체 대신 오류를 표시합니다. 개인 PC 경로를 고정하지 않으며 CLI/API로 영상·모델·쓰기 가능한 출력 경로를 지정합니다.

원본 영상이 `D:\materials`에 준비됐다는 예시입니다. 실제 위치로 바꿉니다. 모델은 `D:\materials\models\yolo11n.pt`의 동일 해시 파일을 사용합니다. 첫 검사는 짧게, 전체 분석은 `--end`를 생략합니다.

```powershell
& .\.venv-cctv\Scripts\python.exe examples/analyze_video.py --room north --profile demo --video 'D:\materials\북쪽_화장실_cctv.mp4' --model 'D:\materials\models\yolo11n.pt' --output 'D:\results' --device cpu --end 3.25
& .\.venv-cctv\Scripts\python.exe -m streamlit run examples/streamlit_app.py
```

새 원본 파일이나 다른 카메라 구도에 기존 마스킹이 맞는지는 확인해야 합니다. 모델은 자동 다운로드하지 않습니다. 기존 `models/yolo11n.pt`의 해시와 모델 제약은 [MODEL](MODEL.md)을 참고합니다.

## 내 Streamlit 프로그램에서 호출

[DATA_CONTRACT](DATA_CONTRACT.md)의 `AnalysisService`를 사용합니다.

- 시작: `service.start(owner=session_id, restroom_id="north", profile="demo", video_path=..., model_path=..., output_dir=..., device="cpu")` → `AnalysisJob` 반환.
- 상태: `service.status(session_id)` 또는 `job.status()`.
- 최신 저장값: `job.latest()` → 레코드가 아직 없으면 `None`.
- 비차단 순차 수신: `batch = job.read_records(cursor, limit=100)`; 처리 후 `cursor = batch.next_cursor`. cursor는 바이트 오프셋입니다.
- 단순 Python 순차 수신: `job.records()`; 이 대기형 iterator를 UI 스레드에서 반복하지 않습니다.
- 중지: UI에서는 `service.stop(session_id, wait=False)` 후 상태 조회. 일반 Python에서는 `job.stop()`.

`examples/streamlit_app.py`는 설치된 패키지의 실제 예제를 실행합니다. `st.cache_resource`로 Service를 공유하고, `st.fragment(run_every=1)`에서 상태·레코드를 조회합니다. 전체 Streamlit 서버 세션에서 작업 하나만 허용하며 같은 소유자/다른 소유자의 중복 시작을 막습니다. 소유자만 중지할 수 있습니다. 모델/분석은 별도 spawn 프로세스에서 실행하고 UI rerun으로 새 분석을 만들지 않습니다. 기존 90초 lease·종료/복구 정책은 HANDOFF에 있습니다. Windows 진입점에는 `if __name__ == "__main__"` 가드가 필요합니다.

출력은 `output_dir` 아래 새 실행 폴더에 저장되며 설치 패키지 폴더에 쓰지 않습니다. 전달은 disabled이고 새 API 서버·예측 클라이언트·완성 프론트는 추가하지 않았습니다. Service 기본 프로필은 operating(10초)이므로 시연 1초 기록에는 `profile="demo"`를 명시하세요. 사용자 프로그램이 받은 레코드는 CSV 저장 후 동일 직렬화된 envelope이며 최신값 조회 사이에 여러 행이 생겨도 순차 수신으로 모두 읽을 수 있습니다.

## 로컬 최종 결과와 공개 CSV

저장소 루트 기준입니다. `outputs/final/`은 로컬 전달 자료이며 Git에는 포함하지 않습니다.

```text
outputs/final/
  manifest.json
  README.md
  north/  south/  east/
    annotated.mp4
    shared/{환경}_2026-10-14_0000.csv
    events.csv
    timeseries.csv
    final_state.json
    config_used.json
    summary.json
    diagnostics.jsonl
    interval_details.jsonl
    remainder.json
    final_usage_detail.json
    record_index.jsonl
    [렌더링·기록 지연 검증 자료]
  evidence/retired_output_metadata/  # 과거 시험의 작은 측정·설정·결론
```

각 환경의 공유 CSV는 하나입니다. 같은 내용의 `usage_summary.csv`는 최종 폴더에 두지 않고 참조를 `shared/`로 통일했습니다. `timeseries.csv`는 프레임별 상세값이며 공유 CSV와 의미가 다릅니다. `final_state.json`은 마지막 프레임 상태이고 정기 CSV의 마지막 행과 항상 같은 시각은 아닙니다. 1초 미만 잔여는 `remainder.json`으로 별도 보존합니다.

| 환경 | 원본 / 영상 ID | 길이·프레임 | CSV 행 수 | 정기 기록 범위(KST) | 자동 입장/퇴장·최종 내부 |
|---|---|---|---:|---|---|
| north | 북쪽_화장실_cctv.mp4 / north_b4126dab3c98ce77 | 105.166667초·2,524 | 105 | 2026-10-14 00:00:00~00:01:45 | 5/9·25명 |
| south | 남쪽 화장실_CCTV.mov / south_66e33f774b247cd0 | 94.233333초·2,827 | 94 | 2026-10-14 00:00:00~00:01:34 | 2/2·3명 |
| east | 동쪽_화장실_cctv.mov / east_9b25794e5b6aff09 | 90초·2,700 | 90 | 2026-10-14 00:00:00~00:01:30 | 5/3·5명 |

초기 내부/운영 가능 칸은 north 29/27, south 3/19, east 3/23입니다. 평균 칸 이용시간은 모두105초, 가상 촬영 시작일시는 `2026-10-14T00:00:00+09:00`, 시연 기록1초·한국시간 정시1시간 분할·UTF-8 BOM 공유13열입니다. 실제 촬영일이나 실제 내부 관측값을 뜻하지 않습니다. `demo_assumptions`, `synthetic_material`, `virtual_scenario_time` 상태를 유지합니다.

Git 공개용 동일 CSV는 [examples/data](../examples/data/)의 환경별3개 파일입니다. 입력·출력 개인 경로가 없는13열 CSV이며 로컬 대표 파일과 바이트 해시가 같습니다. API 응답 형식은 이 CSV만으로 충분하지 않으므로 DATA_CONTRACT의 envelope도 확인하세요.

최신 단독 전체 실행의 로그와 CSV를 선택했습니다. 북쪽 영상은 이전 전체 GPU A-video와 최신 전체 로그/이벤트/상세/CSV가 바이트 일치해 그대로 사용합니다. 남쪽·동쪽은 최신 저장 관측을 원본 프레임에 재생해 전체 영상을 재렌더링했습니다. 탐지·추적을 다시 실행하거나 집계를 재계산·보정하지 않았습니다. 기존 CPU 기반 동쪽 영상/CSV를 최신 GPU CSV에 혼합하지 않았습니다. 이전 동쪽 CSV와 최신 CSV는77~84번째 행의 대기값 일부가 달랐지만 출입 총합은 같았습니다.

원본 SHA-256·마스킹·프레임 수·이벤트·정기 상태·최종 상태·출력 전체 디코딩을 검증했습니다. 공개 요약은 [final_output_checks.json](final_output_checks.json), 로컬 파일별 출처·해시·구 경로 대응은 `outputs/final/manifest.json`입니다. 과거 docs의 outputs 경로는 당시 시험 이력이며 현행 최종 경로는 위 경로입니다. 삭제된 과거 파일은 `cleanup_report.json`과 보존한 소규모 근거로 추적합니다.

## 수동 총합과 정확도 한계

| 환경 | 사용자 수동 입장/퇴장 | 자동 입장/퇴장 | 수동−자동 입장/퇴장 |
|---|---:|---:|---:|
| north | 10/11 | 5/9 | +5/+2 |
| south | 4/3 | 2/2 | +2/+1 |
| east | 7/6 | 5/3 | +2/+3 |

출처는 사용자 전체 영상 수동 집계이며 이벤트별 시각은 아직 없습니다. [manual_totals_20261018.json](manual_totals_20261018.json)에 별도 저장했습니다. 총합 차이만으로 누락 수·Precision·Recall·F1을 만들 수 없습니다. 수동 총합 검산 내부값 north28·south4·east4는 자동 이벤트·CSV·inside 정답에 덮어쓰지 않았습니다. 실제 내부 정답도 아닙니다.

로컬 `reviews/manual_totals_20261018/`의 원본·기준점 궤적·후보301행과 빈 정답 사본을 보존했습니다. 후보는 중복 사유를 포함하며 실제 누락 수가 아닙니다. 자동 후보 밖의 출입도 확인하는 전체 수동 이벤트 작성이 필요합니다. 시각 기준은 그 안내서에 정의한 목적지 영역 연속0.2초 확인 시각이며, 보조 worksheet의 경계 통과 시각과 구분합니다. 현재 evaluate는 같은 방향의 확정 시각을 ±1초로1:1 매칭합니다. 수동 이벤트별 정확도 평가는 미완료입니다.

## 검증된 범위와 후속 과제

기존 실제 설치·API 호출·중지·오류·Streamlit AppTest 및83개 테스트 근거는 [VALIDATION](VALIDATION.md)과 [validation_checks.json](validation_checks.json)에 있습니다. 이번 정리는 분석 소스/설치 구성을 바꾸지 않았으므로 기존 검증을 재사용하고, 파일 경로·wheel 소스 동일성·관련 API/기록 검사를 확인했습니다. 기존 CPU/GPU 환경에 Streamlit을 새로 설치하지 않았습니다. 과거 임시 CPU 설치 환경은 팀원 실행의 의존성이 아닙니다.

세 환경 각각 단독 재생속도 입력 모사는 준비 완료 후1초 기록 지연 목표를 충족했습니다. 기존 측정의 최대 지연은 북쪽43ms·남쪽44ms·동쪽59ms입니다. 영상 검사/모델 준비/워밍업의 시작 준비시간이 발생하며 이 지연과 구분합니다. 세 환경 동시 입력은 지연 누적으로 보호 기준에 따라 중단되어 목표를 충족하지 못했습니다. 동시 처리 구조 개선은 후속 과제입니다. 기존 수치·측정 CSV·요약은 보존했고 속도 시험을 반복하지 않았습니다.

실제 CCTV·네트워크·장시간 운영·브라우저 연결/타이머와 다른 OS/GPU는 미검증입니다. 실제 예측모델은 미구현·미연동이며 예상 대기시간은105초 사용자 가정식입니다. Random Forest·앙상블·정확도 튜닝·새 모델 학습은 수행하지 않았습니다.

## 별도 전달 자료와 wheel

- 원본3개: `북쪽_화장실_cctv.mp4`, `남쪽 화장실_CCTV.mov`, `동쪽_화장실_cctv.mov`.
- 가중치: `models/yolo11n.pt`; MODEL.md의 SHA-256 대조.
- 로컬 최종 결과: `outputs/final/` 전체. 필요하면 수동 검토 `reviews/manual_totals_20261018/`도 함께 전달.
- 로컬 최신 wheel: `cctv-analysis/dist/busan_cctv_analysis-0.1.0-py3-none-any.whl`. Git 제외. 런타임 소스·마스킹·빈 양식과 wheel 내부 바이트가 일치해 재빌드하지 않았습니다. 이번 최신 인계 문서는 wheel과 함께 소스 폴더의 docs/를 전달합니다.

wheel이 없으면 cctv-analysis에서 `python -m pip install build` 후 `python -m build --wheel`로 생성합니다. wheel 전달받은 팀원은 CPU/CUDA PyTorch를 먼저 준비한 뒤 `python -m pip install 'dist/busan_cctv_analysis-0.1.0-py3-none-any.whl[analysis,streamlit]'`로 설치합니다. 실행 예제와 최신 문서도 함께 제공합니다.
