import itertools
import math
import unittest
from cctv.config import template, validate
from cctv.core import Counter, Observation, SecondSampler
from cctv.evaluate import match_events, sample_mae


def config(initial=None):
    c = template("test", "synthetic.mp4")
    c.update(configured=True, reference_size=[1000, 1000], initial_inside=initial,
             boundary=[[0.5, 0.2], [0.5, 0.8]], entry_direction=[[0.3, 0.5], [0.7, 0.5]],
             outside_zone=[[0.05, 0.05], [0.45, 0.05], [0.45, 0.95], [0.05, 0.95]],
             inside_zone=[[0.55, 0.05], [0.95, 0.05], [0.95, 0.95], [0.55, 0.95]],
             waiting_zone=[[0.1, 0.2], [0.45, 0.2], [0.45, 0.8], [0.1, 0.8]])
    return c


def obs(x, y=500, tid=1):
    return Observation(tid, (x - 40, y - 200, x + 40, y), 0.8)


class Rules(unittest.TestCase):
    def setUp(self):
        self.counter = Counter(config(), 1000, 1000)
        self.t = -0.1
        self.frame = -1

    def step(self, x=None, y=500, tid=1, delta=0.1):
        self.t = round(self.t + delta, 8)
        self.frame += 1
        return self.counter.update(self.t, self.frame, [] if x is None else [obs(x, y, tid)])[0]

    def hold(self, x, n=5, y=500):
        for _ in range(n):
            result = self.step(x, y)
        return result

    def move(self, xs, y=500):
        for x in xs:
            result = self.step(x, y)
        return result

    def test_boundary_jitter_and_return_no_count(self):
        self.hold(400)
        self.move([480, 501, 499, 503, 498, 510, 495, 450, 400])
        self.hold(400)
        self.assertEqual(self.counter.enter, 0)
        self.assertEqual(self.counter.exit, 0)

    def test_entry_exit_reentry(self):
        self.hold(400)
        self.move([470, 490, 510, 530, 600])
        self.hold(600)
        self.assertEqual(self.counter.enter, 1)
        self.hold(600)
        self.assertEqual(self.counter.enter, 1)
        self.move([530, 510, 490, 470, 400])
        self.hold(400)
        self.move([470, 490, 510, 530, 600])
        self.hold(600)
        self.assertEqual((self.counter.enter, self.counter.exit), (2, 1))

    def test_finite_segment_only(self):
        self.hold(400, y=900)
        self.move([490, 510, 600], y=900)
        self.hold(600, y=900)
        self.assertEqual(self.counter.enter, 0)

    def test_gap_does_not_interpolate_crossing(self):
        self.hold(400)
        self.step(None, delta=0.5)
        self.hold(600)
        self.assertEqual(self.counter.enter, 0)
        self.assertGreater(self.counter.anomalies["observation_gap_resets"], 0)

    def test_first_inside_and_disappearance_do_not_count(self):
        self.hold(600)
        for _ in range(20):
            self.step()
        self.assertEqual(self.counter.enter, 0)

    def test_short_missing_frame_invalidates_crossing_order(self):
        self.hold(400)
        self.step(None)
        self.hold(600)
        self.assertEqual(self.counter.enter, 0)
        self.assertGreater(self.counter.anomalies["observation_gap_resets"], 0)

    def test_short_gap_invalidates_pending_crossing(self):
        self.hold(400)
        self.move([490, 510])
        self.assertIsNotNone(self.counter.tracks[1].pending)
        self.step(None)
        self.hold(600)
        self.assertEqual(self.counter.enter, 0)

    def test_short_gap_resets_candidate_slow_evidence(self):
        self.hold(250, 8)
        self.assertGreater(self.counter.tracks[1].slow_elapsed, 0)
        self.step(None)
        self.step(250)
        self.assertEqual(self.counter.tracks[1].slow_elapsed, 0)

    def test_confirmed_wait_sticky_during_advance(self):
        self.assertEqual(self.hold(250, 40)["waiting_observed"], 1)
        self.move([270, 300, 340, 380, 420])
        self.assertEqual(self.counter.tracks[1].wait, "confirmed")
        self.assertEqual(self.hold(480, 10)["waiting_observed"], 0)

    def test_candidate_does_not_confirm_during_occlusion(self):
        self.hold(250, 8)
        self.step(None, delta=1.0)
        self.step(250)
        self.assertEqual(self.counter.tracks[1].wait, "candidate")
        self.assertLess(self.counter.tracks[1].slow_elapsed, 1)

    def test_even_short_missing_time_is_not_waiting_evidence(self):
        self.counter.r["waiting_confirm_s"] = 0.2
        self.counter.r["motion_min_span_s"] = 0.1
        self.hold(250, 2)
        self.step(None)
        result = self.step(250)
        self.assertEqual(result["waiting_observed"], 0)
        self.assertEqual(result["waiting_confirmed_observed"], 0)
        self.assertEqual(self.counter.tracks[1].wait, "candidate")

    def test_grace_expiry_and_short_reobservation(self):
        self.hold(250, 40)
        result = self.step(None, delta=0.5)
        self.assertEqual((result["waiting_observed"], result["waiting_grace"]), (0, 1))
        self.assertEqual(self.step(250)["waiting_observed"], 1)
        self.assertEqual(self.step(None, delta=1.6)["waiting_total"], 0)
        result = self.step(250)
        self.assertEqual(result["waiting_observed"], 0)
        self.assertEqual(result["waiting_confirmed_observed"], 0)

    def test_duplicate_grace_suppressed_without_identity_merge(self):
        self.hold(250, 40)
        result = self.step(255, tid=2)
        self.assertEqual(result["waiting_grace"], 0)
        self.assertEqual(result["grace_suppressed"], 1)
        self.assertIn("uncertain", result["measurement_status"])
        self.assertEqual(set(self.counter.tracks), {1, 2})

    def test_unset_zero_and_negative_inside(self):
        self.assertIsNone(self.hold(600)["inside_estimate"])
        self.counter = Counter(config(0), 1000, 1000)
        self.assertEqual(self.hold(600)["inside_estimate"], 0)
        self.move([530, 490, 400])
        result = self.hold(400)
        self.assertEqual(result["inside_estimate"], -1)
        self.assertIn("negative_inside", result["measurement_status"])

    def test_fast_transit_not_waiting(self):
        self.move([150 + 10 * i for i in range(30)])
        self.assertEqual(self.counter.tracks[1].wait, "candidate")
        self.assertEqual(self.counter.tracks[1].slow_elapsed, 0)

    def test_sampler_never_uses_future(self):
        sampler = SecondSampler(0)
        rows = []
        for t in (0, 0.7, 1.05, 1.8, 2.03):
            rows.extend(sampler.push({"source_time_s": t, "entries": round(t * 10)}))
        self.assertEqual([r["sample_time_s"] for r in rows], [0, 1, 2])
        self.assertEqual([r["source_time_s"] for r in rows], [0, 0.7, 1.8])
        self.assertTrue(all(r["source_time_s"] <= r["sample_time_s"] for r in rows))


class ValidationAndEvaluation(unittest.TestCase):
    def test_configuration_guard_and_geometry(self):
        validate(config())
        c = config()
        c["configured"] = False
        with self.assertRaises(ValueError):
            validate(c)
        c = config()
        c["waiting_zone"] = [[0.1, 0.1], [0.4, 0.4], [0.1, 0.4], [0.4, 0.1]]
        with self.assertRaises(ValueError):
            validate(c)
        with self.assertRaises(ValueError):
            validate(config(), video_size=(1920, 1080))
        c = config()
        c["confidence"] = 0.5
        with self.assertRaises(ValueError):
            validate(c)
        c = config()
        c["entry_direction"] = [[0.3, 0.9], [0.7, 0.9]]
        with self.assertRaises(ValueError):
            validate(c)

    def test_maximum_one_to_one_matching(self):
        gt = [{"video_time_s": t, "direction": "entry"} for t in (1.0, 2.0)]
        pr = [{"video_time_s": t, "direction": "entry"} for t in (0.1, 1.1, 1.2)]
        result = match_events(gt, pr)["entry"]
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (2, 1, 0))
        self.assertEqual(len({m["prediction_confirmation_time_s"] for m in result["matches"]}), 2)
        self.assertIsNone(match_events([], [])["entry"]["f1"])

    def test_matching_cardinality_against_exhaustive_search(self):
        def maximum(gt, pr):
            if not gt:
                return 0
            return max([maximum(gt[1:], pr)] +
                       [1 + maximum(gt[1:], pr[:i] + pr[i + 1:])
                        for i, p in enumerate(pr) if abs(gt[0] - p) <= 1])
        subsets = [list(c) for n in range(4) for c in itertools.combinations([0, 0.7, 1.4, 2.1], n)]
        for gt in subsets:
            for pr in subsets:
                make = lambda ns: [{"video_time_s": n, "direction": "entry"} for n in ns]
                self.assertEqual(match_events(make(gt), make(pr))["entry"]["tp"], maximum(gt, pr))

    def test_missing_truth_not_zero_and_missing_prediction_reported(self):
        truths = [{"video_time_s": 1, "waiting_count": 2}, {"video_time_s": 3, "waiting_count": 5}]
        predictions = [{"sample_time_s": 1, "waiting_total": 3}, {"sample_time_s": 2, "waiting_total": 20}]
        result = sample_mae(truths, predictions, "waiting_count", "waiting_total")
        self.assertEqual((result["mae"], result["matched_samples"], result["missing_prediction_samples"]), (1, 1, 1))
        self.assertEqual(result["unannotated_prediction_samples"], 1)


if __name__ == "__main__":
    unittest.main()
