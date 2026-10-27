import copy
import unittest
from cctv.config import load, preset_path
from cctv.core import Counter, Observation
from cctv.geometry import in_polygon


class EastExtinguisherExclusion(unittest.TestCase):
    def setUp(self):
        self.c = load(preset_path('east'))
        self.poly = self.c['excluded_zones'][-1]
        self.false_box = (690, 447, 740, 535)
        # Actual nearby ID 2 box: overlaps extinguisher but feet are outside mask.
        self.person_box = (713.2191, 334.1667, 801.0899, 624.8911)

    def test_mask_uses_bottom_center_not_box_overlap(self):
        counter = Counter(self.c, 1920, 1080)
        for i in range(121):
            state, _, logs = counter.update(i / 30, i,
                [Observation(1, self.false_box), Observation(2, self.person_box)])
            self.assertEqual(counter.tracks[1].wait, 'nonwaiting')
            self.assertEqual(state['waiting_total'], int(i >= 105))
            self.assertEqual([r['kind'] for r in logs if r.get('track_id') == 1 and 'box' in r],
                             ['excluded_observation'])
        self.assertEqual(counter.tracks[2].wait, 'confirmed')
        state, _, _ = counter.update(4.1, 123, [])
        self.assertEqual(state['waiting_grace'], 1)  # Only the person has grace.

    def test_excluded_confirmed_track_is_cleared_without_lingering_grace(self):
        prior = copy.deepcopy(self.c)
        prior['excluded_zones'] = prior['excluded_zones'][:-1]
        counter = Counter(prior, 1920, 1080)
        for i in range(106):
            counter.update(i / 30, i, [Observation(1, self.false_box)])
        self.assertEqual(counter.tracks[1].wait, 'confirmed')
        counter.c['excluded_zones'] = self.c['excluded_zones']
        state, _, _ = counter.update(3.6, 108, [Observation(1, self.false_box)])
        self.assertEqual(state['waiting_total'], 0)
        state, _, _ = counter.update(3.7, 111, [])
        self.assertEqual(state['waiting_grace'], 0)

    def test_extinguisher_jitter_points_are_covered(self):
        for x, y in [(688.8856, 545.7351), (724.127, 524.458), (692, 537.697), (708.571, 536.992)]:
            self.assertTrue(in_polygon((x / 1920, y / 1080), self.poly))


if __name__ == '__main__':
    unittest.main()
