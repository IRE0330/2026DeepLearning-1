# 최종 인계 — 0.3.1 / 2026-10-18

담당 패키지는 `cctv-analysis/`입니다. 현재 소스·번들 설정·wheel은 0.3.1이며, 루트 `cctv`는 같은 src/cctv를 가리키는 호환 경로입니다. 초기 관측 표시나 더미 데이터 간격 변경은 추가하지 않았습니다. 다른 담당자의 프론트·예측 코드와 main은 변경하지 않습니다.

## 최종 규칙

북쪽·남쪽·동쪽 모두 영상 시각의 연속 정지/느린 이동 증거 3.5초 후 확정합니다. candidate는 별도 표시하며 합계에서 제외합니다. confirmed의 짧은 전진은 유지하고 입장 확정 또는 지속 이탈 0.8초로 종료합니다. 확정자 가림 유예 1.5초와 중복 억제는 유지합니다. 동쪽은 기존 네 제외 구역에 소화기 7각형 하나만 추가했습니다. 제외 기준은 박스 하단 중앙점입니다.

기존 탐지·ByteTrack·출입 판정, 내부=초기+입장−퇴장, 내부 대기/전체 대기/빈 칸/가정식 대기시간 계산과 미설정·음수 예외를 유지합니다. 공유 CSV 13열 이름/순서는 그대로입니다. demo 1초 기록·KST 1시간 분할·초기29/3/3·칸27/19/23·평균105초와 운영 초기값 null·10초 기록은 분리합니다. 예측 전달은 disabled입니다.

## 설치와 공개 API

Python 3.13 기준입니다. CPU/CUDA 분석 의존성은 기존 requirements 잠금 파일과 설치 안내를 따릅니다. 모델과 원본 영상은 별도입니다. 최신 wheel과 이 문서를 함께 전달하세요.

```powershell
python -m pip install 'dist/busan_cctv_analysis-0.3.1-py3-none-any.whl[analysis,streamlit]'
python -m cctv --help
```

wheel 없이 소스에서 설치할 때는 `python -m pip install '.[analysis,streamlit]'`를 사용합니다. 새 환경에서 모델·장치 의존성까지 자동 확보된다는 뜻은 아닙니다.

```python
from cctv import AnalysisService

if __name__ == "__main__":
    with AnalysisService() as service:
        job = service.start(owner="my-session", restroom_id="east",
                            video_path="D:/materials/east.mov",
                            model_path="D:/materials/yolo11n.pt",
                            output_dir="D:/results", profile="demo", device="cpu")
        for record in job.records():
            print(record["csv_row"])
```

상태/최신값/비차단 커서 수신/중지는 [DATA_CONTRACT.md](DATA_CONTRACT.md)를 따릅니다. 기존 서명과 필드는 유지했습니다. API는 실제 영상·모델을 분석하며 examples/data CSV를 입력으로 사용하지 않습니다. 예시 CSV는 출력 예시입니다.

## 로컬 최종 결과

저장소 루트 `outputs/final/`의 north/south/east 각각에 다음 자료를 보존합니다.

- `annotated.mp4`: 전체 결과 영상.
- `shared/{환경}_2026-10-14_0000.csv`: 해당 환경 유일한 공유 1초 CSV.
- `events.csv`, `timeseries.csv`, `diagnostics.jsonl`, `interval_details.jsonl`.
- `config_used.json`, `summary.json`, `final_state.json`, `final_usage_detail.json`, `remainder.json`.
- `record_index.jsonl`: 경로를 갱신한 공개 수신 envelope. 기록 ID·CSV 수치·상세 상태는 보존했습니다.

|환경|프레임 / 길이|CSV 행|입장/퇴장|최종 내부|
|---|---|---:|---:|---:|
|north|2524 / 105.166667초|105|5/9|25|
|south|2827 / 94.233333초|94|2/2|3|
|east|2700 / 90초|90|5/3|5|

북쪽·남쪽은 0.3.0 완료 실행, 동쪽은 0.3.1 소화기 제외 완료 실행에서 가져왔습니다. 설정·영상 전 프레임 디코딩·CSV·상세/최종 상태를 대조했고 복사 전후 영상·CSV·이벤트 SHA-256이 같습니다. 재분석·재추적·수치 보정하지 않았습니다. examples/data의 세 CSV는 final의 공유 CSV와 바이트 동일합니다.

`manifest.json`, `copy_verification.json`, `path_relocation.json`, `cleanup_report.json`과 `evidence/`에 공통 근거를 보존했습니다. evidence/history는 과거 원본 바이트이므로 내부 경로 문자열은 당시 값이며 path_relocation.json으로 해석합니다. 현재 환경별 JSON·envelope와 공통 검증 사본은 현 경로로 갱신했습니다.

## 한계와 검토 장면

[WAITING_35S.md](WAITING_35S.md)의 북쪽 ID198, 80–89초는 실제 대기자로 보이지만 최대 연속 저속3초 때문에 새 기준에서 미확정인 사례입니다. 최초 줄 확정도1초→3.5초로 늦습니다. 인원 감소를 정확도 개선으로 해석하지 않습니다.

[EAST_EXTINGUISHER.md](EAST_EXTINGUISHER.md)의 4.5초·12.4초·41.3초 실제 통행과31초 소화기를 확인하세요. 소화기 confirmed/가림 유예는 전 프레임0, 다른 관측·상태는 동일합니다. 실제 발 위치가 작은 제외 구역에 들어가면 사람도 제외될 수 있습니다. 그 주변에서 실제 사람이3.5초 이상 대기하는 양성 장면은 미검증이며 모델 없는 테스트로 보완했습니다. 실제 CCTV·장시간 운영·세 환경 동시 실시간 처리는 미검증입니다.

## 정리와 전달

[CLEANUP_031.md](CLEANUP_031.md)에 삭제·보존 범위를 기록했습니다. 이전 고유 영상·추적 로그·검토 근거는 evidence/history에 보존하고, 해시 동일한 중간 복사본·검증된 임시 설치/build·구버전 wheel/ZIP만 제거했습니다. 내용 미확인 런타임 캐시는 원래 위치에 보존했습니다. 원본 영상·모델·MICC·가상환경·수동 정답/검토 자료는 삭제하지 않았습니다.

최신 로컬 배포물은 `dist/busan_cctv_analysis-0.3.1-py3-none-any.whl`과 `dist/busan_cctv_analysis-0.3.1-handoff.zip`입니다. Git에는 필요한 소스·설정·테스트·문서·허용된 예시 CSV만 올리고 영상/모델/outputs/가상환경/wheel/ZIP은 올리지 않습니다. 작업 브랜치는 `mvp/busan-cctv-20261014`이며 이번 요청에 따라 일반 commit·push합니다. 실제 원격 반영 결과는 완료 보고와 로컬 publish_status.json을 기준으로 합니다.
