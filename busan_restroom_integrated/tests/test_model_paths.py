"""Portable model selection before CLI/API run overrides."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cctv.config import load, preset_path


class ModelPaths(unittest.TestCase):
    def test_unset_bundle_keeps_explicit_marker(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load(preset_path('east'))['model'], '${CCTV_MODEL_PATH}')

    def test_environment_path_is_relative_to_callers_directory(self):
        with patch.dict(os.environ, {'CCTV_MODEL_PATH': 'my-weights/person.pt'}):
            self.assertEqual(load(preset_path('north'))['model'],
                             str(Path('my-weights/person.pt').resolve()))

    def test_explicit_config_path_retains_config_directory_semantics(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'settings.json'
            config.write_text(json.dumps(dict(model='weights/person.pt', video='clip.mp4', output_dir='runs')))
            with patch.dict(os.environ, {'CCTV_MODEL_PATH': 'other.pt'}):
                self.assertEqual(load(config)['model'], str(Path(folder) / 'weights/person.pt'))
