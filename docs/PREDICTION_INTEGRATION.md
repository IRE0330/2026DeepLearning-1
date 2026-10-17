# 1초 집계·정시 CSV·비동기 전달 연결부

2026-10-17 기준 CSV 저장과 로컬 전달 연결부를 구현했습니다. 기본값은 `disabled`이며 `mock`은 로컬 수신 확인만 합니다. 실제 예측모델·외부 API 호출과 예측값 생성은 구현하지 않았습니다. 기존 `expected_wait_s`는 사용자 가정 공식의 계산값입니다.

## 처리 순서와 주기

매 프레임 탐지·ByteTrack·출입/대기 판정 → `IntervalSampler`의 영상 시각 레코드 생성 → 영상별 CSV/상세 flush → `StreamOutput`의 공유 CSV append/flush → `record_index.jsonl` flush → SQLite outbox 커밋 → 별도 전달 작업자 → 수신 확인 순서입니다. CSV를 다시 읽어 계산하지 않고 같은 `row, detail`을 직렬화해 전달합니다. 직렬화 이후의 프레임 상태 변경이나 수신자의 객체 변경은 저장된 레코드에 영향을 주지 않습니다.

| 설정 | 기본값과 위치 |
|---|---|
| 집계·기록 `record_interval_s` | demo 프로필 1초, operating 프로필 10초. 탐지 간격과 무관 |
| 파일 분할 `csv_split_interval_s` | `configs/streaming.json`의 3600초. 86400은 기존 하루 저장 호환 옵션 |
| 전달 `prediction_mode` | `disabled` 또는 검증용 `mock`. 기본 disabled |
| `delivery.queue_capacity` | 메모리 신호 큐 최대 32개. 본문은 디스크 outbox에 보존 |
| `delivery.max_attempts` / `retry_delay_s` | 전달 주기당 최대 3회 / 재시도 간격 0.05초 |
| `delivery.shutdown_timeout_s` | 종료 시 최대 2초 동안 전달 마무리 |

환경 설정이나 프로필에서 기록/분할/전달 값을 따로 지정할 수 있습니다. CLI의 `--prediction`, `--csv-split-seconds`가 해당 실행 값을 우선합니다. 적용값은 `config_used.json`과 실행 요약에 남습니다. 시연 초기값29/18/18명과 가상 촬영시각은 demo 프로필에만 있으며 운영 초기값/촬영시각 null 및 기록10초는 보존합니다.

## 정시 파일 전환과 읽기

시간별 공유 CSV는 한국시간으로 변환한 **구간 시작일시**의 시간대에 배정합니다. `north_2026-10-14_1400.csv`처럼 화장실별로 분리하며 UTF-8 BOM과 기존13열을 유지합니다.

- 14:59:59~15:00:00은 1400 파일, 15:00:00~15:00:01은 1500 파일입니다.
- 23:59:59~다음날00:00:00은 전날2300 파일입니다. 종료일시로 날짜를 바꾸지 않습니다.
- 화장실별 현재 핸들을 유지하고 매 행 append/flush합니다. 시간대가 바뀌면 이전 핸들을 닫습니다. 파일마다 BOM·헤더는 한 번이며 관측하지 않은 시간대의 빈 파일은 만들지 않습니다.
- 실행 종료 시 한 시간이 되지 않아도 파일을 닫고 manifest에 완료 상태를 남깁니다. 여러 등록 영상은 순차 처리하며 시간별 파일은 처리 순서로 추가합니다.

기록 중인 CSV도 계속 읽을 수 있습니다. 읽기 전용으로 열어 UTF-8/BOM, 정확한13열과 줄이 끝난 완성 레코드를 확인하고 저장 중인 마지막 불완전 행은 다음 읽기까지 보류합니다. CSV 수정·독점 잠금은 피합니다. 전달의 기본 입력은 CSV 재읽기가 아닌 저장 직후의 레코드입니다.

촬영시각이 없으면 `shared/time_unset/{restroom_id}_relative.csv`에 저장하고 절대 구간시각은 비웁니다. 전달에는 상대 구간시각과 `capture_time_unset=true`, 기존 측정상태를 보존합니다. PC 실행시각이나 파일 수정시각으로 촬영일시를 만들지 않습니다.

`--csv-split-seconds 86400`은 기존 종료일시 기준 날짜 분리·정렬·임시 파일 후 교체 방식을 보존합니다. 이 호환 방식의 `row_number_at_write`는 이후 정렬로 바뀔 수 있습니다. 이번 검증은3600을 사용했습니다. 과거 전체 로그 재계산 도구 `cctv.recalculate`의 일별 출력도 그대로 보존합니다.

## 전달 envelope 계약

공유 CSV는 기존13열 그대로이며 아래 메타데이터를 추가하지 않습니다. `record_index.jsonl`의 각 행이 전체 envelope이고 CSV 행과 전달을 대응시킵니다.

| 필드 | 의미 |
|---|---|
| `schema_version` | 현재1 |
| `run_id`, `record_id` | 고유 실행 폴더 이름, 실행 내 안정적인 레코드 ID |
| `restroom_id`, `video_id` | 화장실과 원본 영상 식별자 |
| `interval_start_time`, `interval_end_time` | 촬영 기준 절대 구간시각, 미설정이면 null |
| `interval_start_s`, `interval_end_s`, `source_time_s` | 원본 영상 오프셋과 종료 경계 이하 최신 상태의 소스 시각 |
| `record_index`, `record_interval_s` | 영상 내 기록 번호와 적용 기록 간격 |
| `data_type`, `is_demo` | demo는 `demo_assumptions`/true, 그 외는 `observed_aggregate`/false. 정확도 인증을 뜻하지 않음 |
| `capture_time_kind`, `capture_time_unset` | 가상/실제 촬영시각 구분과 미설정 여부 |
| `csv_row` | 열 이름·순서가 동일한13열 본문. CSV의 빈 칸은 원래 null 의미를 보존 |
| `detail` | 구간 확정 출입, 원본 경계/소스 시각, 누적 출입·내부/외부/내부대기/Q/빈칸/가정 예상시간/관측상태 |
| `assumptions` | 초기 내부 인원·운영 가능 칸 수·평균 이용시간 |
| `csv_ref` | 공유 CSV 경로·저장 당시 데이터 행 번호(1부터)·행 내용 해시·영상별 원장 경로 |
| `persisted_at` | 실제 저장 시각(UTC). 촬영시각으로 사용하지 않음 |

`record_id`는 실행·화장실·영상·기록 번호·상대 구간 경계로 UUID5를 구성합니다. 재전달은 outbox에 저장한 같은 ID와 본문을 사용합니다. 값이 같은 연속 초도 서로 다른 기록이며 새 분석 실행은 새 run_id를 사용합니다. 미설정/음수/미검증/시연 상태를 지우거나0으로 채우지 않습니다. `csv_row['측정상태']`도 그대로 전달합니다. 현재대기와 전체대기는 같은 Q이므로 내부대기를 다시 더하지 않습니다.

## 실제 예측모델을 연결할 위치

`cctv/delivery.py`의 `Receiver` 인터페이스는 `send(envelope) -> {'record_id': 같은 ID, 'acknowledged': True}`입니다. `StreamOutput(..., receiver=...)` 또는 `DeliveryWorker(..., receiver=...)`에 실제 함수/클라이언트 어댑터를 주입할 수 있습니다. 호출은 별도 작업자에서 일어나며 프레임 분석 경로에서 모델 응답을 기다리지 않습니다. 기본 CLI는 disabled/mock만 허용하며 외부 주소를 생성하지 않습니다.

현재 `MockReceiver`는 `delivery/mock_received.jsonl`에 받은 envelope를 저장·flush·fsync한 뒤 확인을 반환합니다. `delivery_acknowledged=true`는 전달 확인이며 `prediction_performed=false`입니다. **전달 성공은 예측 성공이 아닙니다.** 실제 모델의 입력 변환·출력 스키마/유효성 검사·결과 저장과 사용자 표시, 클라이언트의 연결/응답 제한시간은 향후 어댑터 작업입니다. 모델 결과가 없으면 예측값을 만들지 않습니다.

## 실패·중복·재시작

`delivery/outbox.sqlite3`는 WAL과 FULL 동기화로 envelope와 `pending/inflight/acknowledged/failed`, 누적 시도 횟수 및 개별 attempts 이력을 보존합니다. 전달 전에 CSV append/flush를 완료합니다. 실패해도 CSV 행을 취소하지 않습니다. 큐에는 제한된 수의 ID 신호만 넣고 큐가 차면 본문은 디스크에 유지합니다. 작업자가 DB도 조회하므로 신호가 밀려도 레코드를 버리지 않으며 큐 포화·대기 수·지연을 기록합니다. 메모리 큐는 제한되지만 디스크 저장 공간은 별도로 확보해야 합니다.

실패는 같은 ID/본문으로 주기당 최대3회 재시도하고, 한도를 넘으면 failed로 남깁니다. `deliver-outbox --retry-failed`로 명시적으로 새 제한 재시도 주기를 시작하며 누적 이력/ID는 보존합니다. 이미 확인된 항목은 다시 보내지 않습니다. 프로세스 중단으로 남은 inflight는 다음 작업자 시작 시 pending으로 복구합니다. OS 파일 잠금으로 동일 outbox의 동시 작업자를 막으며 비정상 종료 시 잠금은 해제됩니다.

정상 종료 때는 설정된 제한시간만 기다리고 미전달 항목을 보존합니다. 수신 함수가 멈추면 작업자 스레드가 살아 있는 상태로 제한시간을 넘길 수 있으며 요약의 `worker_alive`, `shutdown_timeout`에 나타납니다. 향후 외부 클라이언트는 자체 I/O 제한시간을 반드시 적용해야 합니다. 스레드를 강제로 종료한다고 보장하지 않습니다.

재전달 명령은 같은 실행의 `record_index.jsonl`에서 DB에 빠진 저장 envelope도 복구합니다. 이는 CSV/인덱스 저장 후 DB 커밋 전 중단 구간을 보완하며 CSV 값을 다시 계산하지 않습니다. 마지막 인덱스 줄이 불완전하면 `incomplete_index_tail`을 보고하고 이전 완성 줄까지만 복구합니다. CSV flush와 인덱스 작성 자체 사이에 중단된 마지막 행까지 자동 복구한다고 보장하지 않습니다. 여러 파일 쓰기는 하나의 원자적 트랜잭션이 아니며 원본 CSV와 상세/인덱스는 보존해 대조합니다.

수신은 끝났지만 확인 응답이 유실되면 같은 ID가 중복 전달될 수 있습니다. **정확히 한 번 전송을 보장하지 않습니다.** 실제 수신 측은 record_id의 영속 UNIQUE 키로 중복을 멱등 처리하고 확인을 반환해야 합니다.

## 실행 요약과 시간 의미

`delivery_summary.json`은 CSV 목록/행 수/닫힘, generated/stored/queued/disabled/enqueue_errors/stored_without_outbox, 전달 시도/확인/실패/대기 수, 메모리 큐 최대·포화, 최대 디스크 대기 수, 평균/최대 확인 지연, 미전달 최고 대기시간, 종료 상태와 outbox/수신 로그 경로를 기록합니다. `record_index.jsonl`은 ID와 CSV 행 대응입니다. batch의 영상별 요약은 진행 중 누계 스냅샷이며 최종 누계는 batch 루트의 delivery_summary/batch_summary를 확인합니다. 재전달 요약은 `delivery/retry_summary_고유번호.json`에 별도로 남깁니다.

영상 시각1초마다 레코드를 생성하지만 실제 처리속도는 장치/탐지/인코딩에 달립니다. 이번 북쪽 영상10초를 CPU에서 약24.37초,9.85 FPS로 처리했습니다. 실제 매초 데이터가 도착한다고 보장하지 않으며 실시간처럼 보이게 분석에 sleep을 넣지 않습니다. 재시도 대기는 전달 작업자에만 있습니다. 전달 지연은 outbox 등록부터 확인까지의 실제 시간이며 가상의2026-10-14 촬영시각과 현재 PC 시각 차이가 아닙니다. 분석 FPS와 elapsed_s는 영상별 summary에 있습니다. batch는 세 영상을 순서대로 처리하며 세 CCTV 동시 실시간 처리 기능은 구현하지 않았습니다.

기존 종료 정책은 유지합니다. 첫 구간은 시작 포함, 이후 이전 종료 경계 초과/현재 경계 이하의 확정 이벤트와 경계 이하 최신 상태를 사용합니다. 정확한 정수 초 종료는 마지막 프레임의 유효 시간 범위를 적용해 마지막 정수 경계 행을 남깁니다. 1초 미만 잔여 이벤트/상태는 `remainder.json`, 최종 프레임은 `final_state.json`에 별도로 남깁니다. 잔여에서 상태가 바뀌면 마지막 CSV 행과 최종 프레임 상태가 다를 수 있습니다.

## PowerShell 실행

프로젝트 루트에서 실행합니다. 매 분석은 고유 폴더를 만들며 기존 결과를 덮어쓰지 않습니다.

```powershell
# 기본 전달 중지, demo 1초 기록 / 정시 분할
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 10 --csv-split-seconds 3600 --prediction disabled
# 로컬 mock 검증 (실제 모델 호출 없음)
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 10 --device cpu --csv-split-seconds 3600 --prediction mock
# 기존 하루 저장 호환 옵션
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 10 --csv-split-seconds 86400 --prediction disabled
# 기존 실행의 미전달 복구/재시도. 예시는 이미 전부 확인돼 중복 전송하지 않음
& .\.venv\Scripts\python.exe -m cctv deliver-outbox --outbox outputs/north_20261017_161306_a2a33d11/delivery/outbox.sqlite3 --prediction mock --retry-failed --shutdown-seconds 2
```

`batch`도 같은 전달/분할 옵션을 지원합니다. 이번 실제 영상 검증은 북쪽0~10초만 수행했고 남쪽·동쪽 전체 영상은 재분석하지 않았습니다. 새 결과와 검증 근거는 [HOURLY_DELIVERY.md](HOURLY_DELIVERY.md)를 확인하세요.
