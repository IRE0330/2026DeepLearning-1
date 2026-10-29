#!/bin/bash
set -e
cd "$(dirname "$0")"
cd ..
TASK_PYTHON="${DASHBOARD_PYTHON:-.venv-cctv/bin/python}"
if [ ! -x "$TASK_PYTHON" ]; then
  echo '저장소 README.md대로 .venv-cctv를 준비하거나 DASHBOARD_PYTHON을 지정하세요.'
  read -r -p '엔터를 누르면 종료합니다.'
  exit 1
fi
"$TASK_PYTHON" -m streamlit run busan_restroom_dashboard/app.py
