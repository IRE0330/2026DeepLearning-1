import csv
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from cctv.core import Counter
from cctv.config import validate, save
from cctv.usage import bind_video, usage_row, write_usage, queue_estimates
from test_core import config, obs


class CandidatePolicy(unittest.TestCase):
    def warm(self, grace_track=False):
        c = config(28)
        c.update(available_stalls=27, average_stall_use_s=105)
        counter = Counter(c, 1000, 1000)
        confirmed = [obs(150, tid=3), obs(250, tid=4), obs(350, tid=5)]
        if grace_track:
            confirmed += [obs(400, 250, tid=6)]
        for i in range(36):
            counter.update(i / 10, i, confirmed)
        return c, counter, confirmed[:3]

    def test_two_candidates_three_confirmed_equal_five(self):
        c, counter, confirmed = self.warm()
        result, _, _ = counter.update(3.6, 36, confirmed + [obs(180, 700, 1), obs(400, 700, 2)])
        self.assertEqual((result['waiting_candidate_observed'], result['waiting_confirmed_observed']), (2, 3))
        self.assertEqual((result['waiting_observed'], result['waiting_total']), (5, 5))

    def test_confirmed_grace_adds_six_and_candidates_reach_q_and_seconds(self):
        c, counter, confirmed = self.warm(grace_track=True)
        result, _, _ = counter.update(3.6, 36, confirmed + [obs(180, 700, 1), obs(400, 700, 2)])
        self.assertEqual((result['waiting_observed'], result['waiting_grace'], result['waiting_total']), (5, 1, 6))
        self.assertEqual((result['internal_waiting_estimate'], result['total_queue_estimate']), (1, 7))
        self.assertAlmostEqual(result['expected_wait_s'], 8 * 105 / 27)
        row = usage_row(c, result, 0, 3.6)
        self.assertEqual(row['현재대기인원_추정'], 7)
        self.assertEqual(row['외부대기인원_추정'], 6)
        self.assertEqual(row['전체대기인원_추정'], 7)
        self.assertNotIn('예상대기시간_초', row)

    def test_candidate_to_confirmed_does_not_double_count(self):
        counter = Counter(config(), 1000, 1000)
        seen_states = set()
        for i in range(40):
            result, _, _ = counter.update(i / 10, i, [obs(250)])
            seen_states.add(counter.tracks[1].wait)
            self.assertEqual(result['waiting_total'], 1)
            self.assertEqual(result['waiting_candidate_observed'] + result['waiting_confirmed_observed'], 1)
        self.assertEqual(seen_states, {'candidate', 'confirmed'})

    def test_candidate_missing_has_no_grace(self):
        counter = Counter(config(), 1000, 1000)
        counter.update(0, 0, [obs(250)])
        result, _, _ = counter.update(.1, 1, [])
        self.assertEqual((result['waiting_observed'], result['waiting_grace'], result['waiting_total']), (0, 0, 0))

    def test_observed_candidate_suppresses_nearby_confirmed_grace(self):
        c, counter, confirmed = self.warm(grace_track=True)
        result, _, _ = counter.update(3.6, 36, confirmed + [obs(400, 250, 1)])
        self.assertEqual((result['waiting_candidate_observed'], result['waiting_confirmed_observed']), (1, 3))
        self.assertEqual((result['waiting_total'], result['waiting_grace'], result['grace_suppressed']), (4, 0, 1))
        self.assertIn(6, counter.tracks)
        self.assertIn(1, counter.tracks)

    def test_entry_confirmation_excludes_id_on_same_frame(self):
        c = config()
        # Overlap intentionally ensures entry takes precedence over waiting.
        c['waiting_zone'] = [[.1, .2], [.9, .2], [.9, .8], [.1, .8]]
        counter = Counter(c, 1000, 1000)
        xs = [400] * 5 + [470, 490, 510, 530] + [600] * 5
        found = False
        for i, x in enumerate(xs):
            result, events, _ = counter.update(i / 10, i, [obs(x)])
            if events:
                self.assertEqual(events[0]['direction'], 'entry')
                self.assertEqual(result['waiting_total'], 0)
                self.assertEqual(counter.tracks[1].wait, 'nonwaiting')
                found = True
                break
        self.assertTrue(found)


class UsageSummary(unittest.TestCase):
    def cfg(self):
        c = config(30)
        c.update(video_id='source_001', available_stalls=27, average_stall_use_s=105)
        return c

    def final(self, inside=30, external=5):
        return {'inside_estimate': inside, 'waiting_total': external,
                'entries': 4, 'exits': 1, 'measurement_status': 'measuring;candidate_included'}

    def test_exact_thirteen_headers_bom_and_one_interval_row(self):
        expected = ['촬영시작시각', '촬영종료시각', '화장실ID', '화장실_영상ID', '구간_입장인원',
                    '구간_퇴장인원', '내부잔류인원_추정', '현재대기인원_추정', '측정상태',
                    '추정내부대기인원', '전체대기인원_추정', '현재이용가능칸수_추정', '외부대기인원_추정']
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'usage_summary.csv'
            write_usage(p, usage_row(self.cfg(), self.final(), 6, 9.958333333))
            self.assertTrue(p.read_bytes().startswith(b'\xef\xbb\xbf'))
            with p.open(encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, expected)
                rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['현재대기인원_추정'], '8')
            self.assertEqual(rows[0]['전체대기인원_추정'], '8')
            self.assertEqual(rows[0]['외부대기인원_추정'], '5')
            self.assertEqual(rows[0]['구간_입장인원'], '4')
            self.assertEqual(rows[0]['촬영시작시각'], '')
            self.assertNotIn('정상', rows[0]['측정상태'])

    def test_capture_base_uses_actual_interval_offsets_and_virtual_label(self):
        c = self.cfg()
        c.update(capture_start_time='2026-01-02T09:00:00+09:00', capture_time_kind='virtual')
        row = usage_row(c, self.final(), 6.125, 9.958333333)
        base = datetime.fromisoformat(c['capture_start_time'])
        self.assertEqual(datetime.fromisoformat(row['촬영시작시각']), base + timedelta(seconds=6.125))
        self.assertEqual(datetime.fromisoformat(row['촬영종료시각']), base + timedelta(seconds=9.958333333))
        self.assertIn('virtual_scenario_time', row['측정상태'])

    def test_unknown_initial_blank_and_negative_inside_raw_preserved(self):
        c = self.cfg()
        c['initial_inside'] = None
        row = usage_row(c, self.final(None), 0, 1)
        for key in ('내부잔류인원_추정', '추정내부대기인원', '전체대기인원_추정', '현재대기인원_추정', '현재이용가능칸수_추정'):
            self.assertIsNone(row[key])
        self.assertEqual(row['외부대기인원_추정'], 5)
        self.assertIn('initial_inside_unset', row['측정상태'])
        row = usage_row(self.cfg(), self.final(-2), 0, 1)
        self.assertEqual(row['내부잔류인원_추정'], -2)
        self.assertIn('negative_inside', row['측정상태'])
        self.assertTrue(all(row[k] is None for k in ('추정내부대기인원', '전체대기인원_추정', '현재대기인원_추정', '현재이용가능칸수_추정')))

    def test_no_internal_wait_when_inside_under_capacity_keeps_plus_one(self):
        row = usage_row(self.cfg(), self.final(2, 0), 0, 1)
        self.assertEqual((row['추정내부대기인원'], row['전체대기인원_추정']), (0, 0))
        self.assertEqual(row['현재이용가능칸수_추정'], 25)
        self.assertAlmostEqual(queue_estimates(self.cfg(), 2, 0)['expected_wait_s'], 105 / 27)

    def test_time_reversal_bad_capture_and_overflow_are_rejected(self):
        with self.assertRaises(ValueError):
            usage_row(self.cfg(), self.final(), 10, 9)
        c = self.cfg()
        c.update(capture_start_time='2026-01-02T09:00:00', capture_time_kind='real')
        with self.assertRaises(ValueError):
            validate(c)
        c.update(capture_start_time='2026-01-02T09:00:00+09:00', capture_time_kind=None)
        with self.assertRaises(ValueError):
            validate(c)
        c.update(capture_start_time='9999-12-31T23:59:59+09:00', capture_time_kind='virtual')
        with self.assertRaises(ValueError):
            usage_row(c, self.final(), 0, 10)

    def test_invalid_capacity_and_missing_assumptions(self):
        c = self.cfg()
        c['available_stalls'] = 0
        validate(c)
        row = usage_row(c, self.final(), 0, 1)
        self.assertEqual(row['현재이용가능칸수_추정'], 0)
        self.assertIsNone(queue_estimates(c, 30, 5)['expected_wait_s'])
        self.assertIn('no_operating_stalls', row['측정상태'])
        c['available_stalls'] = -1
        with self.assertRaises(ValueError):
            validate(c)
        c['available_stalls'] = None
        row = usage_row(c, self.final(), 0, 1)
        self.assertIsNone(row['현재대기인원_추정'])
        self.assertIn('available_stalls_unset', row['측정상태'])

    def test_video_id_stable_and_new_content_requires_different_id(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'source.bin'
            p.write_bytes(b'first source')
            c = self.cfg()
            c['video'] = str(p)
            bind_video(c)
            first_id = c['video_id']
            bind_video(c)
            self.assertEqual(c['video_id'], first_id)
            p.write_bytes(b'replacement source')
            with self.assertRaises(ValueError):
                bind_video(c, first_id)
            bind_video(c)
            self.assertNotEqual(c['video_id'], first_id)
            replaced_id = c['video_id']
            bind_video(c)
            self.assertEqual(c['video_id'], replaced_id)

    def test_unbound_video_identity_rejected_before_analysis(self):
        from cctv.pipeline import analyze
        with tempfile.TemporaryDirectory() as folder:
            c = self.cfg()
            path = Path(folder) / 'config.json'
            save(c, path)
            with self.assertRaisesRegex(ValueError, '영상 ID 등록'):
                analyze(path)

    def test_baseline_does_not_export_fake_zero_counts(self):
        row = usage_row(self.cfg(), {'measurement_status': 'baseline_zones_unconfirmed'}, 0, 1, 'baseline')
        self.assertTrue(all(row[k] is None for k in ('구간_입장인원', '구간_퇴장인원', '현재대기인원_추정', '외부대기인원_추정')))
        self.assertIn('baseline_no_counts', row['측정상태'])
