"""Presentation boundaries and missing-value semantics; no detection accuracy claims."""
import copy
import unittest
import numpy as np
from cctv.panel import draw_panel, geometry, panel_text, font_paths


class CompactPanel(unittest.TestCase):
    def state(self):
        return dict(source_time_s=94.2, entries=2, exits=2, inside_estimate=None,
                    waiting_total=3, internal_waiting_estimate=None,
                    total_queue_estimate=None, available_stalls_estimate=None,
                    expected_wait_s=None, measurement_status='initial_inside_unset')

    def test_missing_values_are_dashes_and_source_state_untouched(self):
        state = self.state()
        before = copy.deepcopy(state)
        title, rows, note = panel_text({'restroom_id': 'south', 'profile_name': 'demo'}, state)
        text = title + str(rows) + note
        self.assertEqual(text.count('—'), 5)
        self.assertFalse(any(word in text for word in ('None', 'null', 'unknown', 'candidate', 'suppressed', 'Net=')))
        self.assertEqual(state, before)
        self.assertIn('01:34', title)
        if font_paths()[2] == 'ko':
            self.assertIn('초기 인원 미설정', note)
            self.assertIn('외부 대기 3명', str(rows))

    def test_resolution_relative_panel_and_no_pixels_outside_rectangle(self):
        for w, h in [(1280, 720), (1920, 1080)]:
            for room in ('north', 'south', 'east'):
                cfg = {'restroom_id': room, 'profile_name': 'demo'}
                state = self.state()
                original = copy.deepcopy(state)
                frame = np.full((h, w, 3), 180, dtype=np.uint8)
                g = geometry(w, h, cfg)
                rendered = draw_panel(frame.copy(), cfg, state)
                self.assertEqual(rendered.shape, frame.shape)
                self.assertLessEqual(g['width'] / w, .36)
                self.assertLessEqual(g['height'] / h, .23)
                x, y, pw, ph = (g[k] for k in ('x', 'y', 'width', 'height'))
                outside = rendered.copy()
                outside[y:y + ph, x:x + pw] = 180
                self.assertTrue(np.array_equal(outside, frame))
                self.assertEqual(state, original)
                cfg['overlay'] = {'position': 'top_right'}
                changed = geometry(w, h, cfg)
                self.assertEqual(changed['y'], round(w * .01))

    def test_negative_inside_stays_visible_with_short_status(self):
        state = self.state()
        state.update(inside_estimate=-2, measurement_status='negative_inside')
        _, rows, note = panel_text({'restroom_id': 'north'}, state)
        self.assertIn('-2', str(rows))
        self.assertEqual(str(rows).count('—'), 4)
        if font_paths()[2] == 'ko':
            self.assertIn('내부 음수', note)


if __name__ == '__main__':
    unittest.main()
