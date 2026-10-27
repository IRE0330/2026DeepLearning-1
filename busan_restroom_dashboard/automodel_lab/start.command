#!/bin/bash
cd "$(dirname "$0")" || exit 1
if [ ! -d .venv ]; then
  python3 -m venv .venv || exit 1
fi
source .venv/bin/activate
python -m pip install -r requirements.txt || { read -r -p '설치 실패. Enter로 종료'; exit 1; }
python -m streamlit run app.py --server.port 8511
