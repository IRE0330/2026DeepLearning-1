# 정시 CSV와 로컬 전달 검증 (2026-10-17)

매 프레임 분석·기존 출입/대기 계산을 유지하면서 영상 시각 레코드 저장과 비동기 전달 연결부를 구현했습니다. **실제 영상 실행은 북쪽0~10초 demo+mock 한 번**입니다. 남쪽·동쪽 전체 영상은 재분석하지 않았으며 기존 전체 결과·마스킹·영상 경로·운영 설정·demo 가정을 보존했습니다. Git push와 실제 예측모델 호출은 하지 않았습니다.

## 구현과 검증 범위

| 항목 | 구현 및 검증 |
|---|---|
| 기록/파일 분할/전달 설정 | demo1초·운영10초 유지, 분할3600초 별도, 전달 기본 disabled |
| 공유 CSV | 기존13열·UTF-8 BOM 유지, 화장실별 정시 파일에 매 행 append/flush, 핸들 유지/전환/종료 |
| 파일 소속 | 구간 시작 한국시간 기준. 정각·자정과 UTC→KST 변환 테스트 통과 |
| 미설정 촬영시각 | `shared/time_unset/{room}_relative.csv`, 상대시각과 상태 유지, 임의 날짜 미사용 |
| 동일 레코드 | 생성한 row/detail을 저장 후 직렬화. CSV·mock·outbox·인덱스10건 대조 |
| 비동기 전달 | 별도 작업자, 제한된 신호 큐, SQLite 영속 outbox, 제한 재시도·미전달 보존 |
| 재시작/중복 | 강제 프로세스 종료 후 복구·같은 ID 재시도·인덱스 복구 테스트 통과. 정확히 한 번 전송 보장 없음 |
| 느린 수신 | 메모리 큐 상한·포화 기록·디스크 대기·제한 종료 테스트 통과 |
| 상태/호환 | 초기값 미설정·음수 상태 전달, 기존 하루 분리 호환·관련 회귀 테스트 통과 |
| 남은 작업 | 실제 모델/외부 클라이언트 어댑터, 입력/출력 계약·결과 검증/저장, 수신 측 영속 ID 중복 방지, I/O 제한시간 |

관련 **28개 unittest 통과**(2.910초). 증거는 [hourly_delivery_checks.json](hourly_delivery_checks.json)과 로컬 `inspections/hourly_delivery_20261017_160448_1936ecc5/tests.txt`입니다. 전체 과거 테스트나 실제 사람 카운팅 정확도를 새로 검증했다는 뜻은 아닙니다. 보호 대상 **371개 기존 파일**의 해시가 일치했으며 운영/환경/프로필/등록목록·핵심 계산 코드와 기존 결과가 포함됩니다.

## 이번 실제 결과

새 실행 폴더: `outputs/north_20261017_161306_a2a33d11`

| 파일 | 내용 |
|---|---|
| `shared/north_2026-10-14_0000.csv` | 00:00:00~00:00:10,1초10행. BOM/헤더 한 번·13열 |
| `usage_summary.csv` | 영상별 원장. 위 공유 CSV와 바이트 일치 |
| `record_index.jsonl` | 10개 envelope, record_id와 CSV 데이터 행 번호/해시 대응 |
| `delivery/mock_received.jsonl` | 같은10개 envelope의 모의 수신. 예측 수행 false |
| `delivery/outbox.sqlite3` | 10건 모두 acknowledged. 미전달0건이지만 향후 실패/재시작 상태 저장 위치 |
| `delivery_summary.json` / `summary.json` | 파일 목록/행 수·생성/저장/전달·큐/지연·처리속도·완료 상태 |
| `interval_details.jsonl` | 구간 출입·최신 상태·소스 시각·기존 가정 예상시간 |
| `remainder.json` / `final_state.json` | 잔여0초/출입0·0, 마지막 실제 프레임 상태 |
| `annotated.mp4` | 북쪽10초,1280×720/24 FPS/240프레임. 전체 재디코딩 확인 |

생성10·저장10·전달 시도10·확인10·실패0·대기0입니다. 메모리 신호 큐 최대1/용량32, 디스크 대기 최대1, 큐 포화0, 평균 확인 지연 약0.00982초·최대0.01956초였습니다. 이 지연은 outbox 등록부터 확인까지이며 가상 촬영일시와 PC 실행일시 차이가 아닙니다.

분석240프레임은 실제 약24.37초,9.85 FPS였습니다. 영상 시각1초 기록과 현실의1초 도착은 다릅니다. 임의 sleep 없이 처리 속도로 실행하며 실제 처리가 느리면 매초 새 레코드가 도착하지 않을 수 있습니다. 여러 영상의 batch는 순차 처리이며 세 CCTV 동시 실시간 분석 기능은 구현하지 않았습니다.

기존 종료 정책과 같이 마지막 프레임239의9.958333초 상태로10초 행을 기록했습니다. 구간1~9초는 각 경계 이하 최신 상태를 사용합니다. 새10행은 직전 전체 결과 `outputs/batch_demo_recalc_20261017_144846_e9dd5976/north/usage_summary.csv`의 첫10행과 모든13열이 일치했습니다. 이 구간의 판정 입장/퇴장은0/0, 최종 내부29·외부대기6·내부대기2·전체Q8·빈칸0·가정 예상35초입니다. 이벤트를 수치에 맞춰 수정하지 않았습니다.

일반 실행에서는1초 미만 잔여를 정기 CSV에 넣지 않고 `remainder.json`에 보존합니다. 마지막 CSV 행과 최종 프레임 상태가 다를 수 있습니다. 이번 실행은 정수10초 경계이므로 잔여0초입니다. 짧은 영상에서는 정시 파일 하나만 생성되고 종료 때 닫히는 것이 정상입니다.

## 정확한 PowerShell 명령

프로젝트 루트에서 실행합니다. 다음 두 분석 명령은 각각 새 고유 폴더를 만들고 북쪽0~10초만 분석합니다. 실제 수행한 명령은 두 번째 명령에 `-B -u`를 추가한 형태입니다.

```powershell
# 전달 없이 CSV 저장 (기본 동작)
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 10 --csv-split-seconds 3600 --prediction disabled
# 로컬 mock 전달 검증
& .\.venv\Scripts\python.exe -m cctv analyze --config configs/north.json --profile demo --start 0 --end 10 --device cpu --csv-split-seconds 3600 --prediction mock
# 같은 실행의 미전달 복구/실패 재시도. 현재 예시는 전부 확인돼 재전송하지 않음
& .\.venv\Scripts\python.exe -m cctv deliver-outbox --outbox outputs/north_20261017_161306_a2a33d11/delivery/outbox.sqlite3 --prediction mock --retry-failed --shutdown-seconds 2
```

기존10초 기록 운영 프로필은 `--profile operating`이며 실제 초기값·촬영시각이 없으면 미설정 상태를 유지합니다. `--csv-split-seconds 86400`은 기존 하루 저장 호환 방식입니다. 기본 분할과 전달은 `configs/streaming.json`에서 관리합니다.

바로 열기:

```powershell
$resultPath = Join-Path (Get-Location) 'outputs/north_20261017_161306_a2a33d11'
Invoke-Item -LiteralPath (Join-Path $resultPath 'shared/north_2026-10-14_0000.csv')
Invoke-Item -LiteralPath (Join-Path $resultPath 'annotated.mp4')
Invoke-Item -LiteralPath (Join-Path $resultPath 'delivery/mock_received.jsonl')
Invoke-Item -LiteralPath (Join-Path $resultPath 'delivery_summary.json')
```

관련28개 테스트 재실행:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'tests')
& .\.venv\Scripts\python.exe -B -m unittest test_stream_output test_record_intervals test_batch test_pipeline test_recalculate test_overlay -v
```

전달 envelope·어댑터 주입·실패/중복/제한 종료·복구 한계는 [PREDICTION_INTEGRATION.md](PREDICTION_INTEGRATION.md)를 확인하세요. 모의 수신은 실제 예측 연동 완료가 아닙니다. 기존 세 환경 전체 CSV/영상 경로는 [DEMO_INITIAL18.md](DEMO_INITIAL18.md)에 그대로 남아 있습니다.
