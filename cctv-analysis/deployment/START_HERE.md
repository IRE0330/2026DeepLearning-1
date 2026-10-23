# 화장실 분석 모듈 설치·연동 시작

안정 버전은 **0.3.2**입니다. 2026-10-23 원격 Release 확인 결과 최신 정식 배포이며 draft/prerelease가 아닙니다. 이번 작업은 기존 Release 파일 재배치와 안내 추가입니다. 미게시 정확도 실험이나 기존 개발 PC의 변경을 포함하지 않았습니다.

## 1. GitHub에서 파일 찾기

1. [저장소](https://github.com/IRE0330/2026DeepLearning-1)를 엽니다.
2. **Code → 브랜치 선택 → `mvp/busan-cctv-20261014`**를 선택합니다.
3. **`cctv-analysis` → `deployment` → `START_HERE.md`**를 엽니다. 루트 README와 모듈 README의 첫 링크로도 이동할 수 있습니다.
4. 아래 ZIP 또는 wheel을 클릭하고 파일 화면의 **Download raw file** 버튼으로 내려받습니다.

## 2. 다운로드할 ZIP·가중치

|자료|다운로드|
|---|---|
|설치용 ZIP|[busan_cctv_analysis-0.3.2-deployment.zip](busan_cctv_analysis-0.3.2-deployment.zip)|
|동일 버전 wheel|[busan_cctv_analysis-0.3.2-py3-none-any.whl](busan_cctv_analysis-0.3.2-py3-none-any.whl)|
|검증 해시|[SHA256SUMS.txt](SHA256SUMS.txt)|
|공식 가중치|[yolo11n.pt](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt)|
|공개 예시 CSV 3개|[examples/data](../examples/data/README.md) 또는 [Release의 example-results.zip](https://github.com/IRE0330/2026DeepLearning-1/releases/download/cctv-analysis-v0.3.2/busan_cctv_analysis-0.3.2-example-results.zip)|

[원본 Release](https://github.com/IRE0330/2026DeepLearning-1/releases/tag/cctv-analysis-v0.3.2)의 **Assets**에서도 ZIP·wheel·원본 SHA256SUMS를 받을 수 있습니다. 이 폴더의 ZIP·wheel은 원본 Release와 바이트 및 SHA-256이 같습니다. ZIP에 같은 wheel이 `dist/`에 들어 있어 ZIP을 받았다면 wheel을 별도로 받을 필요는 없습니다. `SHA256SUMS.txt`는 이 폴더의 두 파일만 대상으로 작성한 목록입니다.

ZIP에는 소스·마스킹 설정·문서·예제·검증 자료·wheel이 있습니다. **가중치, 원본/결과 영상, 전체 outputs, 가상환경, MICC 데이터는 포함하지 않습니다.** 영상은 사용 권한이 있는 파일을 별도로 준비하세요. 기존 CSV·outputs는 새 영상 분석의 필수 입력이 아닙니다. 새 분석을 실행하면 새 결과가 생성됩니다.

다운로드한 ZIP과 wheel은 PowerShell에서 `Get-FileHash -Algorithm SHA256 .\파일명`으로 검사해 `SHA256SUMS.txt`와 비교합니다. ZIP은 새 폴더에 풀고 압축을 푼 폴더에서 다음 명령을 실행합니다.

```powershell
Expand-Archive -LiteralPath .\busan_cctv_analysis-0.3.2-deployment.zip -DestinationPath .\cctv032
Set-Location .\cctv032
```

가중치는 재배포 권한이 확정되지 않아 직접 첨부하지 않습니다. [배포 고지](../docs/RELEASE_NOTICES.md)를 확인하세요. 공식 파일을 내려받아 압축을 푼 폴더의 `models/yolo11n.pt`로 저장합니다.

```powershell
New-Item -ItemType Directory -Path .\models -ErrorAction Stop
Invoke-WebRequest -Uri 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt' -OutFile .\models\yolo11n.pt
if ((Get-FileHash .\models\yolo11n.pt -Algorithm SHA256).Hash.ToLower() -ne '0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1') { throw '가중치 SHA-256 불일치' }
```

파일명: `yolo11n.pt`, SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`. 이미 같은 해시의 파일이 있으면 재다운로드 대신 해당 경로를 지정합니다.

## 3. 검증된 Python 환경과 새 가상환경 설치

검증 기준은 **Windows x64 · Python 3.13.9 · CPU**입니다. Python 3.13.9를 준비하고 아래 버전 출력으로 확인하세요. 의존성 설치에는 인터넷이 필요합니다. 기존 가상환경을 복사하지 않습니다.

```powershell
py -3.13 --version
py -3.13 -m venv .venv-cctv
$py = (Resolve-Path .\.venv-cctv\Scripts\python.exe).Path
& $py -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
& $py -m pip install '.\dist\busan_cctv_analysis-0.3.2-py3-none-any.whl[analysis,streamlit]' -c .\requirements-handoff-032.txt
& $py -m pip check
& $py -c "import cctv, importlib.metadata as m; print(m.version('busan-cctv-analysis')); print(cctv.__file__)"
& $py -m cctv --help
```

`py`가 없으면 첫 두 명령의 `py -3.13`을 설치한 Python 3.13.9 실행 파일로 대체하세요. 최신 인계 의존성 목록은 ZIP의 `requirements-handoff-032.txt`입니다. 이전 CPU/GPU 잠금 파일은 당시 환경 기록입니다.

## 4. 가중치·입력 영상 경로 지정

사용 권한이 있는 영상을 `inputs/north.mp4`에 준비한 예입니다. 자신의 실제 파일명으로 바꾸세요. 다음 경로는 모두 압축을 푼 폴더 기준이며 개인 PC의 고정 절대 경로를 사용하지 않습니다.

```powershell
$weights = (Resolve-Path .\models\yolo11n.pt).Path
$video = (Resolve-Path .\inputs\north.mp4).Path
```

CLI는 `--model`, API는 `model_path`로 지정합니다. 대안은 `$env:CCTV_MODEL_PATH = $weights`입니다. 직접 지정한 경로가 우선하며 분석 중 가중치를 자동 다운로드하지 않습니다.

## 5. 화장실별 마스킹 설정 선택

|화장실|API/예제 room|ZIP의 번들 설정|
|---|---|---|
|북쪽|`north`|`src/cctv/data/configs/north.json`|
|남쪽|`south`|`src/cctv/data/configs/south.json`|
|동쪽|`east`|`src/cctv/data/configs/east.json`|

`restroom_id` 또는 `--room`으로 해당 번들 마스킹을 선택합니다. 동쪽은 기존 제외 구역과 소화기 제외 다각형을 포함합니다. **기존 좌표는 기존 카메라·구도용입니다. 다른 CCTV 구도에서는 출입선·대기 구역·제외 구역 마스킹을 다시 설정해야 합니다.**

```powershell
& $py -m cctv export-assets --destination .\my-assets
# 내보낸 configs/north.json의 video를 자신의 영상 경로로 수정한 뒤 실행
& $py -m cctv configure --config .\my-assets\configs\north.json
```

P로 미리보기, S로 확인 저장합니다. 사용자 설정을 사용할 때는 아래 분석 명령에 `--config .\my-assets\configs\north.json`을 추가합니다. API에서는 `config_path`를 지정하며 `restroom_id`는 JSON과 일치시킵니다. demo는 시연 초기값·1초 기록, operating은 초기값 미설정·10초 기록입니다. 새 CCTV에 시연 초기값을 그대로 적용하지 마세요.

## 6. 짧은 실제 분석 검증

기존 north 구도의 영상과 번들 마스킹을 사용하는 0~3.25초 CPU 분석 예입니다. 남쪽·동쪽은 영상 경로와 `--room`을 함께 바꾸세요. 다른 구도는 앞에서 만든 사용자 설정을 추가하세요.

```powershell
& $py .\examples\analyze_video.py --room north --video $video --model $weights --output .\runs-check --profile demo --device cpu --end 3.25
if ($LASTEXITCODE -ne 0) { throw '분석 실패: 위 오류와 경로를 확인하세요' }
```

상태가 `completed`인지, API 레코드가 출력되는지, 상태의 `csv_files`에 새 CSV가 생겼는지 확인하세요. 기존 CSV를 읽어서 성공으로 대신하지 않습니다. 이 명령은 팀원이 실행할 확인 절차이며 이번 정리 작업에서는 영상 분석을 다시 수행하지 않았습니다.

## 7. AnalysisService 연동과 상세 문서

아래 코드를 압축을 푼 폴더의 `integration_check.py`로 저장하고 `& $py .\integration_check.py`로 실행합니다. Windows 프로세스 시작을 위해 `__main__` 보호문이 필요합니다.

```python
from pathlib import Path
from cctv import AnalysisService

def main():
    with AnalysisService() as service:
        job = service.start(
            owner="team-app", restroom_id="north",
            video_path=str(Path("inputs/north.mp4").resolve()),
            model_path=str(Path("models/yolo11n.pt").resolve()),
            output_dir=str(Path("runs-api").resolve()),
            profile="demo", device="cpu", end=3.25,
            # config_path="my-assets/configs/north.json",  # 다른 구도는 재설정 후 지정
        )
        for record in job.records():
            print(record)  # 새 집계 레코드를 팀 앱에 전달
        state = job.status()
        print(state)
        if state["status"] != "completed":
            raise RuntimeError(state)
        print(state["csv_files"])

if __name__ == "__main__":
    main()
```

공개 API와 최소 화면 호출은 [모듈 README](../README.md), [실행 예제](../examples/analyze_video.py), [Streamlit 예제](../examples/streamlit_app.py), [데이터 계약](../docs/DATA_CONTRACT.md)을 보세요. [최종 인계](../docs/FINAL_HANDOFF.md)는 기존 실행과 평가 근거를 보존한 기록입니다. 그 안의 과거 로컬 `dist/` 전달 위치 대신 이번 다운로드 위치를 사용하세요. ZIP 안에서는 이 링크들의 `../`를 제외한 같은 상대 경로로 문서를 찾을 수 있습니다.

## 8. 지원 환경과 미검증 환경

wheel의 Python 범위는 **3.13 이상, 3.14 미만**입니다. 실제 검증 근거는 [RELEASE_VERIFICATION_032.json](../docs/RELEASE_VERIFICATION_032.json) 및 [handoff_verification_032.json](../docs/handoff_verification_032.json)입니다. Windows x64/Python 3.13.9/CPU의 별도 폴더·새 가상환경에서 설치·pip check·짧은 실제 분석·세 환경의 CSV/API 13열 일치를 확인한 기록을 재사용합니다.

macOS·Linux·다른 PC·다른 Python 버전·다른 GPU/드라이버·장시간 운영·실제 CCTV 수신·세 CCTV 동시 실시간 처리는 이번 안정 배포에서 미검증입니다. Python 3.14는 wheel 지원 범위 밖입니다. 정확도 개선이나 실시간 동시 처리 성능을 보장하지 않습니다.

Release 태그의 소스 커밋은 `e4bee7b09b31031a20832d3808faf22ac5a32b64`, 이번 정리 시작 시 작업 브랜치 HEAD는 `2019706fbdedf07885639a84824263a6a9839247`입니다. [정리·복구 기록](CLEANUP_RECORD.md)에서 보존 결정과 검증 범위를 확인할 수 있습니다.
