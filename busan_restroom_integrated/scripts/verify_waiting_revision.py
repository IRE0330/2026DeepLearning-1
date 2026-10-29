"""Reproduce confirmed-only MVP results from complete immutable tracker logs."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cctv.config import load, preset_path
from cctv.core import Counter, Observation
from cctv.media import write_json
from cctv.profiles import load_profile
from cctv.recalculate import recalculate_run
from cctv.rerender import replay, log_frames, digest
from cctv.stream_output import StreamOutput
from cctv.usage import USAGE_FIELDS


def confirmation_comparison(before, after):
    def observations(run):
        tracks = {}
        for _, rows in log_frames(run / 'diagnostics.jsonl'):
            for row in rows:
                if row['kind'] == 'observation':
                    tracks.setdefault(row['track_id'], []).append(row)
        return tracks
    old, new = observations(before), observations(after)
    lost, delayed = [], []
    for tid, rows in old.items():
        confirmed = [r for r in rows if r['waiting_state'] == 'confirmed']
        if not confirmed:
            continue
        current = new.get(tid, [])
        assert current, 'An observed tracker ID disappeared during state-only replay.'
        later = [r for r in current if r['waiting_state'] == 'confirmed']
        item = {'track_id': tid, 'old_first_confirmed_s': confirmed[0]['video_time_s'],
                'new_first_confirmed_s': later[0]['video_time_s'] if later else None,
                'max_slow_evidence_s': max(r['slow_evidence_s'] for r in current),
                'observed_start_s': rows[0]['video_time_s'],
                'observed_end_s': rows[-1]['video_time_s']}
        (delayed if later else lost).append(item)
    return {'never_confirmed_under_3p5s': lost, 'confirmed_but_delayed': delayed,
            'scope': 'tracker IDs; human waiting intent requires manual review'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['prepare', 'render', 'compare'], required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    rooms = ['north', 'south', 'east']
    def source_run(room):
        path = source / room
        return path / 'analysis' if (path / 'analysis').is_dir() else path
    if args.phase == 'prepare':
        output.mkdir(parents=True, exist_ok=False)
        profile = load_profile('demo')
        # First exercise representative first 10 video seconds without inference.
        representative = {}
        for room in rooms:
            old = load(source_run(room) / 'summary.json')
            c = load(source_run(room) / 'config_used.json')
            c['rules']['waiting_confirm_s'] = load(preset_path(room))['rules']['waiting_confirm_s']
            counter = Counter(c, old['input_video']['width'], old['input_video']['height'])
            states = []
            for index, records in log_frames(source_run(room) / 'diagnostics.jsonl'):
                t = index / old['input_video']['fps']
                if t >= 10:
                    break
                observations = [Observation(r['track_id'], tuple(r['box']), r['confidence'])
                                for r in records if r['kind'] in ('observation', 'excluded_observation')]
                state, _, _ = counter.update(t, index, observations)
                assert state['waiting_total'] == state['waiting_confirmed_observed'] + state['waiting_grace']
                states.append(state)
            representative[room] = {'frames': len(states), 'policy_invariant': True,
                                     'max_candidates': max(s['waiting_candidate_observed'] for s in states),
                                     'max_waiting': max(s['waiting_total'] for s in states)}
        write_json(output / 'representative_checks.json', representative)
        for room in rooms:
            with _output(output, room) as stream:
                result = recalculate_run(source_run(room), output / room / 'analysis', stream, profile, confirmed_only=True)
            # Keep each run self-contained, with analysis and shared siblings.
            write_json(output / room / 'result.json', result)
            replay(output / room / 'analysis', output / 'previews', preview_only=True)
            print(f'{room}: prepared {result["processed_frames"]} frames; events identical', flush=True)
    elif args.phase == 'render':
        for room in rooms:
            run = output / room / 'analysis'
            rendered = replay(run, output / 'videos', preview_only=False)
            summary = load(run / 'summary.json')
            summary.update(status='completed', output_video=rendered['output_video'],
                           video_method='original_frames_same_tracker_input_new_waiting_policy')
            write_json(run / 'summary.json', summary)
            print(f'{room}: full video decoded and verified', flush=True)
    else:
        report = {}
        confirmation_changes = {}
        for room in rooms:
            run = output / room / 'analysis'
            before = list(csv.DictReader((source_run(room) / 'timeseries.csv').open(encoding='utf-8-sig')))
            after = list(csv.DictReader((run / 'timeseries.csv').open(encoding='utf-8-sig')))
            assert len(before) == len(after)
            assert all(all(a[k] == b[k] for k in ('source_time_s', 'entries', 'exits', 'inside_estimate')) for a, b in zip(before, after))
            csv_path, = (output / room / 'shared').rglob(f'{room}_*.csv')
            with csv_path.open(encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                assert reader.fieldnames == USAGE_FIELDS
                rows = list(reader)
            details = [json.loads(s) for s in (run / 'interval_details.jsonl').read_text(encoding='utf-8').splitlines()]
            envelopes = [json.loads(s) for s in (output / room / 'shared' / 'record_index.jsonl').read_text(encoding='utf-8').splitlines()]
            assert len(rows) == len(details) == len(envelopes)
            for row, detail, envelope in zip(rows, details, envelopes):
                state = detail['state']
                assert state['waiting_total'] == state['waiting_confirmed_observed'] + state['waiting_grace']
                assert envelope['detail']['state'] == state
                assert row == {k: '' if v is None else str(v) for k, v in envelope['csv_row'].items()}
            def stats(values):
                numbers = [int(s['waiting_total']) for s in values]
                return {'mean_at_integer_seconds': sum(numbers) / len(numbers), 'max': max(numbers), 'last_integer_second': numbers[-1]}
            old_config, new_config = load(source_run(room) / 'config_used.json'), load(run / 'config_used.json')
            for key in ('boundary', 'entry_direction', 'outside_zone', 'inside_zone', 'waiting_zone', 'transit_zone', 'excluded_zones', 'tracker', 'model', 'confidence', 'iou', 'imgsz'):
                assert old_config[key] == new_config[key], key
            assert digest(source_run(room) / 'events.csv') == digest(run / 'events.csv')
            confirmation_changes[room] = confirmation_comparison(source_run(room), run)
            example = Path(__file__).resolve().parents[1] / 'examples' / 'data' / csv_path.name
            shutil.copy2(csv_path, example)
            report[room] = {'before': stats(before), 'after': stats(after), 'changed_integer_samples': sum(a['waiting_total'] != b['waiting_total'] for a,b in zip(before,after)),
                            'events_identical': True, 'entries': after[-1]['entries'], 'exits': after[-1]['exits'],
                            'csv_rows': len(rows), 'csv': str(csv_path), 'video': str(output / 'videos' / room / 'annotated.mp4'),
                            'examples_sha256_equal': digest(csv_path) == digest(example),
                            'geometry_tracking_preserved': True, 'envelope_csv_detail_consistent': True,
                            'method': 'same_tracker_observations_replayed_no_inference',
                            'source_diagnostics_sha256': digest(source_run(room) / 'diagnostics.jsonl')}
        write_json(output / 'comparison.json', report)
        write_json(output / 'missed_waiter_candidates.json', confirmation_changes)
        print(json.dumps(report, ensure_ascii=True, indent=2))


class _output:
    def __init__(self, output, room):
        self.path = output / room / 'shared'
    def __enter__(self):
        self.stream = StreamOutput(self.path, {'prediction_mode': 'disabled', 'csv_split_interval_s': 3600})
        return self.stream
    def __exit__(self, *_):
        self.stream.close()


if __name__ == '__main__':
    main()
