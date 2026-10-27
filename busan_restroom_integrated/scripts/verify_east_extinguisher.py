"""Append-only east mask replay and every-frame observation/state audit."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cctv.config import load, preset_path
from cctv.core import Counter, Observation
from cctv.geometry import in_polygon
from cctv.media import write_json
from cctv.profiles import load_profile
from cctv.recalculate import recalculate_run
from cctv.rerender import log_frames, replay, digest
from cctv.stream_output import StreamOutput
from cctv.usage import USAGE_FIELDS

# Each object was visually reviewed against original source frames, not inferred
# from tracker identity alone. IDs are used only for this fixed-input audit.
FALSE_IDS = {10, 25, 37, 127, 134, 179, 221, 354, 386, 388}
PEOPLE_IDS = {1, 2, 26, 192, 246}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--phase', choices=['prepare', 'render', 'verify'], required=True)
    a = p.parse_args()
    source, output = a.source.resolve(), a.output.resolve()
    run = output / 'east' / 'analysis'
    c = load(preset_path('east'))
    if a.phase == 'prepare':
        stream = StreamOutput(output / 'east' / 'shared', {'prediction_mode': 'disabled', 'csv_split_interval_s': 3600})
        try:
            result = recalculate_run(source, run, stream, load_profile('demo'),
                                     confirmed_only=True, excluded_zones=c['excluded_zones'])
        finally:
            stream.close()
        write_json(output / 'recalculation.json', result)
        replay(run, output / 'previews', preview_only=True)
    elif a.phase == 'render':
        result = replay(run, output / 'videos', preview_only=False)
        summary = load(run / 'summary.json')
        summary.update(status='completed', output_video=result['output_video'],
                       video_method='original_video_same_tracker_input_append_only_east_exclusion')
        write_json(run / 'summary.json', summary)
    else:
        old_c, new_c = load(source / 'config_used.json'), load(run / 'config_used.json')
        assert new_c['excluded_zones'][:-1] == old_c['excluded_zones']
        assert len(new_c['excluded_zones']) == len(old_c['excluded_zones']) + 1
        for key in ('rules', 'boundary', 'waiting_zone', 'transit_zone', 'outside_zone', 'inside_zone',
                    'tracker', 'entry_direction', 'initial_inside', 'available_stalls', 'average_stall_use_s',
                    'record_interval_s', 'csv_split_interval_s', 'prediction_mode'):
            assert old_c[key] == new_c[key], key
        counter = Counter(new_c, 1920, 1080)
        old_logs = dict(log_frames(source / 'diagnostics.jsonl'))
        false_observations = new_exclusions = false_confirmed_before = 0
        people = {tid: {'observations': 0, 'previously_excluded_unchanged': 0,
                        'candidate_frames': 0, 'confirmed_frames': 0} for tid in PEOPLE_IDS}
        for index, rows in log_frames(run / 'diagnostics.jsonl'):
            before = old_logs[index]
            original_obs = [r for r in before if r['kind'] in ('observation', 'excluded_observation')]
            current_obs = [r for r in rows if r['kind'] in ('observation', 'excluded_observation')]
            assert [(r['track_id'], r['box']) for r in original_obs] == [(r['track_id'], r['box']) for r in current_obs]
            original = {r['track_id']: r for r in original_obs}
            marker, = [r for r in rows if r['kind'] == 'detector_boxes']
            state, _, _ = counter.update(marker['video_time_s'], index,
                [Observation(r['track_id'], tuple(r['box']), r['confidence']) for r in current_obs])
            assert all(s.wait != 'confirmed' for tid, s in counter.tracks.items() if tid in FALSE_IDS)
            for r in current_obs:
                prior = original[r['track_id']]
                if r['track_id'] in FALSE_IDS:
                    false_observations += 1
                    assert r['kind'] == 'excluded_observation'
                    assert counter.tracks[r['track_id']].wait == 'nonwaiting'
                    false_confirmed_before += prior.get('waiting_state') == 'confirmed'
                if r['kind'] != prior['kind']:
                    assert r['track_id'] in FALSE_IDS and prior['kind'] == 'observation'
                    new_exclusions += 1
                if r['track_id'] not in FALSE_IDS:
                    assert r == prior, (index, r['track_id'])
                if r['track_id'] in PEOPLE_IDS:
                    if r['kind'] == 'excluded_observation':
                        people[r['track_id']]['previously_excluded_unchanged'] += 1
                        continue
                    people[r['track_id']]['observations'] += 1
                    people[r['track_id']]['candidate_frames'] += r['waiting_state'] == 'candidate'
                    people[r['track_id']]['confirmed_frames'] += r['waiting_state'] == 'confirmed'
            assert state['waiting_total'] == state['waiting_confirmed_observed'] + state['waiting_grace']
        assert digest(source / 'events.csv') == digest(run / 'events.csv')
        csv_path, = (output / 'east' / 'shared').rglob('east_*.csv')
        with csv_path.open(encoding='utf-8-sig') as f:
            reader = csv.DictReader(f); assert reader.fieldnames == USAGE_FIELDS
            shared_rows = list(reader)
        details = [json.loads(s) for s in (run / 'interval_details.jsonl').read_text(encoding='utf-8').splitlines()]
        envelopes = [json.loads(s) for s in (output / 'east/shared/record_index.jsonl').read_text(encoding='utf-8').splitlines()]
        assert len(shared_rows) == len(details) == len(envelopes) == 90
        for row, detail, envelope in zip(shared_rows, details, envelopes):
            assert envelope['detail']['state'] == detail['state']
            assert envelope['detail'] == {k: v for k, v in detail.items()
                                          if k not in ('available_stalls', 'average_stall_use_s')}
            assert row == {k: '' if v is None else str(v) for k, v in envelope['csv_row'].items()}
        def stats(path):
            with path.open(encoding='utf-8-sig') as f: values = [int(r['waiting_total']) for r in csv.DictReader(f)]
            return {'mean_integer_seconds': sum(values) / len(values), 'max': max(values)}
        example = Path(__file__).resolve().parents[1] / 'examples/data' / csv_path.name
        shutil.copy2(csv_path, example)
        report = {'frames': index + 1, 'false_ids': sorted(FALSE_IDS), 'false_object_observations': false_observations,
                  'newly_excluded_observations': new_exclusions, 'old_false_confirmed_observations': false_confirmed_before,
                  'new_false_confirmed_and_grace_every_frame': 0, 'non_object_observations_and_wait_states_unchanged': True,
                  'nearby_people': people, 'events_byte_identical': True,
                  'before': stats(source / 'timeseries.csv'), 'after': stats(run / 'timeseries.csv'),
                  'csv_rows': len(shared_rows), 'csv': str(csv_path), 'video': str(output / 'videos/east/annotated.mp4'),
                  'example_byte_identical': digest(example) == digest(csv_path), 'csv_envelope_details_equal': True,
                  'original_exclusions_preserved': True, 'rules_unchanged': True}
        write_json(output / 'exclusion_checks.json', report)
        print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
