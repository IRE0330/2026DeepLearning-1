"""Headless UI verification; no real browser or CCTV inference."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import copy
import json
import re
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard'))
from streamlit.testing.v1 import AppTest


class SettingsUI(unittest.TestCase):
    def test_playback_identity_tracks_run_and_effective_video_without_layout_changes(self):
        import core
        import preview
        with tempfile.TemporaryDirectory() as folder:
            video=Path(folder)/'test.mp4'
            video.write_bytes(b'identity-only; media decoding is mocked')
            cfg=copy.deepcopy(core.DEFAULTS)
            cfg['videos']={r:str(video) for r in core.ROOMS}
            current=[None]
            with patch.object(core,'settings',return_value=cfg), \
                 patch.object(core,'latest_run',side_effect=lambda:current[0]), \
                 patch.object(core,'run_data',return_value=({r:[] for r in core.ROOMS},{})), \
                 patch.object(preview,'browser_preview',side_effect=lambda source,*args:Path(source)):
                app=AppTest.from_file(str(Path(core.__file__).with_name('app.py')),default_timeout=120).run()
                def key():
                    self.assertFalse(app.exception,[e.message for e in app.exception])
                    frames=app.get('iframe')
                    self.assertEqual(len(frames),1)
                    return re.search(r'"playback_key"\s*:\s*"([^\"]+)"',frames[0].proto.srcdoc).group(1)
                first=key()
                for page in (1,4,0):
                    app.button(key='nav_'+str(page)).click().run()
                    self.assertEqual(key(),first)
                video.write_bytes(b'a different source at exactly the same path')
                app.run();replacement=key()
                self.assertNotEqual(replacement,first)
                current[0]={'id':'new-analysis','request':json.dumps(cfg),'status':'completed'}
                app.run()
                self.assertNotEqual(key(),replacement)

    def test_dashboard_menus_history_and_removed_inputs(self):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard/app.py'),default_timeout=120).run()
        for i in range(5):
            if i:at.button(key='nav_'+str(i)).click().run()
            self.assertFalse(at.exception,[e.message for e in at.exception])
            if i==1:
                for room in ['north','east','south']:
                    at.radio[0].set_value(room).run()
                    self.assertFalse(at.exception)
                    for frame in at.dataframe:
                        self.assertNotIn('대기시간_초',frame.value.columns)
                        self.assertNotIn('예상대기시간_초',frame.value.columns)
            if i==4:
                for widget in at.number_input:
                    self.assertFalse(any(word in widget.label for word in ['평균 이용시간','운영 칸','전체 대기 명','절감시간']))
            for node in at:
                if hasattr(node,'proto'):
                    self.assertNotIn('expected_wait_s',str(node.proto))

    def test_camera_save_roundtrip_without_touching_user_settings(self):
        script = '''
import streamlit as st
from distance_ui import render_distance_settings
if 'saved_cfg' not in st.session_state:
    st.session_state.saved_cfg={'videos':{'north':'','east':'','south':''}}
def save(cfg):
    st.session_state.saved_cfg=cfg
render_distance_settings(st.session_state.saved_cfg,save)
'''
        at=AppTest.from_string(script,default_timeout=20).run()
        self.assertFalse(at.exception)
        import distance_ui
        payload={'origin':[.5,.1],'source_key':'','lines':{str(m):[[.1,y],[.9,y]] for m,y in [(5,.3),(10,.5),(15,.7)]}}
        for room in ['north','east','south']:
            at.radio(key='distance_room').set_value(room).run()
            with patch.object(distance_ui,'_EDITOR',side_effect=[SimpleNamespace(apply=payload),SimpleNamespace(apply=None)]):
                at.run()
            self.assertFalse(at.exception)
            self.assertIn(room,at.session_state.saved_cfg['distance_demo'])
        self.assertEqual(set(at.session_state.saved_cfg['distance_demo']),{'north','east','south'})


if __name__=='__main__':unittest.main()
