"""Headless UI verification; no real browser or CCTV inference."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'busan_restroom_dashboard'))
from streamlit.testing.v1 import AppTest


class SettingsUI(unittest.TestCase):
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
