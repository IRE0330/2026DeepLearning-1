# 설치·실행 시작 — 안정 0.3.2

저장 CCTV 영상의 출입·대기를 분석하고 새 CSV/API 레코드를 생성합니다. [모듈 개요·상세 문서](../README.md)를 함께 확인하세요.

## 다운로드와 준비

GitHub **Code → 브랜치 `mvp/busan-cctv-20261014` → cctv-analysis → deployment**에서 아래 파일을 열고 **Download raw file**로 받습니다.

- [deployment ZIP](busan_cctv_analysis-0.3.2-deployment.zip) · [SHA256SUMS.txt](SHA256SUMS.txt): Release와 동일한 파일입니다. `Get-FileHash -Algorithm SHA256 .\파일명`으로 비교하세요.
- [wheel](busan_cctv_analysis-0.3.2-py3-none-any.whl)은 ZIP의 `dist/`에도 있으므로 ZIP을 받으면 별도 다운로드가 필요 없습니다. 대체 위치: [Release Assets](https://github.com/IRE0330/2026DeepLearning-1/releases/tag/cctv-analysis-v0.3.2).
- ZIP에는 **가중치·원본/결과 영상·가상환경·전체 outputs가 없습니다.** 사용 권한이 있는 영상을 별도로 준비합니다. 기존 CSV·outputs는 새 분석의 필수 입력이 아닙니다.
- [공식 yolo11n.pt](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt)를 압축을 푼 폴더의 `models/yolo11n.pt`에 저장합니다. SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`. 가중치는 재배포 권한 미확정으로 첨부하지 않습니다. [AGPL-3.0/Enterprise·배포 고지](../docs/RELEASE_NOTICES.md)를 확인하세요.

## 설치·짧은 분석 — Windows PowerShell

**Python 3.13.9·Windows x64·CPU**에서 검증한 명령입니다. ZIP을 새 폴더에 풀고 실행합니다. 의존성 설치에는 인터넷이 필요하며 기존 가상환경을 복사하지 않습니다.

```powershell
Expand-Archive -LiteralPath .\busan_cctv_analysis-0.3.2-deployment.zip -DestinationPath .\cctv032
Set-Location .\cctv032
py -3.13 --version
py -3.13 -m venv .venv-cctv
$py = (Resolve-Path .\.venv-cctv\Scripts\python.exe).Path
& $py -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
& $py -m pip install '.\dist\busan_cctv_analysis-0.3.2-py3-none-any.whl[analysis,streamlit]' -c .\requirements-handoff-032.txt
& $py -m pip check
$weights = (Resolve-Path .\models\yolo11n.pt).Path
Get-FileHash -Algorithm SHA256 $weights
$video = (Resolve-Path .\inputs\north.mp4).Path
& $py .\examples\analyze_video.py --room north --video $video --model $weights --output .\runs-check --profile demo --device cpu --end 3.25
```

`inputs/north.mp4`는 준비할 영상의 위치 예시입니다. 자신의 파일명으로 바꾸세요. `py`가 없으면 설치한 Python 3.13.9 실행 파일을 사용합니다. 가중치 해시를 위 값과 비교한 뒤 분석하세요. 상태가 `completed`이고 `csv_files`의 새 CSV가 생성됐는지 확인합니다. 결과는 `runs-check/` 아래 작업별로 생성되며 정확한 위치는 `run_dir`·`csv_files`에 표시됩니다.

## 마스킹·연동·지원 범위

- `--room north|south|east`로 기존 구도의 번들 마스킹을 선택합니다. 남쪽·동쪽은 영상과 room을 함께 바꿉니다. **다른 CCTV 구도는 출입선·대기·제외 구역을 다시 설정해야 합니다.** 사용자 설정은 기존 예제의 `--config <JSON>` 또는 API의 `config_path`로 지정하고 JSON의 화장실 ID와 맞춥니다. [마스킹 내보내기·설정 절차](../docs/FINAL_HANDOFF.md#영상별-마스킹-연결)
- `--profile demo`는 시연 초기값·가상시각·1초 기록을 사용합니다. 운영 프로필은 `operating`(초기값 미설정·10초 기록)이므로 새 CCTV에 시연 가정을 그대로 적용하지 마세요. 가중치는 분석 중 자동 다운로드하지 않으며 직접 지정 대신 `CCTV_MODEL_PATH`도 사용할 수 있습니다.
- AnalysisService 연동: [공개 API·상태·레코드 수신](../docs/DATA_CONTRACT.md), [실행 예제](../examples/analyze_video.py). Windows spawn에서는 `if __name__ == '__main__':` 보호문이 필요합니다. [예시 CSV 3개](../examples/data/README.md)는 추론 입력이나 새 분석 대체물이 아닙니다.
- wheel 지원 범위는 Python >=3.13,<3.14입니다. macOS·Linux·다른 PC/GPU/드라이버·장시간 운영·실제 CCTV 수신·세 CCTV 동시 실시간은 이번 배포에서 미검증입니다. 정확도·가림/ID 유실·추정값의 한계는 [모듈 README](../README.md), 근거는 [배포 검증](../docs/RELEASE_VERIFICATION_032.json)을 보세요. Python 3.14는 지원 범위 밖입니다.

[최종 인계](../docs/FINAL_HANDOFF.md) · [모델·라이선스](../docs/MODEL.md) · [정리·해시 검증 기록](CLEANUP_RECORD.md)
