"""A session-wide simulated clock that starts at 2026-10-14 14:00:00."""
from datetime import datetime, timedelta
import time
import streamlit as st

START=datetime(2026,10,14,14,0,0)

def start_epoch():
    if '_sim_clock_started' not in st.session_state:
        st.session_state['_sim_clock_started']=time.time()
    return st.session_state['_sim_clock_started']

def now():
    return START+timedelta(seconds=max(0,time.time()-start_epoch()))


def reset():
    st.session_state['_sim_clock_started']=time.time()
    st.session_state['_sim_clock_generation']=st.session_state.get('_sim_clock_generation',0)+1
