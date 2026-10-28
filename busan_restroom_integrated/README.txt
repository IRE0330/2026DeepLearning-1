현재 대시보드 설치·실행은 저장소 최상위 README.md를 따릅니다.
이 폴더와 아래 0.3.2 업데이트 명령은 이전 자료 보존본입니다.

---

압축 오류 수정판 - 기존 앱에 코드만 업데이트합니다.
기존 영상, 설정, 분석 기록, 화장실 이용 데이터는 그대로 사용합니다.

앱 실행 터미널에서 Control+C로 종료 후 아래 명령을 실행합니다.

python3 ~/Downloads/busan_restroom_dashboard_repair_update/install_update.py
cd ~/Downloads/cctv032/busan_restroom_dashboard
../.venv-cctv/bin/python -m streamlit run app.py

브라우저에서 Command+Shift+R로 새로고침하세요.
재생 제어 수정, 메뉴 왼쪽 정렬, 현재 혼잡도 색상 카드 및 하단 4행 정보가 모두 포함되어 있습니다.
