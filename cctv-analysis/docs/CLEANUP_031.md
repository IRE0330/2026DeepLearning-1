# 0.3.1 최종 정리·보존 기록

최신 결과를 outputs/final/north·south·east로 복사하고 영상 전 프레임·CSV·설정·상세 상태·이벤트·해시를 검증한 뒤 중복을 삭제했습니다. 재분석이나 수치 보정은 하지 않았습니다.

삭제 항목 699개(파일 및 검증된 생성 폴더 단위)입니다. 세부 원본 SHA-256과 보존 대응 경로는 로컬 outputs/final/cleanup_report.json, 복사799건의 원본 해시는 copy_verification.json에 있습니다.

## 삭제

- 최종/보존 evidence에 바이트 동일 사본을 확인한 중간 결과 파일. 이전 final은 evidence/history/original_final에 원본 바이트로 보존했습니다.
- 0.2.0·0.3.0·0.3.1 검증용 pip target 설치 폴더: 해당 wheel의 패키지 파일과 전부 일치한 경우만 제거했습니다. 가상환경은 아닙니다.
- 소스와 일치한 임시 cctv-analysis/build 및 실패한 장경로 복사 staging(보존 사본과 해시 일치).
- 구버전0.1.0/0.2.0/0.3.0 wheel 및0.2.0/0.3.0 인계 ZIP. 최신0.3.1 wheel/ZIP은 재확인 후 유지합니다.

## 보존

- 원본 영상·가중치·MICC·가상환경·수동 정답/검토 자료·다른 구성원의 파일.
- 최신 영상/공유 CSV·이벤트·상세 추적/상태·설정·실행 요약·공통 검증 근거.
- 고유한 이전 영상·로그·검토 이미지는 final/evidence/history에 보존했습니다. 고유 파일을 중복으로 간주해 삭제하지 않았습니다.
- 내용 미확인 런타임 캐시/컴파일 캐시가 남은 아래 경로는 임의 삭제하지 않았습니다. 자료 본문은 final/evidence로 통합했습니다.
- `outputs/confirmed_waiting_20261018_v020_r2`: 런타임 캐시 또는 미검토 파일 잔여.
- `outputs/confirmed_waiting_20261018_v030`: 런타임 캐시 또는 미검토 파일 잔여.
- `outputs/east_extinguisher_20261018_v031`: 런타임 캐시 또는 미검토 파일 잔여.
- `outputs/final_pre031_verified_hold`: 런타임 캐시 또는 미검토 파일 잔여.

경로 표는 outputs/final/path_relocation.json입니다. 현재 환경별 JSON/공개 수신 envelope 경로는 갱신했고, evidence/history의 원본 경로 문자열은 변경하지 않은 역사적 값이므로 경로 표로 해석합니다. 문서의 중간 결과 경로는 보존 evidence 또는 최신 final로 갱신했습니다.

최종 검증과 원격 공유 상태는 FINAL_HANDOFF.md 및 완료 보고를 따릅니다. wheel·ZIP·outputs는 Git 제외이며 소스/설정/테스트/문서/공유 허용 예시 CSV만 명시적으로 스테이징합니다.
