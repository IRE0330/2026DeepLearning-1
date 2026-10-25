"""Portable annotation binding; no model inference or writes to user settings/DB."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'busan_restroom_dashboard'))
import distance_reference as reference
from distance_demo import evaluate, settings_for, video_key
from distance_display import overlay


def annotation(source):
    return {'source_key': video_key(str(source)), 'origin': [.5, .1], 'frame_s': 0.,
            'lines': {str(m): [[.1, y], [.9, y]] for m, y in [(5, .3), (10, .5), (15, .7)]}}


def record():
    return {'interval_end_s': 1., 'detail': {'state': {'source_time_s': 1., 'waiting_total': 1,
        'queue_geometry': {'version': 1, 'points': [{'track_id': 1, 'point': [.5, .6], 'confidence': .9}],
                           'candidate_count': 0, 'occluded_count': 0, 'suppressed_count': 0}}}}


class PortableReference(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = {'videos': {}, 'distance_demo': {}, 'distance_video_keys': {}}
        for room in reference.ROOMS:
            source = self.root / 'pc-a' / (room + '.mp4')
            source.parent.mkdir(exist_ok=True)
            source.write_bytes((room + ' synthetic original bytes').encode())
            self.cfg['videos'][room] = str(source)
            self.cfg['distance_demo'][room] = annotation(source)
            self.cfg['distance_video_keys'][room] = video_key(str(source))
        self.shared = reference.build_reference(self.cfg)
        self.shared['hide_editor'] = True
        self.file = self.root / 'distance_reference.json'
        self.write_reference()
        self.patch = patch.object(reference, 'REFERENCE_PATH', self.file)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write_reference(self):
        self.file.write_text(json.dumps(self.shared), encoding='utf-8')

    def other_pc(self):
        cfg = copy.deepcopy(self.cfg)
        cfg.pop('distance_demo')
        for room, source in self.cfg['videos'].items():
            target = self.root / 'pc-b' / ('renamed-' + room + '.mov')
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
            os.utime(target, (1_700_000_000, 1_700_000_000))
            cfg['videos'][room] = str(target)
        return cfg

    def test_export_has_exact_coordinates_and_no_machine_paths(self):
        text = json.dumps(self.shared)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn('videos', self.shared)
        for room in reference.ROOMS:
            for key in ('origin', 'lines', 'frame_s'):
                self.assertEqual(self.shared['rooms'][room][key], self.cfg['distance_demo'][room][key])

    def test_other_pc_renamed_copy_new_mtime_applies_without_local_annotations(self):
        cfg = self.other_pc()
        before = copy.deepcopy(cfg)
        for room in reference.ROOMS:
            self.assertNotEqual(video_key(cfg['videos'][room]), self.cfg['distance_video_keys'][room])
            setting, key = settings_for(cfg, room)
            self.assertTrue(key.startswith('sha256:'))
            self.assertEqual(evaluate(record(), setting, key)['reached_m'], 10)
            self.assertEqual(overlay(cfg, room).count('<line '), 3)
        self.assertTrue(reference.shared_editor_hidden(cfg))
        self.assertEqual(cfg, before)

    def test_displayed_source_can_resolve_old_run_paths(self):
        cfg = self.other_pc()
        cfg['distance_current_videos'] = cfg['videos']
        cfg['videos'] = {room: '/other-pc/no-longer-present/' + room for room in reference.ROOMS}
        for room in reference.ROOMS:
            setting, key = settings_for(cfg, room)
            self.assertEqual(evaluate(record(), setting, key)['reached_m'], 10)

    def test_new_run_fingerprint_bridges_unknown_pc_legacy_keys(self):
        cfg = self.other_pc()
        cfg['distance_video_keys'] = {r: '0' * 64 for r in reference.ROOMS}
        cfg['distance_video_fingerprints'] = {r: reference.video_fingerprint(p) for r,p in cfg['videos'].items()}
        for room in reference.ROOMS:
            self.assertTrue(settings_for(cfg, room)[1])
        cfg['distance_video_fingerprints']['north'] = 'f' * 64
        self.assertFalse(settings_for(cfg, 'north')[1])

    def test_unknown_legacy_analysis_binding_is_not_silently_migrated(self):
        cfg = self.other_pc()
        cfg['distance_video_keys']['north'] = 'f' * 64
        self.assertFalse(settings_for(cfg, 'north')[1])
        self.assertFalse(reference.shared_editor_hidden(cfg))

    def test_same_name_and_size_different_bytes_do_not_match(self):
        cfg = self.other_pc()
        source = Path(cfg['videos']['north'])
        source.write_bytes(b'x' * source.stat().st_size)
        self.assertFalse(settings_for(cfg, 'north')[1])
        self.assertEqual(overlay(cfg, 'north'), '')
        self.assertFalse(reference.shared_editor_hidden(cfg))

    def test_swapped_camera_files_never_apply_another_rooms_lines(self):
        cfg = self.other_pc()
        cfg['videos']['north'] = cfg['videos']['east']
        self.assertFalse(settings_for(cfg, 'north')[1])

    def test_missing_invalid_reference_preserves_valid_legacy_local_settings(self):
        for contents in ('{bad json', '{}'):
            self.file.write_text(contents, encoding='utf-8')
            setting, key = settings_for(self.cfg, 'north')
            self.assertEqual(setting, self.cfg['distance_demo']['north'])
            self.assertEqual(key, self.cfg['distance_video_keys']['north'])
            self.assertFalse(reference.shared_editor_hidden(self.cfg))
        with patch.object(reference, 'REFERENCE_PATH', self.root / 'missing.json'):
            self.assertTrue(settings_for(self.cfg, 'north')[1])

    def test_invalid_geometry_and_export_of_unbound_lines_are_rejected(self):
        self.shared['rooms']['north']['lines']['10'] = self.shared['rooms']['north']['lines']['5']
        self.write_reference()
        self.assertFalse(reference.shared_editor_hidden(self.other_pc()))
        cfg = copy.deepcopy(self.cfg)
        cfg['distance_demo']['north']['source_key'] = 'wrong-video'
        with self.assertRaises(ValueError):
            reference.build_reference(cfg)

    def test_returned_reference_cannot_mutate_shared_or_user_settings(self):
        cfg = self.other_pc()
        setting, key = settings_for(cfg, 'north')
        setting['origin'][0] = 0
        self.assertEqual(settings_for(cfg, 'north')[0]['origin'], [.5, .1])

    def test_editor_is_hidden_only_after_all_three_sources_verify(self):
        from streamlit.testing.v1 import AppTest
        import distance_ui
        cfg = self.other_pc()
        script = """
import streamlit as st
from distance_ui import render_distance_settings
render_distance_settings(st.session_state.cfg, lambda cfg: None)
"""
        app = AppTest.from_string(script)
        app.session_state['cfg'] = cfg
        with patch.object(distance_ui, '_EDITOR', side_effect=AssertionError('editor must be hidden')):
            app.run()
        self.assertFalse(app.exception)
        self.assertFalse(any(w.key == 'distance_room' for w in app.radio))
        self.assertTrue(any('공통 기준선' in w.value for w in app.caption))
        for room in reference.ROOMS:
            self.assertEqual(overlay(cfg, room).count('<line '), 3)


if __name__ == '__main__':
    unittest.main()
