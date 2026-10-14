import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from cctv.micc import numeric_files, directory_details
from cctv.sequence import review_sequence
from test_pipeline import FakeDetector


class SequenceReview(unittest.TestCase):
    def test_numeric_order_and_metadata_exclusion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('10.png', '2.png', '1.png', '._1.png'):
                (root / name).touch()
            self.assertEqual([p.name for p in numeric_files(root, '.png')], ['1.png', '2.png', '10.png'])
            with self.assertRaises(ValueError):
                review_sequence(root, 1, 3)

    def test_frame_only_export_and_directory_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for part in ('RGB', 'depth', 'GT_dat'):
                (root / 'Flow' / part).mkdir(parents=True)
            for i in range(3):
                cv2.imwrite(str(root / 'Flow' / 'RGB' / f'{i}.png'), np.zeros((200, 200, 3), dtype=np.uint8))
                cv2.imwrite(str(root / 'Flow' / 'depth' / f'{i}.png'), np.zeros((200, 200), dtype=np.uint16))
                (root / 'Flow' / 'GT_dat' / f'{i}.dat').write_text('10 20 30 30\n', encoding='utf-8')
            (root / 'readme.txt').write_text('Head locations: x y w h', encoding='utf-8')
            detail = directory_details(root)
            self.assertEqual(detail['sequences']['Flow']['ground_truth']['row_column_counts'], {4: 3})
            self.assertIsNone(detail['original_fps'])
            with patch('cctv.sequence.Detector', FakeDetector), \
                 patch('cctv.sequence.unique_dir', return_value=root / 'result'):
                (root / 'result').mkdir()
                out = review_sequence(root / 'Flow' / 'RGB', count=3)
            report = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(report['processed_frames'], 3)
            self.assertTrue(report['output_video']['all_frames_decoded'])
            self.assertFalse(report['behavior_rules_applied'])
            self.assertIsNone(report['source_fps'])
            self.assertFalse(report['visual_review_completed'])
            logs = [json.loads(row) for row in (out / 'diagnostics.jsonl').read_text().splitlines()]
            self.assertEqual([r['source_frame_number'] for r in logs], [0, 1, 2])
            self.assertTrue(all('video_time_s' not in r for r in logs))
