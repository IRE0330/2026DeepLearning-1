import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cctv.batch import run_batch
from cctv.config import clone, save
from cctv.core import Counter
from cctv.intervals import DailyCSVWriter, TenSecondSampler
from cctv.profiles import apply_profile, load_profile
from cctv.usage import USAGE_FIELDS, usage_row, queue_estimates
from test_core import config


def settings(room="north", initial=29):
    c = config(initial)
    c.update(restroom_id=room, video_id=room + "_source", available_stalls=27,
             average_stall_use_s=105, capture_start_time="2026-10-14T00:00:00+09:00",
             capture_time_kind="virtual")
    return c


def state(t, entries=0, exits=0, external=0, initial=29):
    return {"source_time_s": t, "frame_index": round(t * 24), "entries": entries,
            "exits": exits, "inside_estimate": initial + entries - exits,
            "waiting_total": external, "measurement_status": "measuring"}


def event(t, direction):
    return {"video_time_s": t, "direction": direction}


class PeriodicRecords(unittest.TestCase):
    def test_boundaries_once_and_cumulative_inside_not_interval_counts(self):
        rows = []
        sampler = TenSecondSampler(settings(), 0, lambda r, d: rows.append((r, d)))
        sampler.push(state(0, 1), [event(0, "entry")])
        sampler.push(state(9.95, 1, external=3), [])
        sampler.push(state(10, 2, external=4), [event(10, "entry")])
        sampler.push(state(10.05, 2, 1, 5), [event(10.05, "exit")])
        sampler.push(state(20, 3, 1, 6), [event(20, "entry")])
        sampler.push(state(25, 3, 2, 0), [event(25, "exit")])
        remainder = sampler.finish(25.1)
        self.assertEqual([(r['구간_입장인원'], r['구간_퇴장인원']) for r, _ in rows], [(2, 0), (1, 1)])
        self.assertEqual([r['내부잔류인원_추정'] for r, _ in rows], [31, 31])
        self.assertEqual([r['현재대기인원_추정'] for r, _ in rows], [8, 10])
        self.assertTrue(all(r['현재대기인원_추정'] == r['전체대기인원_추정'] for r, _ in rows))
        self.assertEqual(remainder['exits'], 1)
        self.assertAlmostEqual(remainder['duration_s'], 5.1)
        self.assertEqual(remainder['last_state']['waiting_total'], 0)

    def test_latest_past_frame_never_future_and_end_exclusive_coverage(self):
        rows = []
        sampler = TenSecondSampler(settings(), 0, lambda r, d: rows.append((r, d)))
        sampler.push(state(0), [])
        sampler.push(state(9.958333, external=2), [])
        sampler.push(state(10.041666, 1, external=99), [event(10.041666, "entry")])
        self.assertEqual(rows[0][0]['외부대기인원_추정'], 2)
        self.assertEqual(rows[0][0]['구간_입장인원'], 0)
        self.assertLess(rows[0][1]['source_time_s'], rows[0][1]['interval_end_s'])
        self.assertEqual(sampler.finish(10.083333)['entries'], 1)
        rows.clear()
        sampler = TenSecondSampler(settings(), 0, lambda r, d: rows.append((r, d)))
        sampler.push(state(0), [])
        sampler.push(state(9.958333, external=7), [])
        sampler.finish(10)  # Exactly 10s of CFR frames, last frame is 9.9583.
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0]['외부대기인원_추정'], 7)

    def test_partial_analysis_origin_short_remainder_and_time_reversal(self):
        rows = []
        sampler = TenSecondSampler(settings(), 6.125, lambda r, d: rows.append((r, d)))
        sampler.push(state(6.125), [])
        sampler.push(state(15.9, external=1), [])
        self.assertEqual(rows, [])
        sampler.push(state(16.2, external=90), [])
        self.assertEqual(rows[0][1]['interval_end_s'], 16.125)
        self.assertEqual(rows[0][0]['외부대기인원_추정'], 1)
        sampler.push(state(24, external=3), [])
        remainder = sampler.finish(24.1)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(remainder['duration_s'], 7.975)
        with self.assertRaises(ValueError):
            sampler.push(state(23), [])
        with self.assertRaises(ValueError):
            sampler.finish(20)
        empty = TenSecondSampler(settings(), 0, lambda r, d: None)
        with self.assertRaises(ValueError):
            empty.push(state(11), [])

    def test_midnight_room_files_sort_bom_immediate_flush_and_missing_date(self):
        with tempfile.TemporaryDirectory() as folder:
            writer = DailyCSVWriter(folder)
            c = settings()
            c['capture_start_time'] = '2026-10-13T14:59:40+00:00'  # 23:59:40 KST.
            row = usage_row(c, state(30), 20, 30)
            path = writer.add(row)
            self.assertEqual(path.name, 'north_2026-10-14.csv')
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            c['video_id'] = 'b'
            writer.add(usage_row(c, state(20), 10, 20))  # midnight belongs to next day
            c['video_id'] = 'a'
            writer.add(usage_row(c, state(20), 10, 20))
            earlier = writer.add(usage_row(c, state(10), 0, 10))
            self.assertEqual(earlier.name, 'north_2026-10-13.csv')
            with path.open(encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, USAGE_FIELDS)
                rows = list(reader)
            self.assertEqual([r['화장실_영상ID'] for r in rows], ['a', 'b', 'north_source'])
            c.update(restroom_id='south', capture_start_time=None, capture_time_kind=None)
            missing = writer.add(usage_row(c, state(10), 0, 10))
            self.assertEqual(missing.name, 'south_날짜미설정.csv')
            self.assertIn('capture_time_unset', missing.read_text(encoding='utf-8-sig'))
            self.assertEqual(len(writer.manifest()), 3)

    def test_zero_capacity_unknown_negative_and_free_stalls_not_denominator(self):
        c = settings()
        result = queue_estimates(c, 29, 6)
        self.assertEqual((result['internal_waiting_estimate'], result['current_waiting_estimate'],
                          result['total_queue_estimate'], result['available_stalls_estimate']), (2, 8, 8, 0))
        self.assertAlmostEqual(result['expected_wait_s'], 9 * 105 / 27)
        self.assertAlmostEqual(queue_estimates(c, 2, 0)['expected_wait_s'], 105 / 27)
        c['available_stalls'] = 0
        self.assertIsNone(queue_estimates(c, 29, 6)['expected_wait_s'])
        for inside in (None, -3):
            result = queue_estimates(c, inside, 6)
            self.assertTrue(all(v is None for v in result.values()))


class RegistryBatch(unittest.TestCase):
    def test_demo_initial_assumptions_preserve_geometry_and_operating_values(self):
        original = settings()
        original['initial_inside'] = None
        before = clone(original)
        demo = apply_profile(original, load_profile('demo'))
        self.assertEqual(original, before)
        self.assertEqual(demo['boundary'], original['boundary'])
        self.assertEqual((demo['initial_inside'], demo['available_stalls']), (29, 27))
        for room, initial, stalls in [('south', 4, 5), ('east', None, None)]:
            c = settings(room, initial)
            c['available_stalls'] = stalls
            d = apply_profile(c, load_profile('demo'))
            self.assertEqual((d['initial_inside'], d['available_stalls']), (3, stalls))
            self.assertEqual(d['capture_start_time'], '2026-10-14T00:00:00+09:00')
            self.assertEqual(apply_profile(c, load_profile('operating'))['initial_inside'], initial)
        with self.assertRaises(ValueError):
            # Guard applies to custom profiles as well.
            with tempfile.TemporaryDirectory() as folder:
                p = Path(folder) / 'profile.json'
                save({'schema_version': 1, 'name': 'bad', 'defaults': {'boundary': []}}, p)
                load_profile(str(p))

    def test_failures_continue_duplicates_skip_envs_isolated_and_results_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = root / 'registry.json'
            entries = []
            for i, room in enumerate(['north', 'south', 'north', 'east']):
                video = root / f'v{i}.bin'
                video.write_bytes(bytes([i]))
                c = settings(room, 5 if room == 'south' else None)
                c.update(video=str(video), available_stalls=3 if room == 'south' else None)
                if room == 'east':
                    c['configured'] = False
                if room == 'south':
                    c['waiting_zone'] = [[.1, .1], [.4, .1], [.4, .7], [.1, .7]]
                cfg = root / f'c{i}.json'
                save(c, cfg)
                entries.append({'restroom_id': room, 'video': str(video), 'config': str(cfg),
                                'video_id': f'video_{i}', 'capture_start_time': None,
                                'initial_inside': c['initial_inside']})
            missing = dict(entries[0], video=str(root / 'missing.bin'), video_id='missing')
            content_copy = root / 'copy.bin'
            content_copy.write_bytes(b'\x00')
            save({'schema_version': 1, 'videos': [missing, entries[0], entries[3], entries[1],
                                                entries[2], entries[0], dict(entries[0],
                                                video=str(content_copy), video_id='copy')]}, registry)
            config_bytes = {e['config']: Path(e['config']).read_bytes() for e in entries}
            calls = []
            def fake_analyze(path, start, end, **kwargs):
                c = kwargs['config_override']
                counter = Counter(c, 1000, 1000)
                snapshot, _, _ = counter.update(start, 0, [])
                calls.append((clone(c), snapshot['inside_estimate']))
                sink = kwargs['interval_sink']
                row = usage_row(c, snapshot, start, start + 10)
                detail = {'record_index': 1, 'record_interval_s': 10, 'interval_start_s': start,
                          'interval_end_s': start + 10, 'source_time_s': start, 'state': snapshot}
                kwargs['record_output'].write(row, detail, c)
                sink(row, detail)
                # Visible BEFORE fake analysis completes.
                self.assertTrue(list(Path(kwargs['output_base']).parents[1].joinpath('shared').glob('*.csv')))
                run = Path(kwargs['output_base']) / 'fake_run'
                run.mkdir()
                return run
            with patch('cctv.batch.analyze', fake_analyze):
                out = run_batch(registry, 'demo', 20, output_dir=str(root / 'outputs'))
            data = json.loads((out / 'batch_summary.json').read_text(encoding='utf-8'))
            self.assertEqual((data['completed_count'], data['failed_count']), (3, 4))
            self.assertEqual([initial for _, initial in calls], [29, 3, 29])
            # Demo inherits each environment's capacity, including unknown values.
            self.assertEqual([c['available_stalls'] for c, _ in calls], [None, 3, None])
            self.assertNotEqual(calls[0][0]['waiting_zone'], calls[1][0]['waiting_zone'])
            self.assertTrue(all(Path(p).read_bytes() == raw for p, raw in config_bytes.items()))
            original = (out / 'shared' / 'north_2026-10-14_0000.csv').read_bytes()
            with patch('cctv.batch.analyze', fake_analyze):
                second = run_batch(registry, 'demo', 20, output_dir=str(root / 'outputs'))
            self.assertNotEqual(out, second)
            self.assertEqual((out / 'shared' / 'north_2026-10-14_0000.csv').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
