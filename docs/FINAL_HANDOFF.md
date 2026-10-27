# 팀원 인계 — 0.3.2 / 2026-10-21

담당 범위는 `cctv-analysis/`와 현재 분석 설정입니다. 정확한 작업 브랜치 링크는 **https://github.com/IRE0330/2026DeepLearning-1/tree/mvp/busan-cctv-20261014** 입니다. 기존 기준 커밋은 `d0f5a2d9d17aa14a8e98bfe465438fe57e14d336`입니다. 이번 0.3.2 수정은 로컬 소스·wheel·인계 ZIP에 반영했습니다. **추가 삭제·commit·push는 하지 않았습니다.** 브랜치 다운로드만으로 이번 수정이 반영되지는 않으므로 최신 ZIP을 전달받으세요. main·다른 담당 영역·인증정보는 변경하지 않았습니다.

## 전달 목록

아래 경로는 저장소 루트 기준입니다. 구버전 0.3.1 배포물도 보존하며 최신 설치에는 0.3.2를 사용하세요.

|자료|전달 경로 / 내용|
|---|---|
|최신 인계 ZIP|`cctv-analysis/dist/busan_cctv_analysis-0.3.2-handoff.zip`: 소스·설정·문서·테스트·예제·잠금 파일·wheel|
|최신 설치 wheel|`cctv-analysis/dist/busan_cctv_analysis-0.3.2-py3-none-any.whl`|
|가중치, 별도 전달|`models/yolo11n.pt`, SHA-256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`|
|원본 영상, 별도 전달|`북쪽_화장실_cctv.mp4`, `남쪽 화장실_cctv.mov`, `동쪽_화장실_cctv.mov`|
|최종 결과, 별도 폴더 전달|`outputs/final/` 전체: 환경별 영상·CSV·진단·상태·실행 설정 및 공통 manifest·검증 근거·evidence/history|
|최신 공개 CSV 사본|`cctv-analysis/examples/data/{north,south,east}_2026-10-14_0000.csv`|

Git·wheel·인계 ZIP에는 가중치·원본/결과 영상·전체 outputs를 포함하지 않습니다. 별도 자료를 수신자의 인계 폴더에 `models/`, 세 원본 영상, `outputs/final/` 구조로 복사하세요. ZIP의 `manifest.json`은 포함 파일별 SHA-256, `docs/delivery_inventory_032.json`은 별도 자료의 크기·해시를 제공합니다. 의존성은 공식 저장소에서 설치하므로 완전 오프라인 배포 묶음은 아닙니다.

## 설치·실행

Windows / Python 3.13에서 ZIP을 새 폴더에 풀고 그 폴더에서 실행합니다.

```powershell
py -3.13 -m venv .venv-cctv
& .\.venv-cctv\Scripts\python.exe -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
& .\.venv-cctv\Scripts\python.exe -m pip install '.\dist\busan_cctv_analysis-0.3.2-py3-none-any.whl[analysis,streamlit]'
& .\.venv-cctv\Scripts\python.exe -m pip check
& .\.venv-cctv\Scripts\python.exe -c "import cctv, importlib.metadata as m; print(m.version('busan-cctv-analysis')); print(cctv.__file__)"
& .\.venv-cctv\Scripts\python.exe -m cctv --help
$weights = (Resolve-Path '.\models\yolo11n.pt').Path
$video = (Resolve-Path '.\북쪽_화장실_cctv.mp4').Path
& .\.venv-cctv\Scripts\python.exe .\examples\analyze_video.py --room north --video $video --model $weights --output .\runs --profile demo --device cpu --end 3.25
```

`--end 3.25`를 빼면 전체 영상을 분석합니다. API 기본값은 결과 영상 저장 끔입니다. 영상도 필요하면 API의 `save_video=True` 또는 아래 CLI를 사용하세요.

```powershell
$preset = & .\.venv-cctv\Scripts\python.exe -m cctv preset north
& .\.venv-cctv\Scripts\python.exe -m cctv analyze --config $preset --video $video --model $weights --output-dir .\runs-cli --profile demo --device cpu --end 3.25
$app = & .\.venv-cctv\Scripts\python.exe -m cctv example-path
& .\.venv-cctv\Scripts\python.exe -m streamlit run $app
```

Streamlit은 최소 호출 예시이며 화면에서 영상·가중치·결과 폴더를 지정합니다. 소스 설치는 동일 CPU PyTorch 준비 후 `python -m pip install '.[analysis,streamlit]'`입니다. CUDA는 기존 GPU 설치 안내를 따르며 이번 새 환경 검증은 CPU입니다.

이번에 설치한 전이 의존성까지 고정하려면 CPU PyTorch 준비 후 wheel 설치 명령에 `-c .\requirements-handoff-032.txt`를 추가하세요. 기존 `requirements-lock.txt`/`requirements-gpu-lock.txt`는 이전 환경의 기록이며 최신 CPU 설치 목록은 `requirements-handoff-032.txt`입니다.

## 영상별 마스킹 연결

|원본|room / 설정|마스킹|
|---|---|---|
|북쪽_화장실_cctv.mp4|`north` / `src/cctv/data/configs/north.json`|북쪽 출입·대기·제외 구역|
|남쪽 화장실_cctv.mov|`south` / `src/cctv/data/configs/south.json`|남쪽 출입·대기·제외 구역|
|동쪽_화장실_cctv.mov|`east` / `src/cctv/data/configs/east.json`|기존 제외 구역 4개 + 소화기 7각형|

`AnalysisService.start(restroom_id='east', video_path=..., model_path=..., output_dir=...)`는 번들 east 설정을 선택합니다. 직접 설정은 `config_path=...`를 추가하고 `restroom_id`를 JSON과 일치시키세요. CLI는 `python -m cctv preset east` 또는 `--config <사용자 JSON>`을 사용합니다. ZIP의 `configs/`는 같은 좌표의 설정 사본입니다.

현재 실행용/번들 JSON과 새 template의 모델 기본값은 **`${CCTV_MODEL_PATH}`**입니다. `--model`/`model_path`로 자신의 파일을 지정하거나 `$env:CCTV_MODEL_PATH = $weights`를 설정하세요. 직접 CLI/API 지정이 환경변수 기본값보다 우선합니다. 환경변수의 상대 경로는 실행 폴더 기준, JSON에 직접 쓴 상대 model 경로는 JSON 폴더 기준입니다(기존 저장소 루트 `configs/`만 호환상 저장소 루트 기준). 개인 PC 절대 경로를 기본값에 넣지 않았습니다. 미설정 시 파일 누락 오류이며 자동 다운로드하지 않습니다. **과거 `config_used.json`의 당시 경로는 보존하며 현재 실행 기본값으로 사용하지 않습니다.**

`python -m cctv export-assets --destination .\my-assets`로 사용자 편집용 설정을 내보낼 수 있습니다. 기존 좌표는 동일 카메라·구도의 전달 원본에만 사용하세요. 구도가 바뀌면 사용자 JSON의 video를 수정한 후 `python -m cctv configure --config <JSON>`에서 P 미리보기·S 확인 저장으로 다시 설정합니다. 제외 기준은 사람 박스 하단 중앙점이며 소화기 주변 사람도 제외될 수 있습니다.

## 최신 CSV·결과

정본은 저장소 루트의 다음 파일입니다. ZIP의 `examples/data/` 세 CSV는 각각 정본과 바이트 동일합니다.

- `outputs/final/north/shared/north_2026-10-14_0000.csv`
- `outputs/final/south/shared/south_2026-10-14_0000.csv`
- `outputs/final/east/shared/east_2026-10-14_0000.csv`

새 실행 CSV는 `job.status()['csv_files']` 또는 수신 레코드의 `csv_ref.path`로 찾습니다. 새 실행 폴더 아래에 생성됩니다.

|환경|전체 프레임 / 길이|CSV 행|입장/퇴장|최종 내부|
|---|---|---:|---:|---:|
|north|2524 / 105.166667초|105|5/9|25|
|south|2827 / 94.233333초|94|2/2|3|
|east|2700 / 90초|90|5/3|5|

북/남 결과는 0.3.0, 동쪽은 0.3.1 실행 이력입니다. 0.3.2는 경로·인계 보완이며 탐지·추적·마스킹·집계 수치를 바꾸거나 전체 결과를 재생성하지 않았습니다. 공유 CSV는 UTF-8 BOM·기존 13열입니다. demo는 영상 시각1초·KST 정시1시간 분할·초기29/3/3·칸27/19/23·평균105초·가상 촬영시작2026-10-14T00:00:00+09:00입니다. operating은 초기값 null·10초 기록입니다. 대기는 연속 저속 증거3.5초 후 confirmed, candidate 합계 제외, 이탈0.8초·가림 유예1.5초 정책을 유지합니다. 예측 전달은 disabled입니다.

## 이번 검증과 한계

검증 결과와 설치 의존성 목록은 `docs/handoff_verification_032.json`, `requirements-handoff-032.txt`를 따릅니다. ZIP을 별도 폴더에 풀고 전달 영상·가중치를 복사한 후 system site packages를 사용하지 않는 새 가상환경에서 wheel과 analysis/streamlit extra를 설치합니다. import가 새 site-packages를 사용하는지, AnalysisService 실제 분석의 CSV와 API 수신값이 일치하는지 확인합니다. 기존 가상환경의 site-packages를 복사하거나 연결하지 않습니다.

실제 검증 완료: pip check·CLI 도움말·설치된 모듈/Streamlit import 통과. 북쪽 78프레임, 남쪽 98프레임, 동쪽 98프레임(각 시작0~3.25초)을 CPU FP32로 처리했고 각각 API 3행과 생성 CSV 3행의 13열 전체가 일치했습니다. 마스킹·판정 규칙은 번들 설정과 일치했습니다. 북/남은 model_path 직접 지정, 동쪽은 CCTV_MODEL_PATH로 실행했습니다. 미설정 모델은 안내 오류로 종료했습니다. 소스 테스트는 99개 중98개 통과·1개 건너뜀입니다.

동일 검증 재실행: `python .\scripts\verify_handoff.py --materials . --output .\verify-runs`. 이번 원본 검증 로그·새 CSV·API envelope는 저장소 루트 `inspections/handoff_20261021/actual_analysis/verification.json`과 그 실행 폴더에 보존합니다. 설치 wheel의 SHA-256과 CSV/API 샘플은 `docs/handoff_verification_032.json`에 있습니다.

**동일 PC의 분리 폴더·새 가상환경 검증이며 다른 PC 검증은 아닙니다.** CPU의 짧은 원본 구간 검증입니다. 다른 OS·장비·GPU/드라이버·장시간·세 CCTV 동시 실시간·실제 CCTV 수신은 미검증입니다. Streamlit 설치/import를 확인하며 이번에 화면 조작을 재검증하지는 않습니다. 기존 자동 출입과 수동 총합의 차이는 남아 있고 정확도 개선을 주장하지 않습니다. 상세 계약·한계는 DATA_CONTRACT.md, WAITING_35S.md, EAST_EXTINGUISHER.md를 함께 보세요.
