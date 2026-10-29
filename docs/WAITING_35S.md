# 대기 확정 3.5초 — 0.3.0 / 2026-10-18

이 문서가 0.2.0의 1초 확정 설정을 대체합니다. 세 환경 모두 `rules.waiting_confirm_s = 3.5`이며 영상 시각으로 계산합니다. 정지·느린 이동 증거, candidate 합계 제외, confirmed 이후 짧은 전진 유지, 지속 이탈 0.8초/입장 확정 시 종료, confirmed 가림 유예 1.5초는 그대로입니다. 구간 속도·박스 높이 보정·중복 억제·ID 분리·관측 공백 초기화 로직을 바꾸지 않았습니다.

확정 3.5초와 demo CSV 기록 1초는 독립 설정입니다. 운영 프로필의 10초 기록과 초기값 null도 보존했습니다. demo 초기 내부 29/3/3, 칸 수 27/19/23, 평균 105초, 예측 disabled, 1시간 CSV 분할, 기존 계산식/null 예외·13열·출입·마스킹·탐지·ByteTrack·영상 수치표 디자인은 유지합니다.

설정 템플릿·루트 및 번들 north/south/east JSON, 재계산 도구·설치 검증 도구·테스트·빈 정답 메타데이터를 갱신했습니다. 정책 ID는 `confirmed_observed_plus_confirmed_grace_3p5s_v4`입니다. 재계산 도구는 고정 1초 대신 번들 프리셋의 확정 시간을 읽습니다. 기존 정답을 새 정책으로 자동 재분류하지 않습니다. 갱신한 실제 정답 양식은 헤더뿐인 빈 파일입니다.

## 전체 결과

수정 전 입력은 `outputs/final/evidence/history/confirmed_waiting_20261018_v020_r2/`의 전체 추적 로그입니다. 첫 10초씩 대표 검증 후 세 환경 전 프레임을 같은 관측 ID·박스·영상 시각으로 재계산했습니다. 재추론·재추적은 하지 않았고 원본 영상 해시를 확인한 후 새 숫자로 전체 영상을 렌더링했습니다. 이전 결과는 보존했습니다.

새 결과 루트: `outputs/final/evidence/history/confirmed_waiting_20261018_v030/`.

- 전체 영상: `videos/{north,south,east}/annotated.mp4`.
- 공유 CSV: `{환경}/shared/shared/{환경}_2026-10-14_0000.csv`.
- 상세 로그·이벤트·상태: `{환경}/analysis/`.
- 검증: `comparison.json`, `representative_checks.json`, `test_checks.json`, `videos/{환경}/render_summary.json`, `handoff_manifest.json`.
- 누락 비교: `missed_waiter_candidates.json`, `missed_waiter_review.jpg`.
- 실제 새/구 영상의 같은 순간 비교: `missed_waiter_comparison.jpg` (북쪽 ID 112/198, 확정·후보 표시 포함).

|환경|프레임 / CSV 행|외부 대기 평균 1초→3.5초|최대|달라진 정수초 표본|입장/퇴장 유지|
|---|---:|---:|---:|---:|---:|
|북쪽|2524 / 105|2.189→1.868|6→6|17|5/9|
|남쪽|2827 / 94|0→0|0→0|0|2/2|
|동쪽|2700 / 90|0.367→0.178|2→1|17|5/3|

평균은 0초 포함 정수초 상세 표본 기준이며 공유 CSV 구간 끝 평균과 다릅니다. 출입 events.csv는 바이트 동일하고 모든 정수초의 출입·내부값도 동일합니다. 공유 CSV·상세 상태·수신 envelope는 동일 집계값입니다. `examples/data/` 세 CSV는 새 CSV의 바이트 동일 사본이며 실제 분석 입력으로 사용하지 않습니다.

## 실제 대기자 미확정 비교와 한계

북쪽의 기존 confirmed ID 11개 중 9개는 확정이 늦어졌고 2개는 새 기준에서 한 번도 confirmed가 되지 않았습니다. 최초 줄의 ID 2/3/4/5/7/8은 1.0→3.5초로 늦어집니다. 실제 대기자도 최초 3.5초는 합계에서 빠집니다.

북쪽 **ID 198, 80–89초**를 우선 확인하세요. 81.5초와 85초 확대 프레임에서 대기 줄에 서 있는 사람으로 보입니다. 기존 최초 확정은 81.417초였지만 새 설정에서는 끝까지 candidate입니다. 저속 증거가 최대 3.0초이며 83.458초 인접 박스 이동 속도 0.373 body-heights/s가 기존 0.35 기준을 넘어서 초기화됩니다. 실제 동작과 박스 흔들림을 분리한 정답은 없지만, 이 사례는 긴 연속 저속 조건이 실제 대기자를 누락할 수 있음을 보여줍니다. 원 요청대로 이동 조건은 완화하지 않았습니다.

북쪽 **ID 112, 41.75–45.46초**는 기존 43.292초 확정에서 새 기준 미확정으로 바뀝니다. 최대 저속 증거는 3.042초입니다. 입구 가까이 잠시 서 있는 실제 사람이 보이지만 대기인지 입장 중인지 연속 장면 수동 확인이 필요합니다.

동쪽 미확정 ID 134(29–33초), 221(38–43초), 354(76–80초)의 확대 프레임은 벽면 소화기 부근 탐지 박스입니다. 실제 대기자 누락으로 분류하지 않았습니다. 남쪽은 1초 기준에서도 확정 대기 ID가 없어 확정 시간 증가에 따른 실제 대기자 누락 사례는 미검증입니다.

확대 이미지는 **이전 1초 결과 영상**에서 추출했고 표기는 ID별 전체 이력의 확정 유무를 비교한 것입니다. 선택한 순간마다 이전 상태가 confirmed라는 뜻은 아닙니다. 새 영상과 나란히 재생해 확인하세요. 로그상 같은 ID만 비교했으며 서로 다른 ID를 동일인으로 합치지 않았습니다.

대기 인원 감소만으로 정확도 개선을 주장하지 않습니다. 더 긴 확정 시간은 짧은 정지 통행인을 줄일 수 있는 동시에 실제 대기의 확정 지연과 누락을 늘립니다. 시각별 수동 정답에 따른 정확도·재현율은 미검증입니다. 실제 CCTV·장시간 운영·세 환경 동시 실시간 처리는 검증 범위가 아닙니다. 새 예측모델을 개발하지 않았고 commit/push하지 않았습니다.

## 전달과 재현

테스트는 패키지 93개 중 92개 통과·Streamlit 선택 의존성 부재로 1개 건너뜀, 루트 호환 85개 모두 통과했습니다. 모델 없는 상태 테스트에 3.4초 미확정/3.5초 확정, 느린 이동·고속 이동·확정 후 전진/이탈·가림 경계/재관측, 반복 전진하는 실제 대기 형태의 미확정 사례 및 세 프리셋의 확정/기록/가림 시간 독립성을 포함했습니다. 실제 설치 wheel에서 공개 API로 세 환경 각 6초를 CPU 재분석해 총 18개 레코드를 수신했고 CSV·상세 상태·관측 Counter 재계산값이 일치했습니다. 이 짧은 재추론은 설치 검증용이며 전체 결과 전후 비교에는 사용하지 않았습니다. 전체 비교는 동일 추적 입력이므로 추론 차이가 없습니다. 최종 wheel 소스·번들 자산과 설치/API 검증본도 바이트 비교했습니다.

새 설치 파일은 `cctv-analysis/dist/busan_cctv_analysis-0.3.0-py3-none-any.whl`입니다. 0.2.0은 1초 기준의 과거 패키지로 보존하고 전달 시 섞지 마세요. 담당 소스·tests·scripts·docs·examples와 루트 호환 설정을 함께 갱신합니다. `TEAM_UPDATE_FILES.md`와 0.3.0 handoff ZIP을 참고하세요.

```powershell
& .\.venv\Scripts\python.exe cctv-analysis/scripts/verify_waiting_revision.py --source outputs/final/evidence/history/confirmed_waiting_20261018_v020_r2 --output outputs/new_waiting_35s --phase prepare
& .\.venv\Scripts\python.exe cctv-analysis/scripts/verify_waiting_revision.py --source outputs/final/evidence/history/confirmed_waiting_20261018_v020_r2 --output outputs/new_waiting_35s --phase render
& .\.venv\Scripts\python.exe cctv-analysis/scripts/verify_waiting_revision.py --source outputs/final/evidence/history/confirmed_waiting_20261018_v020_r2 --output outputs/new_waiting_35s --phase compare
```
