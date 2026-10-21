# 공개 인터페이스와 데이터 규격 v1

0.3.0은 영상 시각의 정지·느린 이동 증거 3.5초 후 confirmed를 집계합니다. candidate는 제외하며 가림 유예 1.5초·demo 기록 1초·13열은 유지합니다. 정책 식별자는 `confirmed_observed_plus_confirmed_grace_3p5s_v4`이며 상세 검증은 [WAITING_35S.md](WAITING_35S.md)를 따릅니다.

`from cctv import AnalysisService`는 torch/Streamlit/가중치를 로드하지 않습니다. 기존 동기 분석 `cctv.pipeline.analyze`와 CLI도 유지합니다. 새 Service는 이 분석 함수에 생명주기·저장 레코드 조회를 연결한 로컬 래퍼입니다. HTTP 서버·예측 클라이언트는 없습니다.

## 시작·조회·중지

```python
from cctv import AnalysisService

def main():
    with AnalysisService() as service:
        job = service.start(
            owner="front-session", restroom_id="north", profile="demo",
            video_path="D:/materials/north.mp4", model_path="D:/materials/yolo11n.pt",
            output_dir="D:/results", device="cpu", end=3.25,
        )
        # 비동기 시작. GUI에서는 반복문 대신 약1초마다 아래 두 메서드를 조회합니다.
        status = job.status()
        latest = job.latest()  # 정기 레코드가 없으면 None
        for envelope in job.records():  # UI 스레드에서 기다리지 말 것
            print(envelope["record_id"], envelope["csv_row"])
        print(job.status())

if __name__ == "__main__":  # Windows spawn 필수
    main()
```

예시 D: 경로는 호출자가 실제 자료/쓰기 가능한 경로로 바꿉니다. `config_path`를 생략하면 선택한 환경의 번들 최종 마스킹을 사용합니다. 다른 구도는 복사한 설정에서 구역을 다시 확인해야 합니다. `video_path`를 명시하면 실행 사본에서 영상 해시/ID를 등록하며 원본 설정 파일은 수정하지 않습니다. `model_path`를 생략하면 설정의 로컬 가중치 경로를 사용합니다. 자동 가중치 다운로드는 하지 않습니다.

설정 우선순위는 환경 설정 → 지정 프로필 → 명시한 영상/모델/장치/출력 경로입니다. 공개 Service는 prediction disabled를 강제하고 기본 profile은 operating(10초 기록)입니다. 예제 UI는 demo(1초 기록)를 명시합니다. 초기 인원/시연일시/칸 수/105초 가정은 설정에서 읽으며 API에 숫자를 하드코딩하지 않습니다. 기존 CLI의 disabled/mock 선택은 유지합니다.

`start`는 `AnalysisJob`을 즉시 반환하고 준비와 분석은 별도 spawn 프로세스에서 수행합니다. 영상/가중치/설정 오류는 보통 자식의 `failed` 상태와 `error`에 구체적인 경로로 전달됩니다. 출력 폴더 생성 실패·잘못된 화장실/소유자·중복 실행은 호출 시 예외입니다. BusyError는 기존 작업을 유지하며, OwnershipError는 다른 소유자의 제어를 거부합니다.

상태는 `idle`(Service에 작업 없음), `preparing`, `running`, `stopping`, `completed`, `stopped`, `failed`, `force_terminated`입니다. phase는 configuration/spawning/inspecting_video/loading_model/running 등 준비 단계를 표시합니다. `processed_frames`, `expected_frames`, `progress`(0~1 또는 null), `runtime_device`, `error`, `run_dir`, `job_dir`, `worker_pid`, `worker_alive`, `csv_files`, `updated_at`을 조회합니다. 실제 장치는 첫 추론에서 backend/가중치/결과를 확인하기 전까지 null입니다. 요청 장치를 실제 사용 장치로 표시하지 않습니다. 중지 상태에서 progress를1로 만들지 않습니다.

`job.stop(timeout=10, wait=True)`는 정상 중지를 요청하고 최대10초 기다린 뒤 필요하면 프로세스를 강제 종료합니다. UI에서는 `service.stop(owner, wait=False)`로 반환 후 조회를 계속합니다. 정상 중지는 프레임 사이와 검사 단계에서 확인하고 CSV/로그/영상 핸들을 닫아 완료 구간·최종·잔여를 보존합니다. 모델 로딩/개별 추론 호출 도중은 즉시 취소할 수 없습니다. 강제 종료는 completed가 아니며 마지막 파일/영상/저널 꼬리의 완전성을 보장하지 않습니다.

## 최신값과 모든 레코드

`latest()`는 가장 최근에 저장된 정기 레코드 하나의 독립 사본입니다. 조회 사이에 여러 레코드가 생성되면 중간값은 화면에서 보이지 않을 수 있습니다. 이 경우에도 정기 CSV와 `record_index.jsonl`에는 각 레코드가 기록됩니다. 최종 프레임이 마지막 정기 경계와 다르면 latest와 final_state도 다를 수 있습니다.

모든 레코드는 `job.records(cursor=0)` 또는 비차단 `job.read_records(cursor=0, limit=100)`로 받습니다. read_records는 `RecordBatch(records, next_cursor, done, incomplete_tail)`를 반환합니다. cursor는 해당 실행 저널의 **바이트 오프셋**이며 받은 next_cursor를 그대로 보관합니다. 행 번호나 다른 실행의 cursor를 넣지 않습니다. limit은1~1000입니다.

```python
cursor = 0
# UI/다른 소비자가 주기적으로 호출할 부분:
batch = job.read_records(cursor, limit=100)
for record in batch.records:
    consume(record)  # 소비 완료를 확인한 뒤 cursor를 보관
cursor = batch.next_cursor
```

순차 수신은 CSV를 다시 읽어 재계산하지 않습니다. 기존 StreamOutput가 **CSV append/flush 후 직렬화·저장한 동일 envelope**를 저널에서 읽습니다. 최신 상태는 같은 envelope를 SQLite WAL에 보관합니다. Windows에서 JSON 파일을 읽는 UI와 파일 교체가 충돌하지 않도록 상태 저장은 SQLite를 사용합니다. 최종 사람이 읽을 사본은 job.json입니다. 예측용 outbox와는 다른 작업 상태 저장소입니다.

크기8의 알림 큐에는 갱신 신호만 넣고 가득 차면 신호를 합칩니다(notification_coalesced). 알림이 모든 레코드를 담는 전송 큐는 아닙니다. UI의 읽기/렌더링 완료를 작업자가 기다리지 않습니다. 전체 레코드는 기존 디스크 저널에 있고, 메모리에 전체 프레임/전체 레코드를 쌓지 않습니다. 저장장치 지연/오류는 분석에 영향을 줄 수 있습니다.

읽는 도중 쓰이고 있는 마지막 불완전 줄은 cursor를 전진시키지 않고 다음 조회에서 재시도합니다. 종료 후 불완전 꼬리는 incomplete_tail로 보고합니다. 중간의 잘못된 JSON은 예외를 내며 조용히 건너뛰지 않습니다. CSV flush 직후 저널 저장 전 강제 종료되면 CSV에만 행이 남을 수 있습니다. 내구성 fsync·정확히 한 번 수신·강제 종료의 무손실을 보장하지 않습니다. 소비자는 record_id로 중복을 방지하고, 재시작 시 저장한 cursor/ID를 활용해야 합니다. 새 실행은 새 ID이며 이전 Tracker 상태에서 이어서 분석하는 재개 기능은 없습니다.

## Envelope

기존 schema_version=1 envelope를 그대로 사용합니다.

| 필드 | 정의 |
|---|---|
| run_id / record_id | 실행 ID / 실행 내 동일 구간의 안정적인 UUID. 같은 실행의 재조회 시 유지 |
| restroom_id / video_id | 환경 ID / 영상 해시와 연결된 영상 ID |
| record_index / record_interval_s | 실행 내1부터의 정기 행 번호 / 영상 시각 기록 간격(초) |
| interval_start_s / interval_end_s | 원본 영상 시작 기준 구간 시작/종료 초 |
| source_time_s | 기록 경계 이하의 가장 최근 상태를 만든 프레임의 영상 초 |
| interval_start_time / interval_end_time | 확인된 기준시각+영상 오프셋. 타임존 포함 ISO8601. 없으면 null |
| persisted_at | 실제 저장 시 UTC 갱신시각. 촬영시각으로 사용하지 않음 |
| is_demo / data_type / capture_time_kind | 시연 여부 / demo_assumptions 또는 observed_aggregate / virtual·real·null |
| capture_time_unset | 촬영 기준일시 미설정 여부 |
| csv_row | 아래13열에 쓰인 동일 값·순서. 원래 CSV의 빈 문자열 정책 유지 |
| detail.state | 같은 집계의 누적 출입·내부·대기·빈칸·expected_wait_s와 상태. 계산 불가는 null |
| assumptions | initial_inside, available_stalls, average_stall_use_s |
| csv_ref | 공유 CSV 파일 경로·행 번호·행 해시와 원본 usage CSV 참조 |

영상 초는 처리 경과시간이 아닙니다. 저장 파일은 가능한 속도로 처리하므로 demo1초 기록이어도 벽시계로 매초 새 데이터가 도착하는 것은 아닙니다. 이번 API/예제는 입력을 재생속도로 제한하지 않습니다. 기존 simulate-input은 별도 시험 도구로 보존합니다. 실제 카메라/네트워크는 지원하지 않습니다.

## 공유 CSV — 정확히13열

UTF-8 BOM, 파일당 헤더1회, 화장실별·한국시간 정시별 저장입니다. 14:59:59~15:00:00 구간은14시 파일,15:00:00~15:00:01은15시 파일에 속합니다. 알려지지 않은 촬영시각은 임의 날짜 대신 shared/time_unset 경로에 저장합니다. 파일은 각 행마다 flush하고 같은 시간대 핸들을 유지합니다. 하루 분할 호환 옵션은 기존 CLI에 남아 있습니다.

| 순서 | 열 이름 | 단위/의미 |
|---:|---|---|
|1|촬영시작시각|구간 시작 ISO8601, 촬영시각 미설정이면 빈 칸|
|2|촬영종료시각|구간 종료 ISO8601, 동일 정책|
|3|화장실ID|north/south/east|
|4|화장실_영상ID|영상 ID|
|5|구간_입장인원|해당 구간의 확정 입장 수, 명|
|6|구간_퇴장인원|해당 구간의 확정 퇴장 수, 명|
|7|내부잔류인원_추정|초기값+누적 입장−누적 퇴장, 명|
|8|현재대기인원_추정|외부+추정 내부 대기, 명|
|9|측정상태|미설정/음수/시연 가정 등 기존 상태 표시|
|10|추정내부대기인원|MAX(내부−운영 가능 칸 수,0), 명|
|11|전체대기인원_추정|현재 대기와 동일한 Q, 명|
|12|현재이용가능칸수_추정|MAX(운영 가능 칸 수−내부,0), 칸|
|13|외부대기인원_추정|관측 confirmed+중복 억제 후 유효 confirmed 가림 유예, 명. candidate 제외|

예상 대기시간은 `(Q+1)×평균 이용시간/운영 가능 칸 수` 초이며 detail.state.expected_wait_s에만 있습니다. 실제 예측값이 아닌 가정식입니다. 초기값 미설정 또는 음수 등 기존 계산 불가 정책에서 추정값은 CSV 빈 칸/API 상세 null로 유지합니다. 음수 내부 원시 값은 보존하고 0으로 덮지 않습니다. 정확한 정수 초 종료와1초 미만 잔여 구간 정책은 기존대로이며 remainder.json/final_state.json을 함께 봅니다.
