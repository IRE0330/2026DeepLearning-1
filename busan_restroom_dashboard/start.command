#!/bin/bash
set -e
cd "$(dirname "$0")"
TASK_PYTHON=""
for candidate in "../.venv-cctv/bin/python" "$HOME/Downloads/cctv032/.venv-cctv/bin/python"; do
  if [ -x "$candidate" ]; then TASK_PYTHON="$candidate"; break; fi
done
if [ -z "$TASK_PYTHON" ]; then
  echo 'cctv032/.venv-cctv 환경을 찾지 못했습니다. 이 폴더를 Downloads/cctv032 안에 넣어주세요.'
  read -r -p '엔터를 누르면 종료합니다.'
  exit 1
fi
"$TASK_PYTHON" -m streamlit run app.py
