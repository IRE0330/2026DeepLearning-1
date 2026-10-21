"""Video-time waiting policy regressions, independent of detector/model."""
import unittest
from cctv.core import Counter
from test_core import config, obs


class WaitingPolicy(unittest.TestCase):
    def run_path(self, points, scale=1):
        counter = Counter(config(), 1000 * scale, 1000 * scale)
        states = []
        for i, x in enumerate(points):
            observations = [] if x is None else [obs(x * scale, 500 * scale)]
            if observations and scale != 1:
                o = observations[0]
                o.box = (x * scale - 40 * scale, 300 * scale,
                         x * scale + 40 * scale, 500 * scale)
            states.append(counter.update(i / 10, i, observations)[0])
        return counter, states

    def test_entry_candidate_short_stop_then_leave(self):
        counter, states = self.run_path([250] * 10 + [480] * 10)
        self.assertEqual(states[0]['waiting_candidate_observed'], 1)
        self.assertTrue(all(s['waiting_total'] == 0 for s in states))

    def test_three_point_five_seconds_stationary_and_slow_are_confirmed(self):
        for points in ([250] * 36, [250 + i * 2 for i in range(36)]):
            counter, states = self.run_path(points)
            self.assertEqual(states[34]['waiting_total'], 0)
            self.assertEqual(states[35]['waiting_confirmed_observed'], 1)

    def test_fast_path_and_single_low_speed_frame_do_not_confirm(self):
        points = [150 if i % 2 else 400 for i in range(45)] + [150, 150]
        counter, states = self.run_path(points)
        self.assertTrue(all(s['waiting_total'] == 0 for s in states))

    def test_advance_and_exit(self):
        counter, states = self.run_path([250] * 36 + [280, 310, 350, 420] + [480] * 10)
        self.assertTrue(all(s['waiting_total'] == 1 for s in states[35:40]))
        self.assertEqual(states[-1]['waiting_total'], 0)

    def test_candidate_gap_does_not_supply_evidence(self):
        counter, states = self.run_path([250] * 8 + [None] * 10 + [250] * 8)
        self.assertTrue(all(s['waiting_total'] == 0 for s in states))

    def test_grace_boundary_reobservation_and_expiry(self):
        counter, states = self.run_path([250] * 36 + [None] * 15 + [250])
        self.assertEqual(states[50]['waiting_grace'], 1)
        self.assertEqual(states[51]['waiting_observed'], 0)  # 1.6s since last observation
        counter, states = self.run_path([250] * 36 + [None] * 5 + [250])
        self.assertEqual((states[-1]['waiting_total'], states[-1]['waiting_grace']), (1, 0))
        counter, states = self.run_path([250] * 36 + [None] * 16)
        self.assertEqual(states[-1]['waiting_total'], 0)

    def test_normalized_motion_is_scale_invariant(self):
        points = [250 + i * 2 for i in range(36)]
        self.assertEqual([s['waiting_total'] for s in self.run_path(points)[1]],
                         [s['waiting_total'] for s in self.run_path(points, 2)[1]])

    def test_unobserved_gap_without_missing_frame_does_not_confirm(self):
        counter = Counter(config(), 1000, 1000)
        counter.update(0, 0, [obs(250)])
        state, _, _ = counter.update(10, 1, [obs(250)])
        self.assertEqual(state['waiting_total'], 0)

    def test_real_wait_like_periodic_movement_can_prevent_confirmation(self):
        # A waiter moving once per 3s cannot accumulate 3.5 continuous slow seconds.
        points = [250 + (20 if (i // 30) % 2 else 0) for i in range(100)]
        _, states = self.run_path(points)
        self.assertTrue(all(s['waiting_total'] == 0 for s in states))

    def test_three_presets_keep_confirmation_record_and_grace_independent(self):
        from cctv.config import load, preset_path
        from cctv.profiles import apply_profile, load_profile
        for room in ('north', 'south', 'east'):
            c = load(preset_path(room))
            self.assertEqual(c['rules']['waiting_confirm_s'], 3.5)
            self.assertEqual(c['rules']['occlusion_grace_s'], 1.5)
            self.assertEqual(apply_profile(c, load_profile('demo'))['record_interval_s'], 1)
            self.assertEqual(apply_profile(c, load_profile('operating'))['record_interval_s'], 10)


if __name__ == '__main__':
    unittest.main()
