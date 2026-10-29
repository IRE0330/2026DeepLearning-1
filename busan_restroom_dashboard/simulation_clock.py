"""Simulation date and browser clock widgets driven by saved video position."""
from datetime import datetime
import json
import time
import streamlit as st

START=datetime(2026,10,14,14,0,0)


def start_epoch():
    # Session identity only; elapsed wall time must not advance the video clock.
    if '_sim_clock_started' not in st.session_state:
        st.session_state['_sim_clock_started']=time.time()
    return st.session_state['_sim_clock_started']


def now():
    return START


def reset():
    st.session_state['_sim_clock_started']=time.time()
    st.session_state['_sim_clock_generation']=st.session_state.get('_sim_clock_generation',0)+1


def clock_frame(cfg, sidebar=False):
    """Read the same timestamp the video controller saves; paused means frozen."""
    key='busan-cctv-playback-v6:'+cfg['playback_key']
    date=cfg.get('capture_date',START.date().isoformat())
    label=('현재 시각 · 시연 기준' if sidebar else '현재 시각')
    style=('text-align:left;font-size:14px;font-weight:500' if sidebar else
           'text-align:right;font-size:clamp(28px,15vw,46px);font-weight:750')
    prefix=date.replace('-','.')+' ' if sidebar else ''
    return ('<!doctype html><html lang="ko"><meta charset="utf-8">'
            '<style>html,body{margin:0;background:transparent;font-family:system-ui,-apple-system,sans-serif;color:#172431}'
            '#label{color:#718797;font-size:13px;margin-bottom:8px}#value{white-space:nowrap;font-variant-numeric:tabular-nums}</style>'
            '<body style="'+style+'"><div id="label">'+label+'</div><div id="value">'+prefix+'14:00:00</div><script>'
            'const key='+json.dumps(key)+',sharedKey='+json.dumps('busan-platform-clock:'+cfg['playback_key'])+',base=Date.parse('+json.dumps(date+'T14:00:00Z')+'),prefix='+json.dumps(prefix)+';'
            "function paint(){let t=0;try{const state=JSON.parse(localStorage.getItem(key)||'null');if(Number.isFinite(state?.t))t=Math.max(0,state.t);}catch{}"
            "try{const shared=JSON.parse(localStorage.getItem(sharedKey)||'null');if(Number.isFinite(shared?.t))t=Math.max(0,shared.t)+(shared.running?Math.max(0,(Date.now()-shared.savedAt)/1000)*(Number(shared.speed)||1):0);}catch{}"
            "document.getElementById('value').textContent=prefix+new Date(base+t*1000).toISOString().slice(11,19);}"
            "paint();setInterval(paint,100);window.addEventListener('storage',paint);</script></body></html>")
