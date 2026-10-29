"""Headless UI contract tests; synthetic service, not a browser or detector test."""
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch
import cctv
try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except ImportError:
    st = None

APP = Path(cctv.__path__[0]) / 'examples/streamlit_app.py'


class FakeService:
    def __init__(self):
        self.owner = None
        self.starts = 0
        self.state = {'status': 'idle', 'worker_alive': False, 'latest_record': None}
    def status(self, owner=None):
        return {**self.state, 'owned_by_session': owner == self.owner}
    def start(self, **options):
        self.owner = options['owner']
        self.starts += 1
        self.state.update(status='running', worker_alive=True, processed_frames=24, progress=.5,
                          runtime_device={'parameter_device': 'cpu'},
                          latest_record={'interval_end_s': 1., 'persisted_at': '2026-10-17T00:00:00+00:00',
                                         'csv_row': {'외부대기인원_추정': 2}, 'record_id': 'test-record', 'is_demo': True,
                                         'detail': {'state': {'expected_wait_s': None}}})
    def stop(self, owner, wait=False):
        assert owner == self.owner
        self.state.update(status='stopped', worker_alive=False)
    def close(self): pass


class SpawnGuard(unittest.TestCase):
    def test_spawn_import_does_not_import_or_call_streamlit(self):
        with patch.dict(sys.modules, {'streamlit': None}):
            runpy.run_path(str(APP), run_name='__mp_main__')


@unittest.skipIf(st is None, 'Install optional Streamlit extra')
class UIContract(unittest.TestCase):
    def test_rerun_single_job_two_sessions_latest_stop_and_error(self):
        fake = FakeService()
        st.cache_resource.clear()
        with patch('cctv.AnalysisService', return_value=fake):
            first = AppTest.from_file(str(APP)).run()
            self.assertFalse(first.exception)
            first.text_input(key='video').set_value('source.mp4')
            first.text_input(key='model').set_value('yolo11n.pt')
            first.button[0].click().run()
            self.assertFalse(first.exception)
            for _ in range(3): first.run()
            self.assertEqual(fake.starts, 1)
            self.assertIn('test-record', first.json[1].value)
            second = AppTest.from_file(str(APP)).run()
            self.assertFalse(second.exception)
            self.assertTrue(second.button[0].disabled)
            self.assertTrue(second.button(key='stop').disabled)
            self.assertTrue(any('다른 세션' in item.value for item in second.info))
            first.button(key='stop').click().run()
            self.assertFalse(first.exception)
            self.assertTrue(any('중지 완료' in item.value for item in first.text))
            fake.state.update(status='failed', error='Missing video: not_present.mp4')
            first.run()
            self.assertTrue(any('not_present.mp4' in item.value for item in first.error))
            fake.state.update(status='completed', error=None)
            first.run()
            self.assertTrue(any('정상 완료' in item.value for item in first.text))
        st.cache_resource.clear()


if __name__ == '__main__':
    unittest.main()
