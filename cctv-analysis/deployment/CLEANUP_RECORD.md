# 배포 자료 정리·복구 기록

작업일: 2026-10-23. 브랜치: `mvp/busan-cctv-20261014`.
정리 시작 원격 커밋: `2019706fbdedf07885639a84824263a6a9839247`.
안정 Release: `cctv-analysis-v0.3.2`, 태그 소스 커밋: `e4bee7b09b31031a20832d3808faf22ac5a32b64`.

## 보존·삭제 결정

- 삭제 파일: **없음**. 추적된 구버전 wheel/ZIP·임시 build 생성물·불필요함이 확인된 중복 문서를 찾지 못했습니다.
- `release-files/` 5개 파일은 `scripts/verify_release_assets.py`와 `.github/workflows/cctv-analysis-release.yml`이 참조하므로 모두 보존합니다. `handoff.zip`은 최초 검증 묶음이며 deployment ZIP과 역할이 다릅니다.
- 분석 소스·API·번들 마스킹·운영/시연 설정·의존성·설치/진단 스크립트·테스트·연동 예제·문서·고지·예시 CSV 3개·수동 정답·평가/재현 근거를 모두 보존합니다. 개발 실험을 안정 파일로 복사하지 않았습니다.
- 기존 두 README 맨 위에 시작 안내 링크만 추가합니다. 다른 담당 영역은 변경하지 않습니다.

삭제 전 보존/삭제 계획은 별도 clone 밖 `recovery-backup/preserve-delete-plan.json`에 전체 담당 영역의 추적 경로와 SHA-256으로 기록했습니다. 삭제 후보는 빈 목록입니다. 추가로 기존 안정 ZIP·wheel·원본 체크섬 목록의 복구 사본을 만들고 파일별 해시 일치를 `backup-manifest.json`에 기록했습니다. 백업은 Git에 포함하지 않습니다. 정확한 절대 위치는 작업 완료 보고를 따릅니다.

추적 파일을 시작 시점으로 복구하려면 **별도 clone에서만**, 현재 변경을 먼저 보존한 뒤 원하는 개별 경로를 지정합니다.

```powershell
git restore --source=2019706fbdedf07885639a84824263a6a9839247 --worktree -- cctv-analysis/복구할_개별_파일
```

공유 브랜치에 이미 반영한 변경을 취소할 때는 이력 삭제나 force push 대신 새 복구 커밋을 만드세요. 기존 개발 폴더에는 이 명령을 실행하지 않습니다.

## 배포 검증 범위

GitHub Release API의 정식 배포 여부와 첨부 digest를 확인하고 5개 첨부를 별도로 다운로드했습니다. 기존 `release-files/` 및 새 deployment의 ZIP·wheel은 Release SHA-256과 같습니다. 재빌드하지 않았습니다. 새 `SHA256SUMS.txt`는 deployment에 배치한 ZIP과 wheel만 열거합니다.

ZIP/wheel의 파일 목록으로 인증 파일·가상환경·가중치·원본 영상·데이터셋 제외 여부를 점검하며 인증값을 열람하지 않습니다. ZIP manifest의 파일별 해시, ZIP에 내장된 wheel, 공개 예시 CSV 3개의 해시 및 문서 상대 링크도 검증합니다. 실제 설치·짧은 분석은 기존 안정 배포의 검증 기록을 재사용하며 전체 영상 분석·학습은 반복하지 않습니다.

검증 통과: Release 첨부 5개, 새 배치 파일 2개, 압축 파일 목록 366개, 내장 manifest 파일 해시 151개, wheel/소스 일치 58개(CRLF/LF만 정규화), 예시 CSV 3개, 새 안내의 상대 링크 15개. 기존 담당 영역 추적 파일 149개는 모두 보존했으며 README의 안내 링크 추가 외에는 원본 바이트를 유지합니다. 실행 파일은 변경하지 않았습니다.
