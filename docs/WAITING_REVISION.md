**과거 0.2.0 / 1초 기준 이력입니다. 최신 기준은 [WAITING_35S.md](WAITING_35S.md)의 0.3.0 / 3.5초입니다.**

# 대기 판정 수정 — 0.2.0 / 2026-10-18

이 문서가 기존 candidate 포함 지시와 0.1.0 인계 안내를 대체합니다. Git commit/push는 하지 않았습니다. 최신 전체 산출물은 저장소 루트 `outputs/final/evidence/history/confirmed_waiting_20261018_v020_r2/`입니다. `outputs/final/evidence/history/original_final/`은 수정 전 비교 입력으로 보존합니다. 첫 준비 시도의 `outputs/final/evidence/history/confirmed_waiting_20261018_v020/`는 보관 설정의 상대 영상 경로 해석 문제로 중단된 불완전 결과이며 전달하지 않습니다.

## 원인과 규칙

기존 `core.Counter`는 이동 구간 속도와 느린 이동 누적 조건을 이미 계산했지만 `waiting_observed = candidate + confirmed`로 합산했습니다. 따라서 빠른 통과자도 후보가 된 즉시 영상·CSV·공개 API의 외부 대기에 포함됐습니다. 세 환경의 기존 확정 시간은 3초였으며, 체류·속도 계산 자체가 생략된 문제가 아니었습니다.

진입 시 candidate이며 합계 0명입니다. 인접한 실제 관측 사이의 박스 하단점 이동량을 두 박스의 평균 높이로 나눈 속도가 0.35 body-heights/s 이하인 증거를 연속 1초 누적하고, 기존 1초 이동 구간의 경로 평균 속도도 기준 이하일 때 confirmed가 됩니다. 구간 최소 관측 폭은 기존 0.3초입니다. 실제 거리 보정이 없어 m/s는 사용하지 않습니다. 빠른 이동은 증거를 초기화하며 한 프레임만 느려져도 즉시 확정되지 않습니다. 박스 잡음이 큰 정지자는 확정이 늦어질 수 있습니다.

확정 후에는 줄 전진·짧은 이동으로 해제하지 않습니다. 입장 확정 또는 대기 구역 밖에서 연속 관측된 0.8초 이탈로 종료합니다. candidate의 이탈은 즉시 해제합니다. 가림 유예는 confirmed에만 마지막 관측 시각부터 1.5초까지 적용합니다. 후보 가림은 합계에 포함하지 않으며 재관측 시 미관측 시간을 증거에 합산하지 않고 경로·후보 증거를 초기화합니다. 다른 ID는 병합하지 않습니다. 기존 근접 관측 ID가 있으면 이전 confirmed의 가림 합계를 보수적으로 억제하는 규칙을 유지합니다. 이는 동일인 판정이 아니며 진짜로 다른 근접 인원이 있으면 과소 집계할 수 있습니다.

`waiting_observed = waiting_confirmed_observed`, `waiting_total = waiting_observed + waiting_grace`입니다. 후보 수 필드는 그대로 제공하고 상태 태그는 `candidate_excluded`로 변경합니다. 정책 식별자는 `confirmed_observed_plus_confirmed_grace_1s_v3`입니다. 공개 함수·필드·CSV 13열 이름/순서는 유지합니다. 영상·상세 로그·구간 상세·CSV·AnalysisService는 같은 Counter 스냅샷을 사용합니다.

내부 = 초기 내부 + 누적 입장 − 누적 퇴장, 내부 대기 = MAX(내부 − 칸 수, 0), 전체 대기 = 외부 + 내부 대기, 빈 칸 = MAX(칸 수 − 내부, 0), 가정식 시간 = (전체 대기 + 1) × 평균 이용시간 ÷ 칸 수를 유지합니다. 미설정과 음수 내부 등의 기존 예외 및 null 전파도 유지합니다.

확정 1초와 CSV 기록 1초는 별도 설정입니다. 북/남/동 루트 설정과 wheel 번들 설정의 `rules.waiting_confirm_s`를 1.0으로 맞췄습니다. 운영 프로필의 10초 기록·초기값 null과 demo의 1초 기록·초기 29/3/3명은 분리 유지합니다. 칸 수 27/19/23, 평균 105초, 1시간 분할, prediction disabled입니다. 최종 좌표·탐지·ByteTrack·출입·수치표 디자인·프론트·예측 코드는 변경하지 않았습니다.

## 전체 실행과 비교

먼저 세 환경의 첫 10초를 동일 Counter로 검증했습니다(`representative_checks.json`). 그 뒤 기존 전체 로그의 프레임별 시각·ID·박스·관측/제외 기록과 누락 프레임 마커를 검증해 재계산했습니다. 재추론·재추적 없이 원본 해시를 확인한 영상의 모든 프레임에 새 상태를 렌더링하고 결과를 전체 디코딩했습니다. 입력 로그와 결과 경로·검증은 `comparison.json`, 환경별 `analysis/summary.json`, `videos/{환경}/render_summary.json`에 있습니다. 재계산과 렌더 단계에서 로그·스냅샷·이벤트를 다시 비교합니다.

|환경|프레임 / 1초 CSV 행|외부 대기 평균 전→후|최대 전→후|달라진 정수초 표본|입장/퇴장 전후 동일|
|---|---:|---:|---:|---:|---:|
|북쪽|2524 / 105|2.708→2.189|8→6|34|5/9|
|남쪽|2827 / 94|0.042→0.000|1→0|4|2/2|
|동쪽|2700 / 90|0.611→0.367|3→2|20|5/3|

위 평균은 0초를 포함한 `timeseries.csv` 정수초 표본(106/95/90개)이며 구간 끝 공유 CSV의 평균과 다릅니다. 출입 CSV는 바이트 동일합니다. 마스킹·탐지·추적 설정도 비교했습니다. 인원 감소 자체로 정확도 개선을 주장하지 않습니다. 시각별 수동 정답에 의한 precision/recall/MAE는 미검증입니다. 1초는 MVP 초기값으로 잠깐 멈춘 통행인도 대기로 오인할 수 있습니다. 남쪽의 확정 대기·줄 전진·확정자 가림은 이번 로그에 없으므로 해당 실제 장면 검증은 미검증입니다.

대표 프레임 9장을 `review_contact_sheet.jpg`로 육안 확인했습니다. 북쪽 0/1초의 후보→확정 색상과 합계 변경, 세 영상 수치표 위치·박스 표시를 확인했습니다. 동쪽 28.5초 벽면 인근 작은 확정 박스는 실제 사람 여부를 추가 확인해야 합니다. 관측 누락이 실제 가림인지, 확정 후 이동이 실제 줄 전진인지는 연속 장면의 수동 확인이 남아 있습니다. 정지 이미지 검토를 전체 행동 정답 검증으로 간주하지 않습니다.

## 영상에서 확인할 시각

시간은 파일 시작을 0초로 한 영상 시각입니다. 로그의 행동 후보이므로 실제 이용 의도나 동일인 가림 여부를 단정하지 마세요. `review_candidates.json`에 ID/시각이 있습니다.

|환경|재생 구간|확인 항목|
|---|---|---|
|북쪽|0–2초, ID 2|candidate에서 1.0초 confirmed로 전환, 후보 제외|
|북쪽|4–7초, ID 6 / ID 2|빠른 후보 통과와 confirmed 후 이동 유지; 실제 줄 전진 여부 수동 확인|
|북쪽|13–16초, ID 8|관측 누락 후 유예/재관측/만료, 실제 가림 여부 확인|
|남쪽|60–64초, ID 75|빠른 후보 진입 후 합계 0; 정지·확정 장면은 미검증|
|동쪽|1–4초, ID 2|빠른 통과 후보 제외|
|동쪽|27–30초, ID 127|정지·느린 이동 증거 후 28.5초 확정|
|동쪽|31–34초, ID 134|관측 누락과 유예; 실제 가림 여부 확인|

## 전달 파일과 재현

패키지 테스트는 91개 중 90개 통과·Streamlit 선택 의존성 부재로 1개 건너뜀입니다. 루트 호환 테스트는 83개 모두 통과했습니다. 모델 없는 신규 상태 테스트 8개와 기존 상태/집계/출입/누락 테스트를 포함합니다. 설치 wheel의 AnalysisService로 각 환경 첫 6초를 CPU에서 실제 재추론해 6개씩 총 18개 레코드를 수신했고, 수신 CSV 13열·상세 상태·동일 관측 Counter 재계산값이 일치했습니다. 이 짧은 재추론 결과는 설치/API 검증용이며 전체 재생 결과를 대체하거나 추론 차이를 대기 정책 효과로 합산하지 않았습니다. 전체 결과의 전후 비교는 모두 동일한 추적 입력을 사용했습니다. 최종 wheel 설치 경로의 Python·번들 JSON은 소스 및 API 검증 설치본과 바이트 비교했습니다. 근거는 `test_checks.json`, `installed_api/installed_api_checks.json`, `handoff_manifest.json`입니다.

- `cctv-analysis/`의 src, tests, scripts, README, docs, 빈 ground_truth 양식을 함께 갱신합니다. 새 정답 정책 메타데이터는 빈 양식에만 적용했으며 실제 정답을 생성하지 않았습니다.
- `cctv-analysis/dist/busan_cctv_analysis-0.2.0-py3-none-any.whl`을 전달합니다. 0.1.0 wheel은 과거 버전이며 전달하지 않습니다. 최종 wheel SHA-256과 설치/API 결과는 새 실행 폴더의 인계 manifest에 기록합니다.
- 원본 영상과 모델, 새 결과 폴더의 `videos/`, 환경별 `analysis/`, `shared/`, 비교/검증 자료는 별도 전달합니다.
- 루트 호환 사용자는 `cctv/__init__.py`가 동일 `cctv-analysis/src/cctv`를 가리키므로 새 소스와 루트 `configs/{north,south,east}.json`을 함께 갱신합니다.
- `examples/data/` 세 CSV는 새 검증 CSV와 바이트 동일한 출력 예시입니다. 실제 API/pipeline은 이 예시를 입력으로 사용하지 않습니다.

저장소 루트에서 다음으로 새 폴더에 재현합니다. 기존 output을 지정하면 덮어쓰지 않고 실패합니다.

```powershell
& .\.venv\Scripts\python.exe cctv-analysis/scripts/verify_waiting_revision.py --source outputs/final/evidence/history/original_final --output outputs/new_confirmed_waiting --phase prepare
& .\.venv\Scripts\python.exe cctv-analysis/scripts/verify_waiting_revision.py --source outputs/final/evidence/history/original_final --output outputs/new_confirmed_waiting --phase render
& .\.venv\Scripts\python.exe cctv-analysis/scripts/verify_waiting_revision.py --source outputs/final/evidence/history/original_final --output outputs/new_confirmed_waiting --phase compare
& .\.venv\Scripts\python.exe -m unittest discover -s cctv-analysis/tests
```

전체 영상 순차 처리 범위이며 세 환경 동시 실시간 보장은 하지 않습니다. 실제 CCTV·장시간 운영·새 예측모델은 이번 검증 대상이 아닙니다.
