"""Integration boundaries, without substituting mocks for inference validation."""
import copy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'busan_restroom_dashboard'))
import analysis_runtime as runtime
import core
import worker


class ModelRouting(unittest.TestCase):
    def setUp(self):
        self.request = copy.deepcopy(core.DEFAULTS)
        self.request.update(model='n.pt', device='cpu')

    def test_default_n_preserves_each_user_configuration(self):
        service = Mock()
        for room in core.ROOMS:
            self.request['configs'][room] = f'{room}-custom.json'
            runtime.start_room(service, self.request, room, owner='test', video_path=f'{room}.mp4')
            service.start.assert_called_with(restroom_id=room, model_path='n.pt',
                config_path=f'{room}-custom.json', device='cpu', owner='test', video_path=f'{room}.mp4')

    def test_only_explicit_north_uses_s(self):
        self.request.update(runtime_profile='north-gpu-s', north_s_model='s.pt', device='cuda:0')
        service = Mock()
        with patch.object(runtime, 'validate_selection') as validate, \
             patch('cctv.gpu_profile.start_north_gpu_s') as start_s:
            for room in core.ROOMS:
                runtime.start_room(service, self.request, room, owner='test', video_path=f'{room}.mp4')
        validate.assert_called_once_with(self.request)
        start_s.assert_called_once_with(service, model_path='s.pt', owner='test', video_path='north.mp4')
        self.assertEqual([c.kwargs['restroom_id'] for c in service.start.call_args_list], ['east', 'south'])
        for call in service.start.call_args_list:
            self.assertEqual(call.kwargs['model_path'], 'n.pt')
            self.assertEqual(call.kwargs['device'], 'cuda:0')

    def test_s_never_drops_custom_north_mask(self):
        self.request.update(runtime_profile='north-gpu-s', north_s_model='s.pt', device='cuda:0')
        self.request['configs']['north'] = 'my-north.json'
        with self.assertRaisesRegex(ValueError, '사용자 북쪽 JSON'):
            runtime.validate_selection(self.request)

    def test_s_rejects_other_devices_and_missing_path_before_worker(self):
        self.request.update(runtime_profile='north-gpu-s', north_s_model='s.pt')
        for device in ('cpu', 'mps', 'auto'):
            self.request['device'] = device
            with self.subTest(device=device), self.assertRaisesRegex(ValueError, 'cuda:0'):
                runtime.validate_selection(self.request)
        self.request.update(device='cuda:0', north_s_model='')
        with self.assertRaisesRegex(ValueError, 'yolo11s.pt'):
            runtime.validate_selection(self.request)

    def test_version_and_real_source(self):
        info = runtime.runtime_info()
        self.assertEqual(info['version'], '0.3.3')
        self.assertEqual(Path(info['source']), PROJECT / 'cctv-analysis/src/cctv/api.py')
        with patch.object(runtime.metadata, 'version', return_value='0.3.2'):
            with self.assertRaisesRegex(ValueError, '현재 0.3.2'):
                runtime.runtime_info()
        with patch('cctv.api.__file__', str(PROJECT / 'busan_restroom_integrated/src/cctv/api.py')):
            with self.assertRaisesRegex(ValueError, '다른 분석 소스'):
                runtime.runtime_info()

    def test_runtime_json_is_in_source_install_manifest_and_resources(self):
        # Outside the checkout, verify package resources through the installed
        # editable package rather than the root compatibility bridge.
        code = "from importlib.resources import files; print(files('cctv').joinpath('data/configs/runtime_profiles/north_gpu_s.json').read_text())"
        with tempfile.TemporaryDirectory() as folder:
            spec = json.loads(subprocess.check_output([sys.executable, '-B', '-c', code], cwd=folder, text=True))
        self.assertEqual((spec['name'], spec['restroom_id'], spec['device']), ('north-gpu-s', 'north', 'cuda:0'))
        manifest = (PROJECT / 'cctv-analysis/src/busan_cctv_analysis.egg-info/SOURCES.txt').read_text()
        self.assertIn('src/cctv/data/configs/runtime_profiles/north_gpu_s.json', manifest)

    def test_root_bridge_cannot_hide_a_noneditable_distribution(self):
        distribution = Mock()
        distribution.read_text.return_value = '{}'
        with patch.object(runtime.metadata, 'version', return_value='0.3.3'), \
             patch.object(runtime.metadata, 'distribution', return_value=distribution):
            with self.assertRaisesRegex(ValueError, 'editable 소스 설치'):
                runtime.runtime_info()


class DashboardLifecycle(unittest.TestCase):
    def test_start_twice_keeps_one_process_and_stop_flag(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(core, 'DATA', Path(folder)):
            cfg = copy.deepcopy(core.DEFAULTS)
            with patch.object(core, 'validate'), \
                 patch('distance_demo.video_key', return_value='key'), \
                 patch('distance_reference.video_fingerprint', return_value='fingerprint'), \
                 patch.object(core.subprocess, 'Popen', return_value=SimpleNamespace(pid=123)) as spawn:
                rid = core.start_run(cfg)
                with self.assertRaisesRegex(ValueError, '이미 분석 중'):
                    core.start_run(cfg)
            self.assertEqual(spawn.call_count, 1)
            self.assertEqual(spawn.call_args.args[0][0], sys.executable)
            core.request_stop(rid)
            with core.db() as db:
                self.assertEqual(db.execute('SELECT stop FROM runs WHERE id=?', (rid,)).fetchone()[0], 1)

    def test_sequential_worker_receives_records_and_stops(self):
        from cctv.usage import USAGE_FIELDS
        self.assertEqual(core.COLS, USAGE_FIELDS)
        self.assertEqual(len(USAGE_FIELDS), 13)
        for stopping in (False, True):
            with self.subTest(stopping=stopping), tempfile.TemporaryDirectory() as folder:
                data = Path(folder) / 'dashboard/data'
                cfg = copy.deepcopy(core.DEFAULTS)
                cfg.update(model='n.pt', end=5.)
                calls = []
                jobs = []
                class Service:
                    def __enter__(self): return self
                    def __exit__(self, *args): pass
                    def start(self, **kw):
                        calls.append(kw)
                        room = kw['restroom_id']
                        rec = dict(record_id=room, interval_end_s=1., csv_row=dict.fromkeys(USAGE_FIELDS, '0'))
                        def read(*args, **kwargs):
                            if stopping: core.request_stop('run')
                            return SimpleNamespace(records=[rec], next_cursor=1, done=True, incomplete_tail=False)
                        job = Mock(read_records=read, status=lambda:dict(status='stopped' if stopping else 'completed', worker_alive=False))
                        jobs.append(job)
                        return job
                with patch.object(core, 'DATA', data), patch.object(worker, 'DATA', data), \
                     patch.object(worker, 'runtime_info'), patch('cctv.AnalysisService', Service):
                    with core.db() as db:
                        db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',
                            ('run', 0, 'preparing', 0, 0, json.dumps(cfg), '', 0))
                    worker.run('run')
                    with core.db() as db:
                        self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0], 1 if stopping else 3)
                        self.assertEqual(db.execute('SELECT status FROM runs').fetchone()[0], 'stopped' if stopping else 'completed')
                self.assertEqual([c['restroom_id'] for c in calls], ['north'] if stopping else list(core.ROOMS))
                if stopping: jobs[0].stop.assert_called_once_with(wait=False)


if __name__ == '__main__':
    unittest.main()
