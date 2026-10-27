# 부산역 화장실 CCTV 관리자 대시보드

저장된 북쪽·동쪽·남쪽 화장실 영상을 순차 분석하고, 분석 결과를 영상 재생 시각에 맞춰 비교하는 Streamlit 관리자 페이지입니다. 열차 정보는 각 컴퓨터의 MySQL에 저장된 부산역 예정 시간표를 조회합니다.

## 1. 처음 사용하는 팀원이 준비할 것

| 항목 | 준비 방법 |
|---|---|
| 프로젝트 코드 | 이 저장소의 `feature/restroom-dashboard1023` 브랜치를 내려받습니다. `busan_restroom_dashboard`와 `cctv-analysis`가 함께 있어야 합니다. |
| Python | **3.13.x**를 설치합니다. 분석 모듈 0.3.2는 Python `>=3.13,<3.14`를 요구합니다. |
| 영상 | 팀에서 공유받은 북쪽·동쪽·남쪽 영상 3개를 로컬에 넣습니다. |
| 모델 | 팀에서 공유받은 `yolo11n.pt`를 로컬에 넣습니다. |
| 열차 DB | MySQL 서버와 Workbench를 준비하고, 팀에서 공유받은 SQL로 구조와 데이터를 가져옵니다. |

가상환경은 각자 컴퓨터에서 새로 만듭니다. 다른 사람의 `.venv-cctv` 폴더를 복사해서 사용하지 않습니다.

아래 macOS 명령은 저장소를 ZIP으로 내려받은 폴더가 `~/Downloads/2026DeepLearning-1-feature-restroom-dashboard1023`인 경우입니다. 실제 폴더명이 다르면 `cd` 경로만 바꿉니다. 모든 설치 명령은 **저장소 최상위 폴더**에서 실행합니다.

## 2. 영상과 모델 넣기

GitHub에 영상과 모델이 없으면 별도로 공유받아 넣습니다. 권장 위치는 다음과 같습니다.

| 프로젝트 기준 경로 | 내용 |
|---|---|
| `videos/north.mp4` | 북쪽 영상 |
| `videos/east.mp4` | 동쪽 영상 |
| `videos/south.mp4` | 남쪽 영상 |
| `models/yolo11n.pt` | YOLO11n 모델 가중치 |

영상 이름에는 `north / east / south` 또는 `북쪽 / 동쪽 / 남쪽` 중 한 방향만 포함합니다. 지원 확장자는 `.mp4`, `.mov`, `.m4v`이며, 확장자 이름만 변경해서 영상 형식을 변환하지 않습니다.

기존의 유효한 영상·모델 설정을 우선 사용합니다. 해당 경로가 없으면 영상을 앱 폴더와 프로젝트의 `videos`, `media` 등에서 다시 찾습니다. 모델은 프로젝트의 `models`와 `busan_restroom_integrated/models` 등을 우선 확인하고 제한된 깊이의 프로젝트 내부 탐색을 수행합니다. 파일이 실제로 없으면 자동 다운로드하지 않습니다.

자동 연결이 안 되면 **메인 대시보드 → 영상·모델 분석 설정**에서 해당 파일의 경로를 입력하고 **분석 설정 저장**을 누릅니다. 정상적인 기존 경로가 다른 파일을 가리키고 있다면 이 화면에서 직접 바꿉니다.

## 3. macOS 최초 설치 — 한 번만 실행

Python 3.13 설치 후 터미널에서 실행합니다.

```bash
cd ~/Downloads/2026DeepLearning-1-feature-restroom-dashboard1023

python3.13 -m venv .venv-cctv
source .venv-cctv/bin/activate

python -m pip install --upgrade pip
python -m pip install './cctv-analysis[analysis,streamlit]'
python -m pip install -r busan_restroom_dashboard/requirements-dashboard.txt
python -m pip check
```

`[analysis,streamlit]`은 분석에 필요한 패키지와 Streamlit까지 설치하는 옵션입니다. `./cctv-analysis`만 설치하면 분석용 의존성이 모두 설치되지는 않습니다. 설치에 오류가 발생하면 다음 명령으로 넘어가지 말고 오류 내용을 확인합니다.

Python 3.13이 설치되어 있는데 명령을 찾지 못하면 `command -v python3.13`으로 설치 경로를 확인합니다. Apple Silicon Mac의 Homebrew 설치 경로는 `/opt/homebrew/bin/python3.13`일 수 있습니다.

### 밝은 테마 설정 — 최초 1회

앱은 밝은 배경을 기준으로 디자인했습니다. 저장소 최상위 폴더에서 아래를 실행하면 다크 입력창과 밝은 배경이 섞이는 현상을 방지할 수 있습니다. 기존 설정 파일이 있으면 `.bak`으로 백업합니다.

```bash
mkdir -p .streamlit

if [ -f .streamlit/config.toml ]; then
  cp .streamlit/config.toml .streamlit/config.toml.bak
fi

cat > .streamlit/config.toml <<'EOF'
[theme]
base = "light"
primaryColor = "#0867df"
backgroundColor = "#f1f6fa"
secondaryBackgroundColor = "#ffffff"
textColor = "#172431"
font = "sans serif"

[server]
maxUploadSize = 500
address = "localhost"
EOF
```

이후에도 저장소 최상위 폴더에서 실행해야 이 설정을 읽습니다. 브라우저의 앱 설정에서 테마를 직접 선택했다면 Light 또는 프로젝트의 사용자 지정 테마를 선택합니다.

## 4. macOS 평소 실행 코드

설치가 완료된 다음부터는 아래 세 줄만 실행합니다.

```bash
cd ~/Downloads/2026DeepLearning-1-feature-restroom-dashboard1023
source .venv-cctv/bin/activate
python -m streamlit run busan_restroom_dashboard/app.py
```

터미널에 표시된 Local URL을 브라우저에서 엽니다. 종료는 터미널에서 **Control+C**입니다. 앱을 사용하는 동안 터미널을 켜둡니다.

가상환경 활성화가 꼬였지만 해당 환경의 Python이 정상이라면 저장소 최상위 폴더에서 직접 실행할 수도 있습니다.

```bash
./.venv-cctv/bin/python -m streamlit run busan_restroom_dashboard/app.py
```

### Windows PowerShell에서 설치·실행하는 경우

`프로젝트 폴더 경로`를 실제 저장소 폴더로 바꿉니다. 활성화 스크립트 대신 가상환경 Python을 직접 호출합니다.

```powershell
cd '프로젝트 폴더 경로'
py -3.13 -m venv .venv-cctv
& .\.venv-cctv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-cctv\Scripts\python.exe -m pip install './cctv-analysis[analysis,streamlit]'
& .\.venv-cctv\Scripts\python.exe -m pip install -r busan_restroom_dashboard/requirements-dashboard.txt
& .\.venv-cctv\Scripts\python.exe -m pip check
& .\.venv-cctv\Scripts\python.exe -m streamlit run busan_restroom_dashboard/app.py
```

설치 후에는 첫 줄의 폴더 이동과 마지막 실행 명령만 사용합니다. Windows에서도 저장소 최상위의 `.streamlit/config.toml`에 위의 밝은 테마 설정을 넣습니다. GPU 설치·CPU 전용 PyTorch 설치 및 분석 모듈 상세 인계는 [분석 모듈 README](../cctv-analysis/README.md)를 확인합니다.

## 5. MySQL은 팀원마다 어떻게 준비하나요?

현재 연결 주소 `127.0.0.1`은 **앱을 실행하는 사람 본인의 컴퓨터**입니다. GitHub에서 코드를 내려받아도 다른 팀원의 MySQL 데이터가 자동으로 복사되지 않습니다.

### DB를 가지고 있는 사람이 할 일

1. MySQL Workbench에서 기존 DB에 연결합니다.
2. **Server → Data Export**에서 `railway_system`을 선택합니다.
3. 최소한 `열차_운행정보`의 **구조와 데이터 모두** 내보냅니다. Workbench에 옵션이 표시되면 **Dump Structure and Data**를 선택합니다.
4. **Export to Self-Contained File**로 SQL 파일 하나를 생성해 팀원에게 전달합니다.
5. 해당 시간표의 적용 기간과 포함된 날짜도 함께 알려줍니다.

SQL 파일은 별도 공유 자료입니다. 이 README를 작성하는 과정에서 실제 DB를 추출하거나 SQL 파일을 생성한 것은 아닙니다.

### SQL 파일을 받은 팀원이 할 일

1. 자기 컴퓨터에 MySQL 서버와 Workbench를 설치하고 서버를 실행합니다.
2. Workbench에서 자기 MySQL에 연결합니다.
3. **Server → Data Import → Import from Self-Contained File**에서 공유받은 SQL을 선택합니다.
4. 대상 스키마를 `railway_system`으로 선택합니다. 없는 경우 해당 이름으로 새 스키마를 만들어 선택합니다. SQL 자체에 스키마 생성·선택 구문이 있으면 그 구문을 따릅니다.
5. **Start Import**를 실행합니다. 이미 기록이 있는 DB에 반복 가져오기 전에는 중복·덮어쓰기 여부를 확인합니다.
6. 다음 쿼리로 테이블과 시연 날짜의 기록을 확인합니다.

```sql
USE railway_system;

SELECT COUNT(*) AS 전체기록수
FROM 열차_운행정보;

SELECT 날짜, 열차번호, 열차종류, 운행구분, 예정시각
FROM 열차_운행정보
WHERE 날짜 = '2026-10-14'
ORDER BY 예정시각, 열차번호;
```

앱이 사용하는 열은 `날짜`, `열차번호`, `열차종류`, `운행구분`, `예정시각`입니다. 사용자 Mac의 DB에 구조가 이미 있다면 그 DB에 맞는 데이터를 가져옵니다. 대시보드의 열차 조회 기능은 DB나 테이블을 자동 생성하지 않습니다.

### 앱에서 연결하기

앱의 **열차 정보 → MySQL 연결 설정**에서 입력하고 **연결 확인 및 적용**을 누릅니다.

| 항목 | 기본 예시 |
|---|---|
| 호스트 | `127.0.0.1` |
| 포트 | `3306` |
| 데이터베이스 | `railway_system` |
| 사용자 | 본인 MySQL 사용자명, 보통 `root` |
| 비밀번호 | **각자 설정한 MySQL 비밀번호** |

다른 팀원의 비밀번호를 그대로 쓰는 것이 아닙니다. 비밀번호는 GitHub나 README에 적지 않습니다. 앱 입력으로 연결한 비밀번호는 세션에서 사용하므로 새 세션에서는 다시 입력합니다.

DB를 한 번 정상적으로 가져온 후에는 매번 SQL 파일을 가져올 필요가 없습니다. MySQL 서버는 조회하는 동안 실행 중이어야 합니다. 네트워크를 통한 공용 DB 연결은 별도 설정이며 이 문서의 기본 실행 방식에 포함하지 않습니다.

### 해당 날짜의 시간표가 없다면

영상의 시연 기준일이 `2026-10-14`이면 DB에도 그 날짜의 기록이 필요합니다. 팀의 `railway_system_v5` 등록 앱에서 유효한 원본 시간표를 사용해 해당 날짜를 포함한 범위로 **날짜별 기록 생성 → 날짜별 기록 DB 저장**을 수행합니다.

`railway_system_v5`는 시간표를 등록할 때 사용하는 별도 도구입니다. 저장이 완료된 뒤에는 대시보드를 사용하면서 계속 켜둘 필요가 없습니다. 다른 날짜의 기록을 단순히 날짜만 바꿔 실제 시간표처럼 사용하지 않습니다.

## 6. 앱 실행 후 사용 순서

1. 영상 3개와 모델 파일을 준비합니다.
2. MySQL 서버를 실행하고 Streamlit을 실행합니다.
3. **열차 정보**에서 본인 DB 연결을 적용하고 날짜별 기록을 확인합니다.
4. **메인 대시보드 → 영상·모델 분석 설정**에서 파일 연결, CPU/GPU 장치와 시연 날짜를 확인합니다. 일반 Mac 시연은 `cpu`를 사용합니다.
5. **세 CCTV 분석 시작**을 누릅니다. 분석은 북쪽 → 동쪽 → 남쪽 순서로 수행합니다.
6. 완료 후 **결과 불러오기**를 누릅니다.
7. **동시 재생**으로 세 영상을 재생하고 **일시정지**로 함께 멈춥니다. **처음부터**는 공통 재생 위치를 초기화합니다.
8. 화장실 상세와 사이니지에서 해당 영상 시점의 분석 결과를 확인합니다.

분석과 재생은 다른 작업입니다. **세 CCTV 분석 시작**은 영상의 사람 수 등을 계산하는 작업이고, **동시 재생**은 영상과 저장된 결과를 같은 시각에 보여주는 작업입니다.

공통 영상 재생 시각은 `14:00:00`부터 표시합니다. 메뉴를 바꾸면 같은 브라우저의 저장된 재생 위치를 복원하며, 새 화면에서 재생 버튼을 눌러 시작합니다. 브라우저 저장소를 지우면 기억한 위치도 초기화됩니다. 공통 길이는 영상 길이와 완료된 공통 분석 범위의 제한을 받습니다.

## 7. 열차 알림 표시 기준

- MySQL에 저장된 **도착·출발 예정 시간표**를 사용합니다.
- 영상 재생 시각부터 앞으로 **20분 이내**의 도착·출발 열차를 시간순으로 최대 5개 표시합니다.
- 예정 시각 전에는 `출발예정 (7분 30초 남음)`, `도착예정 (3분 남음)`처럼 표시합니다.
- 예정 시각이 되면 `출발` 또는 `도착`으로 바꾸고 **60초 미만** 동안 유지합니다. 예정 시각에서 60초가 지나면 목록에서 제외합니다.
- 예정 시각 경과 후 글씨는 초록색입니다. **실제 운행을 확인했다는 뜻이 아니라 예정 시간표 기준 표시**입니다.
- 일시정지하면 알림의 기준시각과 남은 시간도 멈춥니다. 영상 시점을 바꾸면 알림도 다시 계산합니다.
- DB 결과는 세션에서 최대 30초 동안 재사용합니다. DB 변경 후에는 **DB 새로고침** 또는 **열차 DB 다시 불러오기**로 갱신합니다.

예를 들어 영상 시각이 `14:01:30`이면 `14:09`, `14:20` 출발 열차가 표시 대상입니다. `14:00` 출발은 1분 유지 시간이 지났으므로 제외하고, `14:24` 출발은 앞으로 20분 범위 밖이므로 제외합니다.

## 8. 데이터 저장 위치와 구분

| 데이터 | 저장·조회 위치 | 다른 컴퓨터에서 필요한 준비 |
|---|---|---|
| 열차 예정 시간표 | MySQL `railway_system.열차_운행정보` | 공유 SQL 가져오기 또는 등록 앱으로 데이터 저장 |
| CCTV 분석 결과 | 앱의 `data/dashboard.sqlite`, 실행별 `data/<ID>/`, 분석 원본 CSV | 자기 컴퓨터에서 분석 실행. 기존 결과를 공유하는 경우 별도 전달 및 연결 확인 |
| 영상·모델 경로와 앱 설정 | `data/settings.json` | 현재 컴퓨터의 파일 위치에 맞게 자동 탐색 또는 설정 |
| 날짜별 화장실 모의 기록 | `assets/restroom_usage.csv.gz` 등 | 저장소에 포함된 해당 파일 유지 |
| 원본 CCTV 영상·YOLO 가중치 | `videos/`, `models/` 등 로컬 경로 | 파일을 별도로 공유받아 넣기 |

화장실 상세의 날짜별 모의 기록 그래프와 CCTV 영상 분석 기록은 별개입니다. 기본 모의 기록의 화장실 매핑은 `TOILET_A=북쪽`, `TOILET_B=동쪽`, `TOILET_C=남쪽`입니다. 시각별 대기인원을 단순 합산해 실제 누적 이용객 수로 해석하지 않습니다.

## 9. 자주 발생하는 문제

| 증상 | 확인할 내용 |
|---|---|
| `python: command not found` | 저장소 폴더에서 `source .venv-cctv/bin/activate`를 실행했는지 확인합니다. 옮겨온 가상환경이라면 Python 3.13으로 새로 만듭니다. |
| Python 버전 오류 | `python --version`으로 **3.13.x**인지 확인합니다. |
| `cctv` 또는 분석 패키지가 없음 | 저장소 최상위에서 `python -m pip install './cctv-analysis[analysis,streamlit]'`을 실행합니다. |
| 모델 파일 경로 오류 | `models/yolo11n.pt` 등 프로젝트 안에 실제 파일이 있는지 확인하고 앱을 다시 실행합니다. 자동 탐색은 없는 파일을 다운로드하지 않습니다. |
| 영상이 없음 | 파일명과 위치, 기존 수동 설정을 확인합니다. 메인의 분석 설정에서 각 경로를 바꿀 수 있습니다. |
| 영상이 검게 보이거나 형식 오류 | 시연 설정에서 미리보기용 H.264 MP4를 만듭니다. 변환은 재생용이며 분석 원본과 구분됩니다. |
| MySQL 로그인 거부 | 본인 MySQL 사용자와 비밀번호를 입력한 뒤 연결 확인을 다시 누릅니다. |
| MySQL 연결 실패 | 서버 실행 여부, 호스트·포트와 DB 이름을 확인합니다. |
| 해당 날짜 기록 없음 | DB의 날짜와 영상 시연 기준일을 비교하고, 해당 날짜의 유효한 시간표를 저장합니다. |
| 열차는 있는데 알림이 없음 | 운행구분과 조회 시간 범위를 확인합니다. 지난 열차는 예정 시각 후 1분 동안만 남습니다. |
| 입력창이 검고 글자가 안 보임 | 저장소 최상위 `.streamlit/config.toml`의 `base = "light"`와 실행 위치를 확인하고 앱을 재시작합니다. |
| 수정 파일이 반영되지 않음 | 현재 실행 중인 프로젝트 폴더에 파일을 대치했는지 확인합니다. Control+C로 종료 후 다시 실행하고 브라우저를 새로고침합니다. |

## 10. GitHub에 반영할 내용

공유할 항목은 소스 코드, `requirements-dashboard.txt`, README, 필요한 `assets`, 밝은 테마용 `.streamlit/config.toml`입니다. 테마 설정은 **저장소 최상위 `.streamlit/config.toml`**에 두고 같은 위치에서 실행합니다.

가상환경, 캐시, 개인 비밀번호, `.streamlit/secrets.toml`은 커밋하지 않습니다. 영상·모델·DB 덤프·실행별 분석 결과는 필요한 범위를 확인해 별도 전달합니다. GitHub에 코드를 올리는 것과 팀원의 로컬 DB·파일을 준비하는 것은 별개의 작업입니다.

## 11. 범위와 한계

현재 구성은 저장 영상 기반 시연입니다. 실제 CCTV 스트림, 실시간 열차 도착·지연 수신, 혼잡도 예측 모델은 연결하지 않았습니다. 내부 잔류 인원은 분석 모듈의 추정값을 보존합니다. 대시보드의 예상 대기시간·혼잡도는 CCTV별 5m·10m·15m 기준선을 이용한 **임의 거리 기준 시연값**만 사용합니다. 거리 판정 불가 시 측정 불가이며 인원 기반 수식으로 대체하지 않습니다. 설정 방법과 검증 범위는 [거리 기준선 안내](DISTANCE_DEMO.md)를 확인하세요.

분석 모듈의 기준 버전은 `busan-cctv-analysis 0.3.2`입니다. 모델·API·설치 및 기존 검증 범위는 [분석 모듈 README](../cctv-analysis/README.md)와 [최종 인계 문서](../cctv-analysis/docs/FINAL_HANDOFF.md)를 참고합니다. 세 영상을 순차 분석하는 것과 세 CCTV를 동시에 실시간 추론하는 것은 다릅니다.

이 README의 명령과 경로는 작업 브랜치의 소스·패키지 설정을 확인해 정리했습니다. 팀원 컴퓨터의 실제 설치, MySQL 가져오기 및 영상 분석은 해당 환경에서 확인해야 합니다.
